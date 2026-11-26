"""TDD tests for Option 3: USD inversion, negation handling, 3-star Economic Calendar Shield, Pure Filter, and Optional AI."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pytest

from prado_linux.config import load_config
from prado_linux.engine import PradoTradingService
from prado_linux.news_scout import (
    AINewsAnalyzer,
    EconomicCalendarScout,
    NewsScout,
    analyze_headline,
)
from prado_linux.web_app import PradoWebApp


def test_negation_and_usd_inverse_correlation() -> None:
    neg = analyze_headline("Ouro não sustenta alta e devolve ganhos", "", fallback_symbol="XAUUSD")
    assert neg["bias"] != "BULLISH"

    eur = analyze_headline("Dólar dispara após Payroll forte nos EUA", "", fallback_symbol="EURUSD")
    assert eur["is_macro_usd"] is True
    assert eur["bias"] == "BEARISH"

    usdjpy = analyze_headline("Dólar dispara após Payroll forte nos EUA", "", fallback_symbol="USDJPY")
    assert usdjpy["bias"] == "BULLISH"

    gold_cut = analyze_headline("Fed sinaliza corte de juros e dólar recua", "", fallback_symbol="XAUUSD")
    assert gold_cut["bias"] == "BULLISH"


def test_calendar_3star_shield_blocks_matching_currency_inside_window(tmp_path: Path) -> None:
    EconomicCalendarScout.clear_shared_cache()
    now_ts = time.time()
    usd_10m = datetime.fromtimestamp(now_ts + 600, tz=timezone.utc).isoformat()
    jpy_5m = datetime.fromtimestamp(now_ts + 300, tz=timezone.utc).isoformat()
    usd_45m = datetime.fromtimestamp(now_ts + 2700, tz=timezone.utc).isoformat()

    cal = EconomicCalendarScout(
        fetcher=lambda _u: json.dumps(
            [
                {"title": "US CPI y/y", "country": "USD", "date": usd_10m, "impact": "High"},
                {"title": "BoJ Rate Decision", "country": "JPY", "date": jpy_5m, "impact": "High"},
                {"title": "FOMC Minutes", "country": "USD", "date": usd_45m, "impact": "High"},
            ]
        )
    )
    cal.fetch_week(force=True)

    # Inside 15 min window: USD blocks EURUSD & XAUUSD, JPY does NOT block EURUSD, 45m USD is outside window
    active_eur = cal.get_active_shield_events("EURUSD", window_minutes=15, now_ts=now_ts)
    assert len(active_eur) == 1
    assert active_eur[0]["currency"] == "USD"
    assert active_eur[0]["title"] == "US CPI y/y"

    assert cal.get_active_shield_events("EURGBP", window_minutes=15, now_ts=now_ts) == []

    # Wire into PradoTradingService.step_once -> shields EURUSD bot from opening order
    cfg = load_config(tmp_path / "cfg_shield.json")
    cfg.connection_mode = "SIMULATION"
    cfg.ctrader_access_token = ""
    cfg.news_calendar_shield_enabled = True
    cfg.news_calendar_pause_minutes = 15
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg_shield.json")
    svc.economic_calendar = cal

    bot = svc.create_bot({"name": "Grid EURUSD", "symbol": "EURUSD", "template_id": "GRID_LINEAR_HFT", "auto_start": True})
    svc.step_once()
    assert bot["last_signal"] == "SHIELD_CALENDAR"
    assert "ESCUDO 3" in str(bot.get("last_regime") or "").upper()
    assert len(svc.connector.get_open_positions()) == 0


def test_pure_filter_mode_waits_for_tech_and_blocks_contradiction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    EconomicCalendarScout.clear_shared_cache()
    cfg = load_config(tmp_path / "cfg_filter.json")
    cfg.connection_mode = "SIMULATION"
    cfg.ctrader_access_token = ""
    cfg.news_calendar_shield_enabled = False
    cfg.news_filter_only = True
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg_filter.json")

    bot = svc.create_bot({"name": "PureFilter", "symbol": "EURUSD", "news_assisted": True, "auto_start": True})
    monkeypatch.setattr(svc.news_scout, "summary_by_symbol", lambda: {"EURUSD": {"bias": "BULLISH", "high_impact": 0}})

    # 1. Technical signal WAIT + BULLISH news => MUST NOT open order in pure filter mode
    class _FlowWait:
        vwap = 1.10
        std_dev = 0.002
        aggression_zscore = 0.2
        imbalance_ratio = 0.1
        regime = "NEUTRAL"
        recommended_action = "WAIT"
        sl_points = 0.002
        tp_points = 0.004

    monkeypatch.setattr("prado_linux.engine.compute_flow_metrics", lambda *a, **kw: _FlowWait())
    svc.step_once()
    assert len(svc.connector.get_open_positions()) == 0
    assert bot["last_signal"] == "WAIT"

    # 2. Technical BUY_FLOW + BEARISH news => BLOCKED_BY_NEWS
    class _FlowBuy(_FlowWait):
        recommended_action = "BUY_FLOW"

    monkeypatch.setattr("prado_linux.engine.compute_flow_metrics", lambda *a, **kw: _FlowBuy())
    monkeypatch.setattr(svc.news_scout, "summary_by_symbol", lambda: {"EURUSD": {"bias": "BEARISH", "high_impact": 1}})
    svc.step_once()
    assert bot["last_signal"] == "BLOCKED_BY_NEWS"
    assert len(svc.connector.get_open_positions()) == 0

    # 3. Technical BUY_FLOW + BULLISH news => executes BUY_FLOW
    monkeypatch.setattr(svc.news_scout, "summary_by_symbol", lambda: {"EURUSD": {"bias": "BULLISH", "high_impact": 0}})
    svc.step_once()
    assert bot["trades_executed"] == 1
    assert len(svc.connector.get_open_positions()) == 1


def test_ai_news_analyzer_gemini_openai_cache_and_fallback() -> None:
    calls = 0

    def _gemini_poster(url: str, headers: dict, body: dict) -> dict:
        nonlocal calls
        calls += 1
        assert "generativelanguage.googleapis.com" in url
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    [
                                        {
                                            "id": body["contents"][0]["parts"][0]["text"].split("ID=")[1].split(" ")[0],
                                            "symbol": "XAUUSD",
                                            "impact": "HIGH",
                                            "bias": "BULLISH",
                                            "score": 0.85,
                                            "reason": "Corte de juros enfraquece dólar e impulsiona ouro.",
                                        }
                                    ]
                                )
                            }
                        ]
                    }
                }
            ]
        }

    rss_xml = "<rss><channel><item><title>Fed signals rate cut ahead</title><link>https://ex/1</link></item></channel></rss>"
    scout = NewsScout(fetcher=lambda _u: rss_xml)
    scout.configure_ai(enabled=True, provider="gemini", api_key="fake-gemini-key", model="gemini-2.0-flash", http_poster=_gemini_poster)

    items1, _ = scout.scan(feeds=[{"feed_id": "f1", "source": "Test", "url": "https://ex/rss", "default_symbol": "EURUSD"}])
    assert calls == 1
    assert items1[0]["analysis_source"] == "AI_GEMINI"
    assert items1[0]["bias"] == "BULLISH"
    assert items1[0]["symbol"] == "XAUUSD"
    assert "ouro" in items1[0]["ai_reason"].lower()

    # Second scan with same headline hits cache -> 0 new AI calls
    items2, _ = scout.scan(feeds=[{"feed_id": "f1", "source": "Test", "url": "https://ex/rss", "default_symbol": "EURUSD"}])
    assert calls == 1
    assert items2[0]["analysis_source"] == "AI_GEMINI"

    # OpenAI provider & fallback on error
    oa_calls = 0

    def _openai_poster(url: str, headers: dict, body: dict) -> dict:
        nonlocal oa_calls
        oa_calls += 1
        assert "api.openai.com" in url
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "id": body["messages"][1]["content"].split("ID=")[1].split(" ")[0],
                                        "symbol": "BTCUSD",
                                        "impact": "HIGH",
                                        "bias": "BULLISH",
                                        "score": 0.9,
                                        "reason": "Fluxo institucional positivo em BTC.",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }

    scout_oa = NewsScout(fetcher=lambda _u: "<rss><channel><item><title>Bitcoin ETF inflows jump</title><link>https://ex/2</link></item></channel></rss>")
    scout_oa.configure_ai(enabled=True, provider="openai", api_key="fake-oa-key", model="gpt-4o-mini", http_poster=_openai_poster)
    oa_items, _ = scout_oa.scan(feeds=[{"feed_id": "f2", "source": "Test", "url": "https://ex/rss2", "default_symbol": "ALL"}])
    assert oa_calls == 1
    assert oa_items[0]["analysis_source"] == "AI_OPENAI"
    assert oa_items[0]["symbol"] == "BTCUSD"

    # Failing AI gracefully falls back to LOCAL_RULES
    failing_ai = AINewsAnalyzer(
        enabled=True,
        provider="gemini",
        api_key="k",
        http_poster=lambda *_a: (_ for _ in ()).throw(OSError("AI down")),
    )
    fallback_items = [{"id": "x1", "title": "Bitcoin surges today", "symbol": "BTCUSD", "impact": "MEDIUM", "bias": "BULLISH", "score": 0.4, "analysis_source": "LOCAL_RULES", "ai_reason": ""}]
    res = failing_ai.enrich_items(fallback_items)
    assert res[0]["analysis_source"] == "LOCAL_RULES"


def test_admin_ai_settings_masking_and_persistence(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "cfg_ai.json")
    login_body = json.dumps({"username": "admin", "password": app.cfg.admin_username if False else "prado2026"}).encode()
    code, _, headers = app.handle_request("POST", "/api/login", {}, login_body)
    assert code == 200
    cookie = headers["Set-Cookie"].split(";", 1)[0]

    c_save, _, _ = app.handle_request(
        "POST",
        "/api/admin/settings",
        {"Cookie": cookie},
        json.dumps(
            {
                "ai_news_enabled": True,
                "ai_news_provider": "gemini",
                "ai_news_model": "gemini-2.0-flash",
                "ai_news_api_key": "secret_gemini_key_123",
            }
        ).encode(),
    )
    assert c_save == 200
    assert app.service.news_scout._ai_analyzer.enabled is True
    assert app.service.news_scout._ai_analyzer.api_key == "secret_gemini_key_123"

    # Admin overview masks secret key
    c_ov, b_ov, _ = app.handle_request("GET", "/api/admin/overview", {"Cookie": cookie})
    assert c_ov == 200
    ov = json.loads(b_ov)
    assert ov["settings"]["ai_news_enabled"] is True
    assert ov["settings"]["ai_news_api_key_set"] is True
    assert ov["settings"]["ai_news_api_key"] == ""
