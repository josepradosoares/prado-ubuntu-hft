"""Comprehensive tests for cTrader Open API client, OAuth2, execution, risk, Grid, News, Indicators, and Supabase."""
from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from prado_linux.auth import create_session_token
from prado_linux.config import PradoServerConfig, load_config
from prado_linux.ctrader_client import (
    CTRADER_DEMO_WS_URL,
    CTRADER_LIVE_WS_URL,
    CTraderAuthError,
    CTraderClient,
    CTraderRateLimiter,
    CTraderRateLimitError,
    PT_ACCOUNT_AUTH_REQ,
    PT_ACCOUNT_AUTH_RES,
    PT_APPLICATION_AUTH_REQ,
    PT_APPLICATION_AUTH_RES,
    PT_ASSET_LIST_REQ,
    PT_ASSET_LIST_RES,
    PT_CLOSE_POSITION_REQ,
    PT_EXECUTION_EVENT,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
    PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
    PT_GET_POSITION_UNREALIZED_PNL_REQ,
    PT_GET_POSITION_UNREALIZED_PNL_RES,
    PT_GET_TICKDATA_REQ,
    PT_GET_TICKDATA_RES,
    PT_GET_TRENDBARS_REQ,
    PT_GET_TRENDBARS_RES,
    PT_NEW_ORDER_REQ,
    PT_OA_ERROR_RES,
    PT_RECONCILE_REQ,
    PT_RECONCILE_RES,
    PT_SPOT_EVENT,
    PT_SUBSCRIBE_SPOTS_REQ,
    PT_SUBSCRIBE_SPOTS_RES,
    PT_SYMBOL_BY_ID_REQ,
    PT_SYMBOL_BY_ID_RES,
    PT_SYMBOLS_LIST_REQ,
    PT_SYMBOLS_LIST_RES,
    PT_TRADER_REQ,
    PT_TRADER_RES,
    build_oauth_authorize_url,
    decode_price,
    encode_relative_distance,
    exchange_oauth_code,
    lots_to_protocol_volume,
    protocol_volume_to_lots,
    refresh_oauth_token,
    scale_money,
)
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord
from prado_linux.indicators import INDICATOR_CATALOG
from prado_linux.web_app import PradoWebApp


def test_ctrader_conversions_scales_and_oauth_helpers() -> None:
    assert scale_money(10053099944, 8) == 100.53
    assert scale_money(25050, 2) == 250.50
    assert decode_price(108543, 5) == 1.08543
    assert encode_relative_distance(0.0025) == 250

    meta = {"lotSize": 10_000_000, "minVolume": 100_000, "maxVolume": 500_000_000, "stepVolume": 100_000}
    assert lots_to_protocol_volume(0.01, meta) == 100_000
    assert lots_to_protocol_volume(0.25, meta) == 2_500_000
    assert protocol_volume_to_lots(2_500_000, meta) == 0.25

    url = build_oauth_authorize_url("cid_123", "http://localhost:8080/api/ctrader/oauth/callback")
    assert "id.ctrader.com" in url
    assert "client_id=cid_123" in url
    assert "scope=trading" in url

    tok = exchange_oauth_code(
        "cid_123",
        "sec_456",
        "code_abc",
        "http://localhost:8080/api/ctrader/oauth/callback",
        http_transport=lambda u: {"accessToken": "at_1", "refreshToken": "rt_1", "expiresIn": 2592000},
    )
    assert tok["access_token"] == "at_1"
    assert tok["refresh_token"] == "rt_1"

    ref = refresh_oauth_token(
        "cid_123",
        "sec_456",
        "rt_1",
        http_transport=lambda u: {"accessToken": "at_2", "refreshToken": "rt_2", "expiresIn": 2592000},
    )
    assert ref["access_token"] == "at_2"
    assert ref["refresh_token"] == "rt_2"


