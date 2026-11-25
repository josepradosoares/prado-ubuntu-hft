from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from prado_linux.config import DEFAULT_CATEGORIES, PradoServerConfig
from prado_linux.news_scout import DEFAULT_NEWS_FEEDS
from prado_linux.supabase_store import SupabaseConfig, SupabaseStore, _read_dotenv_fallback


class _DummyResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_DummyResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


def test_dotenv_and_config_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n'
        'INVALID_LINE\n'
        'SUPABASE_URL="https://demo.supabase.co/"\n'
        "SUPABASE_PUBLISHABLE_KEY='pub_key_123'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("prado_linux.supabase_store.__file__", str(tmp_path / "pkg" / "supabase_store.py"))
    monkeypatch.setattr("prado_linux.supabase_store._read_dotenv_fallback", _read_dotenv_fallback)
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)

    parsed = _read_dotenv_fallback()
    assert parsed["SUPABASE_URL"] == "https://demo.supabase.co/"
    assert parsed["SUPABASE_PUBLISHABLE_KEY"] == "pub_key_123"

    cfg = SupabaseConfig.from_env()
    assert cfg.url == "https://demo.supabase.co"
    assert cfg.anon_key == "pub_key_123"
    assert cfg.is_enabled is True

    store = SupabaseStore.from_env()
    assert store.is_enabled is True
    assert store._api_key() == "pub_key_123"


def test_request_success_http_error_and_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseStore(SupabaseConfig(url="https://demo.supabase.co", anon_key="anon", service_role_key="svc"))

    # 200 JSON
    monkeypatch.setattr(
        "prado_linux.supabase_store.urlopen",
        lambda req, timeout=12: _DummyResponse(200, json.dumps({"ok": True})),
    )
    code, data = store._request("POST", "/rest/v1/test", {"a": 1}, extra_headers={"X-Test": "1"})
    assert code == 200 and data == {"ok": True}

    # 204 empty body
    monkeypatch.setattr(
        "prado_linux.supabase_store.urlopen",
        lambda req, timeout=12: _DummyResponse(204, ""),
    )
    code, data = store._request("DELETE", "/rest/v1/test")
    assert code == 204 and data == {}

    # HTTPError with JSON body
    def _raise_http_json(req: Any, timeout: int = 12) -> Any:
        raise HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"msg":"invalid"}'))

    monkeypatch.setattr("prado_linux.supabase_store.urlopen", _raise_http_json)
    code, data = store._request("POST", "/auth/v1/signup", {})
    assert code == 400 and data == {"msg": "invalid"}

    # HTTPError with plain text body
    def _raise_http_plain(req: Any, timeout: int = 12) -> Any:
        raise HTTPError(req.full_url, 500, "Server Error", {}, io.BytesIO(b"plain failure"))

    monkeypatch.setattr("prado_linux.supabase_store.urlopen", _raise_http_plain)
    code, data = store._request("GET", "/rest/v1/test")
    assert code == 500 and data == {"error": "plain failure"}

    # URLError -> 503
    def _raise_net(req: Any, timeout: int = 12) -> Any:
        raise URLError("offline")

    monkeypatch.setattr("prado_linux.supabase_store.urlopen", _raise_net)
    code, data = store._request("GET", "/rest/v1/test")
    assert code == 503 and "Falha de rede Supabase" in data["error"]


