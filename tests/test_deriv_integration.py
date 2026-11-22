"""Tests for Deriv API docs sync, PAT+OTP auth, RateLimiter, trading safety, and security headers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prado_linux.config import PradoServerConfig
from prado_linux.deriv_client import (
    DerivAuthError,
    DerivClient,
    DerivRateLimiter,
    DerivRateLimitError,
    mask_secret,
)
from prado_linux.engine import DerivUniversalConnector
from prado_linux.web_app import PradoWebApp
from scripts.sync_deriv_docs import sync_docs, verify_manifest


def test_deriv_docs_sync_and_verify_manifest(tmp_path: Path) -> None:
    fake_files = {
        "https://developers.deriv.com/llms.txt": (
            b"# Deriv\n- [auth](https://developers.deriv.com/llms/authentication.md)\n"
        ),
        "https://developers.deriv.com/llms/authentication.md": (
            b"# Auth\nSchema: https://developers.deriv.com/schemas/proposal_request.schema.json\n"
        ),
        "https://developers.deriv.com/schemas/proposal_request.schema.json": b'{"type": "object"}',
    }
    manifest = sync_docs(output_dir=tmp_path, fetcher=lambda url: fake_files[url])
    assert manifest["total_files"] == 3
    assert manifest["markdown_count"] == 1
    assert manifest["schema_count"] == 1
    assert manifest["failures"] == []
    ok, errs = verify_manifest(tmp_path)
    assert ok and errs == []

    # Tampering breaks SHA-256 verification
    (tmp_path / "llms" / "authentication.md").write_text("tampered", encoding="utf-8")
    ok_after, errs_after = verify_manifest(tmp_path)
    assert not ok_after
    assert any("SHA-256" in e for e in errs_after)


def test_real_vendor_docs_manifest_integrity() -> None:
    vendor_dir = Path(__file__).resolve().parent.parent / "docs" / "vendor" / "deriv-api"
    ok, errs = verify_manifest(vendor_dir)
    assert ok, f"Vendor docs integrity failed: {errs}"
    assert (vendor_dir / "llms.txt").exists()
    assert (vendor_dir / "INTEGRATION_AUDIT.md").exists()


def test_pat_with_legacy_app_id_1089_raises_app_id_mismatch() -> None:
    client = DerivClient(token="pat_abc1234567890", app_id="1089")
    with pytest.raises(DerivAuthError) as exc_info:
        client.authorize()
    assert exc_info.value.auth_state == "APP_ID_MISMATCH"
    assert client.auth_state == "APP_ID_MISMATCH"


def test_pat_with_custom_app_id_uses_bearer_and_deriv_app_id_and_selects_demo() -> None:
    captured_headers: list[dict[str, str]] = []

    def fake_rest(method: str, url: str, headers: dict[str, str]) -> dict:
        captured_headers.append(dict(headers))
        assert url.endswith("/trading/v1/options/accounts")
        return {
            "data": [
                {"account_id": "CR999", "account_type": "real", "currency": "USD", "balance": 500.0},
                {"account_id": "VRTC123", "account_type": "demo", "currency": "USD", "balance": 10000.0},
            ]
        }

    client = DerivClient(
        token="pat_custom_token_123456",
        app_id="99999",
        rest_transport=fake_rest,
        preferred_account_type="DEMO",
    )
    auth = client.authorize()
    assert auth["loginid"] == "VRTC123"
    assert auth["is_virtual"] == 1
    assert client.auth_state == "AUTHENTICATED"
    assert captured_headers[0]["Authorization"] == "Bearer pat_custom_token_123456"
    assert captured_headers[0]["Deriv-App-ID"] == "99999"


def test_rate_limiter_enforces_ws_and_rest_budgets_and_backoff() -> None:
    rl = DerivRateLimiter()
    now = 1000.0
    # Portfolio budget is 30/min
    for _ in range(30):
        rl.acquire_ws("portfolio", now=now)
    with pytest.raises(DerivRateLimitError):
        rl.acquire_ws("portfolio", now=now)

    # Cooldown recovery
    delay = rl.record_remote_rate_limit("RateLimit", now=now + 100.0)
    assert delay >= 2.0
    assert rl.status(now=now + 100.5)["state"] == "BLOCKED"
    assert rl.status(now=now + 100.5 + delay + 0.1)["state"] == "NORMAL"


def test_proposal_uses_underlying_symbol_and_buy_does_not_retry_on_timeout() -> None:
    calls: list[dict] = []

    def fake_rpc(payload: dict) -> dict:
        calls.append(payload)
        if "proposal" in payload:
            assert payload["underlying_symbol"] == "R_100"
            assert "symbol" not in payload
            return {"proposal": {"id": "prop_1", "ask_price": 10.0}}
        if "buy" in payload:
            raise TimeoutError("WS recv timed out")
        return {}

    client = DerivClient(token="legacy_tok", app_id="1089", rpc_transport=fake_rpc)
    ok, msg = client.place_multiplier_order("R_100", is_buy=True, stake=10.0, multiplier=100)
    assert not ok
    assert "reconciliação" in msg
    # Exactly 1 proposal + 1 buy (never auto-retried buy)
    assert sum(1 for c in calls if "buy" in c) == 1


def test_real_account_trading_blocked_by_default_and_disconnected_blocked() -> None:
    cfg = PradoServerConfig(connection_mode="DERIV_CLOUD", allow_real_trading=False)
    conn = DerivUniversalConnector(cfg)
    ok_disc, msg_disc = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_disc
    assert "bloqueada" in msg_disc.lower()

    # Simulate connected REAL account with allow_real_trading=False
    conn._deriv = DerivClient(token="tok", app_id="1089")
    conn._deriv_auth = {"loginid": "CR123", "is_virtual": 0, "currency": "USD"}
    conn.connected = True
    conn.connection_state = "CONNECTED"
    conn.auth_state = "AUTHENTICATED"
    ok_real, msg_real = conn.place_order("R_100", "BUY_FLOW", 10.0, 100.0, 1.0, 2.0)
    assert not ok_real
    assert "REAL bloqueada" in msg_real


def test_security_headers_no_unrecognized_permissions_policy_and_status_states(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "cfg.json")
    code, _, headers = app.handle_request("GET", "/login", {})
    assert code == 200
    pp = headers.get("Permissions-Policy", "")
    for bad in (
        "attribution-reporting",
        "private-aggregation",
        "join-ad-interest-group",
        "run-ad-auction",
        "browsing-topics",
    ):
        assert bad not in pp

    # Authenticate and check /api/status separated states
    _, _, login_hdrs = app.handle_request(
        "POST", "/api/login", {}, json.dumps({"username": "admin", "password": "prado2026"}).encode()
    )
    cookie = login_hdrs["Set-Cookie"].split(";")[0]
    st_code, st_body, _ = app.handle_request("GET", "/api/status", {"Cookie": cookie})
    assert st_code == 200
    snap = json.loads(st_body)
    acc = snap["account"]
    assert acc["account_mode"] in ("DEMO", "REAL")
    assert acc["connection_state"] == "DISCONNECTED"
    assert acc["auth_state"] == "UNAUTHENTICATED"
    assert acc["trading_state"] == "BLOCKED"
    assert acc["rate_limit"]["state"] == "NORMAL"
    assert mask_secret("1089", 2, 2) == "****"


def test_oauth_headers_no_deriv_app_id_and_token_expired_and_insufficient_scope() -> None:
    captured: list[dict[str, str]] = []

    def oauth_rest(method: str, url: str, headers: dict[str, str]) -> dict:
        captured.append(dict(headers))
        return {"data": [{"account_id": "VRTC777", "account_type": "demo", "currency": "USD", "balance": 5000.0}]}

    oauth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9." + ("x" * 30)
    client = DerivClient(token=oauth_token, app_id="99999", rest_transport=oauth_rest)
    auth = client.authorize()
    assert auth["loginid"] == "VRTC777"
    assert "Deriv-App-ID" not in captured[0]
    assert captured[0]["Authorization"] == f"Bearer {oauth_token}"

    # Expired token via RPC error
    def expired_rpc(payload: dict) -> dict:
        return {"error": {"code": "InvalidToken", "message": "Token has expired"}}

    exp_client = DerivClient(token="legacy_exp", app_id="1089", rpc_transport=expired_rpc)
    with pytest.raises(DerivAuthError) as exc_exp:
        exp_client.authorize()
    assert exc_exp.value.auth_state == "TOKEN_EXPIRED"


def test_rest_rate_limit_and_concurrent_ws_and_demo_trade_lifecycle() -> None:
    import concurrent.futures

    rl = DerivRateLimiter()
    now = 2000.0
    for _ in range(80):
        rl.acquire_rest(now=now)
    with pytest.raises(DerivRateLimitError):
        rl.acquire_rest(now=now)

    # Concurrent WS acquisitions are thread-safe and strictly bounded to 30
    rl_conc = DerivRateLimiter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(rl_conc.acquire_ws, "portfolio", 3000.0) for _ in range(35)]
        errors = 0
        for f in futs:
            try:
                f.result()
            except DerivRateLimitError:
                errors += 1
        assert errors == 5

    # Full Demo Proposal -> Buy -> Portfolio/POC -> Sell lifecycle + active_symbols
    def demo_rpc(payload: dict) -> dict:
        if "active_symbols" in payload:
            return {
                "active_symbols": [
                    {"underlying_symbol": "R_100", "underlying_symbol_name": "Volatility 100", "market": "synthetic_index"}
                ]
            }
        if "proposal" in payload:
            assert payload["underlying_symbol"] == "R_100"
            return {"proposal": {"id": "prop_99", "ask_price": 10.0}}
        if "buy" in payload:
            return {"buy": {"contract_id": 555123}}
        if "portfolio" in payload:
            return {"portfolio": {"contracts": [{"contract_id": 555123, "contract_type": "MULTUP", "symbol": "R_100"}]}}
        if "proposal_open_contract" in payload:
            return {
                "proposal_open_contract": {
                    "contract_id": 555123,
                    "underlying_symbol": "R_100",
                    "contract_type": "MULTUP",
                    "buy_price": 10.0,
                    "entry_spot": 1850.0,
                    "current_spot": 1852.5,
                    "profit": 1.35,
                }
            }
        if "sell" in payload:
            return {"sell": {"sold_for": 11.35}}
        return {}

    client = DerivClient(token="legacy_demo", app_id="1089", rpc_transport=demo_rpc)
    syms = client.get_active_symbols()
    assert syms[0]["name"] == "R_100"

    ok_buy, msg_buy = client.place_multiplier_order("R_100", is_buy=True, stake=10.0, multiplier=100)
    assert ok_buy and "555123" in msg_buy

    positions = client.get_open_contracts()
    assert len(positions) == 1
    assert positions[0]["ticket"] == "555123"
    assert positions[0]["profit"] == 1.35

    ok_sell, msg_sell = client.close_contract("555123")
    assert ok_sell and "11.35" in msg_sell


def test_deriv_cloud_disconnected_data_state_not_live() -> None:
    cfg = PradoServerConfig(connection_mode="DERIV_CLOUD")
    conn = DerivUniversalConnector(cfg)
    conn._get_public_deriv = lambda: type("Broken", (), {"get_ticks_history": lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("offline"))})()  # type: ignore[method-assign]
    conn.fetch_ticks("R_100", count=50)
    summary = conn.get_account_summary()
    assert summary["data_state"] == "NO_DATA"
    assert summary["connection_state"] == "DISCONNECTED"
    assert summary["trading_state"] == "BLOCKED"
