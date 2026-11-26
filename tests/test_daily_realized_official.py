from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import Any

import pytest

from prado_linux.config import load_config
from prado_linux.ctrader_client import (
    PT_ACCOUNT_AUTH_REQ,
    PT_ACCOUNT_AUTH_RES,
    PT_APPLICATION_AUTH_REQ,
    PT_APPLICATION_AUTH_RES,
    PT_ASSET_LIST_REQ,
    PT_ASSET_LIST_RES,
    PT_DEAL_LIST_REQ,
    PT_DEAL_LIST_RES,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
    PT_TRADER_REQ,
    PT_TRADER_RES,
    CTraderClient,
)
from prado_linux.engine import PradoTradingService


def _make_live_service(tmp_path: Path) -> PradoTradingService:
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "CTRADER_CLOUD"
    cfg.active_account_id = "ct_10142159"
    cfg.active_account_type = "DEMO"
    cfg.max_daily_loss_money = 500.0
    cfg.daily_target_money = 1000.0
    return PradoTradingService(cfg, config_path=cfg_path)


def test_ctrader_client_get_deals_history_parses_net_pnl_and_ignores_opening_deals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = CTraderClient(
        client_id="cid",
        client_secret="csec",
        access_token="tok",
        account_id="10142159",
        is_live=False,
    )
    client._selected_account_id = 10142159
    client._symbol_details_cache[1] = (time.time(), {"symbolName": "EURUSD", "lotSize": 10_000_000, "digits": 5})
    client._symbols_by_id[1] = {"name": "EURUSD", "category": "Forex"}

    now_ms = int(time.time() * 1000)
    calls: list[tuple[int, dict[str, Any]]] = []

    def fake_send_rpc(payload_type: int, payload: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
        calls.append((payload_type, payload))
        assert payload_type == PT_DEAL_LIST_REQ
        return {
            "payloadType": PT_DEAL_LIST_RES,
            "payload": {
                "deal": [
                    # Opening deal without closePositionDetail -> ignored
                    {
                        "dealId": 1001,
                        "positionId": 9001,
                        "symbolId": 1,
                        "tradeSide": 1,
                        "volume": 100_000,
                        "executionPrice": 1.09500,
                        "executionTimestamp": now_ms - 50_000,
                        "dealStatus": 2,
                    },
                    # Closed deal 1 (net = 25.00 - 1.20 - 0.30 = 23.50)
                    {
                        "dealId": 1002,
                        "positionId": 9001,
                        "symbolId": 1,
                        "tradeSide": 2,
                        "volume": 100_000,
                        "executionPrice": 1.09750,
                        "executionTimestamp": now_ms - 10_000,
                        "dealStatus": 2,
                        "label": "BotEuro",
                        "closePositionDetail": {
                            "entryPrice": 1.09500,
                            "closedVolume": 100_000,
                            "grossProfit": 2500,
                            "swap": -30,
                            "commission": -120,
                            "moneyDigits": 2,
                        },
                    },
                    # Closed deal 2 (net = -10.00 - 0.50 = -10.50)
                    {
                        "dealId": 1003,
                        "positionId": 9002,
                        "symbolId": 1,
                        "tradeSide": 1,
                        "volume": 200_000,
                        "executionPrice": 1.09600,
                        "executionTimestamp": now_ms - 2_000,
                        "dealStatus": 2,
                        "closePositionDetail": {
                            "entryPrice": 1.09650,
                            "closedVolume": 200_000,
                            "grossProfit": -1000,
                            "swap": 0,
                            "commission": -50,
                            "moneyDigits": 2,
                        },
                    },
                ]
            },
        }

    monkeypatch.setattr(client, "_send_rpc", fake_send_rpc)
    deals = client.get_deals_history(now_ms - 3_600_000, now_ms, max_rows=200)
    assert len(calls) == 1
    assert len(deals) == 2
    # Ordered newest first
    assert deals[0]["deal_id"] == "1003"
    assert deals[0]["ticket"] == "9002"
    assert deals[0]["profit"] == -10.50
    assert deals[0]["gross_profit"] == -10.00
    assert deals[0]["commission"] == -0.50
    assert deals[0]["official"] is True
    assert deals[1]["deal_id"] == "1002"
    assert deals[1]["profit"] == 23.50
    assert deals[1]["gross_profit"] == 25.00
    assert deals[1]["swap"] == -0.30
    assert deals[1]["commission"] == -1.20
    assert deals[1]["date_str"] == datetime.fromtimestamp((now_ms - 10_000) / 1000.0).strftime("%Y-%m-%d")


def test_authorize_retries_asset_list_for_official_currency(monkeypatch: pytest.MonkeyPatch) -> None:
    client = CTraderClient(
        client_id="cid",
        client_secret="csec",
        access_token="tok",
        account_id="10142159",
        is_live=False,
    )
    asset_attempts = 0

    def fake_send_rpc(payload_type: int, payload: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
        nonlocal asset_attempts
        if payload_type == PT_APPLICATION_AUTH_REQ:
            return {"payloadType": PT_APPLICATION_AUTH_RES, "payload": {}}
        if payload_type == PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ:
            return {
                "payloadType": PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
                "payload": {
                    "ctidTraderAccount": [
                        {"ctidTraderAccountId": 10142159, "isLive": False, "brokerName": "Raw Trading Ltd"}
                    ]
                },
            }
        if payload_type == PT_ACCOUNT_AUTH_REQ:
            return {"payloadType": PT_ACCOUNT_AUTH_RES, "payload": {}}
        if payload_type == PT_TRADER_REQ:
            return {
                "payloadType": PT_TRADER_RES,
                "payload": {
                    "trader": {
                        "balance": 1000000,
                        "moneyDigits": 2,
                        "depositAssetId": 42,
                        "leverageInCents": 50000,
                        "brokerName": "Raw Trading Ltd",
                        "traderLogin": 10142159,
                    }
                },
            }
        if payload_type == PT_ASSET_LIST_REQ:
            asset_attempts += 1
            if asset_attempts == 1:
                raise RuntimeError("transient timeout")
            return {
                "payloadType": PT_ASSET_LIST_RES,
                "payload": {"asset": [{"assetId": 42, "name": "eur", "displayName": "EUR"}]},
            }
        raise AssertionError(f"Unexpected payloadType: {payload_type}")

    monkeypatch.setattr(
        client,
        "list_accounts",
        lambda: [{"account_id": "ct_10142159", "ctid_account_id": "10142159", "is_live": False, "broker_name": "Raw Trading Ltd"}],
    )
    client._ws = object()
    monkeypatch.setattr(client, "_send_rpc", fake_send_rpc)
    auth = client.authorize()
    assert asset_attempts == 2
    assert auth["currency"] == "EUR"


def test_official_deal_overwrites_local_estimated_profit(tmp_path: Path) -> None:
    svc = _make_live_service(tmp_path)
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_msc = int(time.time() * 1000)

    # Local estimated close (before official execution event / deal list arrives)
    inserted = svc.connector._record_live_deal(
        ticket="55501",
        symbol="EURUSD",
        side="BUY",
        volume=0.10,
        price_open=1.09000,
        price_close=1.09100,
        profit=10.0,
        reason="MANUAL_PANIC_FLATTEN",
        bot_name="BotAlpha",
        official=False,
    )
    assert inserted is True
    assert len(svc.connector._live_deals_history) == 1

    class _FakeClient:
        def authorize(self) -> dict[str, Any]:
            return {"loginid": "10142159", "currency": "EUR", "balance": 10200.0, "is_virtual": 1}

        def get_balance(self) -> float:
            return 10200.0

        def get_open_positions(self) -> list[dict[str, Any]]:
            return []

        def pop_closed_deals(self) -> list[dict[str, Any]]:
            return [
                {
                    "ticket": "55501",
                    "deal_id": "d_55501",
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "volume": 0.10,
                    "price_open": 1.09000,
                    "price_close": 1.09100,
                    "profit": 8.45,
                    "gross_profit": 10.00,
                    "swap": -0.35,
                    "commission": -1.20,
                    "time_msc": now_msc,
                    "time_str": datetime.now().strftime("%H:%M:%S"),
                    "date_str": today_str,
                    "reason": "CTRADER_EXECUTION_CLOSE",
                    "bot_name": "cTrader",
                    "official": True,
                }
            ]

    svc.connector._client = _FakeClient()  # type: ignore[assignment]
    svc.connector._client_auth = svc.connector._client.authorize()  # type: ignore[union-attr]
    recorded = svc.connector.sync_closed_deals()
    assert len(recorded) == 1
    assert len(svc.connector._live_deals_history) == 1
    row = svc.connector._live_deals_history[0]
    assert row["profit"] == 8.45
    assert row["gross_profit"] == 10.00
    assert row["commission"] == -1.20
    assert row["swap"] == -0.35
    assert row["official"] is True
    assert row["bot_name"] == "BotAlpha"


def test_daily_realized_filters_only_today_caches_30s_and_clears_on_disconnect(tmp_path: Path) -> None:
    svc = _make_live_service(tmp_path)
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    now_msc = int(time.time() * 1000)

    class _FakeServerClient:
        def __init__(self) -> None:
            self.deal_list_calls = 0
            self.closed_queue: list[dict[str, Any]] = []

        def authorize(self) -> dict[str, Any]:
            return {
                "loginid": "10142159",
                "currency": "USD",
                "balance": 10299.90,
                "is_virtual": 1,
                "broker_name": "Raw Trading Ltd Demo",
            }

        def get_balance(self) -> float:
            return 10299.90

        def get_open_positions(self) -> list[dict[str, Any]]:
            return [{"ticket": "open1", "symbol": "EURUSD", "profit": 4.25}]

        def pop_closed_deals(self) -> list[dict[str, Any]]:
            items = list(self.closed_queue)
            self.closed_queue.clear()
            return items

        def get_deals_history(self, from_ms: int, to_ms: int, max_rows: int = 500) -> list[dict[str, Any]]:
            self.deal_list_calls += 1
            return [
                # Deal de ontem -> deve ser ignorado em daily_realized
                {
                    "ticket": "old1",
                    "deal_id": "d_old1",
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "volume": 0.1,
                    "price_open": 1.09,
                    "price_close": 1.08,
                    "profit": -100.00,
                    "gross_profit": -100.00,
                    "swap": 0.0,
                    "commission": 0.0,
                    "time_msc": now_msc - 90_000_000,
                    "time_str": "23:10:00",
                    "date_str": yesterday,
                    "reason": "CTRADER_SERVER_DEAL",
                    "bot_name": "cTrader",
                    "official": True,
                },
                # 2 deals de hoje (-16.58 líquido = -15.00 + -1.58)
                {
                    "ticket": "t1",
                    "deal_id": "d_t1",
                    "symbol": "EURUSD",
                    "side": "SELL",
                    "volume": 0.05,
                    "price_open": 1.095,
                    "price_close": 1.098,
                    "profit": -20.58,
                    "gross_profit": -19.50,
                    "swap": -0.28,
                    "commission": -0.80,
                    "time_msc": now_msc - 300_000,
                    "time_str": "08:55:00",
                    "date_str": today,
                    "reason": "CTRADER_SERVER_DEAL",
                    "bot_name": "cTrader",
                    "official": True,
                },
                {
                    "ticket": "t2",
                    "deal_id": "d_t2",
                    "symbol": "GBPUSD",
                    "side": "BUY",
                    "volume": 0.02,
                    "price_open": 1.270,
                    "price_close": 1.272,
                    "profit": 4.00,
                    "gross_profit": 4.50,
                    "swap": 0.0,
                    "commission": -0.50,
                    "time_msc": now_msc - 60_000,
                    "time_str": "09:05:00",
                    "date_str": today,
                    "reason": "CTRADER_SERVER_DEAL",
                    "bot_name": "cTrader",
                    "official": True,
                },
            ]

        def close(self) -> None:
            return None

    fake = _FakeServerClient()
    svc.connector._client = fake  # type: ignore[assignment]
    svc.connector._client_auth = fake.authorize()

    summary1 = svc.connector.get_account_summary()
    assert fake.deal_list_calls == 1
    assert summary1["daily_realized"] == -16.58
    assert summary1["daily_gross"] == -15.00
    assert summary1["daily_commissions_swap"] == -1.58
    assert summary1["daily_trades_count"] == 2
    assert summary1["daily_win_rate"] == 50.0
    assert summary1["daily_source"] == "CTRADER_SERVER"
    assert summary1["max_daily_loss_money"] == 500.0
    assert summary1["daily_target_money"] == 1000.0

    # Second call within 30s must hit cache
    summary2 = svc.connector.get_account_summary()
    assert fake.deal_list_calls == 1
    assert summary2["daily_realized"] == -16.58

    # Closing a trade clears daily cache so next summary stays in sync
    fake.closed_queue.append(
        {
            "ticket": "t3",
            "deal_id": "d_t3",
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": 0.01,
            "price_open": 2650.0,
            "price_close": 2660.0,
            "profit": 10.00,
            "gross_profit": 10.50,
            "swap": 0.0,
            "commission": -0.50,
            "time_msc": now_msc,
            "time_str": "09:10:00",
            "date_str": today,
            "reason": "CTRADER_EXECUTION_CLOSE",
            "bot_name": "cTrader",
            "official": True,
        }
    )
    svc.connector.sync_closed_deals()
    assert svc.connector._daily_deals_cache_ts == 0.0

    # Disconnect must clear live deals so accounts never leak into each other
    svc.connector.disconnect()
    assert svc.connector._live_deals_history == []
    assert svc.connector._recorded_deal_tickets == set()
    assert svc.connector._daily_deals_from_server is False


def test_simulation_account_summary_daily_fields(tmp_path: Path) -> None:
    cfg_path = tmp_path / "sim_cfg.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    svc = PradoTradingService(cfg, config_path=cfg_path)

    svc.connector._sim_daily_pnl = 45.20
    s_empty = svc.connector.get_account_summary()
    assert s_empty["daily_source"] == "SIMULATION"
    assert s_empty["daily_realized"] == 45.20
    assert s_empty["daily_trades_count"] == 0

    svc.connector._sim_deals_history.append(
        {
            "ticket": "sim_1",
            "symbol": "EURUSD",
            "profit": 25.0,
            "date_str": datetime.now().strftime("%Y-%m-%d"),
            "time_msc": int(time.time() * 1000),
        }
    )
    svc.connector._sim_deals_history.append(
        {
            "ticket": "sim_2",
            "symbol": "EURUSD",
            "profit": -5.0,
            "date_str": datetime.now().strftime("%Y-%m-%d"),
            "time_msc": int(time.time() * 1000),
        }
    )
    s_with_deals = svc.connector.get_account_summary()
    assert s_with_deals["daily_trades_count"] == 2
    assert s_with_deals["daily_win_rate"] == 50.0
    assert s_with_deals["daily_realized"] == 45.20
