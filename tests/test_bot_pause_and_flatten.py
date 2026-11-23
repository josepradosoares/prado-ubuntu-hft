import json
from pathlib import Path
import threading
import time

from prado_linux.auth import create_session_token
from prado_linux.config import PradoServerConfig
from prado_linux.ctrader_client import (
    CTraderClient,
    PT_APPLICATION_AUTH_REQ,
    PT_APPLICATION_AUTH_RES,
    PT_CLOSE_POSITION_REQ,
    PT_EXECUTION_EVENT,
    PT_GET_POSITION_UNREALIZED_PNL_REQ,
    PT_GET_POSITION_UNREALIZED_PNL_RES,
    PT_OA_ERROR_RES,
    PT_RECONCILE_REQ,
    PT_RECONCILE_RES,
)
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord
from prado_linux.web_app import PradoWebApp


def _make_trending_ticks(count: int = 120, start: float = 1.0800, step: float = 0.0005) -> list[TickRecord]:
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
    ticks = _make_trending_ticks(120, 1.0800, 0.0008)
    svc.connector.fetch_ticks = lambda sym, count=200, granularity=0: ticks  # type: ignore[method-assign]

    bot = svc.create_bot(
        {
            "name": "Grid Pausado",
            "symbol": "EURUSD",
            "template_id": "GRID_LINEAR_HFT",
            "operation_mode": "GRID_LINEAR",
            "lot_size": 0.01,
            "grid_direction": "BUY_ONLY",
            "grid_step_points": 0.0005,
            "grid_tp_points": 0.0005,
            "max_grid_levels": 3,
            "auto_start": True,
        }
    )
    bot["last_signal"] = "PAUSED_NEWS"
    svc.control_bot(bot["bot_id"], "PAUSE")
    assert bot["status"] == "PAUSED"
    assert bot["last_signal"] == "PAUSED_MANUAL"

    svc._auto_resume_news_paused_bots()
    assert bot["status"] == "PAUSED"

    svc.connector._sim_positions.append(
        {
            "ticket": 99001,
            "symbol": "EURUSD",
            "type": "BUY",
            "side": "BUY",
            "volume": 0.01,
            "price_open": 1.0800,
            "price_current": 1.2000,
            "sl": 0.0,
            "tp": 0.0,
            "profit": 12.0,
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

    svc.control_bot(bot["bot_id"], "RESUME")
    svc.update_config({"auto_trading_enabled": False})
    svc.step_once()
    assert placed == [], "Bot must not place orders when auto_trading_enabled=False"
    assert len(svc.connector._sim_positions) == 1, "Bot must not auto-close when auto_trading_enabled=False"


def test_ctrader_client_no_deadlock_on_ws_error_and_retries_close():
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
            return json.dumps({"payloadType": PT_EXECUTION_EVENT, "payload": {"executionType": 3}})

        def close(self) -> None:
            attempts["closed"] += 1
            self.connected = False

    client = CTraderClient("cid", "csec", "tok", account_id="55001")
    client._ws = FlakyWS(fail_first=True)
    client._open_connection = lambda: FlakyWS(fail_first=False)  # type: ignore[method-assign]

    done = threading.Event()
    result: dict[str, object] = {}

    def _run() -> None:
        result["res"] = client.close_position("123456", volume_raw=100_000)
        done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    assert done.wait(timeout=3.0), "close_position deadlocked on WS error!"
    ok, msg = result["res"]  # type: ignore[misc]
    assert ok is True
    assert "123456" in msg
    assert attempts["send"] == 2
    assert attempts["closed"] == 1


def test_flatten_and_single_close_bypass_stale_cache_and_handle_errors(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)
    app.cfg.connection_mode = "CTRADER_CLOUD"
    app.cfg.ctrader_access_token = "tok"
    token = create_session_token(app.cfg.admin_username, app.cfg.secret_key)
    headers = {"Cookie": f"prado_session={token}", "Content-Type": "application/json"}

    app.service.connector._client = None
    code, body, _ = app.handle_request("POST", "/api/flatten", headers, b"{}")
    assert code == 200
    data = json.loads(body)
    assert data["ok"] is False

    closed_ids: list[int] = []

    def fake_rpc(env: dict) -> dict:
        pt = env["payloadType"]
        cid = env["clientMsgId"]
        p = env["payload"]
        if pt == PT_RECONCILE_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_RECONCILE_RES,
                "payload": {
                    "position": [
                        {"positionId": 1001, "positionStatus": 1, "price": 1.085, "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1}},
                        {"positionId": 1002, "positionStatus": 1, "price": 2650.0, "tradeData": {"symbolId": 2, "volume": 100_000, "tradeSide": 2}},
                    ]
                },
            }
        if pt == PT_GET_POSITION_UNREALIZED_PNL_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_POSITION_UNREALIZED_PNL_RES,
                "payload": {"moneyDigits": 2, "positionUnrealizedPnL": [{"positionId": 1001, "netUnrealizedPnL": 120}, {"positionId": 1002, "netUnrealizedPnL": 200}]},
            }
        if pt == PT_CLOSE_POSITION_REQ:
            pid = int(p["positionId"])
            if pid == 1001:
                return {"clientMsgId": cid, "payloadType": PT_OA_ERROR_RES, "payload": {"errorCode": "TRADING_DISABLED", "description": "temporary glitch"}}
            closed_ids.append(pid)
            return {"clientMsgId": cid, "payloadType": PT_EXECUTION_EVENT, "payload": {"executionType": 3}}
        return {"clientMsgId": cid, "payloadType": PT_APPLICATION_AUTH_RES, "payload": {}}

    client = CTraderClient("cid", "csec", "tok", account_id="55001", rpc_transport=fake_rpc)
    client._symbols_by_id[1] = {"symbolId": 1, "name": "EURUSD"}
    client._symbols_by_id[2] = {"symbolId": 2, "name": "XAUUSD"}
    app.service.connector._client = client
    app.service.connector.connected = True
    app.service.connector.auth_state = "AUTHENTICATED"
    app.service.connector.connection_state = "CONNECTED"
    app.service.connector._positions_cache = (time.time(), [])

    code, body, _ = app.handle_request("POST", "/api/flatten", headers, json.dumps({"ticket": "1001"}).encode("utf-8"))
    assert code == 200
    assert json.loads(body)["ok"] is False

    code, body, _ = app.handle_request("POST", "/api/flatten", headers, b"{}")
    assert code == 200
    flat = json.loads(body)
    assert flat["ok"] is True
    assert flat["closed"] == 1
    assert closed_ids == [1002]


def test_active_service_is_thread_safe_under_concurrent_supabase_requests(tmp_path: Path):
    class FakeSupabaseCfg:
        service_role_key = "srv_key"

    class FakeSupabase:
        is_enabled = True
        cfg = FakeSupabaseCfg()

        def load_user_config(self, user_id: str, token: str, fallback_path: Path) -> PradoServerConfig:
            time.sleep(0.05)
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
        assert len({id(s) for s in results}) == 1
        assert results[0]._thread is not None and results[0]._thread.is_alive()
    finally:
        for svc in app._user_services.values():
            svc.stop_background_loop()


def test_ctrader_client_retries_when_handshake_fails_on_reconnect():
    calls = {"open": 0, "send": 0}

    class HandshakeFailWS:
        def __init__(self, fail_send: bool) -> None:
            self.connected = True
            self._fail_send = fail_send

        def send(self, data: str) -> None:
            calls["send"] += 1
            if self._fail_send:
                raise ConnectionResetError("handshake reset")

        def recv(self) -> str:
            return json.dumps({"payloadType": PT_EXECUTION_EVENT, "payload": {"executionType": 3}})

        def close(self) -> None:
            self.connected = False

    client = CTraderClient("cid", "csec", "tok", account_id="55001")

    def _open_conn():
        calls["open"] += 1
        return HandshakeFailWS(fail_send=(calls["open"] == 1))

    client._open_connection = _open_conn  # type: ignore[method-assign]
    ok, msg = client.close_position("777888", volume_raw=100_000)
    assert ok is True
    assert "777888" in msg
    assert calls["open"] == 2
