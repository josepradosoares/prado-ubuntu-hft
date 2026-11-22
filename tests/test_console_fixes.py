import json
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
