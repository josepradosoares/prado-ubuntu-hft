"""Regression tests for Deriv proposal_open_contract RateLimit isolation, WS streaming, and bot resilience."""
from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import time

from prado_linux.config import PradoServerConfig
from prado_linux.deriv_client import DerivClient, DerivRateLimiter, DerivRateLimitError
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord


def test_ws_proposal_open_contract_rate_limit_does_not_block_rest_or_other_ws_groups() -> None:
    rl = DerivRateLimiter()
    now = 5000.0
    delay = rl.record_remote_rate_limit(
        "You have reached the rate limit for proposal_open_contract.",
        now=now,
        scope="ws",
        group="trade",
        endpoint="proposal_open_contract",
    )
    assert delay >= 2.0

    # REST calls (e.g. GET /accounts, POST /otp) and other WS groups must NOT be blocked
    rl.acquire_rest(now=now + 0.1)
    rl.acquire_ws("other", now=now + 0.1, endpoint="ticks_history")
    rl.acquire_ws("account", now=now + 0.1, endpoint="balance")
    rl.acquire_ws("portfolio", now=now + 0.1, endpoint="portfolio")
    rl.acquire_ws("trade", now=now + 0.1, endpoint="sell")
    rl.acquire_ws("trade", now=now + 0.1, endpoint="buy")

    # Only proposal_open_contract itself is cooled down
    blocked = False
    try:
        rl.acquire_ws("trade", now=now + 0.1, endpoint="proposal_open_contract")
    except DerivRateLimitError as exc:
        blocked = True
        assert "proposal_open_contract" in str(exc)
    assert blocked is True

    st = rl.status(now=now + 0.1)
    assert st["state"] == "NORMAL"
    assert st["endpoint_cooldowns"]["proposal_open_contract"] > 0


def test_get_open_contracts_uses_poc_cache_aborts_loop_on_rate_limit_and_respects_stream() -> None:
    poc_calls: list[int] = []

    def rpc_cached(payload: dict) -> dict:
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [
                        {"contract_id": 201, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                        {"contract_id": 202, "symbol": "R_75", "contract_type": "MULTDOWN", "buy_price": 15.0},
                    ]
                }
            }
        if "proposal_open_contract" in payload:
            cid = int(payload["contract_id"])
            poc_calls.append(cid)
            return {
                "proposal_open_contract": {
                    "contract_id": cid,
                    "underlying_symbol": "R_100" if cid == 201 else "R_75",
                    "contract_type": "MULTUP" if cid == 201 else "MULTDOWN",
                    "buy_price": 10.0 if cid == 201 else 15.0,
                    "entry_spot": 500.0,
                    "current_spot": 502.0,
                    "profit": 1.25,
                }
            }
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=rpc_cached)
    first = client.get_open_contracts()
    assert len(first) == 2
    assert poc_calls == [201, 202]

    # Second call within TTL must hit _poc_cache without firing more proposal_open_contract calls
    second = client.get_open_contracts()
    assert len(second) == 2
    assert poc_calls == [201, 202]

    # When RateLimit hits mid-loop, abort remaining contracts immediately instead of hammering 303/304
    rl_calls: list[int] = []

    def rpc_rate_limited(payload: dict) -> dict:
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [
                        {"contract_id": 301, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                        {"contract_id": 302, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                        {"contract_id": 303, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                        {"contract_id": 304, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0},
                    ]
                }
            }
        if "proposal_open_contract" in payload:
            cid = int(payload["contract_id"])
            rl_calls.append(cid)
            if cid == 302:
                return {
                    "error": {
                        "code": "RateLimit",
                        "message": "You have reached the rate limit for proposal_open_contract.",
                    },
                    "msg_type": "proposal_open_contract",
                }
            return {
                "proposal_open_contract": {
                    "contract_id": cid,
                    "underlying_symbol": "R_100",
                    "contract_type": "MULTUP",
                    "buy_price": 10.0,
                    "entry_spot": 500.0,
                    "current_spot": 501.0,
                    "profit": 0.5,
                }
            }
        return {}

    rl_client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=rpc_rate_limited)
    pos_rl = rl_client.get_open_contracts()
    assert len(pos_rl) == 4
    assert rl_calls == [301, 302]

    # Live stream entries eliminate proposal_open_contract RPC calls completely
    stream_calls: list[int] = []

    def rpc_stream(payload: dict) -> dict:
        if "portfolio" in payload:
            return {
                "portfolio": {
                    "contracts": [{"contract_id": 901, "symbol": "R_100", "contract_type": "MULTUP", "buy_price": 10.0}]
                }
            }
        if "proposal_open_contract" in payload:
            stream_calls.append(int(payload.get("contract_id", 0)))
        return {}

    s_client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=rpc_stream)
    with s_client._stream_lock:
        s_client._stream_contracts["901"] = {
            "contract_id": 901,
            "underlying_symbol": "R_100",
            "contract_type": "MULTUP",
            "buy_price": 10.0,
            "entry_spot": 100.0,
            "current_spot": 103.5,
            "profit": 2.75,
        }
    stream_pos = s_client.get_open_contracts()
    assert len(stream_pos) == 1
    assert stream_pos[0]["profit"] == 2.75
    assert stream_calls == []


