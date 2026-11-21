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

