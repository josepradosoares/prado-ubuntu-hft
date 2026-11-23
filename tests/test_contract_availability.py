"""Tests for Deriv contracts_for pre-validation and TradingDurationNotAllowed resilience."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from prado_linux.config import PradoServerConfig
from prado_linux.deriv_client import DerivClient
from prado_linux.engine import PradoTradingService


def test_contracts_for_cache_and_blocks_missing_multiplier() -> None:
    calls: list[dict[str, Any]] = []

    def mock_rpc(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        if "contracts_for" in payload:
            return {
                "msg_type": "contracts_for",
                "contracts_for": {
                    "available": [
                        {
                            "barriers": 0,
                            "contract_category": "callput",
                            "contract_type": "CALL",
                            "expiry_type": "intraday",
                            "market": "forex",
                            "max_contract_duration": "365d",
                            "min_contract_duration": "15m",
                            "sentiment": "up",
                            "submarket": "major_pairs",
                            "underlying_symbol": "frxEURUSD",
                        }
                    ]
                },
            }
        raise AssertionError(f"Unexpected RPC call when contract is unavailable: {payload}")

    client = DerivClient(token="pat_test", app_id="1089", rpc_transport=mock_rpc)
    ok1, msg1 = client.place_multiplier_order(symbol="frxEURUSD", is_buy=True, stake=10.0, multiplier=100)
    ok2, msg2 = client.place_multiplier_order(symbol="frxEURUSD", is_buy=True, stake=10.0, multiplier=100)

    assert ok1 is False
    assert "indisponível" in msg1.lower()
    assert ok2 is False
    assert msg2 == msg1
    assert client.last_order_lifecycle["stage"] == "CONTRACT_UNAVAILABLE"
    # Cached after the first contracts_for call
    assert len(calls) == 1
    assert "contracts_for" in calls[0]


def test_contracts_for_empty_available_blocks_proposal() -> None:
    calls: list[dict[str, Any]] = []

    def mock_rpc(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        if "contracts_for" in payload:
            return {"msg_type": "contracts_for", "contracts_for": {"available": []}}
        raise AssertionError(f"Unexpected RPC call when market closed: {payload}")

    client = DerivClient(token="pat_test", app_id="1089", rpc_transport=mock_rpc)
    ok, msg = client.place_multiplier_order(symbol="frxEURUSD", is_buy=False, stake=10.0, multiplier=100)

    assert ok is False
    assert "nenhum contrato disponível" in msg.lower()
    assert len(calls) == 1


def test_place_multiplier_order_handles_trading_duration_not_allowed_without_raising() -> None:
    def mock_rpc(payload: dict[str, Any]) -> dict[str, Any]:
        if "contracts_for" in payload:
            return {
                "msg_type": "contracts_for",
                "contracts_for": {
                    "available": [
                        {
                            "barriers": 0,
                            "contract_category": "multiplier",
                            "contract_type": "MULTUP",
                            "expiry_type": "no_expiry",
                            "market": "synthetic_index",
                            "max_contract_duration": "0",
                            "min_contract_duration": "0",
                            "sentiment": "up",
                            "submarket": "random_index",
                            "underlying_symbol": "R_100",
                        }
                    ]
                },
            }
        if "proposal" in payload:
            raise RuntimeError("Deriv API (TradingDurationNotAllowed): Trading is not offered for this duration.")
        raise AssertionError(f"Unexpected RPC call: {payload}")

    client = DerivClient(token="pat_test", app_id="1089", rpc_transport=mock_rpc)
    ok, msg = client.place_multiplier_order(symbol="R_100", is_buy=True, stake=10.0, multiplier=100)

    assert ok is False
    assert "TradingDurationNotAllowed" in msg
    assert client.last_order_lifecycle["stage"] == "CONTRACT_UNAVAILABLE"


def test_step_once_keeps_bot_running_on_contract_unavailable(tmp_path: Path) -> None:
    cfg = PradoServerConfig(
        connection_mode="SIMULATION",
        auto_trading_enabled=True,
        custom_templates=[{"template_id": "T_UNAVAIL", "name": "Test"}],
        bots=[
            {
                "bot_id": "bot-fx",
                "name": "FX Grid",
                "symbol": "frxEURUSD",
                "template_id": "T_UNAVAIL",
                "status": "RUNNING",
                "active": True,
                "lot_size": 10.0,
                "multiplier": 100,
            }
        ],
    )
    svc = PradoTradingService(cfg=cfg, config_path=tmp_path / "config.json")
    svc.connector.place_order = lambda **kwargs: (  # type: ignore[method-assign]
        False,
        "[Deriv] Contrato/duração indisponível para frxEURUSD: Deriv API (TradingDurationNotAllowed): Trading is not offered for this duration.",
    )
    svc._evaluate_custom_template = lambda tpl, ticks, b: "BUY_FLOW"  # type: ignore[method-assign]

    svc.step_once()

    bot = svc.cfg.bots[0]
    assert bot["status"] == "RUNNING"
    assert bot["active"] is True
    assert bot["last_signal"] == "UNAVAILABLE"
    assert "TradingDurationNotAllowed" in bot["last_error"]
    assert float(bot.get("_unavailable_until", 0.0)) > time.time()


def test_grid_bot_respects_unavailable_cooldown(tmp_path: Path) -> None:
    cfg = PradoServerConfig(
        connection_mode="SIMULATION",
        auto_trading_enabled=True,
        bots=[
            {
                "bot_id": "bot-grid-fx",
                "name": "Grid FX",
                "symbol": "frxEURUSD",
                "template_id": "GRID_LINEAR_HFT",
                "operation_mode": "GRID_LINEAR",
                "grid_direction": "BUY_ONLY",
                "status": "RUNNING",
                "active": True,
                "lot_size": 10.0,
                "multiplier": 100,
            }
        ],
    )
    svc = PradoTradingService(cfg=cfg, config_path=tmp_path / "config.json")
    call_count = 0

    def mock_place_order(**kwargs: Any) -> tuple[bool, str]:
        nonlocal call_count
        call_count += 1
        return (
            False,
            "[Deriv] Contrato/duração indisponível para frxEURUSD: Deriv API (TradingDurationNotAllowed): Trading is not offered for this duration.",
        )

    svc.connector.place_order = mock_place_order  # type: ignore[method-assign]

    svc.step_once()
    svc.step_once()

    bot = svc.cfg.bots[0]
    assert bot["status"] == "RUNNING"
    assert bot["active"] is True
    assert bot["last_signal"] == "UNAVAILABLE"
    assert "TradingDurationNotAllowed" in bot["last_error"]
    assert float(bot.get("_unavailable_until", 0.0)) > time.time()
    assert call_count == 1
