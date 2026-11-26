from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Any

from prado_linux.config import PradoServerConfig
from prado_linux.supabase_store import SupabaseConfig, SupabaseStore
from prado_linux.web_app import PradoWebApp


class _FakeMultiUserSupabaseStore(SupabaseStore):
    """In-memory mock SupabaseStore recording HTTP calls and timings for auth/recovery/news-gate tests."""

    def __init__(self, delay_rest_sec: float = 0.0) -> None:
        super().__init__(SupabaseConfig(url="https://fake.supabase.co", anon_key="anon-key"))
        self.delay_rest_sec = delay_rest_sec
        self.requests: list[tuple[str, str, Any, str | None]] = []
        self.user_configs: dict[str, dict[str, Any]] = {}
        self.recover_status: int = 200
        self.recover_response: dict[str, Any] = {}
        self.update_pwd_status: int = 200
        self.update_pwd_response: dict[str, Any] = {"user": {"email": "cliente@ex.com"}}

    def sign_in(self, email: str, password: str) -> tuple[bool, dict[str, Any]]:
        if password != "secret123":
            return False, {"error": "Invalid login credentials"}
        uid = "uid-admin-1" if email == "sitepixer@gmail.com" else f"uid-{email.split('@')[0]}"
        return True, {"user_id": uid, "email": email, "access_token": f"tok-{uid}"}

    def sign_up(self, email: str, password: str) -> tuple[bool, dict[str, Any]]:
        uid = f"uid-{email.split('@')[0]}"
        return True, {"user_id": uid, "email": email, "access_token": f"tok-{uid}"}

    def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        bearer_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        self.requests.append((method, path, body, bearer_token))
        if path.startswith("/auth/v1/recover"):
            return self.recover_status, dict(self.recover_response)
        if path.startswith("/auth/v1/user"):
            return self.update_pwd_status, dict(self.update_pwd_response)
        if self.delay_rest_sec > 0:
            time.sleep(self.delay_rest_sec)
        if path.startswith("/rest/v1/prado_settings"):
            return 200, [
                {
                    "connection_mode": "SIMULATION",
                    "allow_real_trading": False,
                    "auto_trading_enabled": True,
                    "active_account_id": "sim_1",
                    "active_account_type": "DEMO",
                    "default_lot_size": 0.02,
                    "active_symbols": ["EURUSD", "BTCUSD"],
                    "news_config": {"news_bot_enabled": True},
                }
            ]
        if path.startswith("/rest/v1/prado_ctrader_accounts"):
            return 200, [
                {
                    "account_id": "ct_101",
                    "ctid_account_id": "101",
                    "trader_login": "101",
                    "account_type": "DEMO",
                    "is_live": False,
                    "broker_name": "cTrader",
                    "label": "Demo 101",
                    "access_token": "",
                    "refresh_token": "",
                    "default_lot_size": 0.02,
                    "connection_mode": "SIMULATION",
                    "balance": 5000.0,
                    "currency": "USD",
                }
            ]
        if path.startswith("/rest/v1/prado_bots"):
            return 200, [
                {
                    "bot_id": "b1",
                    "name": "Bot 1",
                    "account_id": "ct_101",
                    "symbol": "EURUSD",
                    "template_id": "WALL_STREET_HYBRID_BOTH",
                    "operation_mode": "BOTH",
                    "timeframe": "TICKS",
                    "status": "STOPPED",
                    "lot_size": 0.02,
                    "config_json": {},
                }
            ]
        if path.startswith("/rest/v1/prado_custom_templates"):
            return 200, [
                {
                    "template_id": "CUSTOM_1",
                    "name": "Meu Modelo",
                    "description": "Teste",
                    "custom_mode": "INDICATORS",
                    "combine_mode": "MAJORITY",
                    "formula": "RSI",
                    "indicators": [],
                    "config_json": {},
                }
            ]
        if path.startswith("/rest/v1/prado_news_feeds"):
            return 200, [
                {
                    "feed_id": "f1",
                    "source": "Fonte Teste",
                    "url": "https://example.com/rss",
                    "default_symbol": "EURUSD",
                }
            ]
        return 200, []

    def sync_user_config(self, user_id: str, access_token: str, cfg: PradoServerConfig) -> None:
        self.user_configs[user_id] = {
            "news_ai_enabled": cfg.news_ai_enabled,
            "news_ai_api_key": cfg.news_ai_api_key,
            "news_ai_provider": cfg.news_ai_provider,
            "news_ai_model": cfg.news_ai_model,
        }


