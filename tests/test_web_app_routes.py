from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from prado_linux.config import PradoServerConfig
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


def test_public_static_and_auth_guards(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=SupabaseStore(SupabaseConfig()))

    # Health & mode
    code, body, hdrs = app.handle_request("GET", "/health", {})
    assert code == 200 and json.loads(body)["ok"] is True
    assert hdrs["X-Frame-Options"] == "SAMEORIGIN"

    code, body, _ = app.handle_request("GET", "/api/auth/mode", {})
    assert code == 200 and json.loads(body)["supabase_enabled"] is False

    # Login page & unauthenticated redirects
    code, _, _ = app.handle_request("GET", "/login", {})
    assert code == 200
    code, _, hdrs = app.handle_request("GET", "/", {})
    assert code == 302 and hdrs["Location"] == "/login"

    # Static assets missing
    code, _, _ = app.handle_request("GET", "/assets/nonexistent_file_xyz.js", {})
    assert code == 404
    code, _, _ = app.handle_request("GET", "/favicon.ico", {})
    assert code in (200, 404)

    # Signup disabled without supabase
    code, body, _ = app.handle_request("POST", "/api/signup", {}, b"{}")
    assert code == 400 and "Supabase" in json.loads(body)["error"]

    # Bad login & malformed cookie
    code, _, _ = app.handle_request("POST", "/api/login", {}, b"{bad json")
    assert code == 401
    assert app._extract_session_user({"Cookie": "other=1"}) is None

    # Logout
    auth = _login_headers(app)
    code, body, hdrs = app.handle_request("POST", "/api/logout", auth)
    assert code == 200 and "Max-Age=0" in hdrs["Set-Cookie"]


def test_supabase_auth_signup_login_and_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseStore(SupabaseConfig(url="https://demo.supabase.co", anon_key="anon"))
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=store)
    app.cfg.connection_mode = "SIMULATION"
    app.cfg.accounts = [{"account_id": "a1", "label": "Legacy"}]

    synced: list[str] = []
    monkeypatch.setattr(store, "load_user_config", lambda uid, tok, p: PradoServerConfig(connection_mode="SIMULATION"))
    monkeypatch.setattr(store, "sync_user_config", lambda uid, tok, cfg: synced.append(uid))

    # Signup failure
    monkeypatch.setattr(store, "sign_up", lambda e, p: (False, {"error": "already exists"}))
    code, body, _ = app.handle_request("POST", "/api/signup", {}, json.dumps({"email": "x@y.com", "password": "123"}).encode())
    assert code == 400 and json.loads(body)["error"] == "already exists"

    # Signup requiring confirmation (no access_token)
    monkeypatch.setattr(store, "sign_up", lambda e, p: (True, {"user_id": "u_conf", "email": e, "access_token": ""}))
    code, body, _ = app.handle_request("POST", "/api/signup", {}, json.dumps({"email": "x@y.com", "password": "123"}).encode())
    assert code == 200 and json.loads(body)["confirmation_required"] is True

    # Signup with immediate access_token (triggers migration for sitepixer@gmail.com)
    monkeypatch.setattr(
        store,
        "sign_up",
        lambda e, p: (True, {"user_id": "u_mig", "email": "sitepixer@gmail.com", "access_token": "tok_mig"}),
    )
    code, body, hdrs = app.handle_request(
        "POST",
        "/api/signup",
        {},
        json.dumps({"email": "sitepixer@gmail.com", "password": "123"}).encode(),
    )
    assert code == 200 and "prado_session=" in hdrs["Set-Cookie"]
    assert "u_mig" in synced

    # Login failure
    monkeypatch.setattr(store, "sign_in", lambda e, p: (False, {"error": "wrong"}))
    code, _, _ = app.handle_request("POST", "/api/login", {}, json.dumps({"email": "x@y.com", "password": "bad"}).encode())
    assert code == 401

    # Login success (replaces existing user service)
    monkeypatch.setattr(
        store,
        "sign_in",
        lambda e, p: (True, {"user_id": "u_mig", "email": "sitepixer@gmail.com", "access_token": "tok_mig2"}),
    )
    code, _, hdrs = app.handle_request(
        "POST",
        "/api/login",
        {},
        json.dumps({"email": "sitepixer@gmail.com", "password": "123"}).encode(),
    )
    assert code == 200

    # Logout clears token, then session cookie is rejected
    cookie_hdr = {"Cookie": hdrs["Set-Cookie"]}
    app.handle_request("POST", "/api/logout", cookie_hdr)
    assert app._extract_session_user(cookie_hdr) is None

    # Clean up background threads
    for svc in list(app._user_services.values()):
        svc.stop_background_loop()


