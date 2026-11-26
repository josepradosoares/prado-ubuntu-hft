from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from prado_linux.config import load_config
from prado_linux.ctrader_client import CTraderRateLimitError
from prado_linux.engine import MATH_BOT_TEMPLATES, PradoTradingService, normalize_tp_config
from prado_linux.flow_math import TickRecord


def _sim_service(tmp_path: Path) -> PradoTradingService:
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.active_symbols = ["EURUSD"]
    cfg.correlated_basket = ["EURUSD", "GBPUSD"]
    return PradoTradingService(cfg, config_path=cfg_path)


def test_normalize_tp_config_variants() -> None:
    assert normalize_tp_config("AUTO", 0) == ("AUTO", 0.0)
    assert normalize_tp_config("TICKS", 15) == ("TICKS", 15.0)
    assert normalize_tp_config("USD", 12.5) == ("USD", 12.5)
    assert normalize_tp_config("PIPS", "bad") == ("PIPS", 10.0)
    assert normalize_tp_config("PCT", -1) == ("PCT", 0.25)
    assert normalize_tp_config("UNKNOWN", "bad") == ("AUTO", 0.0)


def test_custom_templates_crud_and_evaluation(tmp_path: Path) -> None:
    svc = _sim_service(tmp_path)
    native_id = MATH_BOT_TEMPLATES[0]["template_id"]

    with pytest.raises(ValueError):
        svc.save_custom_template({"template_id": native_id, "name": "Hack"})
    with pytest.raises(ValueError):
        svc.delete_custom_template(native_id)

    py_tpl = svc.save_custom_template(
        {
            "template_id": "CUSTOM_PY_1",
            "name": "Py Buy",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params): return 'BUY'",
        }
    )
    assert py_tpl["custom_mode"] == "PYTHON"
    # Update existing
    svc.save_custom_template(
        {
            "template_id": "CUSTOM_PY_1",
            "name": "Py Buy Updated",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params): return 'BUY'",
        }
    )

    test_res = svc.test_custom_template(
        {
            "symbol": "EURUSD",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params): return 'SELL'",
        }
    )
    assert test_res["ok"] is True and test_res["signal"] == "SELL"

    ticks = svc.connector._generate_sim_ticks("EURUSD")
    assert svc._evaluate_custom_template(py_tpl, ticks) == "BUY_FLOW"
    assert svc._evaluate_custom_template({"custom_mode": "PYTHON", "python_code": "bad syntax("}, ticks) == "WAIT"
    assert svc._evaluate_custom_template({"custom_mode": "INDICATORS", "indicators": [{"id": "SMA"}]}, ticks) in (
        "BUY_FLOW",
        "SELL_FLOW",
        "WAIT",
    )
    assert svc._evaluate_custom_template({"custom_mode": "OTHER"}, ticks) == ""

    assert svc.delete_custom_template("CUSTOM_PY_1") is True
    assert svc.delete_custom_template("NON_EXISTENT") is False


def test_sync_ctrader_accounts_paths(tmp_path: Path) -> None:
    svc = _sim_service(tmp_path)

    # No access token
    ok, msg, _ = svc.sync_ctrader_accounts()
    assert not ok and "Access Token" in msg

    # With fake client returning 2 accounts (existing + new)
    class _FakeClient:
        def __init__(self, accounts: list[dict[str, Any]] | None = None, boom: bool = False) -> None:
            self._accounts = accounts if accounts is not None else []
            self._boom = boom

        def list_accounts(self) -> list[dict[str, Any]]:
            if self._boom:
                raise RuntimeError("ws failure")
            return self._accounts

    svc.cfg.ctrader_access_token = "tok_1"
    svc.cfg.accounts = [{"account_id": "ct_100", "ctid_account_id": "100", "account_type": "DEMO"}]

    svc.connector._client = _FakeClient(boom=True)  # type: ignore[assignment]
    ok, msg, _ = svc.sync_ctrader_accounts()
    assert not ok and "Erro ao sincronizar" in msg

    svc.connector._client = _FakeClient(accounts=[])  # type: ignore[assignment]
    ok, msg, _ = svc.sync_ctrader_accounts()
    assert not ok and "Nenhuma conta" in msg

    svc.connector._client = _FakeClient(
        accounts=[
            {"ctid_account_id": "100", "account_type": "DEMO", "is_live": False, "broker_name": "B1", "balance": 5000.0},
            {"ctid_account_id": "200", "account_type": "REAL", "is_live": True, "broker_name": "B1", "balance": 1200.0},
        ]
    )  # type: ignore[assignment]
    ok, msg, accs = svc.sync_ctrader_accounts()
    assert ok and len(accs) == 2
    assert svc.cfg.active_account_id == "ct_100"


