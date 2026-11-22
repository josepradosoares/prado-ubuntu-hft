import json
from pathlib import Path
import pytest

from prado_linux.auth import create_session_token, verify_password, verify_session_token
from prado_linux.config import load_config, save_config
from prado_linux.engine import PradoTradingService


def test_default_config_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg = load_config(cfg_file)
    assert cfg.admin_username == "admin"
    assert cfg.zscore_threshold == 1.8
    assert cfg.imbalance_threshold == 0.35
    assert cfg.operation_mode == "BOTH"
    assert cfg.deriv_app_id == "1089"
    assert cfg.default_stake_usd == 10.0
    assert cfg.default_multiplier == 100
    assert cfg.deriv_token == ""

    cfg.deriv_token = "pat_test_123"
    cfg.active_symbols = ["R_100", "R_75", "cryBTCUSD"]
    cfg.correlated_basket = ["R_50", "R_25"]
    save_config(cfg, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded.deriv_token == "pat_test_123"
    assert reloaded.active_symbols == ["R_100", "R_75", "cryBTCUSD"]
    assert reloaded.correlated_basket == ["R_50", "R_25"]


def test_auth_password_and_session_tokens(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    assert verify_password("prado2026", cfg.admin_password_hash) is True
    assert verify_password("wrong", cfg.admin_password_hash) is False

    token = create_session_token("admin", cfg.secret_key)
    assert verify_session_token(token, cfg.secret_key) == "admin"
    assert verify_session_token(token + "tampered", cfg.secret_key) is None


def test_trading_service_snapshot_and_vwap_flow_cycle(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    cfg.connection_mode = "SIMULATION"
    cfg.active_symbols = ["R_100", "cryBTCUSD"]
    cfg.correlated_basket = ["R_50", "R_75"]
    service = PradoTradingService(cfg, config_path=tmp_path / "config.json")

    snap = service.step_once()
    assert "account" in snap
    assert "symbols" in snap
    assert "R_100" in snap["symbols"]
    assert "cryBTCUSD" in snap["symbols"]

    r100_state = snap["symbols"]["R_100"]
    assert r100_state["vwap"] > 0
    assert r100_state["upper_2"] > r100_state["vwap"] > r100_state["lower_2"]
    assert r100_state["regime"] in (
        "NEUTRAL",
        "INSTITUTIONAL_TREND_UP",
        "INSTITUTIONAL_TREND_DOWN",
        "HFT_MEAN_REVERSION",
    )


def test_deriv_client_websocket_rpc_and_multipliers(tmp_path: Path):
    from prado_linux.deriv_client import DerivClient

    calls: list[dict] = []

    def fake_rpc(payload: dict) -> dict:
        calls.append(payload)
        if "authorize" in payload:
            return {
                "authorize": {
                    "loginid": "VRTC998877",
                    "currency": "USD",
                    "balance": 10000.0,
                    "is_virtual": 1,
                    "fullname": "Jose Demo Deriv",
                }
            }
        if "active_symbols" in payload:
            return {
                "active_symbols": [
                    {"symbol": "R_100", "display_name": "Volatility 100 Index", "market_display_name": "Derived"},
                    {"symbol": "frxEURUSD", "display_name": "EUR/USD", "market_display_name": "Forex"},
                    {"symbol": "cryBTCUSD", "display_name": "BTC/USD", "market_display_name": "Cryptocurrencies"},
                ]
            }
        if "ticks_history" in payload:
            return {
                "history": {
                    "prices": [100.1, 100.2, 100.35, 100.5, 100.4],
                    "times": [1700000001, 1700000002, 1700000003, 1700000004, 1700000005],
                }
            }
        if "proposal" in payload:
            return {"proposal": {"id": "prop_12345", "ask_price": 10.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 778899, "buy_price": 10.0}}
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [
                        {
                            "contract_id": 778899,
                            "symbol": "R_100",
                            "contract_type": "MULTUP",
                            "buy_price": 10.0,
                        }
                    ]
                }
            }
        if "proposal_open_contract" in payload:
            return {
                "proposal_open_contract": {
                    "contract_id": 778899,
                    "underlying": "R_100",
                    "contract_type": "MULTUP",
                    "buy_price": 10.0,
                    "entry_spot": 100.2,
                    "current_spot": 101.0,
                    "profit": 4.5,
                    "limit_order": {"stop_loss": {"order_amount": 5.0}, "take_profit": {"order_amount": 9.0}},
                }
            }
        if "sell" in payload:
            return {"sell": {"sold_for": 14.5, "transaction_id": 556677}}
        return {}

    client = DerivClient(token="pat_demo_test", app_id="1089", rpc_transport=fake_rpc)
    auth = client.authorize()
    assert auth["loginid"] == "VRTC998877"
    assert auth["balance"] == 10000.0
    assert auth["is_virtual"] == 1

    syms = client.get_active_symbols()
    assert len(syms) == 3
    assert syms[0]["name"] == "R_100"

    ticks = client.get_ticks_history("R_100", count=5)
    assert len(ticks) == 5
    assert ticks[-1].last == 100.4

    ok, msg = client.place_multiplier_order(
        symbol="R_100",
        is_buy=True,
        stake=10.0,
        multiplier=100,
        sl_amount=5.0,
        tp_amount=9.0,
    )
    assert ok is True
    assert "778899" in msg

    contracts = client.get_open_contracts()
    assert len(contracts) == 1
    assert contracts[0]["profit"] == 4.5

    closed_ok, _ = client.close_contract("778899")
    assert closed_ok is True


def test_deriv_cloud_disconnected_shows_zero_balance_never_fake_sim(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    cfg.connection_mode = "DERIV_CLOUD"
    cfg.deriv_token = ""
    service = PradoTradingService(cfg, config_path=tmp_path / "config.json")

    snap = service.step_once()
    assert snap["account"]["balance"] == 0.0
    assert snap["account"]["equity"] == 0.0
    assert snap["account"]["backend"] == "DERIV_DISCONNECTED"
    assert snap["account"]["login"] == "DESCONECTADO"


def test_web_app_deriv_token_vault_bots_categories_and_backtester(tmp_path: Path):
    from prado_linux.web_app import PradoWebApp

    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)
    app.cfg.connection_mode = "SIMULATION"

    # 1. Unauthenticated request blocked
    code, _, _ = app.handle_request("GET", "/api/status", headers={}, body=b"")
    assert code == 401

    # 2. Login
    login_payload = json.dumps({"username": "admin", "password": "prado2026"}).encode("utf-8")
    code, body, resp_headers = app.handle_request(
        "POST", "/api/login", headers={"Content-Type": "application/json"}, body=login_payload
    )
    assert code == 200
    auth_headers = {"Cookie": resp_headers["Set-Cookie"], "Content-Type": "application/json"}

    # 3. Save Deriv Demo & Real Tokens (and verify token is masked in response)
    demo_acc = json.dumps(
        {
            "account_id": "deriv_demo_1",
            "account_type": "DEMO",
            "label": "Minha Deriv Demo",
            "deriv_token": "pat_secret_demo_token",
            "deriv_app_id": "1089",
            "default_stake_usd": 10.0,
            "default_multiplier": 100,
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/accounts", headers=auth_headers, body=demo_acc)
    assert code == 200
    resp_demo = json.loads(body)
    assert resp_demo["ok"] is True
    assert resp_demo["account"]["deriv_token"] == "********"
    assert resp_demo["account"]["account_type"] == "DEMO"

    real_acc = json.dumps(
        {
            "account_id": "deriv_real_1",
            "account_type": "REAL",
            "label": "Minha Deriv Real",
            "deriv_token": "pat_secret_real_token",
            "deriv_app_id": "1089",
            "default_stake_usd": 20.0,
            "default_multiplier": 50,
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/accounts", headers=auth_headers, body=real_acc)
    assert code == 200

    # 3b. Save default token in Config Deriv and verify new account inherits it automatically
    code, body, _ = app.handle_request(
        "POST",
        "/api/config",
        headers=auth_headers,
        body=json.dumps({"deriv_token": "classic_default_token_123", "deriv_app_id": "1089"}).encode("utf-8"),
    )
    assert code == 200
    assert json.loads(body)["config"]["deriv_token_set"] is True

    inherited_acc = json.dumps(
        {
            "account_id": "deriv_inherited_1",
            "account_type": "REAL",
            "label": "Real Herdada",
            "deriv_token": "",
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/accounts", headers=auth_headers, body=inherited_acc)
    assert code == 200
    assert json.loads(body)["account"]["deriv_token"] == "********"

    # Switch between Demo and Real tokens
    code, body, _ = app.handle_request(
        "POST", "/api/accounts/select", headers=auth_headers, body=json.dumps({"account_id": "deriv_demo_1"}).encode("utf-8")
    )
    assert code == 200
    assert json.loads(body)["active_account"]["account_type"] == "DEMO"

    # 4. Symbols Principais vs Todos + Custom Categories
    code, body, _ = app.handle_request("GET", "/api/symbols?mode=PRINCIPAIS", headers=auth_headers, body=b"")
    assert code == 200
    sym_main = json.loads(body)
    assert len(sym_main["symbols"]) > 0

    code, body, _ = app.handle_request("GET", "/api/symbols?mode=TODOS", headers=auth_headers, body=b"")
    assert code == 200
    sym_all = json.loads(body)
    assert len(sym_all["symbols"]) >= len(sym_main["symbols"])

    code, body, _ = app.handle_request(
        "POST",
        "/api/categories",
        headers=auth_headers,
        body=json.dumps({"category_name": "Sintéticos 24h", "symbols": ["R_100", "1HZ100V"]}).encode("utf-8"),
    )
    assert code == 200
    assert "Sintéticos 24h" in json.loads(body)["categories"]

    # 5. Create, Edit, Fire Order (in SIMULATION mode) & Delete Bot
    code, _, _ = app.handle_request(
        "POST",
        "/api/config",
        headers=auth_headers,
        body=json.dumps({"connection_mode": "SIMULATION"}).encode("utf-8"),
    )
    assert code == 200

    code, body, _ = app.handle_request(
        "POST",
        "/api/bots",
        headers=auth_headers,
        body=json.dumps(
            {
                "name": "Bot Deriv R_100",
                "account_id": "deriv_demo_1",
                "symbol": "R_100",
                "lot_size": 10.0,
                "multiplier": 100,
                "auto_start": True,
            }
        ).encode("utf-8"),
    )
    assert code == 200
    bot_id = json.loads(body)["bot"]["bot_id"]

    code, body, _ = app.handle_request(
        "POST",
        "/api/bots/action",
        headers=auth_headers,
        body=json.dumps({"bot_id": bot_id, "action": "FIRE_BUY"}).encode("utf-8"),
    )
    assert code == 200

    code, body, _ = app.handle_request("GET", "/api/status", headers=auth_headers, body=b"")
    snap = json.loads(body)
    assert len(snap["positions"]) >= 1

    # 6. Backtester
    code, body, _ = app.handle_request(
        "POST",
        "/api/backtest",
        headers=auth_headers,
        body=json.dumps({"symbol": "R_100", "tick_count": 400, "initial_capital": 10000.0, "lot_size": 10.0}).encode("utf-8"),
    )
    assert code == 200
    report = json.loads(body)["report"]
    assert report["symbol"] == "R_100"
    assert "net_profit" in report

    # 7. Lightweight Charts API & React Static Build
    code, body, _ = app.handle_request("GET", "/api/chart?symbol=R_100", headers=auth_headers, body=b"")
    assert code == 200
    chart_data = json.loads(body)
    assert chart_data["ok"] is True
    assert len(chart_data["points"]) > 0

    code, html_body, _ = app.handle_request("GET", "/", headers=auth_headers, body=b"")
    assert code == 200
    assert "Prado Institutional HFT" in html_body


def test_simulation_mode_ignores_stale_live_tick_cache(tmp_path: Path):
    import time
    from prado_linux.config import PradoServerConfig
    from prado_linux.engine import DerivUniversalConnector
    from prado_linux.flow_math import TickRecord

    cfg = PradoServerConfig(connection_mode="SIMULATION")
    conn = DerivUniversalConnector(cfg)
    # Seed stale live-style tick cache (far from simulated R_100 base price ~1850)
    conn._tick_cache["R_100"] = (
        time.time(),
        [TickRecord(int(time.time() * 1000), 500.0, 500.0, 500.0, 0.0, 10.0, 0) for _ in range(60)],
    )
    ticks = conn.fetch_ticks("R_100", count=60)
    assert ticks
    assert ticks[-1].effective_price() > 1000.0

    # Switching to SIMULATION via connect() also clears _tick_cache
    conn._tick_cache["R_100"] = (
        time.time(),
        [TickRecord(int(time.time() * 1000), 500.0, 500.0, 500.0, 0.0, 10.0, 0) for _ in range(60)],
    )
    ok, _ = conn.connect()
    assert ok is True
    assert conn._tick_cache == {}


def test_deriv_cloud_disconnected_does_not_leak_sim_positions(tmp_path: Path):
    from prado_linux.config import PradoServerConfig
    from prado_linux.engine import DerivUniversalConnector

    cfg = PradoServerConfig(connection_mode="SIMULATION")
    conn = DerivUniversalConnector(cfg)
    conn.connect()
    ticks = conn.fetch_ticks("R_100", count=60)
    price = ticks[-1].effective_price()
    ok, _ = conn.place_order("R_100", "BUY", 10.0, price, price * 0.01, price * 0.01, multiplier=100)
    assert ok is True
    assert len(conn.get_open_positions()) == 1

    # Switch to DERIV_CLOUD without valid token (disconnected)
    cfg.connection_mode = "DERIV_CLOUD"
    conn.connect()
    assert conn.get_open_positions() == []
    closed_count, _ = conn.close_all_positions()
    assert closed_count == 0
    ok_single, _ = conn.close_single_position(conn._sim_positions[0]["ticket"])
    assert ok_single is False

    # Switching back to SIMULATION restores access to the open simulated position
    cfg.connection_mode = "SIMULATION"
    conn.connect()
    assert len(conn.get_open_positions()) == 1
