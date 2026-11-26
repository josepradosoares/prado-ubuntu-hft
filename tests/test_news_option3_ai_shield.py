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
    AI_PROVIDER_CATALOG,
    AINewsAnalyzer,
    DEFAULT_GEMINI_MODEL,
    EconomicCalendarScout,
    NewsScout,
    analyze_headline,
    friendly_ai_error,
    list_ai_provider_models,
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


def test_ai_news_analyzer_claude_openrouter_deepseek_groq_xai_custom_and_test_connection() -> None:
    provider_ids = {p["id"] for p in AI_PROVIDER_CATALOG}
    assert {"gemini", "openai", "claude", "openrouter", "deepseek", "groq", "xai", "custom"} <= provider_ids
    for p in AI_PROVIDER_CATALOG:
        assert {"id", "name", "default_model", "models", "needs_base_url"} <= set(p.keys())

    # 1. Anthropic Claude
    claude_calls: list[tuple[str, dict, dict]] = []

    def _claude_poster(url: str, headers: dict, body: dict) -> dict:
        claude_calls.append((url, headers, body))
        iid = body["messages"][0]["content"].split("ID=")[1].split(" ")[0]
        return {
            "content": [
                {
                    "type": "text",
                    "text": "```json\n"
                    + json.dumps(
                        [
                            {
                                "id": iid,
                                "symbol": "EURUSD",
                                "impact": "HIGH",
                                "bias": "BULLISH",
                                "score": 0.72,
                                "reason": "BCE mantém tom firme e fortalece o euro.",
                            }
                        ]
                    )
                    + "\n```",
                }
            ]
        }

    analyzer = AINewsAnalyzer(
        enabled=True,
        provider="claude",
        api_key="sk-ant-test",
        model="claude-3-5-haiku-latest",
        http_poster=_claude_poster,
    )
    res_cl = analyzer.enrich_items(
        [{"id": "c1", "title": "ECB turns hawkish", "symbol": "EURUSD", "impact": "LOW", "bias": "NEUTRAL", "score": 0.0}]
    )
    assert res_cl[0]["analysis_source"] == "AI_CLAUDE"
    assert res_cl[0]["bias"] == "BULLISH"
    assert claude_calls[0][0] == "https://api.anthropic.com/v1/messages"
    assert claude_calls[0][1]["x-api-key"] == "sk-ant-test"
    assert claude_calls[0][1]["anthropic-version"] == "2023-06-01"

    # Cache invalidation when configure switches provider/model
    oai_compat_calls: list[tuple[str, dict, dict]] = []

    def _compat_poster(url: str, headers: dict, body: dict) -> dict:
        oai_compat_calls.append((url, headers, body))
        iid = body["messages"][1]["content"].split("ID=")[1].split(" ")[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "id": iid,
                                    "symbol": "XAUUSD",
                                    "impact": "HIGH",
                                    "bias": "BEARISH",
                                    "score": -0.65,
                                    "reason": "Dólar forte pressiona o ouro.",
                                }
                            ]
                        )
                    }
                }
            ]
        }

    analyzer.configure(
        enabled=True,
        provider="openrouter",
        api_key="sk-or-test",
        model="anthropic/claude-3.5-haiku",
        http_poster=_compat_poster,
    )
    assert analyzer._cache == {}
    res_or = analyzer.enrich_items(
        [{"id": "c1", "title": "ECB turns hawkish", "symbol": "EURUSD", "impact": "LOW", "bias": "NEUTRAL", "score": 0.0}]
    )
    assert res_or[0]["analysis_source"] == "AI_OPENROUTER"
    assert oai_compat_calls[-1][0] == "https://openrouter.ai/api/v1/chat/completions"
    assert "response_format" not in oai_compat_calls[-1][2]
    assert oai_compat_calls[-1][1]["HTTP-Referer"]

    # DeepSeek, Groq, xAI, Custom base_url
    for prov, expected_url, expected_tag in (
        ("deepseek", "https://api.deepseek.com/chat/completions", "AI_DEEPSEEK"),
        ("groq", "https://api.groq.com/openai/v1/chat/completions", "AI_GROQ"),
        ("xai", "https://api.x.ai/v1/chat/completions", "AI_XAI"),
    ):
        analyzer.configure(enabled=True, provider=prov, api_key="sk-x", model="m1", http_poster=_compat_poster)
        out = analyzer.enrich_items([{"id": f"id_{prov}", "title": "Fed speaks", "symbol": "ALL"}])
        assert out[0]["analysis_source"] == expected_tag
        assert oai_compat_calls[-1][0] == expected_url

    analyzer.configure(
        enabled=True,
        provider="custom",
        api_key="sk-mistral",
        model="mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        http_poster=_compat_poster,
    )
    out_custom = analyzer.enrich_items([{"id": "id_cust", "title": "US CPI beats", "symbol": "EURUSD"}])
    assert out_custom[0]["analysis_source"] == "AI_CUSTOM"
    assert oai_compat_calls[-1][0] == "https://api.mistral.ai/v1/chat/completions"

    # OpenAI reasoning model omits temperature
    analyzer.configure(enabled=True, provider="openai", api_key="sk-oa", model="o4-mini", http_poster=_compat_poster)
    analyzer.enrich_items([{"id": "id_o4", "title": "NFP release", "symbol": "EURUSD"}])
    assert "temperature" not in oai_compat_calls[-1][2]

    # test_connection success & failures
    ok_conn = analyzer.test_connection()
    assert ok_conn["ok"] is True
    assert ok_conn["provider"] == "openai"
    assert ok_conn["model"] == "o4-mini"
    assert ok_conn["bias"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(ok_conn["latency_ms"], int)

    no_key = AINewsAnalyzer(enabled=True, provider="openai", api_key="")
    assert no_key.test_connection()["ok"] is False

    err_ai = AINewsAnalyzer(
        enabled=True,
        provider="openai",
        api_key="bad",
        http_poster=lambda *_a: (_ for _ in ()).throw(RuntimeError("HTTP 401: Unauthorized")),
    )
    err_conn = err_ai.test_connection()
    assert err_conn["ok"] is False
    assert "inválida" in err_conn["error"].lower()


def test_subscriber_byok_ai_config_isolation_and_test_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_saas_plans_kiwify import _FakeMultiTenantSupabase, _login_cookie

    fake_sb = _FakeMultiTenantSupabase()
    app = PradoWebApp(config_path=tmp_path / "cfg_byok.json", supabase_store=fake_sb)  # type: ignore[arg-type]

    admin_cookie = _login_cookie(app, "sitepixer@gmail.com")
    # Grant Elite (includes news_bot) to cliente@teste.com
    c_grant, _, _ = app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "cliente@teste.com", "plan_id": "institutional", "status": "active", "duration_days": 30}).encode(),
    )
    assert c_grant == 200
    client_cookie = _login_cookie(app, "cliente@teste.com")

    # 1. GET / serves Cache-Control: no-store
    c_idx, _, idx_headers = app.handle_request("GET", "/", {"Cookie": client_cookie})
    assert c_idx == 200
    assert "no-store" in idx_headers.get("Cache-Control", "")

    # 2. Subscriber saves BYOK config
    c_cfg, b_cfg, _ = app.handle_request(
        "POST",
        "/api/config",
        {"Cookie": client_cookie},
        json.dumps(
            {
                "news_ai_enabled": True,
                "news_ai_provider": "openrouter",
                "news_ai_model": "anthropic/claude-3.5-haiku",
                "news_ai_api_key": "sk-or-user-secret-123",
            }
        ).encode(),
    )
    assert c_cfg == 200
    cfg_resp = json.loads(b_cfg)["config"]
    assert cfg_resp["news_ai_api_key"] == "********"
    assert cfg_resp["news_ai_api_key_set"] is True

    # 3. GET /api/status exposes catalog & metadata without leaking secret
    c_st, b_st, _ = app.handle_request("GET", "/api/status", {"Cookie": client_cookie})
    assert c_st == 200
    assert "sk-or-user-secret-123" not in b_st
    news_st = json.loads(b_st)["news"]
    assert news_st["ai_enabled"] is True
    assert news_st["ai_active"] is True
    assert news_st["ai_provider"] == "openrouter"
    assert news_st["ai_model"] == "anthropic/claude-3.5-haiku"
    assert news_st["ai_api_key_set"] is True
    assert len(news_st["ai_providers"]) >= 8

    # 4. Updating another setting with masked key preserves real key
    app.handle_request(
        "POST",
        "/api/config",
        {"Cookie": client_cookie},
        json.dumps({"news_ai_api_key": "********", "news_filter_only": False}).encode(),
    )
    assert app._active_service("uid-client").cfg.news_ai_api_key == "sk-or-user-secret-123"

    # 5. SSRF protection rejects localhost base URL for custom provider
    c_ssrf, b_ssrf, _ = app.handle_request(
        "POST",
        "/api/config",
        {"Cookie": client_cookie},
        json.dumps({"news_ai_provider": "custom", "news_ai_base_url": "http://127.0.0.1:8081/v1"}).encode(),
    )
    assert c_ssrf == 400
    assert json.loads(b_ssrf)["ok"] is False

    # 6. POST /api/news/ai-test works for authorized user and blocks plan without news_bot
    def _mock_post(self, url: str, headers: dict, body: dict) -> dict:
        iid = body["messages"][1]["content"].split("ID=")[1].split(" ")[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "id": iid,
                                    "symbol": "EURUSD",
                                    "impact": "HIGH",
                                    "bias": "BULLISH",
                                    "score": 0.8,
                                    "reason": "Fed dovish favorece EURUSD.",
                                }
                            ]
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(AINewsAnalyzer, "_default_post_json", _mock_post)
    c_test, b_test, _ = app.handle_request(
        "POST",
        "/api/news/ai-test",
        {"Cookie": client_cookie},
        json.dumps({"provider": "openrouter", "model": "anthropic/claude-3.5-haiku", "api_key": "********"}).encode(),
    )
    assert c_test == 200
    t_res = json.loads(b_test)
    assert t_res["ok"] is True
    assert t_res["bias"] == "BULLISH"

    # Restrict semconta@teste.com to Starter (without news_bot) -> 403 on ai-test
    app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "semconta@teste.com", "plan_id": "starter", "status": "active", "duration_days": 30}).encode(),
    )
    locked_cookie = _login_cookie(app, "semconta@teste.com")
    c_lock, _, _ = app.handle_request("POST", "/api/news/ai-test", {"Cookie": locked_cookie}, b"{}")
    assert c_lock == 403


