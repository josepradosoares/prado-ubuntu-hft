"""Tests for P0/P1 security, risk, concurrency, and bug fixes from the engineering audit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prado_linux.config import load_config
from prado_linux.deriv_client import DerivAuthError, DerivClient
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord
from prado_linux.indicators import evaluate_python_model
from prado_linux.news_scout import validate_rss_url
from prado_linux.web_app import PradoWebApp


def test_python_model_blocks_rce_dunder_import_and_infinite_loop() -> None:
    ticks = [TickRecord(time_msc=1000 + i, last=100.0 + i * 0.1, bid=100.0, ask=100.1, volume_real=0.0, tick_volume=1.0, flags=0) for i in range(10)]
    prices = [t.effective_price() for t in ticks]

    r_dunder = evaluate_python_model("def evaluate(prices, ticks, params):\n    return ().__class__.__mro__[1].__subclasses__()\n", prices, ticks)
    assert r_dunder["ok"] is False

    r_import = evaluate_python_model("import os\ndef evaluate(prices, ticks, params):\n    return 'BUY'\n", prices, ticks)
    assert r_import["ok"] is False

    r_loop = evaluate_python_model("def evaluate(prices, ticks, params):\n    while True:\n        pass\n", prices, ticks)
    assert r_loop["ok"] is False
    assert "limite" in r_loop["error"].lower() or "timeout" in r_loop["error"].lower()

    r_ok = evaluate_python_model("def evaluate(prices, ticks, params):\n    return 'BUY' if prices[-1] > prices[0] else 'WAIT'\n", prices, ticks)
    assert r_ok["ok"] is True
    assert r_ok["signal"] == "BUY"


def test_update_config_blocks_mass_assignment_of_sensitive_fields(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    cfg = load_config(cfg_path)
    orig_secret = cfg.secret_key
    orig_admin = cfg.admin_username
    svc = PradoTradingService(cfg, config_path=cfg_path)

    svc.update_config({
        "secret_key": "attacker_forged_secret",
        "admin_username": "hacker",
        "bots": [{"name": "injected"}],
        "zscore_threshold": 2.25,
    })

    assert svc.cfg.secret_key == orig_secret
    assert svc.cfg.admin_username == orig_admin
    assert svc.cfg.bots == []
    assert svc.cfg.zscore_threshold == 2.25


def test_ssrf_validation_blocks_internal_and_non_http_urls(tmp_path: Path) -> None:
    for bad_url in (
        "file:///etc/passwd",
        "http://127.0.0.1:8080/api/status",
        "http://localhost:8080/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
    ):
        ok, _ = validate_rss_url(bad_url)
        assert ok is False, f"Expected SSRF block for {bad_url}"

    ok_pub, _ = validate_rss_url("https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD")
    assert ok_pub is True

    cfg_path = tmp_path / "cfg.json"
    svc = PradoTradingService(load_config(cfg_path), config_path=cfg_path)
    with pytest.raises(ValueError):
        svc.save_news_feed({"source": "Bad", "url": "http://127.0.0.1:8080/secret", "default_symbol": "R_100"})


def test_pick_account_never_falls_back_silently_from_demo_to_real() -> None:
    client = DerivClient(token="pat_test_123", app_id="12345", preferred_account_type="DEMO")
    with pytest.raises(DerivAuthError) as exc_info:
        client._pick_account([{"account_id": "CR12345", "account_type": "real", "is_virtual": 0}])
    assert "NO_DEMO_ACCOUNT" in str(exc_info.value) or "DEMO" in str(exc_info.value)


def test_step_once_with_new_news_produces_json_serializable_positions(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.news_bot_enabled = True
    cfg.news_pause_grid_on_high_impact = True
    cfg.news_poll_interval_sec = 30
    svc = PradoTradingService(cfg, config_path=cfg_path)
    svc.news_scout.last_scan_at = 0.0
    svc.news_scout._fetcher = lambda _url: (
        "<rss><channel><item><title>Fed rate hike shock hits BTC</title>"
        "<link>https://example.com/1</link><pubDate>Mon, 23 Nov 2026 04:00:00 GMT</pubDate></item></channel></rss>"
    )

    snap = svc.step_once()
    assert isinstance(snap["positions"], list)
    json.dumps(snap)


def test_health_endpoint_is_public_and_fire_buy_respects_risk_lock(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    app = PradoWebApp(config_path=cfg_path)
    code, body, _ = app.handle_request("GET", "/health", {}, b"")
    assert code == 200
    assert json.loads(body)["status"] == "healthy"

    app.service.cfg.connection_mode = "SIMULATION"
    app.service.cfg.max_daily_loss_money = 100.0
    app.service.connector._sim_daily_pnl = -150.0
    bot = app.service.create_bot({"name": "TestBot", "symbol": "R_100"})
    res = app.service.control_bot(bot["bot_id"], "FIRE_BUY")
    assert res is not None
    assert res["last_signal"] == "RISK_LOCKED"
    assert res["trades_executed"] == 0


def test_bet_expired_and_sold_contracts_handled_gracefully() -> None:
    def _fake_rpc(payload: dict) -> dict:
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [
                        {"contract_id": "101", "symbol": "R_100", "buy_price": 10.0},
                        {"contract_id": "102", "symbol": "R_100", "buy_price": 10.0},
                    ]
                }
            }
        if "proposal_open_contract" in payload:
            cid = payload["contract_id"]
            if cid == 101:
                return {"proposal_open_contract": {"contract_id": 101, "is_sold": 1, "is_expired": 1, "status": "sold"}}
            return {"proposal_open_contract": {"contract_id": 102, "underlying_symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0, "entry_spot": 500.0, "current_spot": 501.0, "profit": 1.2}}
        if "sell" in payload:
            return {"error": {"code": "BetExpired", "message": "The contract has expired."}}
        return {}

    client = DerivClient(token="pat_test_123", app_id="12345", rpc_transport=_fake_rpc)
    open_contracts = client.get_open_contracts()
    assert [c["ticket"] for c in open_contracts] == ["102"]

    ok, msg = client.close_contract("101")
    assert ok is True
    assert "expirado" in msg.lower() or "encerrado" in msg.lower()


def test_control_bot_pause_resume_stop_updates_snapshot_immediately(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    app = PradoWebApp(config_path=cfg_path)
    app.service.cfg.connection_mode = "SIMULATION"
    bot = app.service.create_bot({"name": "BotInstant", "symbol": "R_100"})
    app.service.step_once()

    res_pause = app.service.control_bot(bot["bot_id"], "PAUSE")
    assert res_pause is not None and res_pause["status"] == "PAUSED" and res_pause["active"] is False
    snap = app.service.get_snapshot()
    assert snap["bots"][0]["status"] == "PAUSED"

    res_resume = app.service.control_bot(bot["bot_id"], "RESUME")
    assert res_resume is not None and res_resume["status"] == "RUNNING" and res_resume["active"] is True
    snap = app.service.get_snapshot()
    assert snap["bots"][0]["status"] == "RUNNING"

    res_stop = app.service.control_bot(bot["bot_id"], "STOP")
    assert res_stop is not None and res_stop["status"] == "STOPPED" and res_stop["active"] is False
    snap = app.service.get_snapshot()
    assert snap["bots"][0]["status"] == "STOPPED"


