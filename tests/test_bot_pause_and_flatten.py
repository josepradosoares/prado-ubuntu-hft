import json
from pathlib import Path
import threading
import time

from prado_linux.auth import create_session_token
from prado_linux.config import PradoServerConfig
from prado_linux.deriv_client import DerivClient
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord
from prado_linux.web_app import PradoWebApp


def _make_trending_ticks(count: int = 120, start: float = 1000.0, step: float = 2.0) -> list[TickRecord]:
    now_ms = int(time.time() * 1000)
    out: list[TickRecord] = []
    p = start
    for i in range(count):
        p += step
        out.append(TickRecord(now_ms - (count - i) * 1000, p, p, p, 0.0, 50.0, 1))
    return out


def test_paused_bot_and_auto_trading_disabled_never_place_or_auto_close_orders(tmp_path: Path):
    cfg = PradoServerConfig(
        connection_mode="SIMULATION",
        auto_trading_enabled=True,
        min_order_interval_sec=0.0,
    )
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")
    ticks = _make_trending_ticks(120, 1000.0, 3.0)
    svc.connector.fetch_ticks = lambda sym, count=200, granularity=0: ticks  # type: ignore[method-assign]

    bot = svc.create_bot(
        {
            "name": "Grid Pausado",
            "symbol": "R_100",
            "template_id": "GRID_LINEAR_HFT",
            "operation_mode": "GRID_LINEAR",
            "lot_size": 10.0,
            "multiplier": 100,
            "grid_direction": "BUY_ONLY",
            "grid_step_points": 1.0,
            "grid_tp_points": 0.5,
            "max_grid_levels": 3,
            "auto_start": True,
        }
    )
    # Pause bot manually (even if last_signal was PAUSED_NEWS before)
    bot["last_signal"] = "PAUSED_NEWS"
    svc.control_bot(bot["bot_id"], "PAUSE")
    assert bot["status"] == "PAUSED"
    assert bot["last_signal"] == "PAUSED_MANUAL"

    # News auto-resume must NOT resume a manually paused bot
    svc._auto_resume_news_paused_bots()
    assert bot["status"] == "PAUSED"

    # Seed an open position that would hit TP if bot were active
    svc.connector._sim_positions.append(
        {
            "ticket": 99001,
            "symbol": "R_100",
            "type": "BUY",
            "side": "BUY",
            "volume": 10.0,
            "multiplier": 100,
            "price_open": 1000.0,
            "price_current": 1200.0,
            "sl": 0.0,
            "tp": 0.0,
            "profit": 5.0,
            "bot_name": bot["name"],
            "comment": bot["name"][:14],
        }
    )

    placed: list[tuple] = []
    orig_place = svc.connector.place_order

    def spy_place(*args, **kwargs):
        placed.append((args, kwargs))
        return orig_place(*args, **kwargs)

    svc.connector.place_order = spy_place  # type: ignore[method-assign]

    svc.step_once()
    assert placed == [], "Paused bot must not place any order"
    assert len(svc.connector._sim_positions) == 1, "Paused bot must not auto-close positions"

    # Resume bot, but disable global auto_trading_enabled
    svc.control_bot(bot["bot_id"], "RESUME")
    svc.update_config({"auto_trading_enabled": False})
    svc.step_once()
    assert placed == [], "Bot must not place orders when auto_trading_enabled=False"
    assert len(svc.connector._sim_positions) == 1, "Bot must not auto-close when auto_trading_enabled=False"


def test_deriv_client_no_deadlock_on_ws_error_and_retries_sell(tmp_path: Path):
    attempts = {"send": 0, "closed": 0}

    class FlakyWS:
        def __init__(self, fail_first: bool) -> None:
            self.connected = True
            self._fail_first = fail_first

        def send(self, data: str) -> None:
            attempts["send"] += 1
            if self._fail_first and attempts["send"] == 1:
                raise BrokenPipeError("socket closed by peer")

        def recv(self) -> str:
            return json.dumps({"sell": {"sold_for": 12.5, "transaction_id": 9988}})

        def close(self) -> None:
            attempts["closed"] += 1
            self.connected = False

    client = DerivClient(token="classic_tok", app_id="1089")
    client._ws = FlakyWS(fail_first=True)
    # Reopen returns a healthy WS
    client._open_connection = lambda: FlakyWS(fail_first=False)  # type: ignore[method-assign]

    done = threading.Event()
    result: dict[str, object] = {}

    def _run() -> None:
        result["res"] = client.close_contract("123456")
        done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    assert done.wait(timeout=3.0), "close_contract deadlocked on WS error!"
    ok, msg = result["res"]  # type: ignore[misc]
    assert ok is True
    assert "123456" in msg
    assert attempts["send"] == 3  # 1 failed sell + 1 authorize on reconnect + 1 retried sell
    assert attempts["closed"] == 1