def test_ctrader_handshake_symbols_tickdata_trendbars_and_orders() -> None:
    seen_envelopes: list[dict] = []

    def fake_rpc(env: dict) -> dict:
        seen_envelopes.append(env)
        pt = env["payloadType"]
        cid = env["clientMsgId"]
        p = env["payload"]
        if pt == PT_APPLICATION_AUTH_REQ:
            return {"clientMsgId": cid, "payloadType": PT_APPLICATION_AUTH_RES, "payload": {}}
        if pt == PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
                "payload": {
                    "permissionScope": "SCOPE_TRADE",
                    "ctidTraderAccount": [
                        {"ctidTraderAccountId": 55001, "isLive": False, "traderLogin": 9001, "brokerTitleShort": "IC Markets"},
                        {"ctidTraderAccountId": 55002, "isLive": True, "traderLogin": 9002, "brokerTitleShort": "IC Markets"},
                    ],
                },
            }
        if pt == PT_ACCOUNT_AUTH_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ACCOUNT_AUTH_RES, "payload": {"ctidTraderAccountId": p["ctidTraderAccountId"]}}
        if pt == PT_TRADER_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_TRADER_RES,
                "payload": {
                    "trader": {
                        "ctidTraderAccountId": p["ctidTraderAccountId"],
                        "balance": 1250000,
                        "moneyDigits": 2,
                        "depositAssetId": 1,
                        "leverageInCents": 50000,
                        "traderLogin": 9001,
                        "brokerName": "IC Markets",
                    }
                },
            }
        if pt == PT_ASSET_LIST_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ASSET_LIST_RES, "payload": {"asset": [{"assetId": 1, "name": "USD"}]}}
        if pt == PT_SYMBOLS_LIST_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_SYMBOLS_LIST_RES,
                "payload": {
                    "symbol": [
                        {"symbolId": 1, "symbolName": "EURUSD", "enabled": True, "description": "EUR vs USD"},
                        {"symbolId": 41, "symbolName": "XAUUSD", "enabled": True, "description": "Gold vs USD"},
                    ]
                },
            }
        if pt == PT_SYMBOL_BY_ID_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_SYMBOL_BY_ID_RES,
                "payload": {
                    "symbol": [
                        {"symbolId": 1, "digits": 5, "pipPosition": 4, "lotSize": 10_000_000, "minVolume": 100_000, "maxVolume": 500_000_000, "stepVolume": 100_000}
                    ]
                },
            }
        if pt == PT_SUBSCRIBE_SPOTS_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SUBSCRIBE_SPOTS_RES, "payload": {}}
        if pt == PT_GET_TICKDATA_REQ:
            # Newest-first cumulative delta encoding
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_TICKDATA_RES,
                "payload": {
                    "hasMore": False,
                    "tickData": [
                        {"timestamp": 1700000003000, "tick": 108530},
                        {"timestamp": -1000, "tick": -10},
                        {"timestamp": -1000, "tick": -20},
                    ],
                },
            }
        if pt == PT_GET_TRENDBARS_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_TRENDBARS_RES,
                "payload": {
                    "trendbar": [
                        {"utcTimestampInMinutes": 28333330, "low": 108400, "deltaOpen": 20, "deltaClose": 100, "deltaHigh": 120, "volume": 45},
                        {"utcTimestampInMinutes": 28333331, "low": 108450, "deltaOpen": 10, "deltaClose": 90, "deltaHigh": 110, "volume": 62},
                    ]
                },
            }
        if pt == PT_NEW_ORDER_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_EXECUTION_EVENT,
                "payload": {
                    "executionType": 3,
                    "order": {"orderId": 8801, "positionId": 7701},
                    "position": {
                        "positionId": 7701,
                        "positionStatus": 1,
                        "price": 1.0853,
                        "tradeData": {"symbolId": 1, "volume": p["volume"], "tradeSide": p["tradeSide"], "label": p.get("label", "")},
                    },
                },
            }
        if pt == PT_RECONCILE_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_RECONCILE_RES,
                "payload": {
                    "position": [
                        {
                            "positionId": 7701,
                            "positionStatus": 1,
                            "price": 1.0853,
                            "stopLoss": 1.0833,
                            "takeProfit": 1.0893,
                            "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1, "label": "BotEUR"},
                        }
                    ]
                },
            }
        if pt == PT_GET_POSITION_UNREALIZED_PNL_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_POSITION_UNREALIZED_PNL_RES,
                "payload": {
                    "moneyDigits": 2,
                    "positionUnrealizedPnL": [{"positionId": 7701, "grossUnrealizedPnL": 1450, "netUnrealizedPnL": 1410}],
                },
            }
        if pt == PT_CLOSE_POSITION_REQ:
            return {"clientMsgId": cid, "payloadType": PT_EXECUTION_EVENT, "payload": {"executionType": 3}}
        return {"clientMsgId": cid, "payloadType": 0, "payload": {}}

    client = CTraderClient(
        client_id="app_cid",
        client_secret="app_sec",
        access_token="tok_demo",
        preferred_account_type="DEMO",
        rpc_transport=fake_rpc,
    )
    assert client.ws_url == CTRADER_DEMO_WS_URL
    auth = client.authorize()
    assert auth["loginid"] == "9001"
    assert auth["ctid_account_id"] == "55001"
    assert auth["balance"] == 12500.0
    assert auth["leverage"] == 500
    assert auth["is_virtual"] == 1

    syms = client.get_active_symbols()
    assert len(syms) == 2

    # Tickdata delta-decoding & chronological reversal (oldest-first)
    ticks = client.get_ticks_history("EURUSD", count=10, granularity=0)
    assert len(ticks) == 3
    assert [t.time_msc for t in ticks] == [1700000001000, 1700000002000, 1700000003000]
    assert [t.last for t in ticks] == [1.085, 1.0852, 1.0853]

    # Trendbars decoding
    bars = client.get_ticks_history("EURUSD", count=10, granularity=60)
    assert len(bars) == 2
    assert bars[0].last == 1.085
    assert bars[1].last == 1.0854
    assert bars[1].tick_volume == 62.0

    # Market order uses relative SL/TP and volume in centicents
    ok, msg = client.place_market_order("EURUSD", is_buy=True, lots=0.01, sl_points=0.0020, tp_points=0.0040, label="BotEUR")
    assert ok is True
    assert "7701" in msg
    order_env = next(e for e in seen_envelopes if e["payloadType"] == PT_NEW_ORDER_REQ)
    assert order_env["payload"]["orderType"] == 1
    assert order_env["payload"]["volume"] == 100_000
    assert order_env["payload"]["relativeStopLoss"] == 200
    assert order_env["payload"]["relativeTakeProfit"] == 400

    # Open positions with unrealized PnL
    positions = client.get_open_positions()
    assert len(positions) == 1
    assert positions[0]["ticket"] == "7701"
    assert positions[0]["volume"] == 0.01
    assert positions[0]["profit"] == 14.10

    closed_ok, _ = client.close_position("7701")
    assert closed_ok is True


