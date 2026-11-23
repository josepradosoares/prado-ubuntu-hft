import json
from pathlib import Path

from prado_linux.auth import create_session_token, verify_password, verify_session_token
from prado_linux.config import PradoServerConfig, load_config, save_config
from prado_linux.ctrader_client import (
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
    PT_NEW_ORDER_REQ,
    PT_RECONCILE_REQ,
    PT_RECONCILE_RES,
    PT_SUBSCRIBE_SPOTS_REQ,
    PT_SUBSCRIBE_SPOTS_RES,
    PT_SYMBOL_BY_ID_REQ,
    PT_SYMBOL_BY_ID_RES,
    PT_SYMBOLS_LIST_REQ,
    PT_SYMBOLS_LIST_RES,
    PT_TRADER_REQ,
    PT_TRADER_RES,
)
from prado_linux.engine import CTraderUniversalConnector, PradoTradingService
from prado_linux.flow_math import TickRecord


def test_default_config_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg = load_config(cfg_file)
    assert cfg.admin_username == "admin"
    assert cfg.zscore_threshold == 1.8
    assert cfg.imbalance_threshold == 0.35
    assert cfg.operation_mode == "BOTH"
    assert cfg.connection_mode == "CTRADER_CLOUD"
    assert cfg.default_lot_size == 0.01
    assert cfg.ctrader_access_token == ""

    cfg.ctrader_client_id = "cid_100"
    cfg.ctrader_access_token = "tok_test_123"
    cfg.active_symbols = ["EURUSD", "XAUUSD", "BTCUSD"]
    cfg.correlated_basket = ["EURUSD", "GBPUSD"]
    save_config(cfg, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded.ctrader_client_id == "cid_100"
    assert reloaded.ctrader_access_token == "tok_test_123"
    assert reloaded.active_symbols == ["EURUSD", "XAUUSD", "BTCUSD"]
    assert reloaded.correlated_basket == ["EURUSD", "GBPUSD"]

    # Legacy symbol auto-migration
    raw = json.loads(cfg_file.read_text(encoding="utf-8"))
    raw["connection_mode"] = "DERIV_CLOUD"
    raw["active_symbols"] = ["R_100", "frxEURUSD"]
    raw["bots"] = [{"bot_id": "b1", "symbol": "cryBTCUSD"}]
    cfg_file.write_text(json.dumps(raw), encoding="utf-8")
    cleaned = load_config(cfg_file)
    assert cleaned.connection_mode == "CTRADER_CLOUD"
    assert cleaned.active_symbols == ["EURUSD"]
    assert cleaned.bots[0]["symbol"] == "BTCUSD"


def test_auth_password_and_session_tokens(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    assert verify_password("prado2026", cfg.admin_password_hash) is True
    assert verify_password("wrong", cfg.admin_password_hash) is False

    token = create_session_token("admin", cfg.secret_key)
    assert verify_session_token(token, cfg.secret_key) == "admin"
    assert verify_session_token(token + "tampered", cfg.secret_key) is None


def test_trading_service_snapshot_and_vwap_flow_cycle(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    cfg.connection_mode = "SIMULATION"
    cfg.active_symbols = ["EURUSD", "BTCUSD"]
    cfg.correlated_basket = ["EURUSD", "GBPUSD"]
    service = PradoTradingService(cfg, config_path=tmp_path / "config.json")

    snap = service.step_once()
    assert "account" in snap
    assert "symbols" in snap
    assert "EURUSD" in snap["symbols"]
    assert "BTCUSD" in snap["symbols"]

    eur_state = snap["symbols"]["EURUSD"]
    assert eur_state["vwap"] > 0
    assert eur_state["upper_2"] > eur_state["vwap"] > eur_state["lower_2"]
    assert eur_state["regime"] in (
        "NEUTRAL",
        "INSTITUTIONAL_TREND_UP",
        "INSTITUTIONAL_TREND_DOWN",
        "HFT_MEAN_REVERSION",
    )


def test_ctrader_client_websocket_rpc_and_orders(tmp_path: Path):
    from prado_linux.ctrader_client import CTraderClient

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
                "payload": {
                    "ctidTraderAccount": [
                        {"ctidTraderAccountId": 998877, "isLive": False, "traderLogin": 998877, "brokerTitleShort": "DemoBroker"}
                    ]
                },
            }
        if pt == PT_ACCOUNT_AUTH_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ACCOUNT_AUTH_RES, "payload": {}}
        if pt == PT_TRADER_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_TRADER_RES,
                "payload": {"trader": {"ctidTraderAccountId": 998877, "balance": 1000000, "moneyDigits": 2, "depositAssetId": 1, "traderLogin": 998877, "brokerName": "DemoBroker"}},
            }
        if pt == PT_ASSET_LIST_REQ:
            return {"clientMsgId": cid, "payloadType": PT_ASSET_LIST_RES, "payload": {"asset": [{"assetId": 1, "name": "USD"}]}}
        if pt == PT_SYMBOLS_LIST_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_SYMBOLS_LIST_RES,
                "payload": {
                    "symbol": [
                        {"symbolId": 1, "symbolName": "EURUSD", "enabled": True},
                        {"symbolId": 2, "symbolName": "BTCUSD", "enabled": True},
                    ]
                },
            }
        if pt == PT_SYMBOL_BY_ID_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SYMBOL_BY_ID_RES, "payload": {"symbol": [{"symbolId": 1, "digits": 5, "lotSize": 10_000_000}]}}
        if pt == PT_SUBSCRIBE_SPOTS_REQ:
            return {"clientMsgId": cid, "payloadType": PT_SUBSCRIBE_SPOTS_RES, "payload": {}}
        if pt == PT_GET_TICKDATA_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_TICKDATA_RES,
                "payload": {
                    "hasMore": False,
                    "tickData": [
                        {"timestamp": 1700000005000, "tick": 108540},
                        {"timestamp": -1000, "tick": -10},
                        {"timestamp": -1000, "tick": -10},
                    ],
                },
            }
        if pt == PT_NEW_ORDER_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_EXECUTION_EVENT,
                "payload": {"executionType": 3, "position": {"positionId": 778899, "positionStatus": 1, "tradeData": {"symbolId": 1, "volume": p["volume"], "tradeSide": 1}}},
            }
        if pt == PT_RECONCILE_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_RECONCILE_RES,
                "payload": {
                    "position": [
                        {"positionId": 778899, "positionStatus": 1, "price": 1.085, "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1}}
                    ]
                },
            }
        if pt == PT_GET_POSITION_UNREALIZED_PNL_REQ:
            return {
                "clientMsgId": cid,
                "payloadType": PT_GET_POSITION_UNREALIZED_PNL_RES,
                "payload": {"moneyDigits": 2, "positionUnrealizedPnL": [{"positionId": 778899, "netUnrealizedPnL": 450}]},
            }
        if pt == PT_CLOSE_POSITION_REQ:
            return {"clientMsgId": cid, "payloadType": PT_EXECUTION_EVENT, "payload": {"executionType": 3}}
        return {"clientMsgId": cid, "payloadType": 0, "payload": {}}

    client = CTraderClient("cid", "csec", "tok", rpc_transport=fake_rpc)
    auth = client.authorize()
    assert auth["loginid"] == "998877"
    assert auth["balance"] == 10000.0
    assert auth["is_virtual"] == 1

    syms = client.get_active_symbols()
    assert len(syms) == 2

    ticks = client.get_ticks_history("EURUSD", count=5)
    assert len(ticks) == 3
    assert ticks[-1].last == 1.0854

    ok, msg = client.place_market_order("EURUSD", is_buy=True, lots=0.01, sl_points=0.0020, tp_points=0.0040)
    assert ok is True
    assert "778899" in msg

    positions = client.get_open_positions()
    assert len(positions) == 1
    assert positions[0]["profit"] == 4.5

    closed_ok, _ = client.close_position("778899")
    assert closed_ok is True


