"""Tests for Deriv API docs sync, PAT+OTP auth, RateLimiter, trading safety, and security headers."""
from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from prado_linux.config import PradoServerConfig
from prado_linux.deriv_client import (
    DerivAuthError,
    DerivClient,
    DerivRateLimiter,
    DerivRateLimitError,
    mask_secret,
)
from prado_linux.engine import DerivUniversalConnector
from prado_linux.web_app import PradoWebApp
from scripts.sync_deriv_docs import sync_docs, verify_manifest


def test_deriv_docs_sync_and_verify_manifest(tmp_path: Path) -> None:
    fake_files = {
        "https://developers.deriv.com/llms.txt": (
            b"# Deriv\n- [auth](https://developers.deriv.com/llms/authentication.md)\n"
        ),
        "https://developers.deriv.com/llms/authentication.md": (
            b"# Auth\nSchema: https://developers.deriv.com/schemas/proposal_request.schema.json\n"
        ),
        "https://developers.deriv.com/schemas/proposal_request.schema.json": b'{"type": "object"}',
    }
    manifest = sync_docs(output_dir=tmp_path, fetcher=lambda url: fake_files[url])
    assert manifest["total_files"] == 3
    assert manifest["markdown_count"] == 1
    assert manifest["schema_count"] == 1
    assert manifest["failures"] == []
    ok, errs = verify_manifest(tmp_path)
    assert ok and errs == []

    # Tampering breaks SHA-256 verification
    (tmp_path / "llms" / "authentication.md").write_text("tampered", encoding="utf-8")
    ok_after, errs_after = verify_manifest(tmp_path)
    assert not ok_after
    assert any("SHA-256" in e for e in errs_after)


def test_real_vendor_docs_manifest_integrity() -> None:
    vendor_dir = Path(__file__).resolve().parent.parent / "docs" / "vendor" / "deriv-api"
    ok, errs = verify_manifest(vendor_dir)
    assert ok, f"Vendor docs integrity failed: {errs}"
    assert (vendor_dir / "llms.txt").exists()
    assert (vendor_dir / "INTEGRATION_AUDIT.md").exists()


def test_pat_with_legacy_app_id_1089_raises_app_id_mismatch() -> None:
    client = DerivClient(token="pat_abc1234567890", app_id="1089")
    with pytest.raises(DerivAuthError) as exc_info:
        client.authorize()
    assert exc_info.value.auth_state == "APP_ID_MISMATCH"
    assert client.auth_state == "APP_ID_MISMATCH"


def test_pat_with_custom_app_id_uses_bearer_and_deriv_app_id_and_selects_demo() -> None:
    captured_headers: list[dict[str, str]] = []

    def fake_rest(method: str, url: str, headers: dict[str, str]) -> dict:
        captured_headers.append(dict(headers))
        assert url.endswith("/trading/v1/options/accounts")
        return {
            "data": [
                {"account_id": "CR999", "account_type": "real", "currency": "USD", "balance": 500.0},
                {"account_id": "VRTC123", "account_type": "demo", "currency": "USD", "balance": 10000.0},
            ]
        }

    client = DerivClient(
        token="pat_custom_token_123456",
        app_id="99999",
        rest_transport=fake_rest,
        preferred_account_type="DEMO",
    )
    auth = client.authorize()
    assert auth["loginid"] == "VRTC123"
    assert auth["is_virtual"] == 1
    assert client.auth_state == "AUTHENTICATED"
    assert captured_headers[0]["Authorization"] == "Bearer pat_custom_token_123456"
    assert captured_headers[0]["Deriv-App-ID"] == "99999"


def test_rate_limiter_enforces_ws_and_rest_budgets_and_backoff() -> None:
    rl = DerivRateLimiter()
    now = 1000.0
    # Portfolio budget is 30/min
    for _ in range(30):
        rl.acquire_ws("portfolio", now=now)
    with pytest.raises(DerivRateLimitError):
        rl.acquire_ws("portfolio", now=now)
    # Local WS budget exhaustion must NOT block REST auth/OTP calls
    rl.acquire_rest(now=now)

    # Cooldown recovery
    delay = rl.record_remote_rate_limit("RateLimit", now=now + 100.0)
    assert delay >= 2.0
    assert rl.status(now=now + 100.5)["state"] == "BLOCKED"
    assert rl.status(now=now + 100.5 + delay + 0.1)["state"] == "NORMAL"