def test_parallel_load_user_config_fetches_all_tables_concurrently(tmp_path: Path) -> None:
    sb = _FakeMultiUserSupabaseStore(delay_rest_sec=0.15)
    t0 = time.monotonic()
    cfg = sb.load_user_config("uid-cliente", "tok-1", tmp_path / "user.json")
    elapsed = time.monotonic() - t0
    assert cfg.default_lot_size == 0.02
    assert len(cfg.accounts) == 1
    assert len(cfg.bots) == 1
    assert len(cfg.custom_templates) == 1
    assert cfg.news_feeds[0]["feed_id"] == "f1"
    # 5 requests * 0.15s sequentially = 0.75s; parallel should complete far faster (< 0.45s)
    assert elapsed < 0.45


def test_login_and_api_me_do_not_block_on_news_scan_or_old_service_stop(tmp_path: Path) -> None:
    sb = _FakeMultiUserSupabaseStore()
    app = PradoWebApp(config_path=tmp_path / "cfg_fast.json", supabase_store=sb)
    try:
        # Inject an existing service for the client whose stop_background_loop sleeps 1.5s
        old_stopped = threading.Event()

        class _SlowStopService:
            _thread = None

            def stop_background_loop(self) -> None:
                time.sleep(1.2)
                old_stopped.set()

        app._user_services["uid-cliente"] = _SlowStopService()  # type: ignore[assignment]

        # Ensure news scan is slow if called synchronously
        scan_calls: list[float] = []
        orig_load = sb.load_user_config

        def _load_with_sim(user_id: str, access_token: str, fallback_path: Path) -> PradoServerConfig:
            c = orig_load(user_id, access_token, fallback_path)
            c.news_bot_enabled = True
            return c

        sb.load_user_config = _load_with_sim  # type: ignore[method-assign]

        t0 = time.monotonic()
        code, body, headers = app.handle_request(
            "POST",
            "/api/login",
            {},
            json.dumps({"email": "cliente@ex.com", "password": "secret123"}).encode(),
        )
        elapsed_login = time.monotonic() - t0
        assert code == 200
        assert json.loads(body)["ok"] is True
        assert elapsed_login < 0.5
        cookie = headers["Set-Cookie"].split(";", 1)[0]

        # Wait briefly so background warmer populates or let /api/me run immediately without requiring step_once
        me_code, me_body, _ = app.handle_request("GET", "/api/me", {"Cookie": cookie})
        assert me_code == 200
        me_data = json.loads(me_body)
        assert me_data["email"] == "cliente@ex.com"
        assert me_data["is_admin"] is False

        svc = app._active_service("uid-cliente")
        # Spy on scan inside step_once(run_news=False)
        svc.news_scout.scan = lambda **_kw: (scan_calls.append(time.monotonic()) or ([], []))  # type: ignore[method-assign]
        svc.step_once(run_news=False)
        assert scan_calls == []
    finally:
        app.service.stop_background_loop()
        for u_svc in list(app._user_services.values()):
            if hasattr(u_svc, "stop_background_loop"):
                try:
                    u_svc.stop_background_loop()
                except Exception:
                    pass