def test_gemini_recommended_default_and_list_ai_models_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_saas_plans_kiwify import _FakeMultiTenantSupabase, _login_cookie

    assert DEFAULT_GEMINI_MODEL == "gemini-3.5-flash-lite"
    gem_entry = next(p for p in AI_PROVIDER_CATALOG if p["id"] == "gemini")
    assert gem_entry["default_model"] == "gemini-3.5-flash-lite"
    assert gem_entry["models"][0] == "gemini-3.5-flash-lite"

    # Gemini filters to text generateContent models only
    r_gem = list_ai_provider_models(
        "gemini",
        "fake-gem-key",
        http_getter=lambda url, _hdr: {
            "models": [
                {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.8-flash-tts", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
            ]
        },
    )
    assert r_gem["ok"] is True
    assert r_gem["models"] == ["gemini-3.5-flash-lite"]

    # OpenAI-compatible provider returns sorted deduplicated model IDs
    r_oai = list_ai_provider_models(
        "openai",
        "fake-oai-key",
        http_getter=lambda _u, _h: {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4.1"}, {"id": "gpt-4o-mini"}]},
    )
    assert r_oai["ok"] is True
    assert r_oai["models"] == ["gpt-4.1", "gpt-4o-mini"]

    # Claude sends required headers
    seen_hdrs: dict = {}

    def _claude_get(_url: str, hdrs: dict) -> dict:
        seen_hdrs.update(hdrs)
        return {"data": [{"id": "claude-3-5-haiku-latest"}]}

    r_cl = list_ai_provider_models("claude", "fake-cl-key", http_getter=_claude_get)
    assert r_cl["ok"] is True
    assert r_cl["models"] == ["claude-3-5-haiku-latest"]
    assert seen_hdrs["x-api-key"] == "fake-cl-key"
    assert seen_hdrs["anthropic-version"] == "2023-06-01"

    # SSRF block on custom private URL and error on missing key
    r_ssrf = list_ai_provider_models("custom", "fake-k", base_url="http://127.0.0.1:8081/v1")
    assert r_ssrf["ok"] is False
    assert list_ai_provider_models("gemini", "")["ok"] is False

    # HTTP endpoint POST /api/news/ai-models respects news_bot entitlement
    fake_sb = _FakeMultiTenantSupabase()
    app = PradoWebApp(config_path=tmp_path / "cfg_models.json", supabase_store=fake_sb)  # type: ignore[arg-type]
    admin_cookie = _login_cookie(app, "sitepixer@gmail.com")
    app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "cliente@teste.com", "plan_id": "institutional", "status": "active", "duration_days": 30}).encode(),
    )
    app.handle_request(
        "POST",
        "/api/admin/subscriptions",
        {"Cookie": admin_cookie},
        json.dumps({"email": "semconta@teste.com", "plan_id": "starter", "status": "active", "duration_days": 30}).encode(),
    )
    client_cookie = _login_cookie(app, "cliente@teste.com")
    locked_cookie = _login_cookie(app, "semconta@teste.com")

    monkeypatch.setattr(
        "prado_linux.news_scout._default_get_json",
        lambda _u, _h: {"models": [{"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]}]},
    )
    c_ok, b_ok, _ = app.handle_request(
        "POST",
        "/api/news/ai-models",
        {"Cookie": client_cookie},
        json.dumps({"provider": "gemini", "api_key": "fake-live-key"}).encode(),
    )
    assert c_ok == 200
    assert json.loads(b_ok)["models"] == ["gemini-3.5-flash-lite"]

    c_den, _, _ = app.handle_request(
        "POST",
        "/api/news/ai-models",
        {"Cookie": locked_cookie},
        json.dumps({"provider": "gemini", "api_key": "fake-live-key"}).encode(),
    )
    assert c_den == 403


def test_openrouter_sends_bounded_max_tokens_and_gemini_503_failover() -> None:
    seen_bodies: list[dict] = []

    def _or_poster(url: str, headers: dict, body: dict) -> dict:
        seen_bodies.append(body)
        iid = body["messages"][1]["content"].split("ID=")[1].split(" ")[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                {
                                    "id": iid,
                                    "symbol": "EURUSD",
                                    "impact": "MEDIUM",
                                    "bias": "BULLISH",
                                    "score": 0.55,
                                    "reason": "OpenRouter respondeu dentro do limite.",
                                }
                            ]
                        )
                    }
                }
            ]
        }

    or_ai = AINewsAnalyzer(
        enabled=True,
        provider="openrouter",
        api_key="sk-or-test",
        model="meta-llama/llama-3.3-70b-instruct:free",
        http_poster=_or_poster,
    )
    res_or = or_ai.enrich_items([{"id": "or1", "title": "ECB steady on rates", "symbol": "EURUSD"}])
    assert res_or[0]["analysis_source"] == "AI_OPENROUTER"
    assert "max_tokens" in seen_bodies[-1]
    assert 0 < seen_bodies[-1]["max_tokens"] <= 1500

    res_conn = or_ai.test_connection()
    assert res_conn["ok"] is True
    assert seen_bodies[-1]["max_tokens"] <= 500

    # OpenAI o4-mini uses max_completion_tokens instead of max_tokens
    or_ai.configure(enabled=True, provider="openai", api_key="sk-oa-test", model="o4-mini", http_poster=_or_poster)
    or_ai.enrich_items([{"id": "oa1", "title": "Fed speaks", "symbol": "EURUSD"}])
    assert "max_completion_tokens" in seen_bodies[-1]
    assert "max_tokens" not in seen_bodies[-1]

    # Gemini 503 failover automatically tries sibling flash model
    tried_urls: list[str] = []

    def _flaky_gemini(url: str, headers: dict, body: dict) -> dict:
        tried_urls.append(url)
        if "gemini-3.5-flash-lite" in url:
            raise RuntimeError('HTTP 503: {"error":{"code":503,"message":"high demand","status":"UNAVAILABLE"}}')
        iid = body["contents"][0]["parts"][0]["text"].split("ID=")[1].split(" ")[0]
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    [
                                        {
                                            "id": iid,
                                            "symbol": "XAUUSD",
                                            "impact": "HIGH",
                                            "bias": "BULLISH",
                                            "score": 0.78,
                                            "reason": "Ouro sobe com dólar fraco.",
                                        }
                                    ]
                                )
                            }
                        ]
                    }
                }
            ]
        }

    gem_ai = AINewsAnalyzer(
        enabled=True,
        provider="gemini",
        api_key="fake-gem",
        model="gemini-3.5-flash-lite",
        http_poster=_flaky_gemini,
    )
    out_gem = gem_ai.enrich_items([{"id": "g1", "title": "Fed cut signals weaken dollar", "symbol": "XAUUSD"}])
    assert len(tried_urls) >= 2
    assert "gemini-3.5-flash-lite" in tried_urls[0]
    assert "gemini-3.1-flash-lite" in tried_urls[1]
    assert out_gem[0]["analysis_source"] == "AI_GEMINI"
    assert gem_ai.last_error == ""

    # Friendly error translation strips ugly JSON
    assert "Créditos insuficientes" in friendly_ai_error('HTTP 402: {"error":{"message":"more credits"}}')
    assert "congestionado" in friendly_ai_error("HTTP 503: high demand UNAVAILABLE")
    assert "{" not in friendly_ai_error('HTTP 503: {"error":{"code":503}}')