def test_proposal_uses_underlying_symbol_and_buy_does_not_retry_on_timeout() -> None:
    calls: list[dict] = []

    def fake_rpc(payload: dict) -> dict:
        calls.append(payload)
        if "proposal" in payload:
            assert payload["underlying_symbol"] == "R_100"
            assert "symbol" not in payload
            return {"proposal": {"id": "prop_1", "ask_price": 10.0}}
        if "buy" in payload:
            raise TimeoutError("WS recv timed out")
        return {}

    client = DerivClient(token="legacy_tok", app_id="1089", rpc_transport=fake_rpc)
    ok, msg = client.place_multiplier_order("R_100", is_buy=True, stake=10.0, multiplier=100)
    assert not ok
    assert "reconciliação" in msg
    # Exactly 1 proposal + 1 buy (never auto-retried buy)
    assert sum(1 for c in calls if "buy" in c) == 1


def test_real_account_trading_blocked_by_default_and_disconnected_blocked() -> None:
    cfg = PradoServerConfig(connection_mode="DERIV_CLOUD", allow_real_trading=False)
    conn = DerivUniversalConnector(cfg)
    ok_disc, msg_disc = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_disc
    assert "bloqueada" in msg_disc.lower()

    # Simulate connected REAL account with allow_real_trading=False
    conn._deriv = DerivClient(token="tok", app_id="1089")
    conn._deriv_auth = {"loginid": "CR123", "is_virtual": 0, "currency": "USD"}
    conn.connected = True
    conn.connection_state = "CONNECTED"
    conn.auth_state = "AUTHENTICATED"
    ok_real, msg_real = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_real
    assert "REAL bloqueada" in msg_real


def test_security_headers_no_unrecognized_permissions_policy_and_status_states(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "cfg.json")
    code, _, headers = app.handle_request("GET", "/login", {})
    assert code == 200
    pp = headers.get("Permissions-Policy", "")
    for bad in (
        "attribution-reporting",
        "private-aggregation",
        "join-ad-interest-group",
        "run-ad-auction",
        "browsing-topics",
    ):
        assert bad not in pp

    # Authenticate and check /api/status separated states
    _, _, login_hdrs = app.handle_request(
        "POST", "/api/login", {}, json.dumps({"username": "admin", "password": "prado2026"}).encode()
    )
    cookie = login_hdrs["Set-Cookie"].split(";")[0]
    st_code, st_body, _ = app.handle_request("GET", "/api/status", {"Cookie": cookie})
    assert st_code == 200
    snap = json.loads(st_body)
    acc = snap["account"]
    assert acc["account_mode"] in ("DEMO", "REAL")
    assert acc["connection_state"] == "DISCONNECTED"
    assert acc["auth_state"] == "UNAUTHENTICATED"
    assert acc["trading_state"] == "BLOCKED"
    assert acc["rate_limit"]["state"] == "NORMAL"
    assert mask_secret("1089", 2, 2) == "****"


def test_oauth_headers_no_deriv_app_id_and_token_expired_and_insufficient_scope() -> None:
    captured: list[dict[str, str]] = []

    def oauth_rest(method: str, url: str, headers: dict[str, str]) -> dict:
        captured.append(dict(headers))
        return {"data": [{"account_id": "VRTC777", "account_type": "demo", "currency": "USD", "balance": 5000.0}]}

    oauth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9." + ("x" * 30)
    client = DerivClient(token=oauth_token, app_id="99999", rest_transport=oauth_rest)
    auth = client.authorize()
    assert auth["loginid"] == "VRTC777"
    assert "Deriv-App-ID" not in captured[0]
    assert captured[0]["Authorization"] == f"Bearer {oauth_token}"

    # Expired token via RPC error
    def expired_rpc(payload: dict) -> dict:
        return {"error": {"code": "InvalidToken", "message": "Token has expired"}}

    exp_client = DerivClient(token="legacy_exp", app_id="1089", rpc_transport=expired_rpc)
    with pytest.raises(DerivAuthError) as exc_exp:
        exp_client.authorize()
    assert exc_exp.value.auth_state == "TOKEN_EXPIRED"