def test_flatten_and_single_close_bypass_stale_cache_and_handle_errors(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)
    app.cfg.connection_mode = "DERIV_CLOUD"
    app.cfg.deriv_token = "classic_tok"
    token = create_session_token(app.cfg.admin_username, app.cfg.secret_key)
    headers = {"Cookie": f"prado_session={token}", "Content-Type": "application/json"}

    # Disconnected Deriv -> /api/flatten must return ok=False
    app.service.connector._deriv = None
    code, body, _ = app.handle_request("POST", "/api/flatten", headers, b"{}")
    assert code == 200
    data = json.loads(body)
    assert data["ok"] is False

    # Connected Deriv with stale empty _positions_cache -> flatten must bypass cache and sell!
    sold_ids: list[int] = []

    def fake_rpc(payload: dict) -> dict:
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [
                        {"contract_id": 1001, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                        {"contract_id": 1002, "symbol": "R_75", "contract_type": "MULTDOWN", "buy_price": 15.0},
                    ]
                }
            }
        if "proposal_open_contract" in payload:
            cid = payload["contract_id"]
            return {
                "proposal_open_contract": {
                    "contract_id": cid,
                    "underlying": "R_100",
                    "contract_type": "MULTUP",
                    "buy_price": 10.0,
                    "entry_spot": 100.0,
                    "current_spot": 101.0,
                    "profit": 1.2,
                }
            }
        if "sell" in payload:
            cid = int(payload["sell"])
            if cid == 1001:
                raise RuntimeError("Deriv API (ContractSellError): temporary glitch")
            sold_ids.append(cid)
            return {"sell": {"sold_for": 16.2, "transaction_id": 444}}
        return {}

    deriv = DerivClient(token="classic_tok", app_id="1089", rpc_transport=fake_rpc)
    app.service.connector._deriv = deriv
    app.service.connector.connected = True
    app.service.connector.auth_state = "AUTHENTICATED"
    app.service.connector.connection_state = "CONNECTED"
    # Seed stale empty cache (< 5s old)
    app.service.connector._positions_cache = (time.time(), [])

    # Single close on failing contract 1001 must return ok=False cleanly (no 500)
    code, body, _ = app.handle_request("POST", "/api/flatten", headers, json.dumps({"ticket": "1001"}).encode("utf-8"))
    assert code == 200
    single_fail = json.loads(body)
    assert single_fail["ok"] is False

    # Full flatten must bypass stale empty cache, survive 1001 error, and still close 1002
    code, body, _ = app.handle_request("POST", "/api/flatten", headers, b"{}")
    assert code == 200
    flat = json.loads(body)
    assert flat["ok"] is True
    assert flat["closed"] == 1
    assert sold_ids == [1002]


def test_active_service_is_thread_safe_under_concurrent_supabase_requests(tmp_path: Path):
    class FakeSupabaseCfg:
        service_role_key = "srv_key"

    class FakeSupabase:
        is_enabled = True
        cfg = FakeSupabaseCfg()

        def load_user_config(self, user_id: str, token: str, fallback_path: Path) -> PradoServerConfig:
            time.sleep(0.05)  # widen race window
            return PradoServerConfig(connection_mode="SIMULATION", auto_trading_enabled=True)

        def sync_user_config(self, user_id: str, token: str, cfg: PradoServerConfig) -> None:
            return None

    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=FakeSupabase())  # type: ignore[arg-type]
    results: list[PradoTradingService] = []
    barrier = threading.Barrier(4)

    def _worker() -> None:
        barrier.wait(timeout=3.0)
        results.append(app._active_service("user-123"))

    threads = [threading.Thread(target=_worker, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    try:
        assert len(results) == 4
        assert len({id(s) for s in results}) == 1, "Concurrent _active_service spawned duplicate services!"
        assert results[0]._thread is not None and results[0]._thread.is_alive()
    finally:
        for svc in app._user_services.values():
            svc.stop_background_loop()


def test_deriv_client_retries_when_authorize_handshake_fails_on_reconnect():
    calls = {"open": 0, "send": 0}

    class HandshakeFailWS:
        def __init__(self, fail_auth: bool) -> None:
            self.connected = True
            self._fail_auth = fail_auth

        def send(self, data: str) -> None:
            calls["send"] += 1
            payload = json.loads(data)
            if self._fail_auth and "authorize" in payload:
                raise ConnectionResetError("handshake reset")

        def recv(self) -> str:
            if calls["send"] == 2:
                return json.dumps({"authorize": {"loginid": "VRTC1", "currency": "USD"}})
            return json.dumps({"sell": {"sold_for": 9.5, "transaction_id": 555}})

        def close(self) -> None:
            self.connected = False

    client = DerivClient(token="classic_tok", app_id="1089")

    def _open_conn():
        calls["open"] += 1
        return HandshakeFailWS(fail_auth=(calls["open"] == 1))

    client._open_connection = _open_conn  # type: ignore[method-assign]
    ok, msg = client.close_contract("777888")
    assert ok is True
    assert "777888" in msg
    assert calls["open"] == 2
