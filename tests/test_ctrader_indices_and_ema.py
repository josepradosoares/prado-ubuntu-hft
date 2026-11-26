from __future__ import annotations

import pytest

from prado_linux.config import migrate_legacy_symbol
from prado_linux.ctrader_client import (
    CTraderClient,
    PT_ACCOUNT_AUTH_REQ,
    PT_ACCOUNT_AUTH_RES,
    PT_APPLICATION_AUTH_REQ,
    PT_APPLICATION_AUTH_RES,
    PT_ASSET_LIST_REQ,
    PT_ASSET_LIST_RES,
    PT_EXECUTION_EVENT,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
    PT_GET_TICKDATA_REQ,
    PT_GET_TICKDATA_RES,
    PT_NEW_ORDER_REQ,
    PT_SPOT_EVENT,
    PT_SYMBOL_BY_ID_REQ,
    PT_SYMBOL_BY_ID_RES,
    PT_SYMBOLS_LIST_REQ,
    PT_SYMBOLS_LIST_RES,
    PT_TRADER_REQ,
    PT_TRADER_RES,
)
from prado_linux.flow_math import TickRecord
from prado_linux.indicators import evaluate_single_indicator


def _ticks_from_prices(prices: list[float]) -> list[TickRecord]:
    return [
        TickRecord(
            time_msc=1_700_000_000_000 + i * 1000,
            bid=p - 0.0001,
            ask=p + 0.0001,
            last=p,
            volume_real=0.0,
            tick_volume=10.0,
        )
        for i, p in enumerate(prices)
    ]


def _make_alias_client(broker_symbols: list[dict], captured: dict | None = None) -> CTraderClient:
    cap = captured if captured is not None else {}
    cap.setdefault("tick_reqs", [])
    cap.setdefault("orders", [])

    def fake_rpc(env: dict) -> dict:
        pt = env["payloadType"]
        cid = env["clientMsgId"]
        p = env["payload"]
        if pt == PT_APPLICATION_AUTH_REQ:
            return {"clientMsgId": cid, "payloadType": PT_APPLICATION_AUTH_RES, "payload": {}}
        if pt == PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
                "payload": {"ctidTraderAccount": [{"ctidTraderAccountId": 101, "isLive": False, "traderLogin": 101}]},
            }
        if pt == PT_ACCOUNT_AUTH_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ACCOUNT_AUTH_RES, "payload": {}}
        if pt == PT_TRADER_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_TRADER_RES,
                "payload": {"trader": {"ctidTraderAccountId": 101, "balance": 1000000, "moneyDigits": 2, "depositAssetId": 1}},
            }
        if pt == PT_ASSET_LIST_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ASSET_LIST_RES, "payload": {"asset": [{"assetId": 1, "name": "USD"}]}}
        if pt == PT_SYMBOLS_LIST_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SYMBOLS_LIST_RES, "payload": {"symbol": broker_symbols}}
        if pt == PT_SYMBOL_BY_ID_REQ:
            sid = int((p.get("symbolId") or [1])[0])
            return {
                "clientMsgId": cid,
                "payloadType": PT_SYMBOL_BY_ID_RES,
                "payload": {
                    "symbol": [
                        {
                            "symbolId": sid,
                            "digits": 2,
                            "pipPosition": 1,
                            "lotSize": 100,
                            "minVolume": 1,
                            "stepVolume": 1,
                            "distanceSetIn": 1,
                            "slDistance": 500,
                            "tpDistance": 500,
                        }
                    ]
                },
            }
        if pt == PT_GET_TICKDATA_REQ:
            cap["tick_reqs"].append(dict(p))
            span = int(p["toTimestamp"]) - int(p["fromTimestamp"])
            if span <= 3600 * 1000 + 1000:
                return {"clientMsgId": cid, "payloadType": PT_GET_TICKDATA_RES, "payload": {"tickData": []}}
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_TICKDATA_RES,
                "payload": {
                    "tickData": [
                        {"timestamp": 1700000002000, "tick": 2085000000},
                        {"timestamp": -1000, "tick": -100000},
                    ]
                },
            }
        if pt == PT_NEW_ORDER_REQ:
            cap["orders"].append(dict(p))
            return {
                "clientMsgId": cid,
                "payloadType": PT_EXECUTION_EVENT,
                "payload": {"executionType": 3, "position": {"positionId": 555, "positionStatus": 1}},
            }
        return {"clientMsgId": cid, "payloadType": 0, "payload": {}}

    client = CTraderClient("cid", "csec", "tok", rpc_transport=fake_rpc)
    client.authorize()
    return client


def test_ctrader_resolves_us100_and_index_aliases_and_spot_stream() -> None:
    broker_syms = [
        {"symbolId": 10, "symbolName": "USTEC", "enabled": True},
        {"symbolId": 11, "symbolName": "US500.cash", "enabled": True},
        {"symbolId": 12, "symbolName": "DJ30", "enabled": True},
        {"symbolId": 13, "symbolName": "GER40", "enabled": True},
    ]
    client = _make_alias_client(broker_syms)

    assert client._resolve_symbol_id("US100") == 10
    assert client._resolve_symbol_id("US500") == 11
    assert client._resolve_symbol_id("US30") == 12
    assert client._resolve_symbol_id("DE40") == 13

    # Spot event arrives for symbolId 10 (USTEC) -> get_live_ticks("US100") must see it!
    client._ingest_async_event(
        {
            "payloadType": PT_SPOT_EVENT,
            "payload": {"symbolId": 10, "bid": 2085000000, "ask": 2085020000, "timestamp": 1700000005000},
        }
    )
    live = client.get_live_ticks("US100")
    assert len(live) == 1
    assert live[0].bid == 20850.0


