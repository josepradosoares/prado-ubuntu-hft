"""TDD suite for SaaS Bloco 1 (1-click cTrader OAuth & token isolation) and Bloco 2 (Plans, Trial, Kiwify, Admin)."""
from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

from prado_linux.config import load_config
from prado_linux.saas_store import ALL_FEATURES, SaasStore
from prado_linux.web_app import PradoWebApp


class _FakeMultiTenantSupabase:
    """In-memory multi-tenant Supabase mock supporting admin + normal client users."""

    is_enabled = True

    def __init__(self) -> None:
        self.users: dict[str, dict[str, str]] = {
            "sitepixer@gmail.com": {"user_id": "uid-admin", "email": "sitepixer@gmail.com"},
            "cliente@teste.com": {"user_id": "uid-client", "email": "cliente@teste.com"},
            "semconta@teste.com": {"user_id": "uid-new", "email": "semconta@teste.com"},
        }
        self.configs: dict[str, dict] = {}
        self.saas_settings: dict | None = None
        self.saas_plans: list[dict] = []
        self.saas_subscriptions: list[dict] = []

    def sign_up(self, email: str, password: str) -> tuple[bool, dict]:
        uid = f"uid-{email.split('@')[0]}"
        self.users[email.lower()] = {"user_id": uid, "email": email.lower()}
        return True, {"user_id": uid, "email": email.lower(), "access_token": f"tok-{uid}"}

    def sign_in(self, email: str, password: str) -> tuple[bool, dict]:
        rec = self.users.get(email.lower())
        if not rec:
            return False, {"error": "Credenciais inválidas."}
        return True, {
            "user_id": rec["user_id"],
            "email": rec["email"],
            "access_token": f"tok-{rec['user_id']}",
        }

    def load_user_config(self, user_id: str, access_token: str, fallback_path: Path):
        return load_config(fallback_path, inherit_user_tokens=False)

    def sync_user_config(self, user_id: str, access_token: str, cfg) -> None:
        self.configs[user_id] = {"bots": list(cfg.bots), "accounts": list(cfg.accounts)}

    def load_saas_tables(self) -> dict | None:
        return None

    def upsert_saas_settings(self, settings_dict: dict) -> None:
        self.saas_settings = dict(settings_dict)

    def upsert_saas_plan(self, plan_dict: dict) -> None:
        self.saas_plans = [p for p in self.saas_plans if p.get("plan_id") != plan_dict.get("plan_id")]
        self.saas_plans.append(dict(plan_dict))

    def delete_saas_plan(self, plan_id: str) -> None:
        self.saas_plans = [p for p in self.saas_plans if p.get("plan_id") != plan_id]

    def upsert_saas_subscription(self, sub_dict: dict) -> None:
        self.saas_subscriptions = [s for s in self.saas_subscriptions if s.get("email") != sub_dict.get("email")]
        self.saas_subscriptions.append(dict(sub_dict))


def _login_cookie(app: PradoWebApp, email_or_user: str, password: str = "prado2026") -> str:
    body = json.dumps({"username": email_or_user, "email": email_or_user, "password": password}).encode("utf-8")
    code, _, headers = app.handle_request("POST", "/api/login", {}, body)
    assert code == 200
    raw = headers.get("Set-Cookie", "")
    assert "prado_session=" in raw
    return raw.split(";", 1)[0]


# ---------------------------------------------------------------------------
# Bloco 1: Token Isolation & Central App Inheritance
# ---------------------------------------------------------------------------


def test_load_config_token_isolation_for_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTRADER_CLIENT_ID", "app_cid_999")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "app_csec_999")
    monkeypatch.setenv("CTRADER_REDIRECT_URI", "https://quantix.example.com/api/ctrader/oauth/callback")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "owner_secret_access_tok")
    monkeypatch.setenv("CTRADER_REFRESH_TOKEN", "owner_secret_refresh_tok")
    monkeypatch.setenv("ALLOW_REAL_TRADING", "true")

    client_cfg = load_config(tmp_path / "client_u1.json", inherit_user_tokens=False)
    assert client_cfg.ctrader_client_id == "app_cid_999"
    assert client_cfg.ctrader_client_secret == "app_csec_999"
    assert client_cfg.ctrader_redirect_uri == "https://quantix.example.com/api/ctrader/oauth/callback"
    assert client_cfg.ctrader_access_token == ""
    assert client_cfg.ctrader_refresh_token == ""
    assert client_cfg.allow_real_trading is False

    admin_cfg = load_config(tmp_path / "admin.json")
    assert admin_cfg.ctrader_access_token == "owner_secret_access_tok"
    assert admin_cfg.ctrader_refresh_token == "owner_secret_refresh_tok"
    assert admin_cfg.allow_real_trading is True


