from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from prado_linux.config import load_config
from prado_linux.ctrader_client import CTraderClient
from prado_linux.engine import PradoTradingService
from prado_linux.supabase_store import SupabaseConfig, SupabaseStore
from prado_linux.web_app import PradoWebApp


def _login_headers(app: PradoWebApp, password: str = "prado2026") -> dict[str, str]:
    code, _, hdrs = app.handle_request(
        "POST",
        "/api/login",
        {"Content-Type": "application/json"},
        json.dumps({"username": "admin", "password": password}).encode("utf-8"),
    )
    assert code == 200
    return {"Cookie": hdrs["Set-Cookie"], "Content-Type": "application/json"}


def test_format_position_extracts_open_timestamp_and_costs() -> None:
    client = CTraderClient(
        client_id="cid",
        client_secret="csec",
        access_token="tok",
        account_id="10142159",
        is_live=False,
    )
    client._symbols_by_id[1] = {"name": "EURUSD", "category": "Forex"}
    client._symbol_details_cache[1] = (time.time(), {"symbolName": "EURUSD", "lotSize": 10_000_000, "digits": 5})

    open_ts = int(time.time() * 1000) - 90_000
    expected_str = datetime.fromtimestamp(open_ts / 1000.0).strftime("%d/%m %H:%M:%S")
    pos = {
        "positionId": 7711,
        "tradeData": {
            "symbolId": 1,
            "tradeSide": 1,
            "volume": 200_000,
            "openTimestamp": open_ts,
            "label": "BotTrend",
        },
        "price": 1.09500,
        "stopLoss": 1.09000,
        "takeProfit": 1.10200,
        "swap": -45,
        "commission": -120,
        "usedMargin": 2500,
        "moneyDigits": 2,
    }
    pnl_entry = {"positionId": 7711, "netUnrealizedPnL": 1420}
    formatted = client._format_position(pos, pnl_entry=pnl_entry, pnl_digits=2)

    assert formatted["open_timestamp_ms"] == open_ts
    assert formatted["open_time_str"] == expected_str
    assert formatted["swap"] == -0.45
    assert formatted["commission"] == -1.20
    assert formatted["used_margin"] == 25.00
    assert formatted["sl"] == 1.09
    assert formatted["tp"] == 1.102
    assert formatted["profit"] == 14.20


def test_simulation_place_order_records_open_time_and_costs(tmp_path: Path) -> None:
    cfg_path = tmp_path / "sim.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    svc = PradoTradingService(cfg, config_path=cfg_path)

    ok, _ = svc.connector.place_order(
        symbol="EURUSD",
        action="BUY_FLOW",
        lot_size=0.05,
        price=1.09500,
        sl_points=0.0020,
        tp_points=0.0040,
        bot_name="BotSim",
    )
    assert ok is True
    positions = svc.connector.get_open_positions()
    assert len(positions) == 1
    p = positions[0]
    assert int(p["open_timestamp_ms"]) > 0
    assert len(str(p["open_time_str"])) == 14  # dd/MM HH:mm:ss
    assert p["swap"] == 0.0
    assert p["commission"] == 0.0


def test_close_profitable_positions_sim_and_live(tmp_path: Path) -> None:
    # 1) Simulation mode via HTTP POST /api/flatten {profitable_only: true}
    app = PradoWebApp(config_path=tmp_path / "app.json", supabase_store=SupabaseStore(SupabaseConfig()))
    app.cfg.connection_mode = "SIMULATION"
    auth = _login_headers(app)

    app.service.connector._sim_positions = [
        {
            "ticket": "sim_win",
            "symbol": "EURUSD",
            "type": "BUY",
            "side": "BUY",
            "volume": 0.1,
            "price_open": 1.0900,
            "price_current": 1.0920,
            "sl": 1.0880,
            "tp": 1.0940,
            "profit": 15.0,
            "bot_name": "BotW",
            "comment": "BotW",
            "open_timestamp_ms": int(time.time() * 1000) - 60_000,
            "open_time_str": "26/11 09:40:00",
        },
        {
            "ticket": "sim_loss",
            "symbol": "GBPUSD",
            "type": "SELL",
            "side": "SELL",
            "volume": 0.1,
            "price_open": 1.2700,
            "price_current": 1.2710,
            "sl": 0.0,
            "tp": 0.0,
            "profit": -8.0,
            "bot_name": "BotL",
            "comment": "BotL",
            "open_timestamp_ms": int(time.time() * 1000) - 30_000,
            "open_time_str": "26/11 09:41:00",
        },
    ]

    code, body, _ = app.handle_request(
        "POST",
        "/api/flatten",
        auth,
        json.dumps({"profitable_only": True}).encode("utf-8"),
    )
    assert code == 200
    resp = json.loads(body)
    assert resp["ok"] is True
    assert resp["closed"] == 1
    assert [p["ticket"] for p in app.service.connector._sim_positions] == ["sim_loss"]
    assert app.service.connector._sim_daily_pnl == 15.0
    assert app.service.connector._sim_deals_history[0]["ticket"] == "sim_win"

    # 2) Live cTrader mode: closes only positive profit positions
    svc = app.service
    svc.cfg.connection_mode = "CTRADER_CLOUD"

    class _FakeClient:
        def __init__(self) -> None:
            self.closed_calls: list[str] = []

        def get_open_positions(self) -> list[dict[str, Any]]:
            return [
                {"ticket": "w1", "symbol": "EURUSD", "side": "BUY", "volume": 0.1, "volume_raw": 100000, "price_open": 1.09, "price_current": 1.091, "profit": 12.5, "bot_name": "B1", "comment": "B1"},
                {"ticket": "l1", "symbol": "XAUUSD", "side": "SELL", "volume": 0.05, "volume_raw": 5000, "price_open": 2650.0, "price_current": 2651.0, "profit": -4.0, "bot_name": "B2", "comment": "B2"},
            ]

        def close_position(self, position_id: str | int, volume_raw: int | None = None) -> tuple[bool, str]:
            self.closed_calls.append(str(position_id))
            return True, f"closed #{position_id}"

    fake = _FakeClient()
    svc.connector._client = fake  # type: ignore[assignment]
    cnt, msg = svc.flatten_profitable("TEST_WINNERS")
    assert cnt == 1
    assert "1" in msg
    assert fake.closed_calls == ["w1"]