def test_sign_up_and_sign_in(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseStore(SupabaseConfig(url="https://demo.supabase.co", anon_key="anon"))

    monkeypatch.setattr(
        store,
        "_request",
        lambda m, p, b=None, **kw: (200, {"user": {"id": "u1", "email": "a@b.com"}, "access_token": "tok1"}),
    )
    ok, res = store.sign_up("a@b.com", "secret")
    assert ok and res == {"user_id": "u1", "email": "a@b.com", "access_token": "tok1"}

    ok, res = store.sign_in("a@b.com", "secret")
    assert ok and res["access_token"] == "tok1"

    monkeypatch.setattr(store, "_request", lambda m, p, b=None, **kw: (400, {"error_description": "bad creds"}))
    ok, res = store.sign_up("a@b.com", "bad")
    assert not ok and res["error"] == "bad creds"

    ok, res = store.sign_in("a@b.com", "bad")
    assert not ok and res["error"] == "bad creds"


def test_load_user_config_full_and_fallback_feeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseStore(SupabaseConfig(url="https://demo.supabase.co", anon_key="anon"))
    fallback = tmp_path / "config.json"

    responses = {
        "prado_settings": (
            200,
            [
                {
                    "connection_mode": "DERIV_CLOUD",
                    "allow_real_trading": True,
                    "auto_trading_enabled": False,
                    "active_account_id": "acc_1",
                    "active_account_type": "REAL",
                    "ctrader_client_id": "cid_1",
                    "ctrader_redirect_uri": "https://example.com/cb",
                    "default_lot_size": 0.05,
                    "active_symbols": ["R_100", "EURUSD"],
                    "correlated_basket": ["GBPUSD"],
                    "custom_categories": {},
                }
            ],
        ),
        "prado_ctrader_accounts": (
            200,
            [
                {
                    "account_id": "acc_1",
                    "ctid_account_id": "12345",
                    "trader_login": "999",
                    "account_type": "REAL",
                    "is_live": True,
                    "broker_name": "ICMarkets",
                    "label": "Main",
                    "access_token": "ct_tok",
                    "refresh_token": "ct_ref",
                    "default_lot_size": 0.02,
                    "balance": 1500.5,
                    "currency": "USD",
                }
            ],
        ),
        "prado_bots": (
            200,
            [
                {
                    "bot_id": "bot_1",
                    "name": "Scalper",
                    "account_id": "acc_1",
                    "symbol": "EURUSD",
                    "template_id": "CUSTOM_1",
                    "operation_mode": "BUY",
                    "timeframe": "M1",
                    "status": "RUNNING",
                    "lot_size": 0.03,
                    "realized_pnl": 12.5,
                    "config_json": {"tp_mode": "fixed", "tp_value": 5.0},
                }
            ],
        ),
        "prado_custom_templates": (
            200,
            [
                {
                    "template_id": "tpl_1",
                    "name": "MyTpl",
                    "description": "desc",
                    "custom_mode": "INDICATORS",
                    "combine_mode": "ALL",
                    "indicators": [{"id": "SMA"}],
                    "config_json": {"window_ticks": 80, "zscore_threshold": 2.1},
                }
            ],
        ),
        "prado_news_feeds": (
            200,
            [
                {
                    "feed_id": "f1",
                    "source": "FXStreet",
                    "url": "https://fxstreet.com/rss",
                    "default_symbol": "EURUSD",
                }
            ],
        ),
    }

    def _fake_req(method: str, path: str, body: Any = None, **kw: Any) -> tuple[int, Any]:
        for key, resp in responses.items():
            if key in path:
                return resp
        return 404, {}

    monkeypatch.setattr(store, "_request", _fake_req)
    cfg = store.load_user_config("user_1", "tok", fallback)

    assert cfg.connection_mode == "CTRADER_CLOUD"
    assert cfg.allow_real_trading is True
    assert cfg.auto_trading_enabled is False
    assert cfg.custom_categories == DEFAULT_CATEGORIES
    assert cfg.ctrader_access_token == "ct_tok"
    assert cfg.ctrader_refresh_token == "ct_ref"
    assert len(cfg.bots) == 1 and cfg.bots[0]["active"] is True and cfg.bots[0]["tp_mode"] == "FIXED"
    assert len(cfg.custom_templates) == 1 and cfg.custom_templates[0]["window_ticks"] == 80
    assert len(cfg.news_feeds) == 1 and cfg.news_feeds[0]["feed_id"] == "f1"

    # Empty feeds fallback to DEFAULT_NEWS_FEEDS
    responses["prado_news_feeds"] = (200, [])
    responses["prado_settings"] = (200, [{"custom_categories": {"FX": ["EURUSD"]}}])
    cfg2 = store.load_user_config("user_1", "tok", fallback)
    assert cfg2.custom_categories == {"FX": ["EURUSD"]}
    assert len(cfg2.news_feeds) == len(DEFAULT_NEWS_FEEDS)


def test_sync_user_config_disabled_and_full(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, Any]] = []

    disabled = SupabaseStore(SupabaseConfig())
    monkeypatch.setattr(disabled, "_request", lambda m, p, b=None, **kw: calls.append((m, p, b)) or (200, {}))
    disabled.sync_user_config("u1", "tok", PradoServerConfig())
    assert calls == []

    store = SupabaseStore(SupabaseConfig(url="https://demo.supabase.co", anon_key="anon"))
    monkeypatch.setattr(store, "_request", lambda m, p, b=None, **kw: calls.append((m, p, b)) or (200, {}))

    cfg = PradoServerConfig(
        accounts=[{"account_id": "acc_1", "ctid_account_id": "10", "label": "Demo"}],
        bots=[{"bot_id": "b1", "name": "Bot 1", "symbol": "EURUSD"}],
        custom_templates=[{"template_id": "t1", "name": "Tpl 1"}],
        news_feeds=[{"feed_id": "f1", "source": "News", "url": "https://example.com"}],
    )
    store.sync_user_config("user_1", "tok", cfg)

    methods_paths = [(m, p.split("?")[0]) for m, p, _ in calls]
    assert ("POST", "/rest/v1/prado_settings") in methods_paths
    assert ("POST", "/rest/v1/prado_ctrader_accounts") in methods_paths
    assert ("DELETE", "/rest/v1/prado_bots") in methods_paths
    assert ("POST", "/rest/v1/prado_bots") in methods_paths
    assert ("DELETE", "/rest/v1/prado_custom_templates") in methods_paths
    assert ("POST", "/rest/v1/prado_custom_templates") in methods_paths
    assert ("DELETE", "/rest/v1/prado_news_feeds") in methods_paths
    assert ("POST", "/rest/v1/prado_news_feeds") in methods_paths