def test_ctrader_cloud_disconnected_shows_zero_balance_never_fake_sim(tmp_path: Path):
    cfg = load_config(tmp_path / "config.json")
    cfg.connection_mode = "CTRADER_CLOUD"
    cfg.ctrader_access_token = ""
    service = PradoTradingService(cfg, config_path=tmp_path / "config.json")

    snap = service.step_once()
    assert snap["account"]["balance"] == 0.0
    assert snap["account"]["equity"] == 0.0
    assert snap["account"]["backend"] == "CTRADER_DISCONNECTED"
    assert snap["account"]["login"] == "DESCONECTADO"


def test_web_app_ctrader_vault_bots_categories_and_backtester(tmp_path: Path):
    from prado_linux.web_app import PradoWebApp

    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path)
    app.cfg.connection_mode = "SIMULATION"

    code, _, _ = app.handle_request("GET", "/api/status", headers={}, body=b"")
    assert code == 401

    login_payload = json.dumps({"username": "admin", "password": "prado2026"}).encode("utf-8")
    code, body, resp_headers = app.handle_request(
        "POST", "/api/login", headers={"Content-Type": "application/json"}, body=login_payload
    )
    assert code == 200
    auth_headers = {"Cookie": resp_headers["Set-Cookie"], "Content-Type": "application/json"}

    demo_acc = json.dumps(
        {
            "account_id": "ct_demo_1",
            "account_type": "DEMO",
            "label": "Minha cTrader Demo",
            "access_token": "secret_demo_token",
            "default_lot_size": 0.02,
        }
    ).encode("utf-8")
    code, body, _ = app.handle_request("POST", "/api/accounts", headers=auth_headers, body=demo_acc)
    assert code == 200
    resp_demo = json.loads(body)
    assert resp_demo["ok"] is True
    assert resp_demo["account"]["access_token"] == "********"
    assert resp_demo["account"]["account_type"] == "DEMO"

    code, body, _ = app.handle_request(
        "POST",
        "/api/config",
        headers=auth_headers,
        body=json.dumps({"ctrader_client_id": "cid_99", "ctrader_client_secret": "sec_99", "ctrader_access_token": "tok_99"}).encode("utf-8"),
    )
    assert code == 200
    cfg_resp = json.loads(body)["config"]
    assert cfg_resp["ctrader_client_secret"] == "********"
    assert cfg_resp["ctrader_access_token_set"] is True

    code, body, _ = app.handle_request(
        "POST", "/api/accounts/select", headers=auth_headers, body=json.dumps({"account_id": "ct_demo_1"}).encode("utf-8")
    )
    assert code == 200
    assert json.loads(body)["active_account"]["account_type"] == "DEMO"

    code, body, _ = app.handle_request("GET", "/api/symbols?mode=PRINCIPAIS", headers=auth_headers, body=b"")
    assert code == 200
    assert len(json.loads(body)["symbols"]) > 0

    code, body, _ = app.handle_request(
        "POST",
        "/api/categories",
        headers=auth_headers,
        body=json.dumps({"category_name": "Metais Spot", "symbols": ["XAUUSD", "XAGUSD"]}).encode("utf-8"),
    )
    assert code == 200
    assert "Metais Spot" in json.loads(body)["categories"]

    code, _, _ = app.handle_request(
        "POST",
        "/api/config",
        headers=auth_headers,
        body=json.dumps({"connection_mode": "SIMULATION"}).encode("utf-8"),
    )
    assert code == 200

    code, body, _ = app.handle_request(
        "POST",
        "/api/bots",
        headers=auth_headers,
        body=json.dumps(
            {
                "name": "Bot cTrader EURUSD",
                "account_id": "ct_demo_1",
                "symbol": "EURUSD",
                "lot_size": 0.02,
                "auto_start": True,
            }
        ).encode("utf-8"),
    )
    assert code == 200
    bot_id = json.loads(body)["bot"]["bot_id"]

    code, body, _ = app.handle_request(
        "POST",
        "/api/bots/action",
        headers=auth_headers,
        body=json.dumps({"bot_id": bot_id, "action": "FIRE_BUY"}).encode("utf-8"),
    )
    assert code == 200

    code, body, _ = app.handle_request("GET", "/api/status", headers=auth_headers, body=b"")
    snap = json.loads(body)
    assert len(snap["positions"]) >= 1

    code, body, _ = app.handle_request(
        "POST",
        "/api/backtest",
        headers=auth_headers,
        body=json.dumps({"symbol": "EURUSD", "tick_count": 400, "initial_capital": 10000.0, "lot_size": 0.05}).encode("utf-8"),
    )
    assert code == 200
    report = json.loads(body)["report"]
    assert report["symbol"] == "EURUSD"
    assert "net_profit" in report

    code, body, _ = app.handle_request("GET", "/api/chart?symbol=EURUSD", headers=auth_headers, body=b"")
    assert code == 200
    chart_data = json.loads(body)
    assert chart_data["ok"] is True
    assert len(chart_data["points"]) > 0

    code, html_body, _ = app.handle_request("GET", "/", headers=auth_headers, body=b"")
    assert code == 200
    assert "Prado Institutional HFT" in html_body


