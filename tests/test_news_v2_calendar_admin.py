"""TDD tests for News V2: RSS+Atom, PT-BR sentiment, recency weighting, feed_status, Economic Calendar & Admin-only feeds."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import time

import pytest

from prado_linux.config import load_config
from prado_linux.news_scout import (
    CURATED_NEWS_CATALOG,
    EconomicCalendarScout,
    NewsScout,
    analyze_headline,
    parse_rss_xml,
)
from prado_linux.web_app import PradoWebApp


class _FakeNewsMultiTenantSupabase:
    is_enabled = True

    def __init__(self) -> None:
        self.users = {
            "sitepixer@gmail.com": {"user_id": "uid-admin", "email": "sitepixer@gmail.com"},
            "cliente@teste.com": {"user_id": "uid-client", "email": "cliente@teste.com"},
        }

    def sign_up(self, email: str, password: str) -> tuple[bool, dict]:
        return True, {"user_id": f"uid-{email}", "email": email, "access_token": "tok"}

    def sign_in(self, email: str, password: str) -> tuple[bool, dict]:
        rec = self.users[email.lower()]
        return True, {"user_id": rec["user_id"], "email": rec["email"], "access_token": f"tok-{rec['user_id']}"}

    def load_user_config(self, user_id: str, access_token: str, fallback_path: Path):
        return load_config(fallback_path, inherit_user_tokens=False)

    def sync_user_config(self, user_id: str, access_token: str, cfg) -> None:
        return None

    def load_saas_tables(self):
        return None

    def upsert_saas_settings(self, settings_dict: dict) -> None:
        return None

    def upsert_saas_plan(self, plan_dict: dict) -> None:
        return None

    def upsert_saas_subscription(self, sub_dict: dict) -> None:
        return None


def _login_cookie(app: PradoWebApp, email: str) -> str:
    body = json.dumps({"email": email, "password": "secret"}).encode()
    code, _, headers = app.handle_request("POST", "/api/login", {}, body)
    assert code == 200
    return headers["Set-Cookie"].split(";", 1)[0]


def test_parse_atom_feed_and_ptbr_sentiment_classification() -> None:
    assert len(CURATED_NEWS_CATALOG) >= 4
    assert all("fxstreet.com/rss/news" not in item["url"] for item in CURATED_NEWS_CATALOG)
    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Noticias Mercado</title>
      <entry>
        <title>Fed sinaliza corte de juros e ouro dispara para recorde</title>
        <link href="https://example.com/ouro-alta" />
        <updated>2026-11-26T14:00:00Z</updated>
        <summary>Ouro dispara após declaração dovish do Fed.</summary>
      </entry>
      <entry>
        <title>Inflação acelera e bolsa desaba com temores de recessão</title>
        <link href="https://example.com/bolsa-desaba" />
        <updated>2026-11-26T13:30:00Z</updated>
        <summary>Nasdaq e S&amp;P recuam forte hoje.</summary>
      </entry>
    </feed>"""

    items = parse_rss_xml(atom_xml, source="Atom BR", default_symbol="XAUUSD")
    assert len(items) == 2
    assert items[0]["link"] == "https://example.com/ouro-alta"
    assert items[0]["impact"] == "HIGH"
    assert items[0]["bias"] == "BULLISH"
    assert items[0]["symbol"] == "XAUUSD"
    assert items[0]["is_macro_usd"] is True

    assert items[1]["impact"] == "HIGH"
    assert items[1]["bias"] == "BEARISH"

    pt = analyze_headline("Bitcoin dispara após aprovação de ETF", "", fallback_symbol="EURUSD")
    assert pt["symbol"] == "BTCUSD"
    assert pt["bias"] == "BULLISH"
    assert pt["impact"] == "HIGH"