def test_us100_sl_distance_clamp_and_24h_tick_history_retry() -> None:
    captured: dict = {}
    client = _make_alias_client([{"symbolId": 10, "symbolName": "NAS100", "enabled": True}], captured=captured)

    # First 1h tick window returns empty -> should automatically retry with 24h lookback
    ticks = client.get_ticks_history("US100", count=10)
    assert len(captured["tick_reqs"]) == 2
    assert len(ticks) == 2
    assert ticks[-1].last == 20850.0

    # slDistance=500 with digits=2 => min 5.0 price points => relativeStopLoss >= 500_000
    ok, _ = client.place_market_order("US100", is_buy=True, lots=0.05, sl_points=0.5, tp_points=1.0)
    assert ok is True
    sent = captured["orders"][0]
    assert sent["symbolId"] == 10
    assert sent["relativeStopLoss"] >= 500_000
    assert sent["relativeTakeProfit"] >= 500_000


def test_migrate_legacy_us100_symbol() -> None:
    assert migrate_legacy_symbol("US100Cash#") == "US100"


def test_moving_averages_position_vs_crossover_only() -> None:
    # Continuous uptrend: EMA9 stays above EMA21 on both previous and current bar
    steady_up = _ticks_from_prices([100.0 + i * 0.5 for i in range(40)])
    assert evaluate_single_indicator("EMA", steady_up, {"fast": 5, "slow": 12, "crossover_only": 0})[0] == 1
    assert evaluate_single_indicator("EMA", steady_up, {"fast": 5, "slow": 12, "crossover_only": 1})[0] == 0

    # Bullish EMA crossover on last tick: downtrend then sharp jump on final tick
    bull_cross_prices = [200.0 - i * 1.0 for i in range(30)] + [230.0]
    bull_cross = _ticks_from_prices(bull_cross_prices)
    assert evaluate_single_indicator("EMA", bull_cross, {"fast": 5, "slow": 12, "crossover_only": 1})[0] == 1

    # Bearish EMA crossover on last tick: uptrend then sharp drop on final tick
    bear_cross_prices = [100.0 + i * 1.0 for i in range(30)] + [70.0]
    bear_cross = _ticks_from_prices(bear_cross_prices)
    assert evaluate_single_indicator("EMA", bear_cross, {"fast": 5, "slow": 12, "crossover_only": 1})[0] == -1

    # SMA, WMA, DEMA crossover_only=1: steady uptrend returns 0; sharp drop across MA returns -1
    for ma in ("SMA", "WMA", "DEMA"):
        assert evaluate_single_indicator(ma, steady_up, {"period": 10, "crossover_only": 1})[0] == 0
        assert evaluate_single_indicator(ma, bear_cross, {"period": 10, "crossover_only": 1})[0] == -1
        assert evaluate_single_indicator(ma, bull_cross, {"period": 10, "crossover_only": 1})[0] == 1


def test_sync_and_select_account_persist_live_balance(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from prado_linux.config import load_config
    from prado_linux.engine import PradoTradingService

    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "CTRADER_CLOUD"
    cfg.ctrader_client_id = "cid"
    cfg.ctrader_client_secret = "csec"
    cfg.ctrader_access_token = "tok"
    svc = PradoTradingService(cfg, config_path=cfg_path)

    class _FakeSyncClient:
        def list_accounts(self):
            return [
                {"ctid_account_id": "101", "account_type": "DEMO", "is_live": False, "broker_name": "ICMarkets", "trader_login": "5001"},
                {"ctid_account_id": "202", "account_type": "REAL", "is_live": True, "broker_name": "ICMarkets", "trader_login": "9002"},
            ]

    svc.connector._client = _FakeSyncClient()  # type: ignore[assignment]
    svc.connector._client_auth = {"ctid_account_id": "101", "balance": 12345.67, "currency": "EUR"}
    ok, _msg, accounts = svc.sync_ctrader_accounts()
    assert ok is True
    demo_acc = next(a for a in accounts if a["ctid_account_id"] == "101")
    assert demo_acc["balance"] == 12345.67
    assert demo_acc["currency"] == "EUR"

    def _fake_connect(**kwargs):
        svc.connector._client_auth = {
            "ctid_account_id": "202",
            "loginid": "9002",
            "broker_name": "ICMarkets",
            "balance": 888.50,
            "currency": "USD",
            "is_virtual": 0,
        }
        return True, "Conectado"

    monkeypatch.setattr(svc.connector, "connect", _fake_connect)
    selected = svc.select_active_account("ct_202")
    assert selected is not None
    assert selected["balance"] == 888.50
    assert selected["currency"] == "USD"
    reloaded = load_config(cfg_path)
    real_acc = next(a for a in reloaded.accounts if a["account_id"] == "ct_202")
    assert real_acc["balance"] == 888.50
