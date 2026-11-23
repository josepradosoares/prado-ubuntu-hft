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

from prado_linux.config import DEFAULT_CATEGORIES, PradoServerConfig, load_config
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
        cfg = load_config(fallback_path)
        uid_q = quote(user_id, safe="")

        code, settings_rows = self._request(
            "GET",
            f"/rest/v1/prado_settings?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code == 200 and isinstance(settings_rows, list) and settings_rows:
            s = settings_rows[0]
            cfg.connection_mode = str(s.get("connection_mode") or cfg.connection_mode)
            cfg.allow_real_trading = bool(s.get("allow_real_trading", False))
            cfg.auto_trading_enabled = bool(s.get("auto_trading_enabled", True))
            cfg.active_account_id = str(s.get("active_account_id") or "")
            cfg.active_account_type = str(s.get("active_account_type") or "DEMO")
            cfg.deriv_app_id = str(s.get("deriv_app_id") or "1089")
            cfg.default_stake_usd = float(s.get("default_stake_usd") or 10.0)
            cfg.default_multiplier = int(s.get("default_multiplier") or 100)
            if isinstance(s.get("active_symbols"), list) and s["active_symbols"]:
                cfg.active_symbols = list(s["active_symbols"])
            if isinstance(s.get("correlated_basket"), list):
                cfg.correlated_basket = list(s["correlated_basket"])
            if isinstance(s.get("custom_categories"), dict) and s["custom_categories"]:
                cfg.custom_categories = dict(s["custom_categories"])
            else:
                cfg.custom_categories = dict(DEFAULT_CATEGORIES)

        code_acc, acc_rows = self._request(
            "GET",
            f"/rest/v1/prado_deriv_accounts?user_id=eq.{uid_q}&select=*",
            bearer_token=access_token,
        )
        if code_acc == 200 and isinstance(acc_rows, list):
            cfg.accounts = [
                {
                    "account_id": str(r.get("account_id") or ""),
                    "account_type": str(r.get("account_type") or "DEMO"),
                    "label": str(r.get("label") or "Deriv"),
                    "deriv_token": str(r.get("deriv_token") or ""),
                    "deriv_app_id": str(r.get("deriv_app_id") or "1089"),
                    "default_stake_usd": float(r.get("default_stake_usd") or 10.0),
                    "default_multiplier": int(r.get("default_multiplier") or 100),
                    "connection_mode": str(r.get("connection_mode") or "DERIV_CLOUD"),
                    "loginid": str(r.get("loginid") or ""),
                }
                for r in acc_rows
            ]
            active = next((a for a in cfg.accounts if a["account_id"] == cfg.active_account_id), None)
            if active:
                cfg.deriv_token = active["deriv_token"]
                cfg.deriv_app_id = active["deriv_app_id"]

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
                        "symbol": str(r.get("symbol") or "R_100"),
                        "template_id": str(r.get("template_id") or "WALL_STREET_HYBRID_BOTH"),
                        "bot_template_id": str(r.get("template_id") or "WALL_STREET_HYBRID_BOTH"),
                        "operation_mode": str(r.get("operation_mode") or "BOTH"),
                        "timeframe": str(r.get("timeframe") or "TICKS"),
                        "news_assisted": bool(r.get("news_assisted", False)),
                        "loss_guard_enabled": bool(r.get("loss_guard_enabled", False)),
                        "max_loss_usd": float(r.get("max_loss_usd") or 20.0),
                        "status": str(r.get("status") or "STOPPED"),
                        "active": str(r.get("status") or "STOPPED") == "RUNNING",
                        "lot_size": float(r.get("lot_size") or 10.0),
                        "multiplier": int(r.get("multiplier") or 100),
                        "realized_pnl": float(r.get("realized_pnl") or 0.0),
                        "floating_pnl": float(r.get("floating_pnl") or 0.0),
                        "total_pnl": float(r.get("total_pnl") or 0.0),
                        "trades_executed": int(r.get("trades_executed") or 0),
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
                    "default_symbol": str(r.get("default_symbol") or "ALL"),
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
                "deriv_app_id": cfg.deriv_app_id,
                "default_stake_usd": float(cfg.default_stake_usd),
                "default_multiplier": int(cfg.default_multiplier),
                "active_symbols": list(cfg.active_symbols),
                "correlated_basket": list(cfg.correlated_basket),
                "custom_categories": dict(cfg.custom_categories),
                "risk_config": {
                    "max_daily_loss_money": cfg.max_daily_loss_money,
                    "daily_target_money": cfg.daily_target_money,
                    "max_stake_per_trade": cfg.max_stake_per_trade,
                    "max_concurrent_trades": cfg.max_concurrent_trades,
                    "max_total_exposure_usd": cfg.max_total_exposure_usd,
                },
                "news_config": {
                    "news_bot_enabled": cfg.news_bot_enabled,
                    "news_pause_grid_on_high_impact": cfg.news_pause_grid_on_high_impact,
                    "news_auto_trade_enabled": cfg.news_auto_trade_enabled,
                },
            },
            bearer_token=access_token,
            extra_headers=upsert_headers,
        )

        # Sync accounts
        if cfg.accounts:
            acc_payload = [
                {
                    "user_id": user_id,
                    "account_id": str(a.get("account_id") or ""),
                    "account_type": str(a.get("account_type") or "DEMO"),
                    "label": str(a.get("label") or "Deriv"),
                    "deriv_token": str(a.get("deriv_token") or ""),
                    "deriv_app_id": str(a.get("deriv_app_id") or "1089"),
                    "default_stake_usd": float(a.get("default_stake_usd") or 10.0),
                    "default_multiplier": int(a.get("default_multiplier") or 100),
                    "connection_mode": str(a.get("connection_mode") or "DERIV_CLOUD"),
                    "loginid": str(a.get("loginid") or ""),
                }
                for a in cfg.accounts
                if a.get("account_id")
            ]
            if acc_payload:
                self._request(
                    "POST",
                    "/rest/v1/prado_deriv_accounts?on_conflict=user_id,account_id",
                    acc_payload,
                    bearer_token=access_token,
                    extra_headers=upsert_headers,
                )

        # Sync bots (replace user's bot list cleanly)
        self._request("DELETE", f"/rest/v1/prado_bots?user_id=eq.{uid_q}", bearer_token=access_token)
        if cfg.bots:
            bot_rows = [
                {
                    "bot_id": str(b.get("bot_id") or ""),
                    "user_id": user_id,
                    "name": str(b.get("name") or ""),
                    "account_id": str(b.get("account_id") or ""),
                    "symbol": str(b.get("symbol") or "R_100"),
                    "template_id": str(b.get("template_id") or b.get("bot_template_id") or "WALL_STREET_HYBRID_BOTH"),
                    "operation_mode": str(b.get("operation_mode") or "BOTH"),
                    "timeframe": str(b.get("timeframe") or "TICKS"),
                    "news_assisted": bool(b.get("news_assisted", False)),
                    "loss_guard_enabled": bool(b.get("loss_guard_enabled", False)),
                    "max_loss_usd": float(b.get("max_loss_usd") or 20.0),
                    "status": str(b.get("status") or "STOPPED"),
                    "lot_size": float(b.get("lot_size") or 10.0),
                    "multiplier": int(b.get("multiplier") or 100),
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