# ---------------------------------------------------------------------------
# Bloco 2: SaasStore — Plans CRUD, Trial Days Across All Plans & Kiwify
# ---------------------------------------------------------------------------


def test_saas_store_defaults_crud_and_editable_trial_days(tmp_path: Path) -> None:
    state_path = tmp_path / "saas_state.json"
    store = SaasStore(state_path)

    settings = store.get_settings()
    assert settings["trial_days"] == 7
    assert settings["trial_allow_real_trading"] is False

    plans = store.list_plans()
    assert {p["plan_id"] for p in plans} >= {"starter", "pro", "institutional"}

    assert store.is_admin("uid-admin", "sitepixer@gmail.com", supabase_enabled=True) is True
    assert store.is_admin("admin", "", supabase_enabled=False) is True
    assert store.is_admin("uid-c", "cliente@teste.com", supabase_enabled=True) is False

    # Create & edit a plan and verify persistence on reload
    created = store.save_plan(
        {
            "name": "VIP Scalper",
            "description": "Plano VIP personalizado",
            "price_brl": 497.0,
            "billing_cycle": "monthly",
            "kiwify_product_id": "kw_vip_123",
            "kiwify_checkout_url": "https://pay.kiwify.com.br/vip123",
            "max_bots": 25,
            "allow_real_trading": True,
            "allowed_features": ["backtest", "market_radar"],
            "active": True,
        }
    )
    assert created["plan_id"] == "vip_scalper"
    assert "real_trading" in created["allowed_features"]

    store2 = SaasStore(state_path)
    vip = next(p for p in store2.list_plans() if p["plan_id"] == "vip_scalper")
    assert vip["max_bots"] == 25
    assert vip["kiwify_product_id"] == "kw_vip_123"

    # Update global trial_days to 14 and check new user trial
    store2.update_settings({"trial_days": 14})
    ent = store2.get_entitlements("uid-t1", "novo1@teste.com", supabase_enabled=True)
    assert ent["status"] == "trial"
    assert ent["has_access"] is True
    assert 13 <= ent["days_left"] <= 14

    # Trial works across all active plans
    switched = store2.select_trial_plan("uid-t1", "novo1@teste.com", "vip_scalper")
    assert switched["plan_id"] == "vip_scalper"
    assert switched["max_bots"] == 25

    # Disable trial globally (trial_days = 0) -> new users start expired
    store2.update_settings({"trial_days": 0})
    ent_zero = store2.get_entitlements("uid-t2", "novo2@teste.com", supabase_enabled=True)
    assert ent_zero["status"] == "expired"
    assert ent_zero["has_access"] is False

    # Delete custom plan
    assert store2.delete_plan("vip_scalper") is True
    assert all(p["plan_id"] != "vip_scalper" for p in store2.list_plans())