def test_config_oauth_accounts_risk_and_symbols(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=SupabaseStore(SupabaseConfig()))
    app.cfg.connection_mode = "SIMULATION"
    auth = _login_headers(app)

    # GET & POST /api/config
    code, body, _ = app.handle_request("GET", "/api/config", auth)
    assert code == 200 and "config" in json.loads(body)

    code, _, _ = app.handle_request("POST", "/api/config", auth, b"{invalid")
    assert code == 400

    code, body, _ = app.handle_request(
        "POST",
        "/api/config",
        auth,
        json.dumps(
            {
                "ctrader_client_id": "cid_1",
                "ctrader_client_secret": "real_sec",
                "new_admin_password": "new_password_123",
            }
        ).encode(),
    )
    assert code == 200
    # Masked secret should NOT overwrite stored secret
    code, _, _ = app.handle_request(
        "POST",
        "/api/config",
        auth,
        json.dumps({"ctrader_client_secret": "********"}).encode(),
    )
    assert code == 200 and app.cfg.ctrader_client_secret == "real_sec"

    # OAuth start & callback
    code, body, _ = app.handle_request("GET", "/api/ctrader/oauth/start", {**auth, "Host": "localhost:8080"})
    assert code == 200 and "auth_url" in json.loads(body)

    code, _, hdrs = app.handle_request("GET", "/api/ctrader/oauth/callback?error=access_denied", auth)
    assert code == 302 and "ctrader_oauth=error" in hdrs["Location"]

    code, _, _ = app.handle_request("GET", "/api/ctrader/oauth/callback", auth)
    assert code == 400

    monkeypatch.setattr(app.service, "complete_ctrader_oauth", lambda c, r: (True, "OAuth OK"))
    code, _, hdrs = app.handle_request("GET", "/api/ctrader/oauth/callback?code=abc123", auth)
    assert code == 302 and "ctrader_oauth=ok" in hdrs["Location"]

    # Accounts CRUD, sync, select
    code, body, _ = app.handle_request("GET", "/api/accounts", auth)
    assert code == 200
    code, _, _ = app.handle_request("POST", "/api/accounts", auth, b"{bad")
    assert code == 400

    app.handle_request(
        "POST",
        "/api/accounts",
        auth,
        json.dumps({"account_id": "acc1", "label": "Demo 1", "access_token": "tok1"}).encode(),
    )
    code, body, _ = app.handle_request(
        "POST",
        "/api/accounts",
        auth,
        json.dumps({"action": "DELETE", "account_id": "acc1"}).encode(),
    )
    assert code == 200 and json.loads(body)["accounts"] == []

    code, body, _ = app.handle_request(
        "POST",
        "/api/accounts",
        auth,
        json.dumps({"action": "DELETE_ALL"}).encode(),
    )
    assert code == 200 and json.loads(body)["accounts"] == []

    monkeypatch.setattr(app.service, "sync_ctrader_accounts", lambda: (True, "Synced", []))
    code, body, _ = app.handle_request("POST", "/api/accounts/sync", auth)
    assert code == 200 and json.loads(body)["ok"] is True

    code, _, _ = app.handle_request("POST", "/api/accounts/select", auth, b"{bad")
    assert code == 400
    code, _, _ = app.handle_request("POST", "/api/accounts/select", auth, json.dumps({"account_id": "missing"}).encode())
    assert code == 404

    # Risk reset
    code, body, _ = app.handle_request("POST", "/api/risk/reset", auth)
    assert code == 200 and json.loads(body)["ok"] is True

    # Symbols filtered by custom category
    cat_name = next(iter(app.cfg.custom_categories.keys()))
    code, body, _ = app.handle_request("GET", f"/api/symbols?category={cat_name}", auth)
    assert code == 200 and len(json.loads(body)["symbols"]) > 0


