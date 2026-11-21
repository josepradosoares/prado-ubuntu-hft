"""Zero-dependency HTTP Web Application & REST API for Prado Institutional HFT Ubuntu Server."""
from __future__ import annotations

from dataclasses import asdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from prado_linux.auth import create_session_token, hash_password, verify_password, verify_session_token
from prado_linux.config import load_config
from prado_linux.engine import PradoTradingService
from prado_linux.templates import DASHBOARD_HTML, LOGIN_HTML


class PradoWebApp:
    """Testable WSGI/HTTP router for Login, MT5 Connection, Strategy Config, and Real-Time Monitoring."""

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
        return d

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, str, dict[str, str]]:
        method = method.upper()
        clean_path = path.split("?", 1)[0]

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
            return (
                302,
                "",
                {"Location": "/login"},
            )

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
            if reconnect or "mt5_login" in updates or "mt5_server" in updates:
                _, conn_msg = self.service.reconnect_mt5()
                msg = conn_msg

            self.service.step_once()
            return (
                200,
                json.dumps({"ok": True, "message": msg, "config": self._safe_config_dict()}, ensure_ascii=False),
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
