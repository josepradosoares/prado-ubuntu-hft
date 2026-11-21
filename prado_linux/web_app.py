"""Zero-dependency HTTP Web Application & REST API for Prado Institutional HFT Ubuntu Server."""
from __future__ import annotations

from dataclasses import asdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from prado_linux.auth import create_session_token, hash_password, verify_password, verify_session_token
from prado_linux.config import KNOWN_BROKER_SERVERS, MATH_BOT_TEMPLATES, load_config
from prado_linux.engine import PradoTradingService
from prado_linux.templates import DASHBOARD_HTML, LOGIN_HTML


class PradoWebApp:
    """Testable WSGI/HTTP router for Login, MT5 Accounts, Broker Symbols, Categories, Robot Fleet, and Monitoring."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.cfg = load_config(config_path)
        self.service = PradoTradingService(self.cfg, config_path=config_path)

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
        return verify_session_token(morsel.value, self.cfg.secret_key)

    def _safe_config_dict(self) -> dict[str, Any]:
        d = asdict(self.cfg)
        d.pop("admin_password_hash", None)
        d.pop("secret_key", None)
        if d.get("mt5_password"):
            d["mt5_password_set"] = True
            d["mt5_password"] = "********"
        else:
            d["mt5_password_set"] = False
        safe_accs = []
        for a in d.get("accounts", []):
            cp = dict(a)
            if cp.get("mt5_password"):
                cp["mt5_password"] = "********"
            safe_accs.append(cp)
        d["accounts"] = safe_accs
        return d

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, str, dict[str, str]]:
        method = method.upper()
        parsed_url = urlparse(path)
        clean_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Public Endpoints
        if method == "GET" and clean_path == "/login":
            return 200, LOGIN_HTML, {"Content-Type": "text/html; charset=utf-8"}

        if method == "POST" and clean_path == "/api/login":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            if username == self.cfg.admin_username and verify_password(password, self.cfg.admin_password_hash):
                token = create_session_token(username, self.cfg.secret_key)
                cookie_val = f"prado_session={token}; HttpOnly; Path=/; Max-Age=604800; SameSite=Lax"
                return (
                    200,
                    json.dumps({"ok": True, "username": username}),
                    {"Content-Type": "application/json", "Set-Cookie": cookie_val},
                )
            return (
                401,
                json.dumps({"ok": False, "error": "Credenciais invalidas."}),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/logout":
            return (
                200,
                json.dumps({"ok": True}),
                {
                    "Content-Type": "application/json",
                    "Set-Cookie": "prado_session=; HttpOnly; Path=/; Max-Age=0",
                },
            )

        # Auth Check for Protected Routes
        user = self._extract_session_user(headers)
        if not user:
            if clean_path.startswith("/api/"):
                return (
                    401,
                    json.dumps({"ok": False, "error": "Nao autenticado."}),
                    {"Content-Type": "application/json"},
                )
            return (302, "", {"Location": "/login"})

        if method == "GET" and clean_path == "/":
            return 200, DASHBOARD_HTML, {"Content-Type": "text/html; charset=utf-8"}

        if method == "GET" and clean_path == "/api/status":
            snap = self.service.get_snapshot()
            return 200, json.dumps(snap, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "GET" and clean_path == "/api/config":
            return (
                200,
                json.dumps({"ok": True, "config": self._safe_config_dict()}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/config":
            try:
                updates = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}

            reconnect = bool(updates.pop("reconnect", False))
            new_admin_pwd = updates.pop("new_admin_password", None)
            if new_admin_pwd and str(new_admin_pwd).strip():
                updates["admin_password_hash"] = hash_password(str(new_admin_pwd).strip())

            if updates.get("mt5_password") == "********":
                updates.pop("mt5_password", None)

            self.service.update_config(updates)
            msg = "Configuracao salva com sucesso."
            if reconnect:
                _, conn_msg = self.service.reconnect_mt5()
                msg = conn_msg

            self.service.step_once()
            return (
                200,
                json.dumps({"ok": True, "message": msg, "config": self._safe_config_dict()}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        # Accounts API
        if method == "GET" and clean_path == "/api/accounts":
            return (
                200,
                json.dumps({"ok": True, "accounts": self._safe_config_dict()["accounts"]}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/accounts":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            act_acc = str(payload.get("action", "")).upper()
            if act_acc == "DELETE":
                acc_id = str(payload.get("account_id", "")).strip()
                self.service.delete_mt5_account(acc_id)
                return (
                    200,
                    json.dumps({"ok": True, "accounts": self._safe_config_dict()["accounts"]}, ensure_ascii=False),
                    {"Content-Type": "application/json"},
                )
            if act_acc == "DELETE_ALL":
                self.service.clear_all_accounts()
                return (
                    200,
                    json.dumps({"ok": True, "accounts": []}, ensure_ascii=False),
                    {"Content-Type": "application/json"},
                )
            acc = self.service.save_mt5_account(payload)
            if payload.get("connect_now"):
                self.service.reconnect_mt5()
            return (
                200,
                json.dumps(
                    {
                        "ok": True,
                        "account": {k: ("********" if k == "mt5_password" else v) for k, v in acc.items()},
                        "accounts": self._safe_config_dict()["accounts"],
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        if method == "GET" and clean_path == "/api/broker-servers":
            q = (query_params.get("q", [""])[0] or "").strip().lower()
            extra = [str(a.get("mt5_server", "")) for a in self.cfg.accounts if a.get("mt5_server")]
            all_srvs = list(dict.fromkeys(KNOWN_BROKER_SERVERS + extra))
            if q:
                filtered = [s for s in all_srvs if q in s.lower()]
            else:
                filtered = all_srvs
            return (
                200,
                json.dumps({"ok": True, "servers": filtered}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/risk/reset":
            res = self.service.reset_daily_risk_lock()
            self.service.step_once()
            return 200, json.dumps(res, ensure_ascii=False), {"Content-Type": "application/json"}

        if method == "POST" and clean_path == "/api/accounts/select":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            acc_id = str(payload.get("account_id", "")).strip()
            selected = self.service.select_active_account(acc_id)
            if selected is None:
                return 404, json.dumps({"ok": False, "error": "Conta nao encontrada"}), {"Content-Type": "application/json"}
            self.service.step_once()
            return (
                200,
                json.dumps(
                    {
                        "ok": True,
                        "active_account": selected,
                        "accounts": self._safe_config_dict()["accounts"],
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        if method == "GET" and clean_path == "/api/bot-templates":
            return (
                200,
                json.dumps({"ok": True, "templates": MATH_BOT_TEMPLATES}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/backtest":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            report = self.service.run_mathematical_backtest(payload)
            return (
                200,
                json.dumps(
                    {"ok": True, "report": report, "history": self.cfg.backtest_history},
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        # Broker Symbols Discovery API ("PRINCIPAIS" vs "TODOS")
        if method == "GET" and clean_path == "/api/symbols":
            mode = (query_params.get("mode", ["PRINCIPAIS"])[0] or "PRINCIPAIS").upper()
            category_filter = (query_params.get("category", [""])[0] or "").strip()
            symbols = self.service.connector.discover_broker_symbols(mode=mode)
            if category_filter and category_filter in self.cfg.custom_categories:
                allowed = set(self.cfg.custom_categories[category_filter])
                symbols = [s for s in symbols if s["name"] in allowed] + [
                    {"name": sym, "category": category_filter, "description": sym, "visible": True}
                    for sym in self.cfg.custom_categories[category_filter]
                    if sym not in {x["name"] for x in symbols}
                ]
            return (
                200,
                json.dumps(
                    {
                        "ok": True,
                        "mode": mode,
                        "symbols": symbols,
                        "categories": self.cfg.custom_categories,
                    },
                    ensure_ascii=False,
                ),
                {"Content-Type": "application/json"},
            )

        # Custom Broker Symbol Categories API
        if method == "GET" and clean_path == "/api/categories":
            return (
                200,
                json.dumps({"ok": True, "categories": self.cfg.custom_categories}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/categories":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            action = str(payload.get("action", "SAVE")).upper()
            cat_name = str(payload.get("category_name", "")).strip()
            if action == "DELETE":
                cats = self.service.delete_custom_category(cat_name)
            else:
                raw_syms = payload.get("symbols", [])
                if isinstance(raw_syms, str):
                    raw_syms = [s.strip() for s in raw_syms.split(",") if s.strip()]
                cats = self.service.save_custom_category(cat_name, list(raw_syms))
            return (
                200,
                json.dumps({"ok": True, "categories": cats}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        # Multi-Bot Fleet API (Criar Robô, Selecionar Conta + Ativo, Executar / Pausar)
        if method == "GET" and clean_path == "/api/bots":
            return (
                200,
                json.dumps({"ok": True, "bots": self.cfg.bots}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/bots":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            bot = self.service.create_bot(payload)
            self.service.step_once()
            return (
                200,
                json.dumps({"ok": True, "bot": bot, "bots": self.cfg.bots}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/bots/action":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                return 400, json.dumps({"ok": False, "error": "JSON invalido"}), {"Content-Type": "application/json"}
            bot_id = str(payload.get("bot_id", "")).strip()
            action = str(payload.get("action", "START")).strip().upper()
            if action == "DELETE_ALL":
                self.service.delete_all_bots()
                self.service.step_once()
                return (
                    200,
                    json.dumps({"ok": True, "bots": []}, ensure_ascii=False),
                    {"Content-Type": "application/json"},
                )
            updated = self.service.control_bot(bot_id, action)
            if updated is None:
                return 404, json.dumps({"ok": False, "error": "Robô não encontrado"}), {"Content-Type": "application/json"}
            self.service.step_once()
            return (
                200,
                json.dumps({"ok": True, "bot": updated, "bots": self.cfg.bots}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        if method == "POST" and clean_path == "/api/flatten":
            cnt, msg = self.service.flatten_all("ZERAR_TUDO_PAINEL_WEB")
            self.service.step_once()
            return (
                200,
                json.dumps({"ok": True, "closed": cnt, "message": msg}, ensure_ascii=False),
                {"Content-Type": "application/json"},
            )

        return 404, json.dumps({"error": "Not found"}), {"Content-Type": "application/json"}


def run_http_server(config_path: Path, host: str = "0.0.0.0", port: int | None = None) -> None:
    app = PradoWebApp(config_path=config_path)
    app.service.start_background_loop()
    bind_port = port or app.cfg.web_port

    class _Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b""
            hdrs = {k: v for k, v in self.headers.items()}
            code, resp_body, resp_headers = app.handle_request(method, self.path, hdrs, body)
            self.send_response(code)
            for hk, hv in resp_headers.items():
                self.send_header(hk, hv)
            self.end_headers()
            if resp_body:
                self.wfile.write(resp_body.encode("utf-8"))

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, bind_port), _Handler)
    print(f"[PRADO UBUNTU WEB SERVER] Painel rodando em http://{host}:{bind_port}")
    print("[PRADO UBUNTU WEB SERVER] Login padrao: admin / prado2026")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.service.stop_background_loop()
        server.server_close()