def test_categories_news_templates_bots_and_flatten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=SupabaseStore(SupabaseConfig()))
    app.cfg.connection_mode = "SIMULATION"
    auth = _login_headers(app)

    # Categories GET / SAVE (csv string) / DELETE / bad JSON
    code, body, _ = app.handle_request("GET", "/api/categories", auth)
    assert code == 200
    code, _, _ = app.handle_request("POST", "/api/categories", auth, b"{bad")
    assert code == 400
    code, body, _ = app.handle_request(
        "POST",
        "/api/categories",
        auth,
        json.dumps({"category_name": "TempCat", "symbols": "EURUSD, GBPUSD"}).encode(),
    )
    assert code == 200 and "TempCat" in json.loads(body)["categories"]
    code, body, _ = app.handle_request(
        "POST",
        "/api/categories",
        auth,
        json.dumps({"action": "DELETE", "category_name": "TempCat"}).encode(),
    )
    assert code == 200 and "TempCat" not in json.loads(body)["categories"]

    # News scan & feeds CRUD
    monkeypatch.setattr(app.service, "scan_news", lambda force=True: {"items": []})
    code, body, _ = app.handle_request("POST", "/api/news/scan", auth)
    assert code == 200 and json.loads(body)["ok"] is True

    code, _, _ = app.handle_request("POST", "/api/news/feeds", auth, b"{bad")
    assert code == 400
    code, _, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        auth,
        json.dumps({"source": "SSRF", "url": "http://127.0.0.1/secret"}).encode(),
    )
    assert code == 400
    code, body, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        auth,
        json.dumps({"feed_id": "custom_f1", "source": "TestRSS", "url": "https://example.com/rss"}).encode(),
    )
    assert code == 200
    code, _, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        auth,
        json.dumps({"action": "DELETE", "feed_id": "custom_f1"}).encode(),
    )
    assert code == 200
    code, _, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        auth,
        json.dumps({"action": "RESET_DEFAULT"}).encode(),
    )
    assert code == 200

    # Bot templates GET / SAVE / DELETE / TEST
    code, body, _ = app.handle_request("GET", "/api/bot-templates", auth)
    assert code == 200 and len(json.loads(body)["indicators"]) == 21
    code, _, _ = app.handle_request("POST", "/api/bot-templates", auth, b"{bad")
    assert code == 400
    code, body, _ = app.handle_request(
        "POST",
        "/api/bot-templates",
        auth,
        json.dumps(
            {
                "template_id": "MY_IND_TPL",
                "name": "My Ind",
                "custom_mode": "INDICATORS",
                "indicators": [{"id": "SMA", "params": {"period": 10}}],
            }
        ).encode(),
    )
    assert code == 200
    code, _, _ = app.handle_request(
        "POST",
        "/api/bot-templates",
        auth,
        json.dumps({"action": "DELETE", "template_id": "MY_IND_TPL"}).encode(),
    )
    assert code == 200

    code, _, _ = app.handle_request("POST", "/api/bot-templates/test", auth, b"{bad")
    assert code == 400
    code, body, _ = app.handle_request(
        "POST",
        "/api/bot-templates/test",
        auth,
        json.dumps(
            {
                "symbol": "EURUSD",
                "custom_mode": "INDICATORS",
                "indicators": [{"id": "SMA", "params": {"period": 10}}],
            }
        ).encode(),
    )
    assert code == 200 and json.loads(body)["ok"] is True

    # Bots GET / POST / action (404, DELETE_ALL) & bad JSON
    code, body, _ = app.handle_request("GET", "/api/bots", auth)
    assert code == 200
    code, _, _ = app.handle_request("POST", "/api/bots", auth, b"{bad")
    assert code == 400
    code, _, _ = app.handle_request("POST", "/api/bots/action", auth, b"{bad")
    assert code == 400
    code, _, _ = app.handle_request(
        "POST", "/api/bots/action", auth, json.dumps({"bot_id": "missing", "action": "START"}).encode()
    )
    assert code == 404
    code, body, _ = app.handle_request(
        "POST", "/api/bots/action", auth, json.dumps({"action": "DELETE_ALL"}).encode()
    )
    assert code == 200 and json.loads(body)["bots"] == []

    # Backtest bad JSON
    code, _, _ = app.handle_request("POST", "/api/backtest", auth, b"{bad")
    assert code == 400

    # Flatten single ticket & flatten all
    code, body, _ = app.handle_request("POST", "/api/flatten", auth, json.dumps({"ticket": 999999}).encode())
    assert code == 200 and json.loads(body)["ok"] is False
    code, body, _ = app.handle_request("POST", "/api/flatten", auth, b"{bad")
    assert code == 200

    # Unknown route -> 404
    code, _, _ = app.handle_request("GET", "/api/does-not-exist", auth)
    assert code == 404