def test_news_scout_rss_429_host_cooldown_and_cached_fallback() -> None:
    calls = 0

    def _fetcher(url: str) -> str:
        nonlocal calls
        calls += 1
        if "news.google.com" in url and calls >= 2:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        if "news.google.com" in url:
            return "<rss><channel><item><title>Fed holds rates steady</title><link>https://g/1</link></item></channel></rss>"
        return "<rss><channel><item><title>Bitcoin rallies above key level</title><link>https://y/1</link></item></channel></rss>"

    scout = NewsScout(fetcher=_fetcher)
    feeds = [
        {"feed_id": "g1", "source": "Google News", "url": "https://news.google.com/rss/search?q=fed", "default_symbol": "EURUSD"},
        {"feed_id": "y1", "source": "Yahoo", "url": "https://feeds.finance.yahoo.com/rss/2.0/headline", "default_symbol": "BTCUSD"},
    ]
    items1, _ = scout.scan(feeds=feeds)
    assert len(items1) == 2

    # Force 429 on Google News -> preserves cached item, sets cooldown, keeps last_error clean
    calls_before_second = calls
    items2, _ = scout.scan(feeds=feeds)
    assert scout.last_error == ""
    assert any(it["title"] == "Fed holds rates steady" for it in items2)

    # Next scan during host cooldown skips network call for Google News completely
    calls_before_third = calls
    items3, _ = scout.scan(feeds=feeds)
    assert calls - calls_before_third == 1  # only Yahoo called
    assert any(it["title"] == "Fed holds rates steady" for it in items3)