def test_forgot_password_and_reset_password_routes(tmp_path: Path) -> None:
    sb = _FakeMultiUserSupabaseStore()
    app = PradoWebApp(config_path=tmp_path / "cfg_pwd.json", supabase_store=sb)
    try:
        # GET /reset-password serves index HTML cleanly without auth cookie
        c_page, b_page, h_page = app.handle_request("GET", "/reset-password", {})
        assert c_page == 200
        assert "text/html" in h_page.get("Content-Type", "")
        assert len(b_page) > 0

        # Invalid email
        c_bad, _, _ = app.handle_request(
            "POST",
            "/api/forgot-password",
            {},
            json.dumps({"email": "invalido"}).encode(),
        )
        assert c_bad == 400

        # Valid forgot-password forwards redirect_to=/reset-password
        c_fg, b_fg, _ = app.handle_request(
            "POST",
            "/api/forgot-password",
            {"Host": "paineljose.duckdns.org", "X-Forwarded-Proto": "https"},
            json.dumps({"email": "cliente@ex.com"}).encode(),
        )
        assert c_fg == 200
        fg_data = json.loads(b_fg)
        assert fg_data["ok"] is True
        recover_calls = [r for r in sb.requests if r[1].startswith("/auth/v1/recover")]
        assert len(recover_calls) == 1
        assert "redirect_to=https%3A%2F%2Fpaineljose.duckdns.org%2Freset-password" in recover_calls[0][1]
        assert recover_calls[0][2] == {"email": "cliente@ex.com"}

        # Reset password validations
        c_short, _, _ = app.handle_request(
            "POST",
            "/api/reset-password",
            {},
            json.dumps({"access_token": "rec-tok-123", "password": "123"}).encode(),
        )
        assert c_short == 400

        c_missing_tok, _, _ = app.handle_request(
            "POST",
            "/api/reset-password",
            {},
            json.dumps({"access_token": "", "password": "nova_senha_123"}).encode(),
        )
        assert c_missing_tok == 400

        # Valid reset password calls PUT /auth/v1/user with user bearer token
        c_rst, b_rst, _ = app.handle_request(
            "POST",
            "/api/reset-password",
            {},
            json.dumps({"access_token": "rec-tok-123", "password": "nova_senha_123"}).encode(),
        )
        assert c_rst == 200
        assert json.loads(b_rst)["ok"] is True
        user_calls = [r for r in sb.requests if r[1] == "/auth/v1/user"]
        assert len(user_calls) == 1
        assert user_calls[0][0] == "PUT"
        assert user_calls[0][2] == {"password": "nova_senha_123"}
        assert user_calls[0][3] == "rec-tok-123"
    finally:
        app.service.stop_background_loop()


def test_forgot_password_requires_supabase_in_local_mode(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "cfg_local.json")
    try:
        c, _, _ = app.handle_request(
            "POST",
            "/api/forgot-password",
            {},
            json.dumps({"email": "x@ex.com"}).encode(),
        )
        assert c == 400
    finally:
        app.service.stop_background_loop()