def test_news_scout_recency_weighting_and_feed_status() -> None:
    now = time.time()

    def _fetcher(url: str) -> str:
        if "fail" in url:
            raise OSError("timeout")
        return "<rss><channel><item><title>Bitcoin surges strongly</title><link>https://ok/1</link></item></channel></rss>"

    scout = NewsScout(fetcher=_fetcher)
    feeds = [
        {"feed_id": "ok1", "source": "OkFeed", "url": "https://ok.example/rss", "default_symbol": "BTCUSD"},
        {"feed_id": "bad1", "source": "BadFeed", "url": "https://fail.example/rss", "default_symbol": "EURUSD"},
    ]
    items, _ = scout.scan(feeds=feeds)
    assert len(items) == 1
    assert len(scout.feed_status) == 2
    ok_st = next(s for s in scout.feed_status if s["feed_id"] == "ok1")
    bad_st = next(s for s in scout.feed_status if s["feed_id"] == "bad1")
    assert ok_st["ok"] is True and ok_st["count"] == 1
    assert bad_st["ok"] is False and "timeout" in bad_st["error"].lower()
    assert "BadFeed" in scout.last_error

    # Recency weighting: 10-min old bullish item beats 5-day old bearish item
    scout.items = [
        {"id": "1", "symbol": "EURUSD", "impact": "HIGH", "bias": "BULLISH", "score": 0.9, "published_ts": now - 600},
        {"id": "2", "symbol": "EURUSD", "impact": "HIGH", "bias": "BEARISH", "score": -0.9, "published_ts": now - 5 * 86400},
    ]
    summary = scout.summary_by_symbol(now_ts=now)
    assert summary["EURUSD"]["bias"] == "BULLISH"
    assert summary["EURUSD"]["avg_score"] > 0.1


def test_economic_calendar_scout_parse_and_error_handling() -> None:
    now_ts = time.time()
    future_iso = datetime.fromtimestamp(now_ts + 3600, tz=timezone.utc).isoformat()
    past_iso = datetime.fromtimestamp(now_ts - 3600, tz=timezone.utc).isoformat()

    payload = json.dumps(
        [
            {"title": "Non-Farm Employment Change", "country": "USD", "date": future_iso, "impact": "High", "forecast": "185K", "previous": "170K"},
            {"title": "Retail Sales m/m", "country": "EUR", "date": past_iso, "impact": "Medium", "forecast": "0.3%", "previous": "0.1%"},
        ]
    )
    cal = EconomicCalendarScout(fetcher=lambda _url: payload)
    events = cal.fetch_week(force=True)
    assert len(events) == 2
    snap = cal.snapshot_dict(now_ts=now_ts)
    assert snap["last_error"] == ""
    assert snap["next_high_impact"] is not None
    assert snap["next_high_impact"]["currency"] == "USD"
    assert snap["next_high_impact"]["is_upcoming"] is True

    cal_err = EconomicCalendarScout(fetcher=lambda _url: (_ for _ in ()).throw(OSError("network down")))
    assert cal_err.fetch_week(force=True) == []
    assert "network down" in cal_err.last_error.lower()


def test_economic_calendar_shared_cache_anti_429_and_upcoming_first(tmp_path: Path) -> None:
    EconomicCalendarScout.clear_shared_cache()
    now_ts = time.time()
    future_early = datetime.fromtimestamp(now_ts + 1800, tz=timezone.utc).isoformat()
    future_late = datetime.fromtimestamp(now_ts + 7200, tz=timezone.utc).isoformat()
    past_old = datetime.fromtimestamp(now_ts - 7200, tz=timezone.utc).isoformat()
    past_recent = datetime.fromtimestamp(now_ts - 1800, tz=timezone.utc).isoformat()

    calls = 0
    payload = json.dumps(
        [
            {"title": "Past Old", "country": "AUD", "date": past_old, "impact": "Low"},
            {"title": "Future Late", "country": "EUR", "date": future_late, "impact": "Medium"},
            {"title": "Past Recent", "country": "GBP", "date": past_recent, "impact": "Low"},
            {"title": "Future Early", "country": "USD", "date": future_early, "impact": "High"},
        ]
    )

    def _counting_fetcher(_url: str) -> str:
        nonlocal calls
        calls += 1
        return payload

    cache_file = tmp_path / "cal_cache.json"
    cal = EconomicCalendarScout(
        fetcher=_counting_fetcher,
        cache_path=cache_file,
        min_force_interval_sec=300,
    )
    events = cal.fetch_week(force=True)
    assert calls == 1
    assert len(events) == 4
    assert cache_file.exists()

    # Second force=True within 5-minute protection window skips network hit
    events2 = cal.fetch_week(force=True)
    assert calls == 1
    assert len(events2) == 4
    assert cal.last_error == ""

    # Upcoming events sorted first ascending, then past events descending (most recent past first)
    snap = cal.snapshot_dict(now_ts=now_ts)
    titles = [e["title"] for e in snap["events"]]
    assert titles == ["Future Early", "Future Late", "Past Recent", "Past Old"]

    # Simulate 429 error while cached events exist -> NO scary last_error, sets status_note + cooldown
    def _rate_limited(_url: str) -> str:
        raise OSError("HTTP Error 429: Too Many Requests")

    cal_cached_429 = EconomicCalendarScout(
        fetcher=_rate_limited,
        cache_path=cache_file,
        min_force_interval_sec=0,
        rate_limit_cooldown_sec=600,
    )
    res_429 = cal_cached_429.fetch_week(force=True)
    assert len(res_429) == 4
    assert cal_cached_429.last_error == ""
    assert "cache" in cal_cached_429.status_note.lower()

    # Without cache, 429 yields friendly PT-BR error (not raw technical HTTP 429)
    EconomicCalendarScout.clear_shared_cache()
    cal_cold_429 = EconomicCalendarScout(fetcher=_rate_limited)
    assert cal_cold_429.fetch_week(force=True) == []
    assert "429" not in cal_cold_429.last_error
    assert "limite" in cal_cold_429.last_error.lower() or "ocupada" in cal_cold_429.last_error.lower()