def test_place_market_order_does_not_auto_retry_on_timeout() -> None:
    attempts = {"order": 0}

    def fake_rpc(env: dict) -> dict:
        pt = env["payloadType"]
        cid = env["clientMsgId"]
        if pt == PT_SYMBOLS_LIST_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SYMBOLS_LIST_RES, "payload": {"symbol": [{"symbolId": 1, "symbolName": "EURUSD"}]}}
        if pt == PT_SYMBOL_BY_ID_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SYMBOL_BY_ID_RES, "payload": {"symbol": [{"symbolId": 1, "digits": 5, "lotSize": 10_000_000}]}}
        if pt == PT_NEW_ORDER_REQ:
            attempts["order"] += 1
            raise TimeoutError("WS timeout waiting for execution event")
        return {"clientMsgId": cid, "payloadType": 0, "payload": {}}

    client = CTraderClient("cid", "sec", "tok", account_id="55001", rpc_transport=fake_rpc)
    ok, msg = client.place_market_order("EURUSD", is_buy=True, lots=0.01, sl_points=0.002)
    assert ok is False
    assert "reconcilia" in msg.lower()
    assert client.last_order_lifecycle["stage"] == "RECONCILIATION_REQUIRED"
    assert attempts["order"] == 1


def test_ctrader_rate_limiter_enforces_50_rt_and_5_hist_and_retry_after() -> None:
    rl = CTraderRateLimiter()
    t0 = 1000.0
    for _ in range(50):
        rl.acquire("realtime", now=t0)
    with pytest.raises(CTraderRateLimitError):
        rl.acquire("realtime", now=t0)

    for _ in range(5):
        rl.acquire("historical", now=t0)
    with pytest.raises(CTraderRateLimitError):
        rl.acquire("historical", now=t0)

    delay = rl.record_remote_rate_limit("BLOCKED_PAYLOAD_TYPE", retry_after=12.0, group="realtime", now=t0)
    assert delay == 12.0
    assert rl.status(now=t0)["state"] == "BLOCKED"