def test_kiwify_webhook_lifecycle_and_signature(tmp_path: Path) -> None:
    store = SaasStore(tmp_path / "saas_state.json")
    store.update_settings({"kiwify_webhook_secret": "segredo_kiwify_99"})
    store.save_plan(
        {
            "plan_id": "pro",
            "name": "Pro",
            "price_brl": 197.0,
            "billing_cycle": "monthly",
            "kiwify_product_id": "prod_kw_pro",
            "max_bots": 10,
            "allow_real_trading": True,
            "allowed_features": ["backtest", "custom_strategies", "market_radar", "real_trading"],
            "active": True,
        }
    )

    payload_approve = {
        "webhook_event_type": "order_approved",
        "order_id": "ord-100",
        "subscription_id": "sub-100",
        "Customer": {"email": "Comprador@Teste.com", "full_name": "Comprador Teste"},
        "Product": {"product_id": "prod_kw_pro", "product_name": "Quantix Pro"},
    }

    # Wrong token rejected
    code_bad, res_bad = store.handle_kiwify_webhook(payload_approve, provided_token="errado")
    assert code_bad == 401
    assert res_bad["ok"] is False

    # Valid token activates Pro subscription even before first login
    code_ok, res_ok = store.handle_kiwify_webhook(payload_approve, provided_token="segredo_kiwify_99")
    assert code_ok == 200
    assert res_ok["ok"] is True
    assert res_ok["revoked"] is False
    assert res_ok["plan_id"] == "pro"

    ent = store.get_entitlements("uid-comprador", "comprador@teste.com", supabase_enabled=True)
    assert ent["status"] == "active"
    assert ent["plan_id"] == "pro"
    assert ent["allow_real_trading"] is True
    assert ent["max_bots"] == 10
    assert ent["days_left"] >= 29

    # Renewal extends period
    code_ren, _ = store.handle_kiwify_webhook(
        {**payload_approve, "webhook_event_type": "subscription_renewed"},
        provided_token="segredo_kiwify_99",
    )
    assert code_ren == 200

    # Cancel/refund revokes access
    code_can, res_can = store.handle_kiwify_webhook(
        {**payload_approve, "webhook_event_type": "subscription_canceled"},
        provided_token="segredo_kiwify_99",
    )
    assert code_can == 200
    assert res_can["revoked"] is True

    ent_after = store.get_entitlements("uid-comprador", "comprador@teste.com", supabase_enabled=True)
    assert ent_after["has_access"] is False
    assert ent_after["status"] == "canceled"


# ---------------------------------------------------------------------------
# Web App Routes, Admin Gating & Plan Enforcement
# ---------------------------------------------------------------------------


