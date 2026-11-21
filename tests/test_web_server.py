import json
from pathlib import Path
import pytest

from prado_linux.config import PradoServerConfig, load_config, save_config
from prado_linux.auth import create_session_token, verify_password, verify_session_token
from prado_linux.engine import PradoTradingService


def test_default_config_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg = load_config(cfg_file)
    assert cfg.admin_username == "admin"
    assert cfg.zscore_threshold == 1.8
    assert cfg.imbalance_threshold == 0.35
    assert cfg.eod_flatten_time == "17:35"
    assert cfg.operation_mode == "BOTH"
    assert cfg.mt5_login == ""

    cfg.mt5_login = "12345678"
    cfg.mt5_server = "XPInvestimentos-PRD"
    cfg.active_symbols = ["WIN$N", "WDO$N", "BTCUSD#"]
    cfg.correlated_basket = ["PETR4", "VALE3"]
    save_config(cfg, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded.mt5_login == "12345678"
    assert reloaded.mt5_server == "XPInvestimentos-PRD"
    assert reloaded.active_symbols == ["WIN$N", "WDO$N", "BTCUSD#"]
    assert reloaded.correlated_basket == ["PETR4", "VALE3"]


def test_auth_password_and_session_tokens(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    assert verify_password("prado2026", cfg.admin_password_hash) is True
    assert verify_password("wrong", cfg.admin_password_hash) is False

    token = create_session_token("admin", cfg.secret_key)
    assert verify_session_token(token, cfg.secret_key) == "admin"
    assert verify_session_token(token + "tampered", cfg.secret_key) is None


def test_trading_service_snapshot_and_vwap_flow_cycle(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    cfg.active_symbols = ["WIN$N", "BTCUSD#"]
    cfg.correlated_basket = ["PETR4", "VALE3"]
    service = PradoTradingService(cfg, config_path=tmp_path / "config.json")

    snap = service.step_once()
    assert "account" in snap
    assert "symbols" in snap
    assert "WIN$N" in snap["symbols"]
    assert "BTCUSD#" in snap["symbols"]

    win_state = snap["symbols"]["WIN$N"]
    assert win_state["vwap"] > 0
    assert win_state["upper_2"] > win_state["vwap"] > win_state["lower_2"]
    assert win_state["regime"] in (
        "NEUTRAL",
        "INSTITUTIONAL_TREND_UP",
        "INSTITUTIONAL_TREND_DOWN",
        "HFT_MEAN_REVERSION",
    )


def test_web_app_login_config_and_monitoring_endpoints(tmp_path: Path):
    from prado_linux.web_app import PradoWebApp

    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)

    # 1. Unauthenticated request to /api/status returns 401
    status_code, body, _ = app.handle_request("GET", "/api/status", headers={}, body=b"")
    assert status_code == 401

    # 2. Login with default credentials (admin / prado2026)
    login_payload = json.dumps({"username": "admin", "password": "prado2026"}).encode("utf-8")
    status_code, body, resp_headers = app.handle_request(
        "POST", "/api/login", headers={"Content-Type": "application/json"}, body=login_payload
    )
    assert status_code == 200
    data = json.loads(body)
    assert data["ok"] is True
    cookie_header = resp_headers.get("Set-Cookie", "")
    assert "prado_session=" in cookie_header

    # 3. Authenticated request to /api/status returns full monitoring snapshot
    status_code, body, _ = app.handle_request(
        "GET", "/api/status", headers={"Cookie": cookie_header}, body=b""
    )
    assert status_code == 200
    snap = json.loads(body)
    assert "account" in snap
    assert "symbols" in snap

    # 4. Update MT5 account credentials & Broker Wall Street settings via /api/config
    update_payload = json.dumps(
        {
            "mt5_login": "55667788",
            "mt5_password": "secretMt5Password",
            "mt5_server": "ClearInvestimentos-PRD",
            "zscore_threshold": 2.1,
            "imbalance_threshold": 0.42,
            "operation_mode": "TREND_ONLY",
            "active_symbols": ["WIN$N", "WDO$N"],
            "correlated_basket": ["PETR4", "VALE3"],
        }
    ).encode("utf-8")
    status_code, body, _ = app.handle_request(
        "POST",
        "/api/config",
        headers={"Cookie": cookie_header, "Content-Type": "application/json"},
        body=update_payload,
    )
    assert status_code == 200
    cfg_resp = json.loads(body)
    assert cfg_resp["ok"] is True
    assert cfg_resp["config"]["mt5_login"] == "55667788"
    assert cfg_resp["config"]["mt5_server"] == "ClearInvestimentos-PRD"
    assert cfg_resp["config"]["zscore_threshold"] == 2.1
    assert cfg_resp["config"]["operation_mode"] == "TREND_ONLY"


def test_accounts_symbol_modes_custom_categories_and_multi_bot_fleet(tmp_path: Path):
    from prado_linux.web_app import PradoWebApp

    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)

    # Login
    login_payload = json.dumps({"username": "admin", "password": "prado2026"}).encode("utf-8")
    _, _, resp_headers = app.handle_request(
        "POST", "/api/login", headers={"Content-Type": "application/json"}, body=login_payload
    )
    cookie_header = resp_headers.get("Set-Cookie", "")
    auth_headers = {"Cookie": cookie_header, "Content-Type": "application/json"}

    # 1. Save an MT5 Account
    acc_payload = json.dumps(
        {
            "account_id": "acc_xp_1",
            "label": "Conta XP B3 Principal",
            "mt5_login": "10203040",
            "mt5_password": "xp_pass",
            "mt5_server": "XPInvestimentos-PRD",
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/accounts", headers=auth_headers, body=acc_payload)
    assert code == 200
    acc_resp = json.loads(body)
    assert acc_resp["ok"] is True
    assert any(a["account_id"] == "acc_xp_1" for a in acc_resp["accounts"])

    # 2. Fetch Broker Symbols in "PRINCIPAIS" and "TODOS" modes
    code, body, _ = app.handle_request(
        "GET", "/api/symbols?mode=PRINCIPAIS&account_id=acc_xp_1", headers=auth_headers, body=b""
    )
    assert code == 200
    sym_main = json.loads(body)
    assert sym_main["mode"] == "PRINCIPAIS"
    assert len(sym_main["symbols"]) > 0

    code, body, _ = app.handle_request(
        "GET", "/api/symbols?mode=TODOS&account_id=acc_xp_1", headers=auth_headers, body=b""
    )
    assert code == 200
    sym_all = json.loads(body)
    assert sym_all["mode"] == "TODOS"
    assert len(sym_all["symbols"]) >= len(sym_main["symbols"])

    # 3. Create Custom Symbol Category for the Broker
    cat_payload = json.dumps(
        {
            "category_name": "Meus Futuros B3",
            "symbols": ["WIN$N", "WDO$N", "IND$N"],
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/categories", headers=auth_headers, body=cat_payload)
    assert code == 200
    cat_resp = json.loads(body)
    assert cat_resp["ok"] is True
    assert "Meus Futuros B3" in cat_resp["categories"]
    assert "IND$N" in cat_resp["categories"]["Meus Futuros B3"]

    # 4. Create & Start a Robot instance tied to Account + Symbol
    bot_payload = json.dumps(
        {
            "name": "Robô Mini Índice Fala 1 & 2",
            "account_id": "acc_xp_1",
            "symbol": "WIN$N",
            "category": "Meus Futuros B3",
            "operation_mode": "BOTH",
            "lot_size": 2.0,
            "zscore_threshold": 1.8,
            "imbalance_threshold": 0.35,
            "revert_sigma": 2.0,
            "correlated_basket": ["PETR4", "VALE3"],
            "auto_start": True,
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/bots", headers=auth_headers, body=bot_payload)
    assert code == 200
    bot_resp = json.loads(body)
    assert bot_resp["ok"] is True
    created_bot = bot_resp["bot"]
    bot_id = created_bot["bot_id"]
    assert created_bot["status"] == "RUNNING"
    assert created_bot["symbol"] == "WIN$N"
    assert created_bot["account_id"] == "acc_xp_1"

    # 5. Toggle Stop / Start on the Robot instance
    code, body, _ = app.handle_request(
        "POST",
        "/api/bots/action",
        headers=auth_headers,
        body=json.dumps({"bot_id": bot_id, "action": "STOP"}).encode("utf-8"),
    )
    assert code == 200
    assert json.loads(body)["bot"]["status"] == "STOPPED"

    code, body, _ = app.handle_request(
        "POST",
        "/api/bots/action",
        headers=auth_headers,
        body=json.dumps({"bot_id": bot_id, "action": "START"}).encode("utf-8"),
    )
    assert code == 200
    assert json.loads(body)["bot"]["status"] == "RUNNING"