def test_stream_spot_event_and_execution_event_sync_closed_deals(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "cfg.json")
    cfg.connection_mode = "CTRADER_CLOUD"
    cfg.ctrader_client_id = "cid"
    cfg.ctrader_client_secret = "csec"
    cfg.ctrader_access_token = "tok"
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")

    client = CTraderClient("cid", "csec", "tok", account_id="55001")
    client._symbols_by_id[1] = {"symbolId": 1, "name": "EURUSD"}
    client._symbols_by_name["EURUSD"] = {"symbolId": 1, "symbol_id": 1, "name": "EURUSD"}
    client._symbol_details_cache[1] = (time.time(), {"symbolId": 1, "digits": 5, "lotSize": 10_000_000})

    # Ingest live spot event
    client._ingest_async_event(
        {
            "payloadType": PT_SPOT_EVENT,
            "payload": {"ctidTraderAccountId": 55001, "symbolId": 1, "bid": 108500, "ask": 108520, "timestamp": 1700000010000},
        }
    )
    live_ticks = client.get_live_ticks("EURUSD")
    assert len(live_ticks) == 1
    assert live_ticks[0].bid == 1.085
    assert live_ticks[0].ask == 1.0852

    # Ingest closed position execution event
    client._ingest_async_event(
        {
            "payloadType": PT_EXECUTION_EVENT,
            "payload": {
                "ctidTraderAccountId": 55001,
                "executionType": 3,
                "position": {"positionId": 9901, "positionStatus": 2},
                "deal": {
                    "dealId": 3301,
                    "positionId": 9901,
                    "symbolId": 1,
                    "tradeSide": 1,
                    "filledVolume": 100_000,
                    "executionPrice": 1.0890,
                    "label": "BotEUR",
                    "closePositionDetail": {
                        "entryPrice": 1.0850,
                        "grossProfit": 400,
                        "swap": 0,
                        "commission": -7,
                        "balance": 100393,
                        "closedVolume": 100_000,
                        "moneyDigits": 2,
                    },
                },
            },
        }
    )
    svc.connector._client = client
    svc.connector.connected = True
    svc.connector.auth_state = "AUTHENTICATED"
    recorded = svc.connector.sync_closed_deals()
    assert len(recorded) == 1
    assert recorded[0]["profit"] == 3.93
    assert recorded[0]["symbol"] == "EURUSD"