def test_analyst_desk_cards_confluence_conviction_and_shield(tmp_path: Path) -> None:
    EconomicCalendarScout.clear_shared_cache()
    cfg = load_config(tmp_path / "cfg_desk.json")
    cfg.connection_mode = "SIMULATION"
    cfg.ctrader_access_token = ""
    cfg.active_symbols = ["EURUSD", "XAUUSD", "BTCUSD"]
    cfg.news_calendar_shield_enabled = True
    cfg.news_calendar_pause_minutes = 15
    cfg.news_filter_only = True
    svc = PradoTradingService(cfg, config_path=tmp_path / "cfg_desk.json")
    svc.create_bot({"name": "Bot Euro", "symbol": "EURUSD", "news_assisted": True, "auto_start": False})

    now = time.time()
    svc.news_scout.items = [
        {
            "id": "e1",
            "title": "Fed signals rate cut ahead as inflation cools",
            "symbol": "EURUSD",
            "impact": "HIGH",
            "bias": "BULLISH",
            "score": 0.85,
            "published_ts": now,
            "analysis_source": "AI_OPENROUTER",
            "ai_reason": "Corte de juros enfraquece o dólar e favorece EURUSD.",
        },
        {
            "id": "e2",
            "title": "ECB keeps hawkish stance on Eurozone growth",
            "symbol": "EURUSD",
            "impact": "HIGH",
            "bias": "BULLISH",
            "score": 0.75,
            "published_ts": now - 120,
            "analysis_source": "AI_OPENROUTER",
            "ai_reason": "BCE firme sustenta valorização do euro.",
        },
        {
            "id": "x1",
            "title": "Stronger US yields weigh on gold",
            "symbol": "XAUUSD",
            "impact": "HIGH",
            "bias": "BEARISH",
            "score": -0.7,
            "published_ts": now,
            "analysis_source": "AI_GEMINI",
            "ai_reason": "Dólar forte pressiona o ouro.",
        },
        {
            "id": "b1",
            "title": "Bitcoin holds weekly range",
            "symbol": "BTCUSD",
            "impact": "LOW",
            "bias": "NEUTRAL",
            "score": 0.0,
            "published_ts": now,
            "analysis_source": "LOCAL_RULES",
            "ai_reason": "",
        },
        {
            "id": "a1",
            "title": "Global markets steady ahead of macro week",
            "symbol": "ALL",
            "impact": "LOW",
            "bias": "NEUTRAL",
            "score": 0.0,
            "published_ts": now,
            "analysis_source": "LOCAL_RULES",
            "ai_reason": "",
        },
    ]

    summary = svc.news_scout.summary_by_symbol(now_ts=now)
    assert summary["EURUSD"]["confidence"] >= 70
    assert summary["EURUSD"]["recommendation"] == "STRONG_BUY"
    assert summary["EURUSD"]["ai_count"] == 2
    assert summary["EURUSD"]["bullish_count"] == 2
    assert "EURUSD" in summary["EURUSD"]["top_reason"] or "BCE" in summary["EURUSD"]["top_reason"]

    svc._latest_snapshot = {
        "symbols": {
            "EURUSD": {"price": 1.1025, "vwap": 1.1000, "zscore": 1.9, "signal": "BUY_FLOW", "regime": "TREND_UP"},
            "XAUUSD": {"price": 2650.0, "vwap": 2640.0, "zscore": 1.5, "signal": "BUY_FLOW", "regime": "TREND_UP"},
            "BTCUSD": {"price": 90000.0, "vwap": 90000.0, "zscore": 0.1, "signal": "WAIT", "regime": "NEUTRAL"},
        }
    }

    snap_news = svc._news_snapshot_dict()
    cards = snap_news["analyst_cards"]
    assert all(c["symbol"] != "ALL" for c in cards)
    by_sym = {c["symbol"]: c for c in cards}

    eur_card = by_sym["EURUSD"]
    assert eur_card["action"] == "STRONG_BUY"
    assert eur_card["confluence_state"] == "ALIGNED_BUY"
    assert eur_card["conviction"] >= 70
    assert eur_card["bots_count"] == 1
    assert eur_card["shield_active"] is False
    assert "libera" in eur_card["robot_effect"].lower() or "autorizada" in eur_card["robot_effect"].lower()

    xau_card = by_sym["XAUUSD"]
    assert xau_card["action"] == "WAIT_CONFLICT"
    assert xau_card["confluence_state"] == "CONFLICT"
    assert "bloqueia" in xau_card["robot_effect"].lower() or "diverg" in xau_card["robot_effect"].lower()

    btc_card = by_sym["BTCUSD"]
    assert btc_card["action"] == "NEUTRAL"

    # Active 3-star USD calendar event inside ±15m -> PAUSE_SHIELD with conviction 0
    usd_5m = datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat()
    svc.economic_calendar = EconomicCalendarScout(
        fetcher=lambda _u: json.dumps([{"title": "US CPI y/y", "country": "USD", "date": usd_5m, "impact": "High"}])
    )
    svc.economic_calendar.fetch_week(force=True)
    shield_cards = {c["symbol"]: c for c in svc._news_snapshot_dict()["analyst_cards"]}
    assert shield_cards["EURUSD"]["action"] == "PAUSE_SHIELD"
    assert shield_cards["EURUSD"]["confluence_state"] == "SHIELD"
    assert shield_cards["EURUSD"]["shield_active"] is True
    assert shield_cards["EURUSD"]["conviction"] == 0
    assert "3★" in shield_cards["EURUSD"]["robot_effect"] or "pausad" in shield_cards["EURUSD"]["robot_effect"].lower()
