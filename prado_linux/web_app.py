"""Zero-dependency HTTP Web Application & REST API for Prado Institutional HFT (Deriv Multipliers)."""
from __future__ import annotations

from dataclasses import asdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from prado_linux.auth import create_session_token, hash_password, verify_password, verify_session_token
from prado_linux.config import MATH_BOT_TEMPLATES, PradoServerConfig, load_config
from prado_linux.engine import PradoTradingService
from prado_linux.indicators import DEFAULT_PYTHON_STRATEGY_TEMPLATE, INDICATOR_CATALOG
from prado_linux.supabase_store import SupabaseStore

STATIC_DIR = Path(__file__).resolve().parent / "static"


class PradoWebApp:
    """Testable HTTP router for Login, Deriv Token Vault, Symbols, Categories, Robot Fleet, and Backtest."""

    def __init__(self, config_path: Path, supabase_store: SupabaseStore | None = None) -> None:
        self.config_path = config_path
        self.cfg = load_config(config_path)
        self.service = PradoTradingService(self.cfg, config_path=config_path)
        self.supabase = supabase_store or SupabaseStore.from_env()
        self._user_services: dict[str, PradoTradingService] = {}
        self._user_tokens: dict[str, str] = {}
        self._user_emails: dict[str, str] = {}
        self._services_lock = threading.Lock()

    def _active_service(self, user: str) -> PradoTradingService:
        if not self.supabase.is_enabled or not user or user == self.cfg.admin_username:
            return self.service
        with self._services_lock:
            svc = self._user_services.get(user)
            if svc is None:
                user_cfg_path = self.config_path.parent / f"prado_user_{user}.json"
                token = self._user_tokens.get(user, "")
                u_cfg = self.supabase.load_user_config(user, token, user_cfg_path)
                u_email = self._user_emails.get(user, "").lower()
                if (
                    not u_cfg.accounts
                    and not u_cfg.bots
                    and u_email == "sitepixer@gmail.com"
                    and (self.cfg.accounts or self.cfg.bots or self.cfg.deriv_token)
                ):
                    u_cfg.deriv_token = self.cfg.deriv_token
                    u_cfg.deriv_app_id = self.cfg.deriv_app_id
                    u_cfg.connection_mode = self.cfg.connection_mode
                    u_cfg.allow_real_trading = self.cfg.allow_real_trading
                    u_cfg.active_account_id = self.cfg.active_account_id
                    u_cfg.active_account_type = self.cfg.active_account_type
                    u_cfg.accounts = [dict(a) for a in self.cfg.accounts]
                    u_cfg.bots = [dict(b) for b in self.cfg.bots]
                    u_cfg.custom_templates = [dict(t) for t in self.cfg.custom_templates]
                    u_cfg.news_feeds = [dict(f) for f in self.cfg.news_feeds]
                    u_cfg.custom_categories = dict(self.cfg.custom_categories)
                    u_cfg.active_symbols = list(self.cfg.active_symbols)
                    u_cfg.news_bot_enabled = self.cfg.news_bot_enabled
                    self.supabase.sync_user_config(user, token, u_cfg)
                svc = PradoTradingService(u_cfg, config_path=user_cfg_path)
                svc.step_once()
                if not svc._thread or not svc._thread.is_alive():
                    svc.start_background_loop()
                self._user_services[user] = svc
            return svc

    def _sync_user(self, user: str, svc: PradoTradingService) -> None:
        if self.supabase.is_enabled and user and user != self.cfg.admin_username:
            token = self._user_tokens.get(user, "")
            try:
                self.supabase.sync_user_config(user, token, svc.cfg)
            except Exception as exc:
                svc._log_event("SUPABASE_SYNC", f"Aviso ao sincronizar Supabase: {exc}")

    def _extract_session_user(self, headers: dict[str, str]) -> str | None:
        cookie_raw = headers.get("Cookie") or headers.get("cookie") or ""
        if not cookie_raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_raw)
        except Exception:
            return None
        morsel = cookie.get("prado_session")
        if morsel is None:
            return None
        uid = verify_session_token(morsel.value, self.cfg.secret_key)
        if uid and self.supabase.is_enabled and uid != self.cfg.admin_username:
            with self._services_lock:
                has_tok = uid in self._user_tokens
            if not has_tok:
                return None
        return uid

    def _safe_config_dict(self, cfg_obj: PradoServerConfig | None = None) -> dict[str, Any]:
        d = asdict(cfg_obj or self.cfg)
        d.pop("admin_password_hash", None)
        d.pop("secret_key", None)
        if d.get("deriv_token"):
            d["deriv_token_set"] = True
            d["deriv_token"] = "********"
        else:
            d["deriv_token_set"] = False
        safe_accs = []
        for a in d.get("accounts", []):
            cp = dict(a)
            if cp.get("deriv_token"):
                cp["deriv_token"] = "********"
            safe_accs.append(cp)
        d["accounts"] = safe_accs
        return d

    def _serve_index(self) -> tuple[int, str, dict[str, str]]:
        idx = STATIC_DIR / "index.html"
        if idx.exists():
            return 200, idx.read_text(encoding="utf-8"), {"Content-Type": "text/html; charset=utf-8"}
        return 200, "<!doctype html><html><body>Prado HFT Static Build Missing</body></html>", {"Content-Type": "text/html; charset=utf-8"}

    def _serve_static_file(self, rel_path: str) -> tuple[int, str | bytes, dict[str, str]] | None:
        rel = rel_path.lstrip("/")
        if not rel:
            return None
        static_root = STATIC_DIR.resolve()
        target = (static_root / rel).resolve()
        if (static_root == target.parent or static_root in target.parents) and target.is_file():
            ctype, _ = mimetypes.guess_type(str(target))
            if target.suffix.lower() == ".svg":
                ctype = "image/svg+xml"
            elif target.suffix.lower() == ".ico":
                ctype = "image/x-icon"
            is_text = (ctype or "").startswith(("text/", "application/javascript", "application/json", "image/svg+xml"))
            if is_text:
                return 200, target.read_text(encoding="utf-8"), {"Content-Type": f"{ctype or 'text/plain'}; charset=utf-8"}
            return 200, target.read_bytes(), {"Content-Type": ctype or "application/octet-stream"}
        return None

    SECURITY_HEADERS: dict[str, str] = {
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, str | bytes, dict[str, str]]:
        code, resp_body, resp_headers = self._route_request(method, path, headers, body)
        merged_headers = dict(self.SECURITY_HEADERS)
        merged_headers.update(resp_headers)
        return code, resp_body, merged_headers

    def _route_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, str | bytes, dict[str, str]]:
        method = method.upper()
        parsed_url = urlparse(path)
        clean_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if method == "GET" and clean_path in ("/favicon.ico", "/favicon.svg"):
            served = self._serve_static_file(clean_path)
            if served is not None:
                return served
            return 404, "Not found", {"Content-Type": "text/plain; charset=utf-8"}

        if method == "GET" and clean_path.startswith("/assets/"):
            served = self._serve_static_file(clean_path)
            if served is not None:
                return served
            return 404, "Not found", {"Content-Type": "text/plain; charset=utf-8"}

        if method == "GET" and clean_path == "/health":
            return 200, json.dumps({"ok": True, "status": "healthy"}), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/login":
            return self._serve_index()

        if method == "GET" and clean_path == "/api/auth/mode":
            return (
                200,
                json.dumps({"ok": True, "supabase_enabled": self.supabase.is_enabled}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/signup":
            if not self.supabase.is_enabled:
                return 400, json.dumps({"ok": False, "error": "Supabase nao configurado."}), {"Content-Type": "application/json"}
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            email = str(payload.get("email") or payload.get("username") or "").strip()
            password = str(payload.get("password") or "")
            ok, res = self.supabase.sign_up(email, password)
            if not ok:
                return 400, json.dumps({"ok": False, "error": res.get("error", "Erro ao cadastrar.")}, ensure_ascii=False), {"Content-Type": "application/json"}
            uid = res.get("user_id") or email
            access_token = res.get("access_token") or ""
            if access_token:
                self._user_tokens[uid] = access_token
                self._user_emails[uid] = str(res.get("email") or email)
                svc = self._active_service(uid)
                self._sync_user(uid, svc)
                token = create_session_token(uid, self.cfg.secret_key)
                cookie_val = f"prado_session={token}; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax"
                return (
                    200,
                    json.dumps({"ok": True, "username": res.get("email", email), "user_id": uid}),
                    {"Content-Type": "application/json", "Set-Cookie": cookie_val},
                )
            return (
                200,
                json.dumps({"ok": True, "confirmation_required": True, "message": "Conta criada! Verifique seu e-mail para confirmar e depois faça login."}),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/login":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            username = str(payload.get("username") or payload.get("email") or "").strip()
            password = str(payload.get("password", ""))
            if self.supabase.is_enabled:
                ok, res = self.supabase.sign_in(username, password)
                if ok and res.get("user_id"):
                    uid = res["user_id"]
                    with self._services_lock:
                        self._user_tokens[uid] = res["access_token"]
                        self._user_emails[uid] = str(res.get("email") or username)
                        old_svc = self._user_services.pop(uid, None)
                    if old_svc is not None:
                        old_svc.stop_background_loop()
                    svc = self._active_service(uid)
                    if not svc._thread or not svc._thread.is_alive():
                        svc.start_background_loop()
                    token = create_session_token(uid, self.cfg.secret_key)
                    cookie_val = f"prado_session={token}; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax"
                    return (
                        200,
                        json.dumps({"ok": True, "username": res.get("email", username), "user_id": uid}),
                        {"Content-Type": "application/json", "Set-Cookie": cookie_val},
                    )
                return 401, json.dumps({"ok": False, "error": res.get("error", "Credenciais invalidas.")}, ensure_ascii=False), {"Content-Type": "application/json"}
            if username == self.cfg.admin_username and verify_password(password, self.cfg.admin_password_hash):
                token = create_session_token(username, self.cfg.secret_key)
                cookie_val = f"prado_session={token}; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax"
                return (
                    200,
                    json.dumps({"ok": True, "username": username}),
                    {"Content-Type": "application/json", "Set-Cookie": cookie_val},
                )
            return 401, json.dumps({"ok": False, "error": "Credenciais invalidas."}), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/logout":
            uid = self._extract_session_user(headers)
            if uid:
                with self._services_lock:
                    self._user_tokens.pop(uid, None)
            return (
                200,
                json.dumps({"ok": True}),
                {"Content-Type": "application/json", "Set-Cookie": "prado_session=; HttpOnly; Path=/; Max-Age=0"},
            )

        user = self._extract_session_user(headers)
        if not user:
            if clean_path.startswith("/api/"):
                return 401, json.dumps({"ok": False, "error": "Nao autenticado."}), {"Content-Type": "application/json"}
            return 302, "", {"Location": "/login"}

        svc = self._active_service(user)
        cfg = svc.cfg

        if method == "GET" and clean_path == "/":
            return self._serve_index()

        if method == "GET" and clean_path == "/api/status":
            return 200, json.dumps(svc.get_snapshot(), ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/chart":
            sym = str(query_params.get("symbol", ["R_100"])[0] or "R_100").strip()
            tf = str(query_params.get("timeframe", ["TICKS"])[0] or "TICKS").strip().upper()
            points = svc.get_chart_series(sym, timeframe=tf)
            return 200, json.dumps({"ok": True, "symbol": sym, "timeframe": tf, "points": points}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/config":
            return (
                200,
                json.dumps({"ok": True, "config": self._safe_config_dict(cfg)}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/config":
            try:
                updates = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            new_admin_pwd = updates.pop("new_admin_password", None)
            if new_admin_pwd and str(new_admin_pwd).strip():
                updates["admin_password_hash"] = hash_password(str(new_admin_pwd).strip())
            if updates.get("deriv_token") == "********":
                updates.pop("deriv_token", None)
            svc.update_config(updates)
            svc.step_once()
            self._sync_user(user, svc)
            return (
                200,
                json.dumps({"ok": True, "message": "Configuracao salva.", "config": self._safe_config_dict(cfg)}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        # Deriv Tokens & Accounts API
        if method == "GET" and clean_path == "/api/accounts":
            return (
                200,
                json.dumps({"ok": True, "accounts": self._safe_config_dict(cfg)["accounts"]}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/accounts":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            act_acc = str(payload.get("action", "")).upper()
            if act_acc == "DELETE":
                svc.delete_account(str(payload.get("account_id", "")).strip())
                self._sync_user(user, svc)
                return 200, json.dumps({"ok": True, "accounts": self._safe_config_dict(cfg)["accounts"]}, ensure_ascii=False), {"Content-Type": "application/json"}
            if act_acc == "DELETE_ALL":
                svc.clear_all_accounts()
                self._sync_user(user, svc)
                return 200, json.dumps({"ok": True, "accounts": []}, ensure_ascii=False), {"Content-Type": "application/json"}

            acc, conn_msg = svc.save_deriv_account(payload)
            safe_acc = {k: ("********" if k == "deriv_token" and v else v) for k, v in acc.items()}
            svc.step_once()
            self._sync_user(user, svc)
            return (
                200,
                json.dumps(
                    {
                        "ok": True,
                        "message": conn_msg,
                        "account": safe_acc,
                        "accounts": self._safe_config_dict(cfg)["accounts"],
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/accounts/sync":
            ok, msg, _ = svc.sync_deriv_accounts()
            svc.step_once()
            self._sync_user(user, svc)
            safe_cfg = self._safe_config_dict(cfg)
            return (
                200 if ok else 400,
                json.dumps(
                    {
                        "ok": ok,
                        "message": msg,
                        "accounts": safe_cfg["accounts"],
                        "active_account_id": safe_cfg["active_account_id"],
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/accounts/select":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            selected = svc.select_active_account(str(payload.get("account_id", "")).strip())
            if selected is None:
                return 404, json.dumps({"ok": False, "error": "Token/conta nao encontrado"}), {"Content-Type": "application/json"}
            svc.step_once()
            self._sync_user(user, svc)
            return (
                200,
                json.dumps({"ok": True, "active_account": selected, "accounts": self._safe_config_dict(cfg)["accounts"]}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/risk/reset":
            res = svc.reset_daily_risk_lock()
            svc.step_once()
            return 200, json.dumps(res, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/symbols":
            mode = (query_params.get("mode", ["PRINCIPAIS"])[0] or "PRINCIPAIS").upper()
            category_filter = (query_params.get("category", [""])[0] or "").strip()
            symbols = svc.connector.discover_broker_symbols(mode=mode)
            if category_filter and category_filter in cfg.custom_categories:
                allowed = set(cfg.custom_categories[category_filter])
                symbols = [s for s in symbols if s["name"] in allowed] + [
                    {"name": sym, "category": category_filter, "description": sym, "visible": True}
                    for sym in cfg.custom_categories[category_filter]
                    if sym not in {x["name"] for x in symbols}
                ]
            return (
                200,
                json.dumps({"ok": True, "mode": mode, "symbols": symbols, "categories": cfg.custom_categories}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "GET" and clean_path == "/api/categories":
            return 200, json.dumps({"ok": True, "categories": cfg.custom_categories}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/categories":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            action = str(payload.get("action", "SAVE")).upper()
            cat_name = str(payload.get("category_name", "")).strip()
            if action == "DELETE":
                cats = svc.delete_custom_category(cat_name)
            else:
                raw_syms = payload.get("symbols", [])
                if isinstance(raw_syms, str):
                    raw_syms = [s.strip() for s in raw_syms.split(",") if s.strip()]
                cats = svc.save_custom_category(cat_name, list(raw_syms))
            self._sync_user(user, svc)
            return 200, json.dumps({"ok": True, "categories": cats}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/news/scan":
            news_data = svc.scan_news(force=True)
            svc.step_once()
            return 200, json.dumps({"ok": True, "news": news_data}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/news/feeds":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            act = str(payload.get("action", "SAVE")).upper()
            if act == "DELETE":
                feeds = svc.delete_news_feed(str(payload.get("feed_id", "")).strip())
            elif act == "RESET_DEFAULT":
                feeds = svc.reset_news_feeds()
            else:
                try:
                    feeds = svc.save_news_feed(payload)
                except ValueError as exc:
                    return 400, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), {"Content-Type": "application/json"}
            self._sync_user(user, svc)
            return 200, json.dumps({"ok": True, "news_feeds": feeds}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/bot-templates":
            return (
                200,
                json.dumps(
                    {
                        "ok": True,
                        "templates": svc.get_all_templates(),
                        "indicators": INDICATOR_CATALOG,
                        "python_template": DEFAULT_PYTHON_STRATEGY_TEMPLATE,
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/bot-templates":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            act = str(payload.get("action") or "SAVE").strip().upper()
            try:
                if act == "DELETE":
                    svc.delete_custom_template(str(payload.get("template_id") or "").strip())
                else:
                    svc.save_custom_template(payload)
            except ValueError as exc:
                return 400, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), {"Content-Type": "application/json"}
            self._sync_user(user, svc)
            return (
                200,
                json.dumps({"ok": True, "templates": svc.get_all_templates()}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/bot-templates/test":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            res = svc.test_custom_template(payload)
            return 200, json.dumps(res, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/bots":
            return 200, json.dumps({"ok": True, "bots": cfg.bots}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/bots":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            try:
                bot = svc.create_bot(payload)
                self._sync_user(user, svc)
                return 200, json.dumps({"ok": True, "bot": bot, "bots": cfg.bots}, ensure_ascii=False), {"Content-Type": "application/json"}
            except Exception as exc:
                return 400, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/bots/action":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            bot_id = str(payload.get("bot_id", "")).strip()
            action = str(payload.get("action", "START")).strip().upper()
            if action == "DELETE_ALL":
                svc.delete_all_bots()
                self._sync_user(user, svc)
                return 200, json.dumps({"ok": True, "bots": []}, ensure_ascii=False), {"Content-Type": "application/json"}
            updated = svc.control_bot(bot_id, action)
            if updated is None:
                return 404, json.dumps({"ok": False, "error": "Robô não encontrado"}), {"Content-Type": "application/json"}
            if action in ("FIRE_BUY", "FIRE_SELL"):
                svc.step_once()
            self._sync_user(user, svc)
            return 200, json.dumps({"ok": True, "bot": updated, "bots": cfg.bots}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/backtest":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            report = svc.run_mathematical_backtest(payload)
            return 200, json.dumps({"ok": True, "report": report, "history": cfg.backtest_history}, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/flatten":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            ticket = payload.get("ticket")
            if ticket is not None:
                ok, msg = svc.close_position(ticket)
                svc.step_once()
                return 200, json.dumps({"ok": ok, "message": msg}, ensure_ascii=False), {"Content-Type": "application/json"}
            cnt, msg = svc.flatten_all("ZERAR_TUDO_PAINEL_WEB")
            svc.step_once()
            is_err = cnt == 0 and ("desconectada" in msg.lower() or "falha" in msg.lower())
            return 200, json.dumps({"ok": not is_err, "closed": cnt, "message": msg}, ensure_ascii=False), {"Content-Type": "application/json"}

        return 404, json.dumps({"error": "Not found"}), {"Content-Type": "application/json"}


def run_http_server(config_path: Path, host: str = "0.0.0.0", port: int | None = None) -> None:
    app = PradoWebApp(config_path=config_path)
    if not app.supabase.is_enabled:
        app.service.start_background_loop()
    bind_port = port or app.cfg.web_port

    class _Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method: str) -> None:
            raw_len = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_len)
            except ValueError:
                length = -1
            if length < 0 or length > 2 * 1024 * 1024:
                self.send_response(413)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":false,"error":"Payload muito grande ou Content-Length invalido."}')
                return
            body = self.rfile.read(length) if length > 0 else b""
            hdrs = {k: v for k, v in self.headers.items()}
            code, resp_body, resp_headers = app.handle_request(method, self.path, hdrs, body)
            self.send_response(code)
            for hk, hv in resp_headers.items():
                self.send_header(hk, hv)
            self.end_headers()
            if resp_body:
                self.wfile.write(resp_body if isinstance(resp_body, bytes) else resp_body.encode("utf-8"))

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, bind_port), _Handler)
    print(f"[PRADO UBUNTU DERIV SERVER] Painel rodando em http://{host}:{bind_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.service.stop_background_loop()
        for usvc in list(app._user_services.values()):
            usvc.stop_background_loop()
        server.server_close()
