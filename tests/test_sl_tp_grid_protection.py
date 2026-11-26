"""TDD tests for Stop Loss modes (PCT/USD/PIPS/TICKS), Grid SL/TP honoring, and negative-SL clamp."""
from __future__ import annotations

from pathlib import Path

import pytest

from prado_linux.config import load_config
from prado_linux.engine import PradoTradingService, normalize_sl_config


def test_normalize_sl_config_modes() -> None:
    assert normalize_sl_config("AUTO", 10) == ("AUTO", 0.0)
    assert normalize_sl_config("PCT", 0.5) == ("PCT", 0.5)
    assert normalize_sl_config("USD", 5.0) == ("USD", 5.0)
    assert normalize_sl_config("PIPS", 15) == ("PIPS", 15.0)
    assert normalize_sl_config("TICKS", 20) == ("TICKS", 20.0)
    assert normalize_sl_config("PCT", -2) == ("PCT", 0.5)
    assert normalize_sl_config("UNKNOWN", 10) == ("AUTO", 0.0)


def test_place_order_sl_pct_usd_pips_and_negative_sl_clamp(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "cfg.json")
    cfg.connection_mode = "SIMULATION"
    cfg.ctrader_access_token = ""
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")

    class _FakeCTraderClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.last_order_lifecycle: dict = {"position_id": 1001}

        def place_market_order(self, **kwargs):
            self.calls.append(kwargs)
            return True, "OK"

    fake = _FakeCTraderClient()
    svc.connector._client = fake  # type: ignore[assignment]

    # 1. SL in PCT (0.5% of 1.1000 = 0.0055)
    ok, _ = svc.connector.place_order(
        symbol="EURUSD",
        action="BUY_FLOW",
        lot_size=0.01,
        price=1.1000,
        sl_points=0.0020,
        tp_points=0.0040,
        bot_name="TestBot",
        sl_mode="PCT",
        sl_value=0.5,
    )
    assert ok is True
    assert fake.calls[-1]["sl_points"] == pytest.approx(0.0055, abs=1e-6)

    # 2. SL in USD ($5 on 0.01 lot EURUSD => contract_size 100k * 0.01 = 1000 => 5 / 1000 = 0.0050)
    ok, _ = svc.connector.place_order(
        symbol="GBPUSD",
        action="BUY_FLOW",
        lot_size=0.01,
        price=1.2500,
        sl_points=0.0020,
        tp_points=0.0040,
        bot_name="TestBot",
        sl_mode="USD",
        sl_value=5.0,
    )
    assert ok is True
    assert fake.calls[-1]["sl_points"] == pytest.approx(0.0050, abs=1e-6)

    # 3. Negative-SL clamp (e.g. huge grid_step * max_levels = 7.5505 on EURUSD 1.09712)
    ok, _ = svc.connector.place_order(
        symbol="USDCAD",
        action="BUY_FLOW",
        lot_size=0.01,
        price=1.09712,
        sl_points=7.5505,
        tp_points=0.0040,
        bot_name="TestBot",
    )
    assert ok is True
    clamped_sl = fake.calls[-1]["sl_points"]
    assert 0.0 < clamped_sl < 1.09712 * 0.50


def test_grid_bot_honors_pct_sl_and_tp_and_create_bot_persists_sl_mode(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "cfg_grid.json")
    cfg.connection_mode = "SIMULATION"
    cfg.ctrader_access_token = ""
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg_grid.json")

    bot = svc.create_bot(
        {
            "name": "Volatilidade EURUSD",
            "symbol": "EURUSD",
            "template_id": "GRID_LINEAR_HFT",
            "lot_size": 0.01,
            "grid_direction": "BUY_ONLY",
            "grid_step_points": 1.5101,
            "grid_tp_points": 1.5101,
            "max_grid_levels": 5,
            "tp_mode": "PCT",
            "tp_value": 0.5,
            "sl_mode": "PCT",
            "sl_value": 1.0,
        }
    )
    assert bot["sl_mode"] == "PCT"
    assert bot["sl_value"] == 1.0

    captured: list[dict] = []
    orig_place = svc.connector.place_order

    def _spy_place(**kwargs):
        captured.append(kwargs)
        return orig_place(**kwargs)

    svc.connector.place_order = _spy_place  # type: ignore[method-assign]
    svc._evaluate_grid_bot(bot, last_price=1.1000, positions=[], risk_locked=False)

    assert len(captured) == 1
    assert captured[0]["tp_mode"] == "PCT"
    assert captured[0]["tp_value"] == 0.5
    assert captured[0]["sl_mode"] == "PCT"
    assert captured[0]["sl_value"] == 1.0

    # Open simulated position should have valid positive SL (~1.089) and realistic TP (~1.1055), never 2.60722
    pos = svc.connector.get_open_positions()
    assert len(pos) == 1
    assert pos[0]["sl"] == pytest.approx(1.089, abs=0.001)
    assert pos[0]["tp"] == pytest.approx(1.1055, abs=0.001)