def test_real_account_trading_blocked_by_default_and_oauth_routes(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    app = PradoWebApp(config_path=cfg_path)
    token = create_session_token(app.cfg.admin_username, app.cfg.secret_key)
    headers = {"Cookie": f"prado_session={token}", "Content-Type": "application/json"}

    # Missing credentials -> /api/ctrader/oauth/start returns 400
    code, body, _ = app.handle_request("GET", "/api/ctrader/oauth/start", headers)
    assert code == 400

    # Save client_id & client_secret
    app.service.cfg.ctrader_client_id = "cid_999"
    app.service.cfg.ctrader_client_secret = "csec_999"
    code, body, _ = app.handle_request("GET", "/api/ctrader/oauth/start", {"Cookie": f"prado_session={token}", "Host": "127.0.0.1:8080"})
    assert code == 200
    d = json.loads(body)
    assert "id.ctrader.com" in d["auth_url"]
    assert "cid_999" in d["auth_url"]

    # Real trading blocked by default
    app.service.cfg.connection_mode = "CTRADER_CLOUD"
    app.service.cfg.allow_real_trading = False
    app.service.connector.connected = True
    app.service.connector.auth_state = "AUTHENTICATED"
    app.service.connector.connection_state = "CONNECTED"
    app.service.connector.last_tick_at = time.time()
    app.service.connector._client = CTraderClient("cid_999", "csec_999", "tok", is_live=True)
    app.service.connector._client_auth = {"is_virtual": 0, "is_live": True}
    assert app.service.connector._client.ws_url == CTRADER_LIVE_WS_URL
    ok, msg = app.service.connector.place_order("EURUSD", "BUY_FLOW", 0.01, 1.085, 0.002, 0.004)
    assert ok is False
    assert "bloqueada" in msg.lower()


def test_grid_linear_news_scout_indicators_and_supabase_isolation(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "cfg.json")
    cfg.connection_mode = "SIMULATION"
    cfg.min_order_interval_sec = 0.0
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")

    assert len(INDICATOR_CATALOG) == 21
    bot = svc.create_bot(
        {
            "name": "Grid EURUSD",
            "symbol": "EURUSD",
            "template_id": "GRID_LINEAR_HFT",
            "lot_size": 0.02,
            "grid_direction": "BUY_ONLY",
            "grid_step_points": 0.001,
            "grid_tp_points": 0.001,
            "max_grid_levels": 3,
            "auto_start": True,
        }
    )
    snap = svc.step_once()
    assert len(snap["positions"]) >= 1
    assert snap["positions"][0]["volume"] == 0.02

    # News Scout maps to cTrader symbols
    svc.news_scout._fetcher = lambda _u: (
        "<rss><channel><item><title>Bitcoin surges to record high after ETF approval</title>"
        "<link>https://example.com/btc</link></item></channel></rss>"
    )
    news_res = svc.scan_news(force=True)
    assert news_res["items"][0]["symbol"] == "BTCUSD"
    assert news_res["items"][0]["bias"] == "BULLISH"

    # Multi-user Supabase service isolation
    class _FakeSb:
        is_enabled = True

        def sign_in(self, email: str, pwd: str):
            return True, {"user_id": f"uid_{email}", "email": email, "access_token": f"tok_{email}"}

        def load_user_config(self, uid: str, tok: str, path: Path) -> PradoServerConfig:
            return PradoServerConfig(connection_mode="SIMULATION", active_symbols=["EURUSD"])

        def sync_user_config(self, uid: str, tok: str, cfg_obj: PradoServerConfig) -> None:
            return None

    app = PradoWebApp(config_path=tmp_path / "app_cfg.json", supabase_store=_FakeSb())  # type: ignore[arg-type]
    try:
        c1, _, h1 = app.handle_request("POST", "/api/login", {"Content-Type": "application/json"}, json.dumps({"email": "u1@test.com", "password": "123"}).encode())
        c2, _, h2 = app.handle_request("POST", "/api/login", {"Content-Type": "application/json"}, json.dumps({"email": "u2@test.com", "password": "123"}).encode())
        assert c1 == 200 and c2 == 200
        app.handle_request("POST", "/api/bots", {"Cookie": h1["Set-Cookie"], "Content-Type": "application/json"}, json.dumps({"name": "Bot U1", "symbol": "EURUSD"}).encode())
        _, st2, _ = app.handle_request("GET", "/api/status", {"Cookie": h2["Set-Cookie"]}, b"")
        assert json.loads(st2)["bots"] == []
    finally:
        for usvc in app._user_services.values():
            usvc.stop_background_loop()
