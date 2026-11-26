"""Zero-dependency Supabase Auth & PostgREST persistence store for Prado Ubuntu HFT."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from prado_linux.config import DEFAULT_CATEGORIES, PradoServerConfig, load_config, migrate_legacy_symbol
from prado_linux.news_scout import DEFAULT_NEWS_FEEDS


def _read_dotenv_fallback() -> dict[str, str]:
    env_map: dict[str, str] = {}
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                env_map[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env_map


@dataclass
class SupabaseConfig:
    url: str = ""
    anon_key: str = ""
    service_role_key: str = ""

    @property
    def is_enabled(self) -> bool:
        return bool(self.url and (self.anon_key or self.service_role_key))

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        dotenv = _read_dotenv_fallback()

        def _get(name: str) -> str:
            return (os.environ.get(name) or dotenv.get(name) or "").strip()

        url = _get("SUPABASE_URL").rstrip("/")
        anon = _get("SUPABASE_ANON_KEY") or _get("SUPABASE_PUBLISHABLE_KEY")
        service = _get("SUPABASE_SERVICE_ROLE_KEY")
        return cls(url=url, anon_key=anon, service_role_key=service)


class SupabaseStore:
    """Lightweight REST client for Supabase Auth + PostgREST tables."""

    def __init__(self, cfg: SupabaseConfig) -> None:
        self.cfg = cfg

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        return cls(SupabaseConfig.from_env())

    @property
    def is_enabled(self) -> bool:
        return self.cfg.is_enabled

    def _api_key(self) -> str:
        return self.cfg.anon_key or self.cfg.service_role_key

    def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        bearer_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.cfg.url}{path}"
        headers: dict[str, str] = {
            "apikey": self._api_key(),
            "Content-Type": "application/json",
        }
        tok = bearer_token or self.cfg.service_role_key or self._api_key()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urlopen(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return resp.status, (json.loads(raw) if raw.strip() else {})
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw.strip() else {"error": str(exc)}
            except Exception:
                parsed = {"error": raw or str(exc)}
            return exc.code, parsed
        except (URLError, OSError, TimeoutError) as exc:
            return 503, {"error": f"Falha de rede Supabase: {exc}"}

    def sign_up(self, email: str, password: str) -> tuple[bool, dict[str, Any]]:
        code, data = self._request("POST", "/auth/v1/signup", {"email": email, "password": password})
        if 200 <= code < 300 and isinstance(data, dict):
            user = data.get("user") or {}
            return True, {
                "user_id": str(user.get("id") or data.get("id") or ""),
                "email": str(user.get("email") or email),
                "access_token": str(data.get("access_token") or ""),
            }
        msg = str(data.get("msg") or data.get("error_description") or data.get("error") or "Falha ao criar conta.")
        return False, {"error": msg}

    def sign_in(self, email: str, password: str) -> tuple[bool, dict[str, Any]]:
        code, data = self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
        )
        if 200 <= code < 300 and isinstance(data, dict) and data.get("access_token"):
            user = data.get("user") or {}
            return True, {
                "user_id": str(user.get("id") or ""),
                "email": str(user.get("email") or email),
                "access_token": str(data.get("access_token") or ""),
            }
        msg = str(data.get("error_description") or data.get("msg") or data.get("error") or "Credenciais inválidas.")
        return False, {"error": msg}

    def load_user_config(self, user_id: str, access_token: str, fallback_path: Path) -> PradoServerConfig:
        cfg = load_config(fallback_path, inherit_user_tokens=False)
        uid_q = quote(user_id, safe="")

        code, settings_rows = self._request(
            "GET",
            f"/rest/v1/prado_settings?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code == 200 and isinstance(settings_rows, list) and settings_rows:
            s = settings_rows[0]
            raw_mode = str(s.get("connection_mode") or cfg.connection_mode)
            cfg.connection_mode = "CTRADER_CLOUD" if raw_mode == "DERIV_CLOUD" else raw_mode
            cfg.allow_real_trading = bool(s.get("allow_real_trading", False))
            cfg.auto_trading_enabled = bool(s.get("auto_trading_enabled", True))
            cfg.active_account_id = str(s.get("active_account_id") or "")
            cfg.active_account_type = str(s.get("active_account_type") or "DEMO")
            cfg.ctrader_client_id = str(s.get("ctrader_client_id") or cfg.ctrader_client_id)
            cfg.ctrader_redirect_uri = str(s.get("ctrader_redirect_uri") or cfg.ctrader_redirect_uri)
            cfg.default_lot_size = max(0.01, float(s.get("default_lot_size") or 0.01))
            if isinstance(s.get("active_symbols"), list) and s["active_symbols"]:
                cfg.active_symbols = [migrate_legacy_symbol(x) for x in s["active_symbols"]]
            if isinstance(s.get("correlated_basket"), list):
                cfg.correlated_basket = [migrate_legacy_symbol(x, "GBPUSD") for x in s["correlated_basket"]]
            if isinstance(s.get("custom_categories"), dict) and s["custom_categories"]:
                cfg.custom_categories = dict(s["custom_categories"])
            else:
                cfg.custom_categories = dict(DEFAULT_CATEGORIES)
            nc = s.get("news_config")
            if isinstance(nc, dict):
                if "news_bot_enabled" in nc:
                    cfg.news_bot_enabled = bool(nc.get("news_bot_enabled"))
                if "news_pause_grid_on_high_impact" in nc:
                    cfg.news_pause_grid_on_high_impact = bool(nc.get("news_pause_grid_on_high_impact"))
                if "news_auto_trade_enabled" in nc:
                    cfg.news_auto_trade_enabled = bool(nc.get("news_auto_trade_enabled"))
                if nc.get("news_poll_interval_sec") is not None:
                    cfg.news_poll_interval_sec = max(30, int(nc.get("news_poll_interval_sec") or 90))
                if "news_calendar_shield_enabled" in nc:
                    cfg.news_calendar_shield_enabled = bool(nc.get("news_calendar_shield_enabled"))
                if nc.get("news_calendar_pause_minutes") is not None:
                    cfg.news_calendar_pause_minutes = max(5, min(60, int(nc.get("news_calendar_pause_minutes") or 15)))
                if "news_filter_only" in nc:
                    cfg.news_filter_only = bool(nc.get("news_filter_only"))
                if "news_ai_enabled" in nc:
                    cfg.news_ai_enabled = bool(nc.get("news_ai_enabled"))
                if nc.get("news_ai_provider"):
                    cfg.news_ai_provider = str(nc.get("news_ai_provider") or "gemini")
                if nc.get("news_ai_model"):
                    cfg.news_ai_model = str(nc.get("news_ai_model") or "gemini-2.0-flash")
                if "news_ai_api_key" in nc:
                    cfg.news_ai_api_key = str(nc.get("news_ai_api_key") or "")
                if "news_ai_base_url" in nc:
                    cfg.news_ai_base_url = str(nc.get("news_ai_base_url") or "")

        code_acc, acc_rows = self._request(
            "GET",
            f"/rest/v1/prado_ctrader_accounts?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code_acc == 200 and isinstance(acc_rows, list):
            cfg.accounts = [
                {
                    "account_id": str(r.get("account_id") or ""),
                    "ctid_account_id": str(r.get("ctid_account_id") or ""),
                    "trader_login": str(r.get("trader_login") or ""),
                    "account_type": str(r.get("account_type") or "DEMO"),
                    "is_live": bool(r.get("is_live", False)),
                    "broker_name": str(r.get("broker_name") or "cTrader"),
                    "label": str(r.get("label") or "cTrader"),
                    "access_token": str(r.get("access_token") or ""),
                    "refresh_token": str(r.get("refresh_token") or ""),
                    "default_lot_size": max(0.01, float(r.get("default_lot_size") or 0.01)),
                    "connection_mode": str(r.get("connection_mode") or "CTRADER_CLOUD"),
                    "balance": float(r.get("balance") or 0.0),
                    "currency": str(r.get("currency") or "USD"),
                }
                for r in acc_rows
            ]
            active = next((a for a in cfg.accounts if a["account_id"] == cfg.active_account_id), None)
            if active:
                cfg.ctrader_access_token = active["access_token"]
                cfg.ctrader_refresh_token = active["refresh_token"]

        code_bots, bot_rows = self._request(
            "GET",
            f"/rest/v1/prado_bots?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code_bots == 200 and isinstance(bot_rows, list):
            loaded_bots: list[dict[str, Any]] = []
            for r in bot_rows:
                raw_cj = r.get("config_json")
                rec = dict(raw_cj) if isinstance(raw_cj, dict) else {}
                rec.update(
                    {
                        "bot_id": str(r.get("bot_id") or ""),
                        "name": str(r.get("name") or ""),
                        "account_id": str(r.get("account_id") or ""),
                        "symbol": migrate_legacy_symbol(str(r.get("symbol") or "EURUSD")),
                        "template_id": str(r.get("template_id") or "WALL_STREET_HYBRID_BOTH"),
                        "bot_template_id": str(r.get("template_id") or "WALL_STREET_HYBRID_BOTH"),
                        "operation_mode": str(r.get("operation_mode") or "BOTH"),
                        "timeframe": str(r.get("timeframe") or "TICKS"),
                        "news_assisted": bool(r.get("news_assisted", False)),
                        "loss_guard_enabled": bool(r.get("loss_guard_enabled", False)),
                        "max_loss_usd": float(r.get("max_loss_usd") or 20.0),
                        "status": str(r.get("status") or "STOPPED"),
                        "active": str(r.get("status") or "STOPPED") == "RUNNING",
                        "lot_size": max(0.01, float(r.get("lot_size") or 0.01)),
                        "realized_pnl": float(r.get("realized_pnl") or 0.0),
                        "floating_pnl": float(r.get("floating_pnl") or 0.0),
                        "total_pnl": float(r.get("total_pnl") or 0.0),
                        "trades_executed": int(r.get("trades_executed") or 0),
                        "sl_sigma_mult": float(rec.get("sl_sigma_mult") or 1.0),
                        "tp_sigma_mult": float(rec.get("tp_sigma_mult") or 1.8),
                        "tp_mode": str(rec.get("tp_mode") or "AUTO").upper(),
                        "tp_value": float(rec.get("tp_value") or 0.0),
                    }
                )
                loaded_bots.append(rec)
            cfg.bots = loaded_bots

        code_tpl, tpl_rows = self._request(
            "GET",
            f"/rest/v1/prado_custom_templates?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code_tpl == 200 and isinstance(tpl_rows, list):
            loaded_tpls: list[dict[str, Any]] = []
            for r in tpl_rows:
                raw_cj = r.get("config_json")
                cj = raw_cj if isinstance(raw_cj, dict) else {}
                loaded_tpls.append(
                    {
                        **cj,
                        "template_id": str(r.get("template_id") or ""),
                        "name": str(r.get("name") or ""),
                        "description": str(r.get("description") or ""),
                        "operation_mode": str(cj.get("operation_mode") or "CUSTOM"),
                        "custom_mode": str(r.get("custom_mode") or "INDICATORS"),
                        "combine_mode": str(r.get("combine_mode") or "MAJORITY"),
                        "formula": str(r.get("formula") or ""),
                        "indicators": list(r.get("indicators") or []),
                        "python_code": str(r.get("python_code") or ""),
                        "window_ticks": max(20, int(cj.get("window_ticks") or 120)),
                        "zscore_threshold": float(cj.get("zscore_threshold") if cj.get("zscore_threshold") is not None else 1.8),
                        "imbalance_threshold": float(cj.get("imbalance_threshold") if cj.get("imbalance_threshold") is not None else 0.35),
                        "revert_sigma": float(cj.get("revert_sigma") if cj.get("revert_sigma") is not None else 2.0),
                        "sl_sigma_mult": float(cj.get("sl_sigma_mult") or 1.0),
                        "tp_sigma_mult": float(cj.get("tp_sigma_mult") or 1.8),
                        "is_custom": True,
                    }
                )
            cfg.custom_templates = loaded_tpls

        code_feeds, feed_rows = self._request(
            "GET",
            f"/rest/v1/prado_news_feeds?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code_feeds == 200 and isinstance(feed_rows, list) and feed_rows:
            cfg.news_feeds = [
                {
                    "feed_id": str(r.get("feed_id") or ""),
                    "source": str(r.get("source") or ""),
                    "url": str(r.get("url") or ""),
                    "default_symbol": migrate_legacy_symbol(str(r.get("default_symbol") or "ALL")),
                }
                for r in feed_rows
            ]
        elif not cfg.news_feeds:
            cfg.news_feeds = [dict(f) for f in DEFAULT_NEWS_FEEDS]

        return cfg

    def sync_user_config(self, user_id: str, access_token: str, cfg: PradoServerConfig) -> None:
        if not self.is_enabled or not user_id:
            return
        uid_q = quote(user_id, safe="")
        upsert_headers = {"Prefer": "resolution=merge-duplicates,return=minimal"}

        self._request(
            "POST",
            "/rest/v1/prado_settings?on_conflict=user_id",
            {
                "user_id": user_id,
                "connection_mode": cfg.connection_mode,
                "allow_real_trading": bool(cfg.allow_real_trading),
                "auto_trading_enabled": bool(cfg.auto_trading_enabled),
                "active_account_id": cfg.active_account_id,
                "active_account_type": cfg.active_account_type,
                "ctrader_client_id": cfg.ctrader_client_id,
                "ctrader_redirect_uri": cfg.ctrader_redirect_uri,
                "default_lot_size": float(cfg.default_lot_size),
                "active_symbols": list(cfg.active_symbols),
                "correlated_basket": list(cfg.correlated_basket),
                "custom_categories": dict(cfg.custom_categories),
                "risk_config": {
                    "max_daily_loss_money": cfg.max_daily_loss_money,
                    "daily_target_money": cfg.daily_target_money,
                    "max_lot_per_trade": cfg.max_lot_per_trade,
                    "max_concurrent_trades": cfg.max_concurrent_trades,
                    "max_total_lots": cfg.max_total_lots,
                },
                "news_config": {
                    "news_bot_enabled": cfg.news_bot_enabled,
                    "news_pause_grid_on_high_impact": cfg.news_pause_grid_on_high_impact,
                    "news_auto_trade_enabled": cfg.news_auto_trade_enabled,
                    "news_poll_interval_sec": cfg.news_poll_interval_sec,
                    "news_calendar_shield_enabled": cfg.news_calendar_shield_enabled,
                    "news_calendar_pause_minutes": cfg.news_calendar_pause_minutes,
                    "news_filter_only": cfg.news_filter_only,
                    "news_ai_enabled": cfg.news_ai_enabled,
                    "news_ai_provider": cfg.news_ai_provider,
                    "news_ai_model": cfg.news_ai_model,
                    "news_ai_api_key": cfg.news_ai_api_key,
                    "news_ai_base_url": cfg.news_ai_base_url,
                },
            },
            bearer_token=access_token,
            extra_headers=upsert_headers,
        )

        # Sync cTrader accounts
        if cfg.accounts:
            acc_payload = [
                {
                    "user_id": user_id,
                    "account_id": str(a.get("account_id") or ""),
                    "ctid_account_id": str(a.get("ctid_account_id") or ""),
                    "trader_login": str(a.get("trader_login") or ""),
                    "account_type": str(a.get("account_type") or "DEMO"),
                    "is_live": bool(a.get("is_live", False)),
                    "broker_name": str(a.get("broker_name") or "cTrader"),
                    "label": str(a.get("label") or "cTrader"),
                    "access_token": str(a.get("access_token") or ""),
                    "refresh_token": str(a.get("refresh_token") or ""),
                    "default_lot_size": float(a.get("default_lot_size") or 0.01),
                    "connection_mode": str(a.get("connection_mode") or "CTRADER_CLOUD"),
                    "balance": float(a.get("balance") or 0.0),
                    "currency": str(a.get("currency") or "USD"),
                }
                for a in cfg.accounts
                if a.get("account_id")
            ]
            if acc_payload:
                self._request(
                    "POST",
                    "/rest/v1/prado_ctrader_accounts?on_conflict=user_id,account_id",
                    acc_payload,
                    bearer_token=access_token,
                    extra_headers=upsert_headers,
                )

        # Sync bots
        self._request("DELETE", f"/rest/v1/prado_bots?user_id=eq.{uid_q}", bearer_token=access_token)
        if cfg.bots:
            bot_rows = [
                {
                    "bot_id": str(b.get("bot_id") or ""),
                    "user_id": user_id,
                    "name": str(b.get("name") or ""),
                    "account_id": str(b.get("account_id") or ""),
                    "symbol": str(b.get("symbol") or "EURUSD"),
                    "template_id": str(b.get("template_id") or b.get("bot_template_id") or "WALL_STREET_HYBRID_BOTH"),
                    "operation_mode": str(b.get("operation_mode") or "BOTH"),
                    "timeframe": str(b.get("timeframe") or "TICKS"),
                    "news_assisted": bool(b.get("news_assisted", False)),
                    "loss_guard_enabled": bool(b.get("loss_guard_enabled", False)),
                    "max_loss_usd": float(b.get("max_loss_usd") or 20.0),
                    "status": str(b.get("status") or "STOPPED"),
                    "lot_size": float(b.get("lot_size") or 0.01),
                    "realized_pnl": float(b.get("realized_pnl") or 0.0),
                    "floating_pnl": float(b.get("floating_pnl") or 0.0),
                    "total_pnl": float(b.get("total_pnl") or 0.0),
                    "trades_executed": int(b.get("trades_executed") or 0),
                    "config_json": b,
                }
                for b in cfg.bots
                if b.get("bot_id")
            ]
            if bot_rows:
                self._request(
                    "POST",
                    "/rest/v1/prado_bots",
                    bot_rows,
                    bearer_token=access_token,
                    extra_headers=upsert_headers,
                )

        # Sync custom templates
        self._request("DELETE", f"/rest/v1/prado_custom_templates?user_id=eq.{uid_q}", bearer_token=access_token)
        if cfg.custom_templates:
            tpl_rows = [
                {
                    "template_id": str(t.get("template_id") or ""),
                    "user_id": user_id,
                    "name": str(t.get("name") or ""),
                    "description": str(t.get("description") or ""),
                    "custom_mode": str(t.get("custom_mode") or "INDICATORS"),
                    "combine_mode": str(t.get("combine_mode") or "MAJORITY"),
                    "formula": str(t.get("formula") or ""),
                    "indicators": list(t.get("indicators") or []),
                    "python_code": str(t.get("python_code") or ""),
                    "config_json": t,
                }
                for t in cfg.custom_templates
                if t.get("template_id")
            ]
            if tpl_rows:
                self._request(
                    "POST",
                    "/rest/v1/prado_custom_templates",
                    tpl_rows,
                    bearer_token=access_token,
                    extra_headers=upsert_headers,
                )

        # Sync news feeds
        self._request("DELETE", f"/rest/v1/prado_news_feeds?user_id=eq.{uid_q}", bearer_token=access_token)
        if cfg.news_feeds:
            feed_rows = [
                {
                    "feed_id": str(f.get("feed_id") or ""),
                    "user_id": user_id,
                    "source": str(f.get("source") or ""),
                    "url": str(f.get("url") or ""),
                    "default_symbol": str(f.get("default_symbol") or "ALL"),
                }
                for f in cfg.news_feeds
                if f.get("feed_id")
            ]
            if feed_rows:
                self._request(
                    "POST",
                    "/rest/v1/prado_news_feeds",
                    feed_rows,
                    bearer_token=access_token,
                    extra_headers=upsert_headers,
                )

    # ------------------------------------------------------------------
    # SaaS Global Tables (Platform Settings, Plans, Subscriptions via service role)
    # ------------------------------------------------------------------

    def load_saas_tables(self) -> dict[str, Any] | None:
        if not self.is_enabled or not self.cfg.service_role_key:
            return None
        sr = self.cfg.service_role_key
        c_set, set_rows = self._request("GET", "/rest/v1/prado_platform_settings?id=eq.default&select=*", bearer_token=sr)
        c_pln, pln_rows = self._request("GET", "/rest/v1/prado_plans?select=*&order=sort_order.asc", bearer_token=sr)
        c_sub, sub_rows = self._request("GET", "/rest/v1/prado_subscriptions?select=*", bearer_token=sr)
        if not (200 <= c_set < 300 and 200 <= c_pln < 300 and 200 <= c_sub < 300):
            return None
        return {
            "settings": set_rows[0] if isinstance(set_rows, list) and set_rows else None,
            "plans": pln_rows if isinstance(pln_rows, list) else [],
            "subscriptions": sub_rows if isinstance(sub_rows, list) else [],
        }

    def upsert_saas_settings(self, settings_dict: dict[str, Any]) -> None:
        if not self.is_enabled or not self.cfg.service_role_key:
            return
        row = {
            "id": "default",
            "trial_days": int(settings_dict.get("trial_days", 7)),
            "trial_allow_real_trading": bool(settings_dict.get("trial_allow_real_trading", False)),
            "default_trial_plan_id": str(settings_dict.get("default_trial_plan_id") or "pro"),
            "kiwify_webhook_secret": str(settings_dict.get("kiwify_webhook_secret") or ""),
            "news_feeds": list(settings_dict.get("news_feeds") or []),
            "ai_news_enabled": bool(settings_dict.get("ai_news_enabled", False)),
            "ai_news_provider": str(settings_dict.get("ai_news_provider") or "gemini"),
            "ai_news_model": str(settings_dict.get("ai_news_model") or "gemini-2.0-flash"),
            "ai_news_api_key": str(settings_dict.get("ai_news_api_key") or ""),
        }
        self._request(
            "POST",
            "/rest/v1/prado_platform_settings?on_conflict=id",
            row,
            bearer_token=self.cfg.service_role_key,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    def upsert_saas_plan(self, plan_dict: dict[str, Any]) -> None:
        if not self.is_enabled or not self.cfg.service_role_key:
            return
        row = {
            "plan_id": str(plan_dict.get("plan_id") or ""),
            "name": str(plan_dict.get("name") or ""),
            "description": str(plan_dict.get("description") or ""),
            "price_brl": float(plan_dict.get("price_brl") or 0.0),
            "billing_cycle": str(plan_dict.get("billing_cycle") or "monthly"),
            "kiwify_product_id": str(plan_dict.get("kiwify_product_id") or ""),
            "kiwify_checkout_url": str(plan_dict.get("kiwify_checkout_url") or ""),
            "max_bots": int(plan_dict.get("max_bots") or 1),
            "allow_real_trading": bool(plan_dict.get("allow_real_trading", False)),
            "allowed_features": list(plan_dict.get("allowed_features") or []),
            "active": bool(plan_dict.get("active", True)),
            "sort_order": int(plan_dict.get("sort_order") or 0),
        }
        self._request(
            "POST",
            "/rest/v1/prado_plans?on_conflict=plan_id",
            row,
            bearer_token=self.cfg.service_role_key,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    def delete_saas_plan(self, plan_id: str) -> None:
        if not self.is_enabled or not self.cfg.service_role_key or not plan_id:
            return
        self._request(
            "DELETE",
            f"/rest/v1/prado_plans?plan_id=eq.{quote(plan_id, safe='')}",
            bearer_token=self.cfg.service_role_key,
        )

    def upsert_saas_subscription(self, sub_dict: dict[str, Any]) -> None:
        if not self.is_enabled or not self.cfg.service_role_key:
            return
        row = {
            "email": str(sub_dict.get("email") or "").lower(),
            "user_id": str(sub_dict.get("user_id") or ""),
            "plan_id": str(sub_dict.get("plan_id") or "starter"),
            "status": str(sub_dict.get("status") or "trial"),
            "trial_ends_at": float(sub_dict.get("trial_ends_at") or 0.0),
            "current_period_end": float(sub_dict.get("current_period_end") or 0.0),
            "kiwify_order_id": str(sub_dict.get("kiwify_order_id") or ""),
            "kiwify_subscription_id": str(sub_dict.get("kiwify_subscription_id") or ""),
            "kiwify_customer_name": str(sub_dict.get("kiwify_customer_name") or ""),
            "last_event": str(sub_dict.get("last_event") or ""),
        }
        self._request(
            "POST",
            "/rest/v1/prado_subscriptions?on_conflict=email",
            row,
            bearer_token=self.cfg.service_role_key,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