def test_web_app_admin_routes_plan_gating_and_webhook_bot_pause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CTRADER_CLIENT_ID", "central_cid")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "central_csec")

    fake_sb = _FakeMultiTenantSupabase()
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=fake_sb)  # type: ignore[arg-type]

    # Public plans route works without auth
    code_pub, body_pub, _ = app.handle_request("GET", "/api/plans/public", {})
    assert code_pub == 200
    pub_json = json.loads(body_pub)
    assert pub_json["trial_days"] == 7
    assert len(pub_json["plans"]) >= 3

    admin_cookie = _login_cookie(app, "sitepixer@gmail.com")
    client_cookie = _login_cookie(app, "cliente@teste.com")

    # /api/me distinguishes super-admin vs normal client + exposes server_oauth_configured
    c_me_adm, b_me_adm, _ = app.handle_request("GET", "/api/me", {"Cookie": admin_cookie})
    assert c_me_adm == 200
    me_adm = json.loads(b_me_adm)
    assert me_adm["is_admin"] is True
    assert me_adm["server_oauth_configured"] is True

    c_me_cli, b_me_cli, _ = app.handle_request("GET", "/api/me", {"Cookie": client_cookie})
    assert c_me_cli == 200
    me_cli = json.loads(b_me_cli)
    assert me_cli["is_admin"] is False
    assert me_cli["server_oauth_configured"] is True
    assert me_cli["entitlements"]["status"] == "trial"
    assert me_cli["entitlements"]["days_left"] == 7

    # Non-admin blocked from admin endpoints
    c_forb, _, _ = app.handle_request("GET", "/api/admin/overview", {"Cookie": client_cookie})
    assert c_forb == 403
    c_forb2, _, _ = app.handle_request(
        "POST",
        "/api/admin/settings",
        {"Cookie": client_cookie},
        json.dumps({"trial_days": 99}).encode(),
    )
    assert c_forb2 == 403

    # Admin updates Starter plan with Kiwify ID & 2-bot limit (no backtest, no python, no news) and configures Kiwify secret
    app.handle_request(
        "POST",
        "/api/admin/settings",
        {"Cookie": admin_cookie},
        json.dumps({"trial_days": 5, "kiwify_webhook_secret": "tok_kw_admin"}).encode(),
    )
    c_plan, _, _ = app.handle_request(
        "POST",
        "/api/admin/plans",
        {"Cookie": admin_cookie},
        json.dumps(
            {
                "plan_id": "starter",
                "name": "Starter",
                "price_brl": 97,
                "kiwify_product_id": "kw_starter_id",
                "max_bots": 2,
                "allow_real_trading": False,
                "allowed_features": [],
                "active": True,
            }
        ).encode(),
    )
    assert c_plan == 200

    # Assign client explicitly to Starter active plan
    c_sub, _, _ = app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "cliente@teste.com", "plan_id": "starter", "status": "active", "duration_days": 30}).encode(),
    )
    assert c_sub == 200

    # Client can create 2 bots, 3rd returns 403
    bot_payload = json.dumps({"name": "Bot 1", "symbol": "EURUSD", "lot_size": 0.01}).encode()
    assert app.handle_request("POST", "/api/bots", {"Cookie": client_cookie}, bot_payload)[0] == 200
    bot_payload2 = json.dumps({"name": "Bot 2", "symbol": "GBPUSD", "lot_size": 0.01}).encode()
    assert app.handle_request("POST", "/api/bots", {"Cookie": client_cookie}, bot_payload2)[0] == 200
    bot_payload3 = json.dumps({"name": "Bot 3", "symbol": "XAUUSD", "lot_size": 0.01}).encode()
    c_b3, b_b3, _ = app.handle_request("POST", "/api/bots", {"Cookie": client_cookie}, bot_payload3)
    assert c_b3 == 403
    assert "Starter" in json.loads(b_b3)["error"]

    # Client blocked from Backtest, Custom Templates, News, Real Trading
    assert (
        app.handle_request(
            "POST",
            "/api/backtest",
            {"Cookie": client_cookie},
            json.dumps({"symbol": "EURUSD", "ticks": 100}).encode(),
        )[0]
        == 403
    )
    assert (
        app.handle_request(
            "POST",
            "/api/bot-templates",
            {"Cookie": client_cookie},
            json.dumps({"name": "Custom 1", "engine_type": "CUSTOM_INDICATORS"}).encode(),
        )[0]
        == 403
    )
    assert app.handle_request("POST", "/api/news/scan", {"Cookie": client_cookie}, b"{}")[0] == 403
    assert (
        app.handle_request(
            "POST",
            "/api/config",
            {"Cookie": client_cookie},
            json.dumps({"allow_real_trading": True}).encode(),
        )[0]
        == 403
    )

    # Super-Admin bypasses all feature/bot restrictions even if tests create more bots or run backtest
    assert (
        app.handle_request(
            "POST",
            "/api/backtest",
            {"Cookie": admin_cookie},
            json.dumps({"symbol": "EURUSD", "ticks": 100}).encode(),
        )[0]
        == 200
    )

    # Kiwify webhook cancellation pauses client's running bots and blocks future bot start while keeping flatten open
    c_wh, b_wh, _ = app.handle_request(
        "POST",
        "/api/webhooks/kiwify?token=tok_kw_admin",
        {},
        json.dumps(
            {
                "webhook_event_type": "subscription_canceled",
                "Customer": {"email": "cliente@teste.com"},
                "Product": {"product_id": "kw_starter_id"},
            }
        ).encode(),
    )
    assert c_wh == 200
    assert json.loads(b_wh)["revoked"] is True

    cli_svc = app._active_service("uid-client")
    assert all(b.get("active") is False for b in cli_svc.cfg.bots)

    # Cannot start bot when canceled, CAN flatten safely
    first_bot_id = cli_svc.cfg.bots[0]["bot_id"]
    c_start, _, _ = app.handle_request(
        "POST",
        "/api/bots/action",
        {"Cookie": client_cookie},
        json.dumps({"bot_id": first_bot_id, "action": "START"}).encode(),
    )
    assert c_start == 403
    c_flat, _, _ = app.handle_request("POST", "/api/flatten", {"Cookie": client_cookie}, b"{}")
    assert c_flat == 200
    assert len(ALL_FEATURES) == 7