def test_simulation_mode_ignores_stale_live_tick_cache():
    import time

    cfg = PradoServerConfig(connection_mode="SIMULATION")
    conn = CTraderUniversalConnector(cfg)
    conn._tick_cache["XAUUSD"] = (
        time.time(),
        [TickRecord(int(time.time() * 1000), 500.0, 500.0, 500.0, 0.0, 10.0, 0) for _ in range(60)],
    )
    ticks = conn.fetch_ticks("XAUUSD", count=60)
    assert ticks
    assert ticks[-1].effective_price() > 2000.0

    ok, _ = conn.connect()
    assert ok is True
    assert conn._tick_cache == {}


def test_ctrader_cloud_disconnected_does_not_leak_sim_positions():
    cfg = PradoServerConfig(connection_mode="SIMULATION")
    conn = CTraderUniversalConnector(cfg)
    conn.connect()
    ticks = conn.fetch_ticks("EURUSD", count=60)
    price = ticks[-1].effective_price()
    ok, _ = conn.place_order("EURUSD", "BUY", 0.01, price, price * 0.01, price * 0.01)
    assert ok is True
    assert len(conn.get_open_positions()) == 1

    cfg.connection_mode = "CTRADER_CLOUD"
    conn.connect()
    assert conn.get_open_positions() == []
    closed_count, _ = conn.close_all_positions()
    assert closed_count == 0
    ok_single, _ = conn.close_single_position(conn._sim_positions[0]["ticket"])
    assert ok_single is False

    cfg.connection_mode = "SIMULATION"
    conn.connect()
    assert len(conn.get_open_positions()) == 1