def test_ws_reader_routes_stream_updates_and_closes_deals_without_blocking_rpc() -> None:
    class MockStreamingWS:
        def __init__(self) -> None:
            self.connected = True
            self.inbox: queue.Queue[str] = queue.Queue()
            self.sent: list[dict] = []

        def settimeout(self, timeout: float) -> None:
            return None

        def send(self, data: str) -> None:
            req = json.loads(data)
            self.sent.append(req)
            rid = req.get("req_id")
            if "portfolio" in req:
                # Push unsolicited contract + balance updates BEFORE the portfolio reply!
                self.inbox.put(
                    json.dumps(
                        {
                            "msg_type": "proposal_open_contract",
                            "proposal_open_contract": {
                                "contract_id": 8801,
                                "underlying_symbol": "R_100",
                                "contract_type": "MULTUP",
                                "buy_price": 10.0,
                                "entry_spot": 500.0,
                                "current_spot": 505.0,
                                "profit": 4.2,
                            },
                        }
                    )
                )
                self.inbox.put(json.dumps({"msg_type": "balance", "balance": {"balance": 10042.5, "currency": "USD"}}))
                self.inbox.put(json.dumps({"msg_type": "portfolio", "req_id": rid, "portfolio": {"contracts": [{"contract_id": 8801}]}}))

        def recv(self) -> str:
            if not self.connected:
                raise ConnectionError("closed")
            try:
                return self.inbox.get(timeout=0.05)
            except queue.Empty:
                raise TimeoutError("idle")

        def close(self) -> None:
            self.connected = False

    ws = MockStreamingWS()
    client = DerivClient(token="pat_stream_tok_123456789012345678901234567890", app_id="99999")
    client._ws = ws
    client._start_ws_reader(ws)
    try:
        resp = client._send_rpc({"portfolio": 1})
        assert resp["portfolio"]["contracts"][0]["contract_id"] == 8801

        # Wait briefly for stream messages processed before portfolio reply
        assert client._stream_contracts["8801"]["profit"] == 4.2
        assert client._authorized_info["balance"] == 10042.5

        # Push contract close notification via stream
        ws.inbox.put(
            json.dumps(
                {
                    "msg_type": "proposal_open_contract",
                    "proposal_open_contract": {
                        "contract_id": 8801,
                        "underlying_symbol": "R_100",
                        "contract_type": "MULTUP",
                        "buy_price": 10.0,
                        "entry_spot": 500.0,
                        "exit_spot": 506.0,
                        "current_spot": 506.0,
                        "profit": 5.1,
                        "is_sold": 1,
                        "status": "sold",
                    },
                }
            )
        )
        deadline = time.time() + 1.0
        closed: list[dict] = []
        while time.time() < deadline:
            closed.extend(client.pop_closed_contracts())
            if closed:
                break
            time.sleep(0.02)
        assert len(closed) == 1
        assert str(closed[0]["contract_id"]) == "8801"
        assert "8801" not in client._stream_contracts
    finally:
        client.close()


