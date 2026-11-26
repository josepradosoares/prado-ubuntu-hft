from __future__ import annotations

from pathlib import Path
import time

import pytest

from prado_linux.config import load_config
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TICK_FLAG_BUY, TICK_FLAG_SELL, TickRecord


def _sim_service(tmp_path: Path) -> PradoTradingService:
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.active_symbols = ["EURUSD", "GBPUSD"]
    return PradoTradingService(cfg, config_path=cfg_path)


def test_backtest_returns_extended_metrics_and_equity_curve(tmp_path: Path) -> None:
    svc = _sim_service(tmp_path)
    report = svc.run_mathematical_backtest(
        {
            "symbol": "EURUSD",
            "timeframe": "TICKS",
            "period": "CUSTOM",
            "tick_count": 600,
            "initial_capital": 10000.0,
            "lot_size": 0.05,
        }
    )

    assert report["symbol"] == "EURUSD"
    assert report["period"] == "CUSTOM"
    assert report["lot_size"] == 0.05
    assert "max_drawdown_pct" in report
    assert "avg_win" in report
    assert "avg_loss" in report
    assert "expectancy" in report
    assert "best_trade" in report
    assert "worst_trade" in report
    assert "max_consecutive_wins" in report
    assert "max_consecutive_losses" in report
    assert "equity_curve" in report
    assert len(report["equity_curve"]) >= 1
    assert report["equity_curve"][0]["equity"] == 10000.0
    assert report["equity_curve"][-1]["equity"] == report["final_equity"]

    # History stored in config must stay compact (no trades or equity_curve)
    assert svc.cfg.backtest_history
    assert "trades" not in svc.cfg.backtest_history[0]
    assert "equity_curve" not in svc.cfg.backtest_history[0]


def test_backtest_checks_every_tick_for_tp_sl_without_skipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _sim_service(tmp_path)
    svc.save_custom_template(
        {
            "template_id": "ENTRY_ONCE_PY",
            "name": "Entry Once",
            "custom_mode": "PYTHON",
            "python_code": "def evaluate(prices, ticks, params): return 'BUY' if len(prices) == 41 else 'WAIT'",
        }
    )

    # Build 600 ticks: flat around 1.1000, with a single sharp TP spike at tick 55 (would be skipped by stride=2)
    now_msc = int(time.time() * 1000)
    ticks: list[TickRecord] = []
    for i in range(600):
        price = 1.1000
        if i == 55:
            price = 1.1200  # Massive upward spike for a single tick -> MUST trigger TP!
        ticks.append(TickRecord(now_msc + i * 1000, price, price, price, 0.0, 50.0, TICK_FLAG_BUY))

    monkeypatch.setattr(svc.connector, "fetch_backtest_history", lambda *a, **kw: (ticks, "CTRADER_REAL"))
    report = svc.run_mathematical_backtest(
        {
            "symbol": "EURUSD",
            "template_id": "ENTRY_ONCE_PY",
            "tick_count": 600,
            "initial_capital": 10000.0,
            "lot_size": 0.10,
        }
    )
    assert report["total_trades"] >= 1
    first_trade = report["trades"][0]
    assert first_trade["exit"] == 1.12
    assert first_trade["result"] == "WIN"
    assert first_trade["pnl"] > 0


def test_backtest_all_symbols_computes_real_profit_factor_and_equity_curve(tmp_path: Path) -> None:
    svc = _sim_service(tmp_path)
    report = svc.run_mathematical_backtest(
        {
            "symbol": "ALL",
            "timeframe": "TICKS",
            "period": "CUSTOM",
            "tick_count": 400,
            "initial_capital": 10000.0,
            "lot_size": 0.05,
        }
    )
    assert report["symbol"].startswith("TODOS")
    assert "max_drawdown_pct" in report
    assert "expectancy" in report
    assert "equity_curve" in report
    if report["gross_loss"] > 0:
        expected_pf = round(report["gross_profit"] / report["gross_loss"], 2)
        assert report["profit_factor"] == expected_pf