def test_news_processing_pause_auto_trade_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _sim_service(tmp_path)
    svc.cfg.news_bot_enabled = True
    svc.cfg.news_pause_grid_on_high_impact = True
    svc.cfg.news_auto_trade_enabled = True
    svc.cfg.auto_trading_enabled = True

    grid_bot = svc.create_bot(
        {
            "name": "Grid EURUSD",
            "symbol": "EURUSD",
            "template_id": "GRID_LINEAR_HFT",
            "operation_mode": "GRID_LINEAR",
            "auto_start": True,
        }
    )
    assert grid_bot["status"] == "RUNNING"

    high_news = [
        {"impact": "LOW", "symbol": "EURUSD", "bias": "NEUTRAL", "title": "Noise"},
        {
            "impact": "HIGH",
            "symbol": "EURUSD",
            "bias": "BULLISH",
            "is_macro_usd": True,
            "title": "CPI Surprise Higher",
        },
    ]
    positions, paused_ids = svc._process_news_items(high_news, [], risk_locked=False)
    assert grid_bot["bot_id"] in paused_ids
    assert grid_bot["status"] == "PAUSED"
    assert grid_bot["last_signal"] == "PAUSED_NEWS"
    assert len(positions) >= 1  # auto-trade opened BUY_NEWS

    # Auto-resume when summary has no high impact
    monkeypatch.setattr(svc.news_scout, "summary_by_symbol", lambda: {"EURUSD": {"high_impact": 0, "bias": "NEUTRAL"}})
    svc._auto_resume_news_paused_bots(skip_bot_ids=set())
    assert grid_bot["status"] == "RUNNING"
    assert grid_bot["last_signal"] == "RESUMED_NEWS"

    # scan_news forced path
    monkeypatch.setattr(svc.news_scout, "scan", lambda feeds=None: (high_news, high_news))
    snap = svc.scan_news(force=True)
    assert isinstance(snap, dict)


def test_step_once_risk_locks_bot_guards_news_hybrid_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _sim_service(tmp_path)
    svc.cfg.max_daily_loss_money = 50.0
    svc.cfg.daily_target_money = 100.0
    svc.cfg.auto_trading_enabled = True

    # 1. Custom Python bot + news-assisted bot + broken bot (no symbol)
    svc.save_custom_template(
        {
            "template_id": "ALWAYS_BUY_PY",
            "name": "Always Buy",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params): return 'BUY'",
        }
    )
    bot_py = svc.create_bot(
        {
            "name": "BotPy",
            "symbol": "EURUSD",
            "template_id": "ALWAYS_BUY_PY",
            "auto_start": True,
            "loss_guard_enabled": True,
            "max_loss_usd": 10.0,
        }
    )
    svc.cfg.news_filter_only = False
    bot_news = svc.create_bot(
        {
            "name": "BotNews",
            "symbol": "GBPUSD",
            "news_assisted": True,
            "auto_start": True,
        }
    )
    svc.cfg.bots.append({"bot_id": "bad_bot", "name": "BadBot", "symbol": "", "status": "RUNNING"})

    monkeypatch.setattr(
        svc.news_scout,
        "summary_by_symbol",
        lambda: {"GBPUSD": {"bias": "BULLISH", "high_impact": 0}},
    )
    snap = svc.step_once()
    assert snap["risk_locked"] is False
    assert bot_py["trades_executed"] >= 1
    assert bot_news["trades_executed"] >= 1
    bad = next(b for b in svc.cfg.bots if b["bot_id"] == "bad_bot")
    assert bad["status"] == "ERROR"

    # 2. Flip news bias against profitable GBPUSD position -> NEWS_TECH_EXIT
    for p in svc.connector._sim_positions:
        if p["symbol"] == "GBPUSD":
            p["profit"] = 25.0
            p["type"] = "BUY"
    monkeypatch.setattr(
        svc.news_scout,
        "summary_by_symbol",
        lambda: {"GBPUSD": {"bias": "BEARISH", "high_impact": 0}},
    )
    svc.step_once()
    assert bot_news["last_signal"] in ("NEWS_TECH_EXIT", "HOLD_NEWS_PROFIT")

    # 3. Bot max loss guard pauses BotPy
    svc.connector._sim_deals_history.append({"bot_name": "BotPy", "symbol": "EURUSD", "profit": -20.0})
    svc.step_once()
    assert bot_py["status"] == "PAUSED"
    assert bot_py["last_signal"] == "PAUSED_MAX_LOSS"

    # 4. Daily loss lock triggers close_all_positions & blocks FIRE_BUY
    svc.connector._sim_daily_pnl = -60.0
    snap_loss = svc.step_once()
    assert snap_loss["risk_locked"] is True
    assert "perda" in snap_loss["risk_status"].lower()

    res_blocked = svc.control_bot(bot_py["bot_id"], "FIRE_BUY")
    assert res_blocked is not None and res_blocked["last_signal"] == "RISK_LOCKED"

    # 5. Daily target reached
    svc.connector._sim_daily_pnl = 150.0
    snap_target = svc.step_once()
    assert snap_target["risk_locked"] is True
    assert "meta" in snap_target["risk_status"].lower()

    # 6. Rate limit exception isolated per bot
    svc.connector._sim_daily_pnl = 0.0
    svc.connector._sim_deals_history.clear()
    svc.control_bot(bot_py["bot_id"], "START")
    svc.control_bot(bot_py["bot_id"], "PAUSE")
    svc.control_bot(bot_py["bot_id"], "RESUME")
    svc.control_bot(bot_py["bot_id"], "STOP")
    svc.control_bot(bot_py["bot_id"], "START")

    orig_fetch = svc.connector.fetch_ticks
    eur_calls = {"n": 0}

    def _rl_fetch(sym: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
        if sym == "EURUSD" and count == 200:
            eur_calls["n"] += 1
            if eur_calls["n"] >= 2:
                raise CTraderRateLimitError("RateLimit exceeded")
        return orig_fetch(sym, count=count, granularity=granularity)

    monkeypatch.setattr(svc.connector, "fetch_ticks", _rl_fetch)
    svc.step_once()
    assert bot_py["last_signal"] == "RATE_LIMITED"

    # 7. Delete bot
    removed = svc.control_bot(bot_py["bot_id"], "DELETE")
    assert removed is not None and removed["bot_id"] == bot_py["bot_id"]