def test_client_news_gated_on_own_ai_key_and_isolated_from_admin_key(tmp_path: Path) -> None:
    sb = _FakeMultiUserSupabaseStore()
    app = PradoWebApp(config_path=tmp_path / "cfg_gate.json", supabase_store=sb)
    try:
        # 1. Super-Admin configures global platform AI Key
        c_adm, _, h_adm = app.handle_request(
            "POST",
            "/api/login",
            {},
            json.dumps({"email": "sitepixer@gmail.com", "password": "secret123"}).encode(),
        )
        assert c_adm == 200
        admin_cookie = h_adm["Set-Cookie"].split(";", 1)[0]

        c_set, _, _ = app.handle_request(
            "POST",
            "/api/admin/settings",
            {"Cookie": admin_cookie},
            json.dumps(
                {
                    "ai_news_enabled": True,
                    "ai_news_provider": "gemini",
                    "ai_news_model": "gemini-3.5-flash-lite",
                    "ai_news_api_key": "ADMIN_SECRET_GLOBAL_KEY",
                }
            ).encode(),
        )
        assert c_set == 200

        # Admin status still has ai_setup_required=False and AI active via fallback
        c_adm_st, b_adm_st, _ = app.handle_request("GET", "/api/status", {"Cookie": admin_cookie})
        assert c_adm_st == 200
        adm_news = json.loads(b_adm_st)["news"]
        assert adm_news["ai_setup_required"] is False
        assert adm_news["ai_active"] is True

        # 2. Normal client logs in (without their own AI key configured) and chooses a plan that includes news_bot
        c_cli, _, h_cli = app.handle_request(
            "POST",
            "/api/login",
            {},
            json.dumps({"email": "gmaisnoticia@gmail.com", "password": "secret123"}).encode(),
        )
        assert c_cli == 200
        cli_cookie = h_cli["Set-Cookie"].split(";", 1)[0]

        c_plan, _, _ = app.handle_request(
            "POST",
            "/api/subscription/select-trial-plan",
            {"Cookie": cli_cookie},
            json.dumps({"plan_id": "institutional"}).encode(),
        )
        assert c_plan == 200

        # Wait up to 1s if warmer is initializing service, then inspect client service
        cli_svc = app._active_service("uid-gmaisnoticia")
        scan_called = False

        def _fake_scan(**_kwargs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            nonlocal scan_called
            scan_called = True
            item = {
                "id": "n1",
                "title": "Fed signals rate cut boost for EURUSD",
                "source": "Reuters",
                "link": "https://ex/1",
                "published_at": "2026-11-26 19:00",
                "symbol": "EURUSD",
                "impact": "HIGH",
                "bias": "BULLISH",
                "score": 0.8,
                "is_macro_usd": True,
                "analysis_source": "AI_GEMINI",
                "ai_reason": "Corte de juros enfraquece dólar.",
            }
            cli_svc.news_scout.items = [item]
            cli_svc.news_scout.last_scan_at = time.time()
            return cli_svc.news_scout.items, [item]

        cli_svc.news_scout.scan = _fake_scan  # type: ignore[method-assign]

        # Must NEVER inherit admin key
        assert cli_svc.news_scout._ai_analyzer.api_key != "ADMIN_SECRET_GLOBAL_KEY"
        assert cli_svc.news_scout._ai_analyzer.enabled is False

        # Status before configuring own AI key: ai_setup_required=True and empty items/cards
        c_st1, b_st1, _ = app.handle_request("GET", "/api/status", {"Cookie": cli_cookie})
        assert c_st1 == 200
        cli_news_before = json.loads(b_st1)["news"]
        assert cli_news_before["ai_setup_required"] is True
        assert cli_news_before["ai_active"] is False
        assert cli_news_before["items"] == []
        assert cli_news_before["analyst_cards"] == []
        assert scan_called is False

        # POST /api/news/scan must refuse with 400 AI_API_KEY_REQUIRED before own key is configured
        c_scan1, b_scan1, _ = app.handle_request("POST", "/api/news/scan", {"Cookie": cli_cookie}, b"{}")
        assert c_scan1 == 400
        d_scan1 = json.loads(b_scan1)
        assert d_scan1["code"] == "AI_API_KEY_REQUIRED"
        assert scan_called is False

        # 3. Client configures & activates their OWN AI API Key via /api/config
        c_cfg, _, _ = app.handle_request(
            "POST",
            "/api/config",
            {"Cookie": cli_cookie},
            json.dumps(
                {
                    "news_ai_enabled": True,
                    "news_ai_provider": "gemini",
                    "news_ai_model": "gemini-3.5-flash-lite",
                    "news_ai_api_key": "CLIENT_OWN_API_KEY",
                }
            ).encode(),
        )
        assert c_cfg == 200
        assert cli_svc.news_scout._ai_analyzer.enabled is True
        assert cli_svc.news_scout._ai_analyzer.api_key == "CLIENT_OWN_API_KEY"

        # Now scan works and news + cards unlock!
        c_scan2, b_scan2, _ = app.handle_request("POST", "/api/news/scan", {"Cookie": cli_cookie}, b"{}")
        assert c_scan2 == 200
        d_scan2 = json.loads(b_scan2)["news"]
        assert d_scan2["ai_setup_required"] is False
        assert d_scan2["ai_active"] is True
        assert len(d_scan2["items"]) == 1
        assert len(d_scan2["analyst_cards"]) >= 1
        assert scan_called is True

        # 4. Clearing client's own AI key re-gates news immediately
        c_clr, _, _ = app.handle_request(
            "POST",
            "/api/config",
            {"Cookie": cli_cookie},
            json.dumps({"clear_news_ai_api_key": True, "news_ai_enabled": False}).encode(),
        )
        assert c_clr == 200
        c_st2, b_st2, _ = app.handle_request("GET", "/api/status", {"Cookie": cli_cookie})
        assert c_st2 == 200
        cli_news_after_clear = json.loads(b_st2)["news"]
        assert cli_news_after_clear["ai_setup_required"] is True
        assert cli_news_after_clear["items"] == []
        assert cli_news_after_clear["analyst_cards"] == []
    finally:
        app.service.stop_background_loop()
        for u_svc in list(app._user_services.values()):
            if hasattr(u_svc, "stop_background_loop"):
                try:
                    u_svc.stop_background_loop()
                except Exception:
                    pass