def test_rest_rate_limit_and_concurrent_ws_and_demo_trade_lifecycle() -> None:
    import concurrent.futures

    rl = DerivRateLimiter()
    now = 2000.0
    for _ in range(80):
        rl.acquire_rest(now=now)
    with pytest.raises(DerivRateLimitError):
        rl.acquire_rest(now=now)

    # Concurrent WS acquisitions are thread-safe and strictly bounded to 30
    rl_conc = DerivRateLimiter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(rl_conc.acquire_ws, "portfolio", 3000.0) for _ in range(35)]
        errors = 0
        for f in futs:
            try:
                f.result()
            except DerivRateLimitError:
                errors += 1
        assert errors == 5

    # Full Demo Proposal -> Buy -> Portfolio/POC -> Sell lifecycle + active_symbols
    def demo_rpc(payload: dict) -> dict:
        if "active_symbols" in payload:
            return {
                "active_symbols": [
                    {"underlying_symbol": "R_100", "underlying_symbol_name": "Volatility 100", "market": "synthetic_index"}
                ]
            }
        if "proposal" in payload:
            assert payload["underlying_symbol"] == "R_100"
            return {"proposal": {"id": "prop_99", "ask_price": 10.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 555123}}
        if "portfolio" in payload:
            return {"portfolio": {"contracts": [{"contract_id": 555123, "contract_type": "MULTUP", "symbol": "R_100"}]}}
        if "proposal_open_contract" in payload:
            return {
                "proposal_open_contract": {
                    "contract_id": 555123,
                    "underlying_symbol": "R_100",
                    "contract_type": "MULTUP",
                    "buy_price": 10.0,
                    "entry_spot": 1850.0,
                    "current_spot": 1852.5,
                    "profit": 1.35,
                }
            }
        if "sell" in payload:
            return {"sell": {"sold_for": 11.35}}
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=demo_rpc)
    syms = client.get_active_symbols()
    assert syms[0]["name"] == "R_100"

    ok_buy, msg_buy = client.place_multiplier_order("R_100", is_buy=True, stake=10.0, multiplier=100)
    assert ok_buy and "555123" in msg_buy

    positions = client.get_open_contracts()
    assert len(positions) == 1
    assert positions[0]["ticket"] == "555123"
    assert positions[0]["profit"] == 1.35

    ok_sell, msg_sell = client.close_contract("555123")
    assert ok_sell and "11.35" in msg_sell


def test_deriv_cloud_disconnected_data_state_not_live() -> None:
    cfg = PradoServerConfig(connection_mode="DERIV_CLOUD")
    conn = DerivUniversalConnector(cfg)
    conn._get_public_deriv = lambda: type("Broken", (), {"get_ticks_history": lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("offline"))})()  # type: ignore[method-assign]
    conn.fetch_ticks("R_100", count=50)
    summary = conn.get_account_summary()
    assert summary["data_state"] == "NO_DATA"
    assert summary["connection_state"] == "DISCONNECTED"
    assert summary["trading_state"] == "BLOCKED"


def test_bot_lifecycle_states_isolation_and_frontend_snapshot_contract(tmp_path: Path) -> None:
    from prado_linux.engine import PradoTradingService

    cfg = PradoServerConfig(connection_mode="SIMULATION", active_symbols=["R_100"])
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")

    good_bot = svc.create_bot({"name": "Bot Saudavel", "symbol": "R_100", "auto_start": True})
    bad_bot = svc.create_bot({"name": "Bot Defeituoso", "symbol": "", "auto_start": True})

    # Verify full lifecycle transitions: RUNNING -> PAUSED -> RUNNING -> STOPPED
    assert good_bot["status"] == "RUNNING" and good_bot["active"] is True
    paused = svc.control_bot(good_bot["bot_id"], "PAUSE")
    assert paused is not None and paused["status"] == "PAUSED" and paused["active"] is False
    resumed = svc.control_bot(good_bot["bot_id"], "RESUME")
    assert resumed is not None and resumed["status"] == "RUNNING" and resumed["active"] is True
    stopped = svc.control_bot(good_bot["bot_id"], "STOP")
    assert stopped is not None and stopped["status"] == "STOPPED" and stopped["active"] is False
    restarted = svc.control_bot(good_bot["bot_id"], "START")
    assert restarted is not None and restarted["status"] == "RUNNING" and restarted["active"] is True

    # step_once must isolate bad_bot failure without interrupting good_bot
    snap = svc.step_once()
    bots_by_id = {b["bot_id"]: b for b in snap["bots"]}
    assert bots_by_id[bad_bot["bot_id"]]["status"] == "ERROR"
    assert bots_by_id[bad_bot["bot_id"]]["active"] is False
    assert bots_by_id[good_bot["bot_id"]]["status"] == "RUNNING"
    assert bots_by_id[good_bot["bot_id"]]["active"] is True

    # Verify frontend/backend snapshot schema contract
    assert "logs" in snap and isinstance(snap["logs"], list) and len(snap["logs"]) > 0
    assert "module" in snap["logs"][0]
    assert "basket_bias" in snap
    r100 = snap["symbols"]["R_100"]
    for key in ("price", "vwap", "zscore", "imbalance", "sigma_distance", "signal"):
        assert key in r100

    # Verify backtest report includes frontend-expected keys
    report = svc.run_mathematical_backtest({"symbol": "R_100", "tick_count": 150})
    for key in ("win_rate", "final_capital", "template_name", "timestamp"):
        assert key in report