def test_web_app_admin_only_feeds_and_calendar_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sb = _FakeNewsMultiTenantSupabase()
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=fake_sb)  # type: ignore[arg-type]

    admin_cookie = _login_cookie(app, "sitepixer@gmail.com")
    client_cookie = _login_cookie(app, "cliente@teste.com")

    # Give client Elite plan (includes news_bot feature)
    app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "cliente@teste.com", "plan_id": "institutional", "status": "active", "duration_days": 30}).encode(),
    )

    # Client with news_bot is gated until own AI key is configured, then CAN scan news & calendar
    cli_svc = app._active_service("uid-client")
    monkeypatch.setattr(cli_svc.news_scout, "scan", lambda feeds=None: ([], []))
    monkeypatch.setattr(cli_svc.economic_calendar, "fetch_week", lambda force=False: [])
    c_gate, b_gate, _ = app.handle_request("POST", "/api/news/scan", {"Cookie": client_cookie}, b"{}")
    assert c_gate == 400
    assert json.loads(b_gate)["code"] == "AI_API_KEY_REQUIRED"
    assert (
        app.handle_request(
            "POST",
            "/api/config",
            {"Cookie": client_cookie},
            json.dumps(
                {
                    "news_ai_enabled": True,
                    "news_ai_provider": "gemini",
                    "news_ai_model": "gemini-3.5-flash-lite",
                    "news_ai_api_key": "client-test-key",
                }
            ).encode(),
        )[0]
        == 200
    )
    assert app.handle_request("POST", "/api/news/scan", {"Cookie": client_cookie}, b"{}")[0] == 200
    assert app.handle_request("POST", "/api/news/calendar", {"Cookie": client_cookie}, b"{}")[0] == 200

    # Client CANNOT create/edit/delete/reset news feeds (403 Admin Only)
    c_cli_feed, b_cli_feed, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        {"Cookie": client_cookie},
        json.dumps({"source": "Hacked", "url": "https://example.com/rss", "default_symbol": "EURUSD"}).encode(),
    )
    assert c_cli_feed == 403
    assert "administrador" in json.loads(b_cli_feed)["error"].lower()

    # Admin CAN save global feed and it propagates to existing client service
    c_adm_feed, _, _ = app.handle_request(
        "POST",
        "/api/news/feeds",
        {"Cookie": admin_cookie},
        json.dumps({"source": "InfoMoney Global", "url": "https://example.com/infomoney.xml", "default_symbol": "ALL"}).encode(),
    )
    assert c_adm_feed == 200
    global_feeds = app.saas.get_global_news_feeds()
    assert any(f.get("source") == "InfoMoney Global" for f in global_feeds)
    assert any(f.get("source") == "InfoMoney Global" for f in cli_svc.cfg.news_feeds)
