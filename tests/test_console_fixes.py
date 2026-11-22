import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from prado_linux.auth import create_session_token
from prado_linux.web_app import PradoWebApp, STATIC_DIR


def _auth_headers(app: PradoWebApp) -> dict[str, str]:
    token = create_session_token(app.cfg.admin_username, app.cfg.secret_key)
    return {"Cookie": f"prado_session={token}"}


def test_favicon_served_without_auth_and_html_references_it(tmp_path: Path):
    app = PradoWebApp(config_path=tmp_path / "config.json")

    code_ico, body_ico, hdrs_ico = app.handle_request("GET", "/favicon.ico", {})
    assert code_ico == 200
    assert isinstance(body_ico, bytes)
    assert len(body_ico) > 0
    assert "image/x-icon" in hdrs_ico["Content-Type"]

    code_svg, body_svg, hdrs_svg = app.handle_request("GET", "/favicon.svg", {})
    assert code_svg == 200
    assert isinstance(body_svg, str)
    assert "<svg" in body_svg
    assert "image/svg+xml" in hdrs_svg["Content-Type"]

    code_root, body_root, _ = app.handle_request("GET", "/", _auth_headers(app))
    assert code_root == 200
    assert isinstance(body_root, str)
    assert "/favicon.svg" in body_root
    assert "/favicon.ico" in body_root


def test_bot_templates_and_no_legacy_templates_reference_in_bundle(tmp_path: Path):
    app = PradoWebApp(config_path=tmp_path / "config.json")
    code, body, _ = app.handle_request("GET", "/api/bot-templates", _auth_headers(app))
    assert code == 200
    payload = json.loads(body)
    assert payload["ok"] is True
    assert len(payload["templates"]) > 0

    assets_dir = STATIC_DIR / "assets"
    js_files = list(assets_dir.glob("*.js"))
    assert js_files, "Compiled JS bundle must exist in prado_linux/static/assets"
    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8")
        assert "/api/templates" not in content


def test_chart_and_status_endpoints_return_valid_json(tmp_path: Path):
    app = PradoWebApp(config_path=tmp_path / "config.json")
    headers = _auth_headers(app)

    code_st, body_st, _ = app.handle_request("GET", "/api/status", headers)
    assert code_st == 200
    snap = json.loads(body_st)
    assert "account" in snap
    assert "symbols" in snap
    assert "bots" in snap

    code_ch, body_ch, _ = app.handle_request("GET", "/api/chart?symbol=R_100", headers)
    assert code_ch == 200
    chart = json.loads(body_ch)
    assert chart["ok"] is True
    assert chart["symbol"] == "R_100"
    assert isinstance(chart["points"], list)


def test_live_http_server_serves_static_assets_favicon_and_api(tmp_path: Path):
    app = PradoWebApp(config_path=tmp_path / "config.json")
    token = create_session_token(app.cfg.admin_username, app.cfg.secret_key)

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
                self.wfile.write(resp_body if isinstance(resp_body, bytes) else resp_body.encode("utf-8"))

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def log_message(self, format: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/favicon.ico", timeout=5) as r:
            assert r.status == 200
            assert len(r.read()) > 0

        with urllib.request.urlopen(f"{base}/favicon.svg", timeout=5) as r:
            assert r.status == 200
            assert b"<svg" in r.read()

        with urllib.request.urlopen(f"{base}/login", timeout=5) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
            assert "/favicon.svg" in html

        req_tpl = urllib.request.Request(
            f"{base}/api/bot-templates",
            headers={"Cookie": f"prado_session={token}"},
        )
        with urllib.request.urlopen(req_tpl, timeout=5) as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
            assert data["ok"] is True

        req_legacy = urllib.request.Request(
            f"{base}/api/templates",
            headers={"Cookie": f"prado_session={token}"},
        )
        try:
            urllib.request.urlopen(req_legacy, timeout=5)
            raise AssertionError("Expected 404 for /api/templates")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()