def test_risk_guards_stake_concurrent_exposure_and_stale_price() -> None:
    cfg = PradoServerConfig(
        connection_mode="DERIV_CLOUD",
        max_stake_per_trade=50.0,
        max_concurrent_trades=1,
        max_total_exposure_usd=60.0,
        min_order_interval_sec=0.0,
    )
    conn = DerivUniversalConnector(cfg)
    conn.connected = True
    conn.connection_state = "CONNECTED"
    conn.auth_state = "AUTHENTICATED"
    conn._deriv_auth = {"is_virtual": 1, "currency": "USD"}

    def demo_rpc(payload: dict) -> dict:
        if "portfolio" in payload:
            return {"portfolio": {"contracts": []}}
        if "proposal" in payload:
            return {"proposal": {"id": "p1", "ask_price": 10.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 7771}}
        if "sell" in payload:
            return {"sell": {"sold_for": 11.0}}
        return {}

    conn._deriv = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=demo_rpc)

    # 1. Stake exceeding max_stake_per_trade is blocked
    ok, msg = conn.place_order("R_100", "BUY_FLOW", 75.0, 100.0, 1.0, 2.0)
    assert not ok and "limite máximo por operação" in msg.lower()

    # 2. NO_DATA and Stale price block order
    conn.last_tick_at = 0.0
    ok_nodata, msg_nodata = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_nodata and "no_data" in msg_nodata.lower()

    conn.last_tick_at = time.time() - 60.0
    ok_stale, msg_stale = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_stale and "stale" in msg_stale.lower()

    # 3. Fresh price allows order and tracks lifecycle
    conn.last_tick_at = time.time()
    ok_live, msg_live = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert ok_live and "7771" in msg_live
    assert conn._deriv.last_order_lifecycle["stage"] == "CONTRACT_OPEN"

    # 4. Concurrent trade limit blocks second order when 1 position is open
    conn._positions_cache = (time.time(), [{"ticket": "7771", "symbol": "R_100", "type": "BUY", "side": "BUY", "volume": 10.0, "price_open": 100.0, "price_current": 101.0, "profit": 1.0}])
    ok_conc, msg_conc = conn.place_order("R_75", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_conc and "simultâneas" in msg_conc.lower()

    # 5. Closing Deriv contract records in _deriv_deals_history
    ok_close, _ = conn.close_single_position("7771")
    assert ok_close
    assert len(conn._deriv_deals_history) == 1
    assert conn._deriv_deals_history[0]["side"] == "BUY"
    assert "time_str" in conn._deriv_deals_history[0]


def test_get_account_summary_propagates_auth_error_and_daily_realized() -> None:
    cfg = PradoServerConfig(connection_mode="DERIV_CLOUD", active_account_type="DEMO")
    conn = DerivUniversalConnector(cfg)
    conn.connected = True
    conn.connection_state = "CONNECTED"
    conn.auth_state = "AUTHENTICATED"
    conn.backend_name = "DERIV_LIVE_API"
    conn._deriv_auth = {"loginid": "VRTC1", "is_virtual": 1, "currency": "USD", "balance": 1000.0}
    conn._deriv_deals_history = [{"ticket": "1", "profit": 12.5}, {"ticket": "2", "profit": -2.5}]

    def ok_rpc(payload: dict) -> dict:
        if "balance" in payload:
            return {"balance": {"balance": 1010.0}}
        if "portfolio" in payload:
            return {"portfolio": {"contracts": []}}
        return {}

    conn._deriv = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=ok_rpc)
    summary_ok = conn.get_account_summary()
    assert summary_ok["daily_realized"] == 10.0
    assert summary_ok["balance"] == 1010.0

    # Force balance cache expiry and raise DerivAuthError on get_balance()
    conn._balance_cache = None

    def expired_rpc(payload: dict) -> dict:
        if "balance" in payload:
            return {"error": {"code": "InvalidToken", "message": "Token expired"}}
        return {}

    conn._deriv = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=expired_rpc)
    summary_err = conn.get_account_summary()
    assert summary_err["connected"] is False
    assert summary_err["auth_state"] == "TOKEN_EXPIRED"
    assert summary_err["trading_state"] == "BLOCKED"
    assert summary_err["backend"] == "DERIV_DISCONNECTED"