def test_place_order_preserves_cache_and_bot_survives_transient_rate_limit(tmp_path: Path) -> None:
    cfg = PradoServerConfig(
        connection_mode="DERIV_CLOUD",
        auto_trading_enabled=True,
        active_symbols=["R_100"],
        correlated_basket=[],
        min_order_interval_sec=0.0,
    )
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")
    ticks = [
        TickRecord(1000 + i * 1000, 100.0 + i * 0.4, 100.1 + i * 0.4, 100.0 + i * 0.4, 0.0, 50.0, 32)
        for i in range(60)
    ]
    svc.connector.fetch_ticks = lambda sym, count=200, granularity=0: ticks  # type: ignore[method-assign]

    portfolio_calls = {"count": 0}
    poc_calls = {"count": 0}
    rate_limit_active = {"flag": True}

    def fake_rpc(payload: dict) -> dict:
        if "portfolio" in payload:
            portfolio_calls["count"] += 1
            return {"portfolio": {"contracts": []}}
        if "proposal_open_contract" in payload:
            poc_calls["count"] += 1
            return {}
        if "proposal" in payload:
            if rate_limit_active["flag"]:
                return {
                    "error": {
                        "code": "RateLimit",
                        "message": "You have reached the rate limit for proposal_open_contract.",
                    },
                    "msg_type": "proposal_open_contract",
                }
            return {"proposal": {"id": "prop_1", "ask_price": 10.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 7711}}
        if "balance" in payload:
            return {"balance": {"balance": 10000.0}}
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=fake_rpc)
    svc.connector._deriv = client
    svc.connector.connected = True
    svc.connector.connection_state = "CONNECTED"
    svc.connector.auth_state = "AUTHENTICATED"
    svc.connector.last_tick_at = time.time()
    svc.connector._deriv_auth = {"loginid": "VRTC1", "is_virtual": 1, "currency": "USD", "balance": 10000.0}

    bot = svc.create_bot(
        {
            "name": "GridResiliente",
            "symbol": "R_100",
            "bot_template_id": "GRID_LINEAR_HFT",
            "grid_direction": "BUY_ONLY",
            "auto_start": True,
        }
    )

    # First step hits RateLimit: bot must stay RUNNING (not ERROR/active=False) and show RATE_LIMITED
    snap1 = svc.step_once()
    b1 = next(b for b in snap1["bots"] if b["bot_id"] == bot["bot_id"])
    assert b1["status"] == "RUNNING"
    assert b1["active"] is True
    assert b1["last_signal"] == "RATE_LIMITED"

    # When RateLimit recovers, bot trades and clears transient last_error without re-polling portfolio
    rate_limit_active["flag"] = False
    client.rate_limiter._ws_endpoint_blocked_until.clear()
    portfolio_before = portfolio_calls["count"]
    snap2 = svc.step_once()
    b2 = next(b for b in snap2["bots"] if b["bot_id"] == bot["bot_id"])
    assert b2["status"] == "RUNNING"
    assert b2["active"] is True
    assert b2["last_error"] == ""
    assert b2["trades_executed"] == 1
    assert portfolio_calls["count"] <= portfolio_before + 1
    assert poc_calls["count"] == 0
    assert any(str(p["ticket"]) == "7711" for p in snap2["positions"])


def test_stream_contract_closed_by_deriv_sl_tp_syncs_to_deals_history(tmp_path: Path) -> None:
    cfg = PradoServerConfig(
        connection_mode="DERIV_CLOUD",
        auto_trading_enabled=True,
        active_symbols=["R_100"],
        correlated_basket=[],
    )
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg.json")
    ticks = [
        TickRecord(1000 + i * 1000, 100.0, 100.1, 100.0, 0.0, 10.0, 32)
        for i in range(40)
    ]
    svc.connector.fetch_ticks = lambda sym, count=200, granularity=0: ticks  # type: ignore[method-assign]

    def fake_rpc(payload: dict) -> dict:
        if "portfolio" in payload:
            return {"portfolio": {"contracts": []}}
        if "balance" in payload:
            return {"balance": {"balance": 10012.5}}
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=fake_rpc)
    svc.connector._deriv = client
    svc.connector.connected = True
    svc.connector.connection_state = "CONNECTED"
    svc.connector.auth_state = "AUTHENTICATED"
    svc.connector.last_tick_at = time.time()
    svc.connector._deriv_auth = {"loginid": "VRTC1", "is_virtual": 1, "currency": "USD", "balance": 10000.0}
    svc.connector._contract_bot_map["9955"] = "ScalpBot"

    bot = svc.create_bot({"name": "ScalpBot", "symbol": "R_100", "auto_start": False})
    with client._stream_lock:
        client._recently_closed_contracts.append(
            {
                "contract_id": 9955,
                "underlying_symbol": "R_100",
                "contract_type": "MULTUP",
                "buy_price": 10.0,
                "entry_spot": 500.0,
                "exit_spot": 504.0,
                "current_spot": 504.0,
                "profit": 3.5,
                "is_sold": 1,
                "status": "sold",
            }
        )

    snap = svc.step_once()
    assert len(snap["deals_history"]) == 1
    assert str(snap["deals_history"][0]["ticket"]) == "9955"
    assert snap["deals_history"][0]["profit"] == 3.5
    assert snap["deals_history"][0]["bot_name"] == "ScalpBot"
    b_out = next(b for b in snap["bots"] if b["bot_id"] == bot["bot_id"])
    assert b_out["realized_pnl"] == 3.5