def test_admin_overview_handles_supabase_iso_timestamps_and_malformed_values(tmp_path: Path) -> None:
    class _IsoPostgresSupabase(_FakeMultiTenantSupabase):
        def load_saas_tables(self) -> dict | None:
            return {
                "settings": {
                    "id": "default",
                    "trial_days": 7,
                    "trial_allow_real_trading": False,
                    "default_trial_plan_id": "pro",
                    "kiwify_webhook_secret": "sec_pg",
                    "updated_at": "2026-11-26 14:01:27.583643+00",
                },
                "plans": [
                    {
                        "plan_id": "starter",
                        "name": "Starter",
                        "price_brl": 97.0,
                        "max_bots": 2,
                        "allow_real_trading": True,
                        "allowed_features": ["real_trading"],
                        "active": True,
                        "sort_order": 1,
                        "updated_at": "2026-11-26T14:01:27+00:00",
                    },
                    {
                        "plan_id": "pro",
                        "name": "Pro",
                        "price_brl": 197.0,
                        "max_bots": 10,
                        "allow_real_trading": True,
                        "allowed_features": ["real_trading", "backtest"],
                        "active": True,
                        "sort_order": 2,
                        "updated_at": "2026-11-26T14:01:27+00:00",
                    },
                    {
                        "plan_id": "institutional",
                        "name": "Elite",
                        "price_brl": 397.0,
                        "max_bots": 50,
                        "allow_real_trading": True,
                        "allowed_features": list(ALL_FEATURES),
                        "active": True,
                        "sort_order": 3,
                        "updated_at": "2026-11-26T14:01:27+00:00",
                    },
                ],
                "subscriptions": [
                    {
                        "email": "sitepixer@gmail.com",
                        "user_id": "uid-admin",
                        "plan_id": "pro",
                        "status": "trial",
                        "trial_ends_at": 1796308849.99375,
                        "current_period_end": 0,
                        "updated_at": "2026-11-26 14:40:50.05518+00",
                    },
                    {
                        "email": "vip@teste.com",
                        "user_id": "uid-vip",
                        "plan_id": "pro",
                        "status": "trial",
                        "trial_ends_at": 1796308849.99375,
                        "current_period_end": 0,
                        "updated_at": "2026-11-26 14:40:50.05518+00",
                    },
                    {
                        "email": "cliente@teste.com",
                        "user_id": "uid-client",
                        "plan_id": "pro",
                        "status": "trial",
                        "trial_ends_at": "2026-12-03T15:10:00+00:00",
                        "current_period_end": 0,
                        "updated_at": "2026-11-26T15:10:00Z",
                    },
                    {
                        "email": "antigo@teste.com",
                        "user_id": "uid-old",
                        "plan_id": "starter",
                        "status": "expired",
                        "trial_ends_at": None,
                        "current_period_end": None,
                        "updated_at": "not-a-timestamp",
                    },
                ],
            }

    sb = _IsoPostgresSupabase()
    cfg_path = tmp_path / "config.json"
    app = PradoWebApp(config_path=cfg_path, supabase_store=sb)  # type: ignore[arg-type]
    admin_cookie = _login_cookie(app, "sitepixer@gmail.com")

    code, raw_body, _ = app.handle_request("GET", "/api/admin/overview", {"Cookie": admin_cookie})
    assert code == 200
    body = json.loads(raw_body)
    assert body["ok"] is True
    assert len(body["plans"]) == 3
    assert len(body["subscriptions"]) == 3
    assert [s["email"] for s in body["subscriptions"]] == [
        "cliente@teste.com",
        "vip@teste.com",
        "antigo@teste.com",
    ]
    assert all(s["email"] != "sitepixer@gmail.com" for s in body["subscriptions"])
    for sub in body["subscriptions"]:
        assert isinstance(sub["updated_at"], float)
        assert sub["updated_at"] >= 0.0

    # Simulate reloading SaasStore from an already-corrupted local saas_state.json on disk
    dirty_state_path = tmp_path / "dirty_saas_state.json"
    dirty_state_path.write_text(
        json.dumps(
            {
                "settings": {"trial_days": 7},
                "plans": [],
                "subscriptions": {
                    "vip@teste.com": {
                        "email": "vip@teste.com",
                        "plan_id": "pro",
                        "status": "trial",
                        "trial_ends_at": "2026-12-03T15:10:00+00:00",
                        "current_period_end": None,
                        "updated_at": "2026-11-26 14:40:50.05518+00",
                    }
                },
                "webhook_logs": [],
            }
        ),
        encoding="utf-8",
    )
    reloaded = SaasStore(dirty_state_path)
    reloaded_subs = reloaded.list_subscriptions()
    assert len(reloaded_subs) == 1
    assert isinstance(reloaded_subs[0]["updated_at"], float)
    assert reloaded_subs[0]["updated_at"] > 0.0

    # Test admin_upsert_subscription and get_entitlements on ISO-hydrated client record
    ent = app.saas.get_entitlements("uid-client", "cliente@teste.com", supabase_enabled=True)
    assert ent["plan_id"] == "pro"
    assert isinstance(ent["trial_ends_at"], float)

    updated = app.saas.admin_upsert_subscription(
        {"email": "cliente@teste.com", "plan_id": "pro", "add_trial_days": 5}
    )
    assert updated["status"] == "trial"
    assert isinstance(updated["trial_ends_at"], float)