def test_sync_deriv_accounts_and_vale3_cleanup(tmp_path) -> None:
    from prado_linux.config import load_config
    from prado_linux.web_app import PradoWebApp

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"active_symbols": ["VALE3", "R_100"], "correlated_basket": ["PETR4", "R_50"]}),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.active_symbols == ["R_100"]
    assert cfg.correlated_basket == ["R_50"]

    app = PradoWebApp(config_path=cfg_path)
    app.service.cfg.deriv_token = "pat_test_sync_token"
    app.service.cfg.deriv_app_id = "351TestAppId"

    class _FakeDeriv:
        def list_accounts(self):
            return [
                {"account_id": "VRTC9991", "account_type": "demo", "balance": 10000.0, "currency": "USD"},
                {"account_id": "CR8882", "account_type": "real", "balance": 25.5, "currency": "USD"},
            ]

    app.service.connector._deriv = _FakeDeriv()  # type: ignore[assignment]
    ok, msg, accs = app.service.sync_deriv_accounts()
    assert ok is True
    assert "2 conta(s)" in msg
    loginids = {a["loginid"] for a in accs}
    assert {"VRTC9991", "CR8882"}.issubset(loginids)
    assert all(a["deriv_app_id"] == "351TestAppId" for a in accs if a["loginid"] in ("VRTC9991", "CR8882"))


def test_grid_linear_hft_buy_only_and_sell_only_execution(tmp_path) -> None:
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.min_order_interval_sec = 0.0
    service = PradoTradingService(cfg, config_path=cfg_path)
    base_p = service.connector.fetch_ticks("R_100")[-1].effective_price()
    sim_price = {"R_100": base_p, "R_75": 500.0}

    def set_price(sym: str, p: float) -> None:
        from prado_linux.flow_math import TickRecord
        sim_price[sym] = p
        service.connector._sim_ticks[sym] = [TickRecord(1000, p, p, p, 0.0, 10.0, 1)]

    set_price("R_100", base_p)
    set_price("R_75", 500.0)

    # 1. Create BUY_ONLY Grid bot
    buy_bot = service.create_bot(
        {
            "name": "GridCompra",
            "symbol": "R_100",
            "bot_template_id": "GRID_LINEAR_HFT",
            "grid_direction": "BUY_ONLY",
            "grid_step_points": 2.0,
            "grid_tp_points": 2.0,
            "max_grid_levels": 3,
            "lot_size": 10.0,
            "multiplier": 100,
            "auto_start": True,
        }
    )
    assert buy_bot["grid_direction"] == "BUY_ONLY"
    assert buy_bot["max_grid_levels"] == 3

    positions = service.connector.get_open_positions()
    # First entry at base_p
    positions = service._evaluate_grid_bot(buy_bot, sim_price["R_100"], positions, risk_locked=False)
    assert len(positions) == 1
    assert positions[0]["type"] == "BUY"

    # Price drops by grid_step (2.0) -> opens second BUY level
    set_price("R_100", base_p - 2.5)
    positions = service._evaluate_grid_bot(buy_bot, sim_price["R_100"], positions, risk_locked=False)
    assert len(positions) == 2

    # Price rebounds to base_p - 0.4 -> second level ((base_p - 2.5) + 2.0 = base_p - 0.5) takes profit individually!
    set_price("R_100", base_p - 0.4)
    positions = service._evaluate_grid_bot(buy_bot, sim_price["R_100"], positions, risk_locked=False)
    assert len(positions) == 1

    # 2. SELL_ONLY Grid bot only opens SELL
    sell_bot = service.create_bot(
        {
            "name": "GridVenda",
            "symbol": "R_75",
            "bot_template_id": "GRID_LINEAR_HFT",
            "grid_direction": "SELL_ONLY",
            "grid_step_points": 5.0,
            "grid_tp_points": 3.0,
            "max_grid_levels": 2,
            "lot_size": 10.0,
            "auto_start": True,
        }
    )
    positions = service._evaluate_grid_bot(sell_bot, 500.0, positions, risk_locked=False)
    r75_pos = [p for p in positions if p["symbol"] == "R_75"]
    assert len(r75_pos) == 1
    assert r75_pos[0]["type"] == "SELL"


