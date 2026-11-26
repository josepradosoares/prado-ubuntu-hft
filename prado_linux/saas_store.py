"""Zero-dependency SaaS Plans, Trial Days, Admin Entitlements & Kiwify Webhook Store."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any

from prado_linux.news_scout import AI_PROVIDER_MAP, normalize_ai_provider

DEFAULT_ADMIN_EMAILS: set[str] = {"sitepixer@gmail.com"}

ALL_FEATURES: tuple[str, ...] = (
    "backtest",
    "custom_strategies",
    "python_code",
    "market_radar",
    "news_bot",
    "multi_accounts",
    "real_trading",
)

FEATURE_LABELS_PT: dict[str, str] = {
    "backtest": "Simulador Histórico (Backtest)",
    "custom_strategies": "Criar Estratégias Personalizadas",
    "python_code": "Estratégias em Código Python",
    "market_radar": "Radar de Mercado (VWAP / Z-Score)",
    "news_bot": "Robô e Monitor de Notícias",
    "multi_accounts": "Múltiplas Contas cTrader",
    "real_trading": "Negociação em Conta Real",
}

FEATURE_CATALOG: list[dict[str, str]] = [
    {"key": "real_trading", "label": FEATURE_LABELS_PT["real_trading"], "description": "Permite destravar envio de ordens em Conta Real"},
    {"key": "backtest", "label": FEATURE_LABELS_PT["backtest"], "description": "Acesso ao Simulador de histórico e curva de capital"},
    {"key": "custom_strategies", "label": FEATURE_LABELS_PT["custom_strategies"], "description": "Montar estratégias combinando indicadores no construtor"},
    {"key": "python_code", "label": FEATURE_LABELS_PT["python_code"], "description": "Escrever e testar scripts Python personalizados"},
    {"key": "market_radar", "label": FEATURE_LABELS_PT["market_radar"], "description": "Aba Radar de Mercado com matriz multi-ativos"},
    {"key": "news_bot", "label": FEATURE_LABELS_PT["news_bot"], "description": "Aba Notícias, leitura de feeds RSS e filtro de impacto"},
    {"key": "multi_accounts", "label": FEATURE_LABELS_PT["multi_accounts"], "description": "Conectar e alternar entre múltiplas contas cTrader manualmente"},
]

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "plan_id": "starter",
        "name": "Starter",
        "description": "Ideal para começar com estratégias prontas e até 2 robôs simultâneos.",
        "price_brl": 97.0,
        "billing_cycle": "monthly",
        "kiwify_product_id": "",
        "kiwify_checkout_url": "",
        "max_bots": 2,
        "allow_real_trading": True,
        "allowed_features": ["real_trading"],
        "active": True,
        "sort_order": 1,
    },
    {
        "plan_id": "pro",
        "name": "Pro",
        "description": "Para traders ativos: simulador histórico, radar de mercado, estratégias próprias e até 10 robôs.",
        "price_brl": 197.0,
        "billing_cycle": "monthly",
        "kiwify_product_id": "",
        "kiwify_checkout_url": "",
        "max_bots": 10,
        "allow_real_trading": True,
        "allowed_features": ["real_trading", "backtest", "custom_strategies", "market_radar", "multi_accounts"],
        "active": True,
        "sort_order": 2,
    },
    {
        "plan_id": "institutional",
        "name": "Elite",
        "description": "Acesso total: código Python, robô de notícias, múltiplas contas e até 50 robôs simultâneos.",
        "price_brl": 397.0,
        "billing_cycle": "monthly",
        "kiwify_product_id": "",
        "kiwify_checkout_url": "",
        "max_bots": 50,
        "allow_real_trading": True,
        "allowed_features": list(ALL_FEATURES),
        "active": True,
        "sort_order": 3,
    },
]

_APPROVE_EVENTS = {"order_approved", "paid", "approved", "subscription_renewed", "active"}
_REVOKE_EVENTS = {"subscription_canceled", "canceled", "cancelled", "subscription_late", "late", "order_refunded", "refunded", "chargeback", "refused"}
_IGNORE_EVENTS = {"boleto_gerado", "pix_gerado", "waiting_payment", "abandoned", "cart_abandoned"}


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return cleaned or f"plan_{int(time.time())}"


def _parse_ts(value: Any) -> float:
    """Parse float, numeric string, or Postgres/ISO-8601 timestamp safely (Python 3.10+ compatible)."""
    if value is None or value == "" or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        fval = float(value)
        return fval if math.isfinite(fval) else 0.0
    raw_str = str(value).strip()
    if not raw_str:
        return 0.0
    try:
        num = float(raw_str)
        return num if math.isfinite(num) else 0.0
    except (ValueError, TypeError, OverflowError):
        pass
    try:
        iso = raw_str.replace(" ", "T")
        if iso.endswith(("Z", "z")):
            iso = iso[:-1] + "+00:00"
        iso = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), iso, count=1)
        iso = re.sub(r"([+-]\d{2})$", r"\1:00", iso)
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except (ValueError, TypeError, OverflowError):
        return 0.0


class SaasStore:
    """Thread-safe SaaS Store with local JSON atomic persistence and optional Supabase mirroring."""

    def __init__(
        self,
        state_path: Path,
        supabase_store: Any = None,
        local_admin_username: str = "admin",
    ) -> None:
        self.state_path = state_path
        self.supabase = supabase_store
        self.local_admin_username = local_admin_username
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {
            "settings": {
                "trial_days": 7,
                "trial_allow_real_trading": False,
                "default_trial_plan_id": "pro",
                "kiwify_webhook_secret": "",
                "news_feeds": [],
                "ai_news_enabled": False,
                "ai_news_provider": "gemini",
                "ai_news_model": "gemini-3.5-flash-lite",
                "ai_news_api_key": "",
            },
            "plans": [dict(p) for p in DEFAULT_PLANS],
            "subscriptions": {},
            "webhook_logs": [],
        }
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.state_path.exists():
                try:
                    raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        if isinstance(raw.get("settings"), dict):
                            self._state["settings"].update(raw["settings"])
                        if isinstance(raw.get("plans"), list) and raw["plans"]:
                            self._state["plans"] = [self._normalize_plan(p) for p in raw["plans"]]
                        if isinstance(raw.get("subscriptions"), dict):
                            norm_subs: dict[str, Any] = {}
                            for k, v in raw["subscriptions"].items():
                                if isinstance(v, dict):
                                    norm_s = self._normalize_subscription(v, str(k))
                                    norm_subs[norm_s["email"] or str(k).strip().lower()] = norm_s
                            self._state["subscriptions"] = norm_subs
                        if isinstance(raw.get("webhook_logs"), list):
                            self._state["webhook_logs"] = list(raw["webhook_logs"])[:50]
                except Exception:
                    pass

            if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "load_saas_tables"):
                try:
                    remote = self.supabase.load_saas_tables()
                    if isinstance(remote, dict):
                        if isinstance(remote.get("settings"), dict):
                            clean_settings = {
                                k: v for k, v in remote["settings"].items() if k not in ("id", "updated_at")
                            }
                            self._state["settings"].update(clean_settings)
                        else:
                            self.supabase.upsert_saas_settings(self._state["settings"])
                        if isinstance(remote.get("plans"), list) and remote["plans"]:
                            self._state["plans"] = [self._normalize_plan(p) for p in remote["plans"]]
                        else:
                            for pl in self._state["plans"]:
                                self.supabase.upsert_saas_plan(pl)
                        if isinstance(remote.get("subscriptions"), list) and remote["subscriptions"]:
                            subs = {}
                            for sr in remote["subscriptions"]:
                                if not isinstance(sr, dict):
                                    continue
                                em = str(sr.get("email") or "").strip().lower()
                                if em:
                                    subs[em] = self._normalize_subscription(sr, em)
                            if subs:
                                self._state["subscriptions"].update(subs)
                except Exception:
                    pass

            self._persist_local()

    def _persist_local(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(prefix=".saas_", suffix=".tmp", dir=str(self.state_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_name, self.state_path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    @staticmethod
    def _normalize_subscription(raw: dict[str, Any], fallback_key: str = "") -> dict[str, Any]:
        rec = dict(raw)
        rec["email"] = str(rec.get("email") or fallback_key or "").strip().lower()
        rec["user_id"] = str(rec.get("user_id") or "")
        rec["plan_id"] = str(rec.get("plan_id") or "starter").strip() or "starter"
        rec["status"] = str(rec.get("status") or "expired").strip().lower() or "expired"
        rec["trial_ends_at"] = _parse_ts(rec.get("trial_ends_at"))
        rec["current_period_end"] = _parse_ts(rec.get("current_period_end"))
        rec["updated_at"] = _parse_ts(rec.get("updated_at"))
        rec["kiwify_order_id"] = str(rec.get("kiwify_order_id") or "")
        rec["kiwify_subscription_id"] = str(rec.get("kiwify_subscription_id") or "")
        rec["kiwify_customer_name"] = str(rec.get("kiwify_customer_name") or "")
        rec["last_event"] = str(rec.get("last_event") or "")
        return rec

    @staticmethod
    def _normalize_plan(raw: dict[str, Any], idx: int = 0) -> dict[str, Any]:
        pid = _slugify(str(raw.get("plan_id") or raw.get("name") or f"plan_{idx + 1}"))
        raw_feats = raw.get("allowed_features") or []
        feats = [str(f) for f in raw_feats if str(f) in ALL_FEATURES]
        allow_real = bool(raw.get("allow_real_trading", "real_trading" in feats))
        if allow_real and "real_trading" not in feats:
            feats.append("real_trading")
        elif not allow_real and "real_trading" in feats:
            feats = [f for f in feats if f != "real_trading"]
        cycle = str(raw.get("billing_cycle") or "monthly").strip().lower()
        if cycle not in ("monthly", "yearly", "lifetime"):
            cycle = "monthly"
        return {
            "plan_id": pid,
            "name": str(raw.get("name") or pid).strip(),
            "description": str(raw.get("description") or "").strip(),
            "price_brl": max(0.0, float(raw.get("price_brl") or 0.0)),
            "billing_cycle": cycle,
            "kiwify_product_id": str(raw.get("kiwify_product_id") or "").strip(),
            "kiwify_checkout_url": str(raw.get("kiwify_checkout_url") or "").strip(),
            "max_bots": max(1, int(raw.get("max_bots") or 1)),
            "allow_real_trading": allow_real,
            "allowed_features": feats,
            "active": bool(raw.get("active", True)),
            "sort_order": int(raw.get("sort_order") or idx + 1),
        }

    def admin_emails(self) -> set[str]:
        extra = os.environ.get("ADMIN_EMAILS", "")
        parsed = {e.strip().lower() for e in extra.split(",") if e.strip()}
        return DEFAULT_ADMIN_EMAILS | parsed

    def is_admin(self, user_id: str, email: str = "", supabase_enabled: bool = False) -> bool:
        clean_email = str(email or "").strip().lower()
        if clean_email and clean_email in self.admin_emails():
            return True
        if not supabase_enabled and user_id == self.local_admin_username:
            return True
        return False

    def get_settings(self) -> dict[str, Any]:
        with self._lock:
            s = dict(self._state["settings"])
            raw_trial = s.get("trial_days")
            s["trial_days"] = max(0, min(365, int(7 if raw_trial is None else raw_trial)))
            s["trial_allow_real_trading"] = bool(s.get("trial_allow_real_trading", False))
            s["default_trial_plan_id"] = str(s.get("default_trial_plan_id") or "pro")
            if not s.get("kiwify_webhook_secret"):
                s["kiwify_webhook_secret"] = os.environ.get("KIWIFY_WEBHOOK_SECRET", "").strip()
            s["ai_news_enabled"] = bool(s.get("ai_news_enabled", False))
            prov = normalize_ai_provider(str(s.get("ai_news_provider") or "gemini"))
            s["ai_news_provider"] = prov
            default_model = str(AI_PROVIDER_MAP[prov]["default_model"])
            s["ai_news_model"] = str(s.get("ai_news_model") or default_model).strip() or default_model
            raw_key = str(s.get("ai_news_api_key") or "").strip()
            if not raw_key and prov in ("gemini", "openai"):
                env_name = "GEMINI_API_KEY" if prov == "gemini" else "OPENAI_API_KEY"
                raw_key = os.environ.get(env_name, "").strip()
            s["ai_news_api_key"] = raw_key
            return s

    def get_public_admin_settings(self) -> dict[str, Any]:
        s = self.get_settings()
        has_key = bool(s.get("ai_news_api_key"))
        s["ai_news_api_key"] = ""
        s["ai_news_api_key_set"] = has_key
        return s

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            s = self._state["settings"]
            if "trial_days" in updates:
                s["trial_days"] = max(0, min(365, int(updates["trial_days"])))
            if "trial_allow_real_trading" in updates:
                s["trial_allow_real_trading"] = bool(updates["trial_allow_real_trading"])
            if "default_trial_plan_id" in updates and str(updates["default_trial_plan_id"]).strip():
                s["default_trial_plan_id"] = str(updates["default_trial_plan_id"]).strip()
            if "kiwify_webhook_secret" in updates:
                s["kiwify_webhook_secret"] = str(updates["kiwify_webhook_secret"] or "").strip()
            if "ai_news_enabled" in updates:
                s["ai_news_enabled"] = bool(updates["ai_news_enabled"])
            if "ai_news_provider" in updates:
                s["ai_news_provider"] = normalize_ai_provider(str(updates["ai_news_provider"] or "gemini"))
            if "ai_news_model" in updates and str(updates["ai_news_model"]).strip():
                s["ai_news_model"] = str(updates["ai_news_model"]).strip()
            if updates.get("clear_ai_api_key"):
                s["ai_news_api_key"] = ""
            elif "ai_news_api_key" in updates:
                cand = str(updates["ai_news_api_key"] or "").strip()
                if cand and cand != "********":
                    s["ai_news_api_key"] = cand
            self._persist_local()
            if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "upsert_saas_settings"):
                try:
                    self.supabase.upsert_saas_settings(s)
                except Exception:
                    pass
            return self.get_settings()

    def get_global_news_feeds(self) -> list[dict[str, str]]:
        with self._lock:
            raw = self._state["settings"].get("news_feeds") or []
            if isinstance(raw, list) and raw:
                return [dict(f) for f in raw if isinstance(f, dict)]
            return []

    def set_global_news_feeds(self, feeds: list[dict[str, str]]) -> list[dict[str, str]]:
        with self._lock:
            cleaned = [dict(f) for f in feeds if isinstance(f, dict) and f.get("url")]
            self._state["settings"]["news_feeds"] = cleaned
            self._persist_local()
            if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "upsert_saas_settings"):
                try:
                    self.supabase.upsert_saas_settings(self._state["settings"])
                except Exception:
                    pass
            return [dict(f) for f in cleaned]

    def list_plans(self, active_only: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            plans = sorted(
                (dict(p) for p in self._state["plans"]),
                key=lambda x: (int(x.get("sort_order", 0)), str(x.get("name", ""))),
            )
            if active_only:
                plans = [p for p in plans if p.get("active", True)]
            return plans

    def _get_plan(self, plan_id: str) -> dict[str, Any] | None:
        for p in self._state["plans"]:
            if p.get("plan_id") == plan_id:
                return p
        return None

    def _default_plan(self, preferred_plan_id: str = "") -> dict[str, Any]:
        active = self.list_plans(active_only=True)
        if preferred_plan_id:
            for p in active:
                if p["plan_id"] == preferred_plan_id:
                    return p
        default_id = self.get_settings().get("default_trial_plan_id", "pro")
        for p in active:
            if p["plan_id"] == default_id:
                return p
        return active[0] if active else self._normalize_plan(DEFAULT_PLANS[0])

    def save_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("Nome do plano é obrigatório.")
        with self._lock:
            norm = self._normalize_plan(payload, idx=len(self._state["plans"]))
            replaced = False
            new_plans: list[dict[str, Any]] = []
            for p in self._state["plans"]:
                if p["plan_id"] == norm["plan_id"]:
                    new_plans.append(norm)
                    replaced = True
                else:
                    new_plans.append(p)
            if not replaced:
                new_plans.append(norm)
            self._state["plans"] = new_plans
            self._persist_local()
            if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "upsert_saas_plan"):
                try:
                    self.supabase.upsert_saas_plan(norm)
                except Exception:
                    pass
            return dict(norm)

    def delete_plan(self, plan_id: str) -> bool:
        pid = str(plan_id or "").strip()
        if not pid:
            raise ValueError("ID do plano é obrigatório.")
        with self._lock:
            remaining = [p for p in self._state["plans"] if p.get("plan_id") != pid]
            if len(remaining) == len(self._state["plans"]):
                return False
            if not any(p.get("active", True) for p in remaining):
                raise ValueError("Mantenha pelo menos um plano ativo na plataforma.")
            self._state["plans"] = remaining
            self._persist_local()
            if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "delete_saas_plan"):
                try:
                    self.supabase.delete_saas_plan(pid)
                except Exception:
                    pass
            return True

    def _sub_key(self, user_id: str, email: str) -> str:
        clean = str(email or "").strip().lower()
        return clean or str(user_id or "").strip().lower()

    def _sync_sub_remote(self, sub: dict[str, Any]) -> None:
        if self.supabase and getattr(self.supabase, "is_enabled", False) and hasattr(self.supabase, "upsert_saas_subscription"):
            try:
                self.supabase.upsert_saas_subscription(sub)
            except Exception:
                pass

    def ensure_user_subscription(
        self,
        user_id: str,
        email: str = "",
        preferred_plan_id: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            key = self._sub_key(user_id, email)
            subs = self._state["subscriptions"]
            existing = subs.get(key)
            if isinstance(existing, dict):
                if user_id and not existing.get("user_id"):
                    existing["user_id"] = user_id
                    existing["updated_at"] = time.time()
                    self._persist_local()
                    self._sync_sub_remote(existing)
                return dict(existing)

            settings = self.get_settings()
            trial_days = int(settings["trial_days"])
            plan = self._default_plan(preferred_plan_id)
            now = time.time()
            if trial_days > 0:
                status = "trial"
                trial_ends = now + (trial_days * 86400)
            else:
                status = "expired"
                trial_ends = 0.0

            rec = {
                "email": key,
                "user_id": user_id,
                "plan_id": plan["plan_id"],
                "status": status,
                "trial_ends_at": trial_ends,
                "current_period_end": 0.0,
                "kiwify_order_id": "",
                "kiwify_subscription_id": "",
                "kiwify_customer_name": "",
                "last_event": "auto_trial" if trial_days > 0 else "trial_disabled",
                "updated_at": now,
            }
            subs[key] = rec
            self._persist_local()
            self._sync_sub_remote(rec)
            return dict(rec)

    def select_trial_plan(self, user_id: str, email: str, plan_id: str) -> dict[str, Any]:
        with self._lock:
            key = self._sub_key(user_id, email)
            sub = self.ensure_user_subscription(user_id, email)
            now = time.time()
            if sub.get("status") != "trial" or _parse_ts(sub.get("trial_ends_at")) <= now:
                raise ValueError("A troca de plano de teste só está disponível durante um período grátis ativo.")
            target = next((p for p in self.list_plans(active_only=True) if p["plan_id"] == plan_id), None)
            if target is None:
                raise ValueError("Plano selecionado não encontrado ou inativo.")
            sub["plan_id"] = target["plan_id"]
            sub["updated_at"] = now
            self._state["subscriptions"][key] = sub
            self._persist_local()
            self._sync_sub_remote(sub)
            return self.get_entitlements(user_id, email, supabase_enabled=True)

    def get_entitlements(
        self,
        user_id: str,
        email: str = "",
        supabase_enabled: bool = False,
    ) -> dict[str, Any]:
        if self.is_admin(user_id, email, supabase_enabled=supabase_enabled):
            return {
                "is_admin": True,
                "has_access": True,
                "status": "admin",
                "plan_id": "super_admin",
                "plan_name": "Super-Admin",
                "max_bots": 999,
                "allow_real_trading": True,
                "allowed_features": list(ALL_FEATURES),
                "days_left": None,
                "trial_ends_at": None,
                "current_period_end": None,
                "kiwify_checkout_url": "",
            }

        with self._lock:
            sub = self.ensure_user_subscription(user_id, email)
            settings = self.get_settings()
            now = time.time()
            raw_status = str(sub.get("status") or "expired")
            trial_ends = _parse_ts(sub.get("trial_ends_at"))
            period_end = _parse_ts(sub.get("current_period_end"))

            effective_status = raw_status
            days_left = 0
            if raw_status == "trial":
                if trial_ends > now:
                    days_left = max(1, math.ceil((trial_ends - now) / 86400))
                else:
                    effective_status = "expired"
            elif raw_status == "active":
                if period_end <= 0:
                    days_left = 999
                elif period_end > now:
                    days_left = max(1, math.ceil((period_end - now) / 86400))
                else:
                    effective_status = "expired"

            plan = self._get_plan(str(sub.get("plan_id") or "")) or self._default_plan()
            has_access = effective_status in ("trial", "active")
            if effective_status == "trial":
                eff_real = bool(plan.get("allow_real_trading") and settings.get("trial_allow_real_trading", False))
            elif effective_status == "active":
                eff_real = bool(plan.get("allow_real_trading"))
            else:
                eff_real = False

            if has_access:
                feats = [str(f) for f in plan.get("allowed_features", []) if str(f) in ALL_FEATURES]
                if eff_real and "real_trading" not in feats:
                    feats.append("real_trading")
                if not eff_real:
                    feats = [f for f in feats if f != "real_trading"]
            else:
                feats = []

            return {
                "is_admin": False,
                "has_access": has_access,
                "status": effective_status,
                "plan_id": plan["plan_id"],
                "plan_name": plan["name"],
                "max_bots": int(plan.get("max_bots", 1)) if has_access else 0,
                "allow_real_trading": eff_real,
                "allowed_features": feats,
                "days_left": days_left,
                "trial_ends_at": trial_ends or None,
                "current_period_end": period_end or None,
                "kiwify_checkout_url": str(plan.get("kiwify_checkout_url") or ""),
            }

    def list_subscriptions(self) -> list[dict[str, Any]]:
        with self._lock:
            now = time.time()
            admins = self.admin_emails()
            out: list[dict[str, Any]] = []
            for key, sub in self._state["subscriptions"].items():
                rec = self._normalize_subscription(sub, str(key))
                if rec["email"] in admins:
                    continue
                plan = self._get_plan(str(rec.get("plan_id") or ""))
                rec["plan_name"] = plan["name"] if plan else rec.get("plan_id", "")
                st = str(rec.get("status") or "expired")
                end_ts = rec["trial_ends_at"] if st == "trial" else rec["current_period_end"]
                if st in ("trial", "active") and end_ts > 0:
                    rec["days_left"] = max(0, math.ceil((end_ts - now) / 86400))
                    if end_ts <= now:
                        rec["effective_status"] = "expired"
                    else:
                        rec["effective_status"] = st
                else:
                    rec["days_left"] = 0
                    rec["effective_status"] = st
                out.append(rec)
            out.sort(key=lambda x: x["updated_at"], reverse=True)
            return out

    def admin_upsert_subscription(self, payload: dict[str, Any]) -> dict[str, Any]:
        email = str(payload.get("email") or "").strip().lower()
        if not email:
            raise ValueError("E-mail do cliente é obrigatório.")
        with self._lock:
            subs = self._state["subscriptions"]
            cur = dict(subs.get(email) or {})
            now = time.time()
            plan_id = str(payload.get("plan_id") or cur.get("plan_id") or self._default_plan()["plan_id"]).strip()
            if self._get_plan(plan_id) is None:
                raise ValueError("Plano informado não existe.")
            status = str(payload.get("status") or cur.get("status") or "active").strip().lower()
            if status not in ("trial", "active", "expired", "canceled", "blocked"):
                raise ValueError("Status inválido.")

            trial_ends = _parse_ts(cur.get("trial_ends_at"))
            period_end = _parse_ts(cur.get("current_period_end"))
            if payload.get("add_trial_days") is not None:
                add_d = max(0, int(payload["add_trial_days"]))
                base = max(now, trial_ends)
                trial_ends = base + add_d * 86400
                status = "trial"
            elif payload.get("duration_days") is not None:
                dur = max(0, int(payload["duration_days"]))
                if status == "trial":
                    trial_ends = now + dur * 86400
                elif status == "active":
                    period_end = (now + dur * 86400) if dur > 0 else 0.0
            elif status == "trial" and trial_ends <= now:
                trial_ends = now + max(1, int(self.get_settings()["trial_days"])) * 86400
            elif status == "active" and period_end <= now:
                period_end = now + 30 * 86400

            rec = {
                "email": email,
                "user_id": str(payload.get("user_id") or cur.get("user_id") or ""),
                "plan_id": plan_id,
                "status": status,
                "trial_ends_at": trial_ends,
                "current_period_end": period_end,
                "kiwify_order_id": str(cur.get("kiwify_order_id") or ""),
                "kiwify_subscription_id": str(cur.get("kiwify_subscription_id") or ""),
                "kiwify_customer_name": str(payload.get("customer_name") or cur.get("kiwify_customer_name") or ""),
                "last_event": "admin_manual",
                "updated_at": now,
            }
            subs[email] = rec
            self._persist_local()
            self._sync_sub_remote(rec)
            return dict(rec)

    def _match_plan_for_kiwify(self, product_id: str, product_name: str) -> dict[str, Any]:
        pid = str(product_id or "").strip()
        pname = str(product_name or "").strip().lower()
        plans = self.list_plans()
        if pid:
            for p in plans:
                if str(p.get("kiwify_product_id") or "").strip() == pid:
                    return p
        if pname:
            for p in plans:
                if p["name"].lower() in pname or p["plan_id"].lower() in pname:
                    return p
        return self._default_plan()

    def handle_kiwify_webhook(self, payload: dict[str, Any], provided_token: str = "") -> tuple[int, dict[str, Any]]:
        settings = self.get_settings()
        expected = str(settings.get("kiwify_webhook_secret") or "").strip()
        candidate = (
            str(provided_token or "").strip()
            or str(payload.get("token") or "").strip()
            or str(payload.get("signature") or "").strip()
        )
        if expected and (not candidate or not hmac.compare_digest(candidate, expected)):
            return 401, {"ok": False, "error": "Token do webhook Kiwify inválido."}

        raw_event = str(
            payload.get("webhook_event_type")
            or payload.get("event")
            or payload.get("order_status")
            or payload.get("subscription_status")
            or ""
        ).strip().lower()

        customer = payload.get("Customer") or payload.get("customer") or {}
        if not isinstance(customer, dict):
            customer = {}
        email = str(customer.get("email") or payload.get("email") or "").strip().lower()
        cust_name = str(customer.get("full_name") or customer.get("name") or "").strip()

        product = payload.get("Product") or payload.get("product") or {}
        if not isinstance(product, dict):
            product = {}
        product_id = str(product.get("product_id") or payload.get("product_id") or "").strip()
        product_name = str(product.get("product_name") or payload.get("product_name") or "").strip()

        if raw_event in _IGNORE_EVENTS:
            return 200, {"ok": True, "ignored": True, "event": raw_event}

        if not email:
            return 400, {"ok": False, "error": "E-mail do comprador ausente no payload Kiwify."}

        with self._lock:
            now = time.time()
            plan = self._match_plan_for_kiwify(product_id, product_name)
            subs = self._state["subscriptions"]
            cur = dict(subs.get(email) or {})

            revoked = False
            if raw_event in _APPROVE_EVENTS:
                cycle = plan.get("billing_cycle", "monthly")
                if cycle == "lifetime":
                    period_end = 0.0
                else:
                    days = 365 if cycle == "yearly" else 30
                    base = max(now, _parse_ts(cur.get("current_period_end")))
                    period_end = base + days * 86400
                status = "active"
            elif raw_event in _REVOKE_EVENTS:
                status = "expired" if "late" in raw_event else "canceled"
                period_end = now
                revoked = True
            else:
                return 200, {"ok": True, "ignored": True, "event": raw_event or "unknown"}

            rec = {
                "email": email,
                "user_id": str(cur.get("user_id") or ""),
                "plan_id": cur.get("plan_id") if revoked and cur.get("plan_id") else plan["plan_id"],
                "status": status,
                "trial_ends_at": _parse_ts(cur.get("trial_ends_at")),
                "current_period_end": period_end,
                "kiwify_order_id": str(payload.get("order_id") or cur.get("kiwify_order_id") or ""),
                "kiwify_subscription_id": str(payload.get("subscription_id") or cur.get("kiwify_subscription_id") or ""),
                "kiwify_customer_name": cust_name or str(cur.get("kiwify_customer_name") or ""),
                "last_event": raw_event,
                "updated_at": now,
            }
            subs[email] = rec
            log_entry = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                "event": raw_event,
                "email": email,
                "plan_id": rec["plan_id"],
                "status": status,
            }
            self._state["webhook_logs"] = [log_entry, *self._state.get("webhook_logs", [])][:50]
            self._persist_local()
            self._sync_sub_remote(rec)
            return 200, {
                "ok": True,
                "event": raw_event,
                "email": email,
                "user_id": rec["user_id"],
                "plan_id": rec["plan_id"],
                "status": status,
                "revoked": revoked,
            }

    def list_webhook_logs(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._state.get("webhook_logs", []))