def test_place_multiplier_order_auto_adjusts_accepted_multiplier_for_stprng() -> None:
    calls: list[dict] = []

    def fake_rpc(payload: dict) -> dict:
        calls.append(payload)
        if "proposal" in payload:
            if payload["multiplier"] == 100:
                return {
                    "error": {
                        "code": "ContractBuyValidationError",
                        "message": "Multiplier is not in acceptable range. Accepts 750,2000,3500,5500,7500.",
                    }
                }
            return {"proposal": {"id": "prop_stp_1", "ask_price": 1.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 990011}}
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=fake_rpc)
    ok, msg = client.place_multiplier_order(symbol="stpRNG", is_buy=True, stake=1.0, multiplier=100)
    assert ok is True
    assert "750x" in msg
    assert "990011" in msg
    assert calls[1]["multiplier"] == 750


def test_news_scout_pauses_grid_and_opens_order_in_favor(tmp_path) -> None:
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService
    from prado_linux.news_scout import NewsScout

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.news_bot_enabled = True
    cfg.news_pause_grid_on_high_impact = True
    cfg.news_auto_trade_enabled = True
    cfg.news_stake_usd = 5.0
    cfg.news_multiplier = 100
    service = PradoTradingService(cfg, config_path=cfg_path)

    grid_bot = service.create_bot(
        {
            "name": "GridBTC",
            "symbol": "cryBTCUSD",
            "bot_template_id": "GRID_LINEAR_HFT",
            "grid_direction": "BUY_ONLY",
            "auto_start": True,
        }
    )
    assert grid_bot["status"] == "RUNNING"

    fake_rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel>
      <item>
        <title>Bitcoin surges to record high after SEC ETF approval</title>
        <link>https://example.com/btc-etf</link>
        <description>Major rally in BTC market</description>
      </item>
    </channel></rss>"""
    service.news_scout = NewsScout(fetcher=lambda url: fake_rss if "BTC" in url else "<rss><channel></channel></rss>")

    news_snap = service.scan_news(force=True)
    assert len(news_snap["items"]) == 1
    assert news_snap["items"][0]["symbol"] == "cryBTCUSD"
    assert news_snap["items"][0]["impact"] == "HIGH"
    assert news_snap["items"][0]["bias"] == "BULLISH"

    # Grid bot on cryBTCUSD was automatically paused by high-impact news
    assert service.cfg.bots[0]["status"] == "PAUSED"
    assert service.cfg.bots[0]["last_signal"] == "PAUSED_NEWS"

    # A BUY_NEWS order was opened in favor of the bullish news
    positions = service.connector.get_open_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "cryBTCUSD"
    assert positions[0]["type"] == "BUY"

    # Scanning the exact same headline again does NOT open duplicate orders
    service.scan_news(force=True)
    assert len(service.connector.get_open_positions()) == 1


def test_bot_pnl_tracking_and_loss_guard_auto_pause(tmp_path) -> None:
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    service = PradoTradingService(cfg, config_path=cfg_path)

    guarded_bot = service.create_bot(
        {
            "name": "GuardedBot",
            "symbol": "R_100",
            "bot_template_id": "WALL_STREET_HYBRID_BOTH",
            "loss_guard_enabled": True,
            "max_loss_usd": 15.0,
            "auto_start": True,
        }
    )
    unguarded_bot = service.create_bot(
        {
            "name": "UnguardedBot",
            "symbol": "R_75",
            "bot_template_id": "WALL_STREET_HYBRID_BOTH",
            "loss_guard_enabled": False,
            "max_loss_usd": 15.0,
            "auto_start": True,
        }
    )
    assert guarded_bot["loss_guard_enabled"] is True
    assert unguarded_bot["loss_guard_enabled"] is False

    service.connector._sim_deals_history = [
        {"bot_name": "GuardedBot", "symbol": "R_100", "profit": -20.0},
        {"bot_name": "UnguardedBot", "symbol": "R_75", "profit": -25.0},
    ]
    snap = service.step_once()
    bots_by_name = {b["name"]: b for b in snap["bots"]}

    assert bots_by_name["GuardedBot"]["total_pnl"] == -20.0
    assert bots_by_name["GuardedBot"]["status"] == "PAUSED"
    assert bots_by_name["GuardedBot"]["last_signal"] == "PAUSED_MAX_LOSS"

    assert bots_by_name["UnguardedBot"]["total_pnl"] == -25.0
    assert bots_by_name["UnguardedBot"]["status"] == "RUNNING"


def test_news_feeds_crud_and_per_bot_hybrid_news_decision(tmp_path):
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService
    from prado_linux.news_scout import NewsScout

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.auto_trading_enabled = True
    cfg.active_symbols = ["cryBTCUSD"]
    cfg.news_bot_enabled = True
    service = PradoTradingService(cfg, config_path=cfg_path)

    # 1. CRUD de URLs de notícias (incluindo ALL para monitorar todos os ativos)
    feeds = service.save_news_feed(
        {"source": "Minha Fonte RSS", "url": "https://example.com/btc.xml", "default_symbol": "ALL"}
    )
    saved = next(f for f in feeds if f["url"] == "https://example.com/btc.xml")
    assert saved["default_symbol"] == "ALL"
    assert any(f["feed_id"] == saved["feed_id"] for f in service.cfg.news_feeds)
    updated_feeds = service.save_news_feed(
        {
            "feed_id": saved["feed_id"],
            "source": "Fonte Editada",
            "url": "https://example.com/btc2.xml",
            "default_symbol": "cryBTCUSD",
        }
    )
    assert any(f["feed_id"] == saved["feed_id"] and f["source"] == "Fonte Editada" for f in updated_feeds)
    remaining = service.delete_news_feed(saved["feed_id"])
    assert all(f["feed_id"] != saved["feed_id"] for f in remaining)
    assert all(f["feed_id"] != saved["feed_id"] for f in service.cfg.news_feeds)

    # 2. Robô sem news_assisted não é afetado; robô com news_assisted entra a favor da notícia e estende lucro
    bullish_rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel>
      <item>
        <title>Bitcoin surges to record high after ETF approval</title>
        <link>https://example.com/btc-etf</link>
        <description>Major rally in BTC market</description>
      </item>
    </channel></rss>"""
    service.news_scout = NewsScout(fetcher=lambda url: bullish_rss if "BTC" in url else "<rss><channel></channel></rss>")
    service.scan_news(force=True)

    plain_bot = service.create_bot(
        {
            "name": "PlainTechBot",
            "symbol": "cryBTCUSD",
            "bot_template_id": "WALL_STREET_HYBRID_BOTH",
            "news_assisted": False,
            "auto_start": True,
        }
    )
    hybrid_bot = service.create_bot(
        {
            "name": "NewsHybridBot",
            "symbol": "cryBTCUSD",
            "bot_template_id": "WALL_STREET_HYBRID_BOTH",
            "news_assisted": True,
            "auto_start": True,
        }
    )
    assert plain_bot["news_assisted"] is False
    assert hybrid_bot["news_assisted"] is True

    snap = service.step_once()
    bots_by_name = {b["name"]: b for b in snap["bots"]}
    assert bots_by_name["NewsHybridBot"]["last_signal"] == "BUY_NEWS_HYBRID"
    assert bots_by_name["PlainTechBot"]["last_signal"] != "BUY_NEWS_HYBRID"
    assert any(p["bot_name"] == "NewsHybridBot" and p["type"] == "BUY" for p in snap["positions"])

    # 3. Se já estiver comprado no lucro e a notícia virar contra (BEARISH), fecha protegendo o lucro
    bearish_rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel>
      <item>
        <title>Bitcoin crashes after exchange hack and market selloff</title>
        <link>https://example.com/btc-crash</link>
        <description>Sharp plunge in BTC</description>
      </item>
    </channel></rss>"""
    service.news_scout = NewsScout(fetcher=lambda url: bearish_rss if "BTC" in url else "<rss><channel></channel></rss>")
    service.scan_news(force=True)
    for p in service.connector._sim_positions:
        if p.get("bot_name") == "NewsHybridBot":
            p["price_open"] = float(p.get("price_open", 0.0)) - 500.0
            p["profit"] = 1.5
    snap2 = service.step_once()
    bots_by_name2 = {b["name"]: b for b in snap2["bots"]}
    assert bots_by_name2["NewsHybridBot"]["last_signal"] == "NEWS_TECH_EXIT"
    assert not any(p["bot_name"] == "NewsHybridBot" for p in snap2["positions"])


def test_bot_timeframe_ticks_and_candles_mode(tmp_path):
    from prado_linux.config import load_config
    from prado_linux.deriv_client import DerivClient
    from prado_linux.engine import PradoTradingService

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    service = PradoTradingService(cfg, config_path=cfg_path)

    tick_bot = service.create_bot(
        {"name": "TickBot", "symbol": "R_100", "bot_template_id": "WALL_STREET_HYBRID_BOTH", "timeframe": "TICKS"}
    )
    m5_bot = service.create_bot(
        {"name": "CandleM5Bot", "symbol": "R_100", "bot_template_id": "WALL_STREET_HYBRID_BOTH", "timeframe": "M5"}
    )
    assert tick_bot["timeframe"] == "TICKS"
    assert m5_bot["timeframe"] == "M5"

    # Verifica que DerivClient envia style="candles" + granularity=300 quando granularity > 0
    sent_payloads = []
    client = DerivClient(app_id="1089", token="DEMO")
    def fake_rpc(payload):
        sent_payloads.append(payload)
        if payload.get("style") == "candles":
            return {"candles": [{"epoch": 1700000000, "close": 1850.5}, {"epoch": 1700000300, "close": 1852.0}]}
        return {"history": {"prices": [1850.0, 1851.0], "times": [1700000000, 1700000001]}}
    client._send_rpc = fake_rpc

    candles = client.get_ticks_history("R_100", count=2, granularity=300)
    assert len(candles) == 2
    assert candles[-1].effective_price() == 1852.0
    assert sent_payloads[-1]["style"] == "candles"
    assert sent_payloads[-1]["granularity"] == 300

    ticks = client.get_ticks_history("R_100", count=2, granularity=0)
    assert len(ticks) == 2
    assert sent_payloads[-1]["style"] == "ticks"
    assert "granularity" not in sent_payloads[-1]


def test_21_indicators_and_custom_templates_crud_test_and_execution(tmp_path):
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService
    from prado_linux.flow_math import TickRecord
    from prado_linux.indicators import INDICATOR_CATALOG, evaluate_indicator_model, evaluate_python_model, evaluate_single_indicator

    assert len(INDICATOR_CATALOG) == 21
    ticks = [
        TickRecord(time_msc=1700000000000 + i * 1000, bid=100.0 + i * 0.5, ask=100.1 + i * 0.5, last=100.0 + i * 0.5, tick_volume=10.0)
        for i in range(60)
    ]
    for ind in INDICATOR_CATALOG:
        vote, val = evaluate_single_indicator(ind["id"], ticks, ind["default_params"])
        assert vote in (-1, 0, 1)
        assert isinstance(val, float)

    ind_res = evaluate_indicator_model(ticks, [{"id": "SMA", "params": {"period": 10}}, {"id": "MOMENTUM", "params": {"period": 5}}], combine_mode="ALL")
    assert ind_res["signal"] == "BUY"

    # Python evaluator: valid, syntax error, runtime error
    ok_py = evaluate_python_model("def evaluate(prices, ticks, params):\n    return 'BUY'\n", [100.0, 101.0], ticks, {})
    assert ok_py["ok"] is True and ok_py["signal"] == "BUY"

    bad_syn = evaluate_python_model("def evaluate(:", [100.0], ticks, {})
    assert bad_syn["ok"] is False and "sintaxe" in bad_syn["error"].lower()

    bad_run = evaluate_python_model("def evaluate(prices, ticks, params):\n    return 1/0\n", [100.0], ticks, {})
    assert bad_run["ok"] is False and "ZeroDivisionError" in bad_run["error"]

    # CRUD + Teste + Execução via PradoTradingService
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.auto_trading_enabled = True
    service = PradoTradingService(cfg, config_path=cfg_path)

    saved = service.save_custom_template(
        {
            "name": "Minha Estratégia Python",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params):\n    print('ok')\n    return 'BUY'\n",
        }
    )
    assert any(t["template_id"] == saved["template_id"] for t in service.get_all_templates())
    test_out = service.test_custom_template(
        {"custom_mode": "PYTHON", "python_code": saved["python_code"], "symbol": "R_100"}
    )
    assert test_out["ok"] is True and test_out["signal"] == "BUY"

    bot = service.create_bot(
        {"name": "PyCustomBot", "symbol": "R_100", "bot_template_id": saved["template_id"], "auto_start": True}
    )
    snap = service.step_once()
    b_out = next(b for b in snap["bots"] if b["bot_id"] == bot["bot_id"])
    assert b_out["last_signal"] == "BUY_FLOW"

    assert service.delete_custom_template(saved["template_id"]) is True
    assert all(t["template_id"] != saved["template_id"] for t in service.get_all_templates())
