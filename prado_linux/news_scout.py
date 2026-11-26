"""Internet financial news (RSS + Atom, PT-BR + EN) & Economic Calendar scout (zero paid keys)."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

AI_PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "default_model": DEFAULT_GEMINI_MODEL,
        "models": [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
        ],
        "needs_base_url": False,
        "endpoint_hint": "https://generativelanguage.googleapis.com/v1beta",
        "key_placeholder": "AIza...",
    },
    {
        "id": "openai",
        "name": "OpenAI (ChatGPT)",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
        "needs_base_url": False,
        "endpoint_hint": "https://api.openai.com/v1/chat/completions",
        "key_placeholder": "sk-...",
    },
    {
        "id": "claude",
        "name": "Anthropic Claude",
        "default_model": "claude-3-5-haiku-latest",
        "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest", "claude-sonnet-4-20250514"],
        "needs_base_url": False,
        "endpoint_hint": "https://api.anthropic.com/v1/messages",
        "key_placeholder": "sk-ant-...",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Todos os modelos)",
        "default_model": "google/gemini-2.0-flash-001",
        "models": [
            "google/gemini-2.0-flash-001",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-haiku",
            "deepseek/deepseek-chat-v3-0324",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen-2.5-72b-instruct",
        ],
        "needs_base_url": False,
        "endpoint_hint": "https://openrouter.ai/api/v1/chat/completions",
        "key_placeholder": "sk-or-v1-...",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "needs_base_url": False,
        "endpoint_hint": "https://api.deepseek.com/chat/completions",
        "key_placeholder": "sk-...",
    },
    {
        "id": "groq",
        "name": "Groq (Ultra-rápido)",
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "deepseek-r1-distill-llama-70b"],
        "needs_base_url": False,
        "endpoint_hint": "https://api.groq.com/openai/v1/chat/completions",
        "key_placeholder": "gsk_...",
    },
    {
        "id": "xai",
        "name": "xAI (Grok)",
        "default_model": "grok-3-mini",
        "models": ["grok-3-mini", "grok-3", "grok-2-latest"],
        "needs_base_url": False,
        "endpoint_hint": "https://api.x.ai/v1/chat/completions",
        "key_placeholder": "xai-...",
    },
    {
        "id": "custom",
        "name": "Outro Provedor (Compatível OpenAI)",
        "default_model": "gpt-4o-mini",
        "models": [],
        "needs_base_url": True,
        "endpoint_hint": "https://api.provedor.com/v1/chat/completions",
        "key_placeholder": "Cole sua API Key",
    },
]

AI_PROVIDER_MAP: dict[str, dict[str, Any]] = {p["id"]: p for p in AI_PROVIDER_CATALOG}


def normalize_ai_provider(provider: str) -> str:
    clean = str(provider or "").strip().lower()
    if clean in ("anthropic",):
        clean = "claude"
    elif clean in ("google",):
        clean = "gemini"
    elif clean in ("chatgpt",):
        clean = "openai"
    return clean if clean in AI_PROVIDER_MAP else "gemini"


def _extract_json_payload(raw_text: str) -> Any:
    clean = str(raw_text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.DOTALL).strip()
    try:
        return json.loads(clean or "[]")
    except Exception:
        pass
    for start_ch, end_ch in (("[", "]"), ("{", "}")):
        s_idx = clean.find(start_ch)
        e_idx = clean.rfind(end_ch)
        if s_idx != -1 and e_idx > s_idx:
            try:
                return json.loads(clean[s_idx : e_idx + 1])
            except Exception:
                continue
    raise ValueError("Resposta da IA não retornou JSON válido.")

RSS_FEEDS: list[dict[str, str]] = [
    {
        "feed_id": "yahoo_btc",
        "source": "Yahoo Finance BTC",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US",
        "default_symbol": "BTCUSD",
    },
    {
        "feed_id": "yahoo_eurusd",
        "source": "Yahoo Finance EURUSD",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=EURUSD=X&region=US&lang=en-US",
        "default_symbol": "EURUSD",
    },
    {
        "feed_id": "yahoo_gold",
        "source": "Yahoo Finance Gold",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US",
        "default_symbol": "XAUUSD",
    },
    {
        "feed_id": "yahoo_sp500",
        "source": "Yahoo Finance S&P500",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
        "default_symbol": "US500",
    },
]
DEFAULT_NEWS_FEEDS = RSS_FEEDS

CURATED_NEWS_CATALOG: list[dict[str, str]] = [
    {
        "feed_id": "gnews_br_macro",
        "source": "Google Notícias Macro & Dólar (PT-BR)",
        "url": "https://news.google.com/rss/search?q=dolar+OR+fed+OR+juros+OR+inflacao+EUA&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "default_symbol": "EURUSD",
        "language": "PT-BR",
        "category": "Macro & Moedas",
    },
    {
        "feed_id": "gnews_br_btc",
        "source": "Google Notícias Bitcoin & Cripto (PT-BR)",
        "url": "https://news.google.com/rss/search?q=bitcoin+OR+criptomoedas+mercado&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "default_symbol": "BTCUSD",
        "language": "PT-BR",
        "category": "Cripto",
    },
    {
        "feed_id": "gnews_br_ouro",
        "source": "Google Notícias Ouro & Commodities (PT-BR)",
        "url": "https://news.google.com/rss/search?q=ouro+cotacao+OR+onca+dolar&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "default_symbol": "XAUUSD",
        "language": "PT-BR",
        "category": "Metais",
    },
    {
        "feed_id": "gnews_br_nasdaq",
        "source": "Google Notícias Nasdaq & S&P 500 (PT-BR)",
        "url": "https://news.google.com/rss/search?q=nasdaq+OR+sp500+OR+wall+street&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        "default_symbol": "US100",
        "language": "PT-BR",
        "category": "Índices EUA",
    },
    {
        "feed_id": "coindesk_rss",
        "source": "CoinDesk (EN)",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "default_symbol": "BTCUSD",
        "language": "EN",
        "category": "Cripto",
    },
    {
        "feed_id": "gnews_en_forex",
        "source": "Google News Forex & Fed (EN)",
        "url": "https://news.google.com/rss/search?q=EURUSD+OR+forex+OR+federal+reserve&hl=en-US&gl=US&ceid=US:en",
        "default_symbol": "EURUSD",
        "language": "EN",
        "category": "Forex",
    },
    {
        "feed_id": "yahoo_nasdaq",
        "source": "Yahoo Finance Nasdaq 100 (EN)",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5ENDX&region=US&lang=en-US",
        "default_symbol": "US100",
        "language": "EN",
        "category": "Índices EUA",
    },
    {
        "feed_id": "infomoney_mercados",
        "source": "InfoMoney Mercados (PT-BR)",
        "url": "https://www.infomoney.com.br/mercados/feed/",
        "default_symbol": "ALL",
        "language": "PT-BR",
        "category": "Brasil & Global",
    },
]

HIGH_IMPACT_KEYWORDS = {
    "fed", "fomc", "powell", "cpi", "inflation", "payroll", "nfp", "interest rate",
    "rate cut", "rate hike", "ecb", "lagarde", "gdp", "sec", "etf", "hack", "exploit",
    "bankruptcy", "collapse", "crash", "emergency", "tariff", "war", "sanction",
    "recession", "unemployment", "halving", "ban",
    # PT-BR
    "inflação", "inflacao", "taxa de juros", "corte de juros", "alta de juros",
    "juros", "bce", "pib", "desemprego", "recessão", "recessao", "tarifa",
    "guerra", "sanção", "sancao", "falência", "falencia", "emergência", "emergencia",
    "aprovação", "aprovacao", "aprovado", "banco central", "copom", "selic",
}

BULLISH_KEYWORDS = {
    "surge", "surges", "rally", "rallies", "jump", "jumps", "soar", "soars", "gain",
    "gains", "rise", "rises", "bullish", "approve", "approved", "etf inflow", "rate cut",
    "dovish", "beat", "record high", "breakout", "rebound",
    # PT-BR
    "alta", "dispara", "sobe", "subida", "valoriza", "valorização", "valorizacao",
    "recorde", "máxima", "maxima", "otimismo", "corte de juros", "aprovado",
    "aprovação", "aprovacao", "avança", "avanca", "recupera", "recuperação", "forte demanda",
}

BEARISH_KEYWORDS = {
    "crash", "crashes", "plunge", "plunges", "drop", "drops", "fall", "falls", "slump",
    "bearish", "rate hike", "hawkish", "hack", "exploit", "bankruptcy", "collapse",
    "lawsuit", "ban", "recession", "inflation fears", "selloff", "sell-off",
    # PT-BR
    "queda", "desaba", "cai", "caída", "recua", "despencam", "despenca", "baixa",
    "pessimismo", "alta de juros", "recessão", "recessao", "colapso", "mínima",
    "minima", "pressão", "pressao", "temores", "liquidação", "liquidacao",
}

SYMBOL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("BTCUSD", ("bitcoin", "btc", "crypto", "cripto", "criptomoeda", "satoshi")),
    ("ETHUSD", ("ethereum", "eth", "ether")),
    ("XAUUSD", ("gold", "xau", "bullion", "ouro")),
    ("EURUSD", ("eurusd", "eur/usd", "euro", "ecb", "bce", "lagarde")),
    ("GBPUSD", ("gbpusd", "gbp/usd", "pound", "sterling", "libra", "boe")),
    ("USDJPY", ("usdjpy", "usd/jpy", "yen", "iene", "boj")),
    ("US500", ("s&p 500", "sp500", "s&p", "wall street", "fed", "fomc", "cpi", "nfp", "payroll")),
    ("US100", ("nasdaq", "tech stocks", "nvidia", "apple", "ai stocks", "big techs")),
]

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


_NEGATION_PREFIX = r"(?:não|nao|sem|nunca|jamais|nem|not|no|never|fails?\s+to|unable\s+to|without)"
_USD_QUOTE_SYMBOLS = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"}
_USD_BASE_SYMBOLS = {"USDJPY", "USDCAD", "USDCHF"}
_USD_SUBJECT_TERMS = ("dólar", "dolar", "usd", "fed", "fomc", "powell", "payroll", "nfp", "cpi", "interest rate", "taxa de juros", "selic usa", "treasury")


def _clean_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", txt).strip()


def _has_keyword(text_lower: str, kw: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text_lower))


def _has_negated_keyword(text_lower: str, kw: str) -> bool:
    return bool(re.search(rf"\b{_NEGATION_PREFIX}\b(?:\s+\w+){{0,2}}\s+{re.escape(kw)}(?!\w)", text_lower))


def infer_symbol(text: str, fallback: str = "BTCUSD") -> str:
    low = text.lower()
    for sym, kws in SYMBOL_KEYWORDS:
        if any(_has_keyword(low, kw) for kw in kws):
            return sym
    return fallback


def analyze_headline(title: str, summary: str = "", fallback_symbol: str = "BTCUSD") -> dict[str, Any]:
    """Classify headline impact (HIGH/MEDIUM/LOW), directional bias with negation & USD inversion, and cTrader symbol."""
    combined = f"{title} {summary}".lower()
    bull_hits = 0
    bear_hits = 0
    for kw in BULLISH_KEYWORDS:
        if _has_keyword(combined, kw):
            if _has_negated_keyword(combined, kw):
                bear_hits += 1
            else:
                bull_hits += 1
    for kw in BEARISH_KEYWORDS:
        if _has_keyword(combined, kw):
            if _has_negated_keyword(combined, kw):
                bull_hits += 1
            else:
                bear_hits += 1
    high_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if _has_keyword(combined, kw))

    if high_hits >= 1 or abs(bull_hits - bear_hits) >= 2:
        impact = "HIGH"
    elif bull_hits > 0 or bear_hits > 0:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    net = bull_hits - bear_hits
    symbol = infer_symbol(combined, fallback=fallback_symbol)
    is_macro_usd = any(
        _has_keyword(combined, kw)
        for kw in ("fed", "fomc", "cpi", "nfp", "payroll", "powell", "interest rate", "taxa de juros", "corte de juros", "inflação", "inflacao")
    )

    # Dollar strength/weakness inverse correlation rule for USD pairs
    reason = ""
    has_usd_subject = any(_has_keyword(combined, kw) for kw in _USD_SUBJECT_TERMS)
    has_other_asset = any(
        _has_keyword(combined, kw)
        for sym, kws in SYMBOL_KEYWORDS
        if sym in ("BTCUSD", "ETHUSD", "XAUUSD", "EURUSD", "GBPUSD", "US100", "US500")
        for kw in kws
        if kw not in ("fed", "fomc", "cpi", "nfp", "payroll")
    )
    explicit_usd_weak = any(_has_keyword(combined, kw) for kw in ("rate cut", "corte de juros", "dovish"))
    explicit_usd_strong = any(_has_keyword(combined, kw) for kw in ("rate hike", "alta de juros", "hawkish"))
    if has_usd_subject and (net != 0 or explicit_usd_weak or explicit_usd_strong) and not has_other_asset:
        usd_strong = net > 0
        if explicit_usd_weak:
            usd_strong = False
        elif explicit_usd_strong:
            usd_strong = True

        mag = max(1, abs(net))
        target_sym = str(fallback_symbol or symbol or "").upper()
        if target_sym in _USD_QUOTE_SYMBOLS or symbol in _USD_QUOTE_SYMBOLS:
            net = -mag if usd_strong else mag
            reason = "Dólar forte pressiona o ativo para baixo." if usd_strong else "Dólar fraco favorece alta do ativo."
        elif target_sym in _USD_BASE_SYMBOLS or symbol in _USD_BASE_SYMBOLS:
            net = mag if usd_strong else -mag
            reason = "Dólar forte impulsiona o par USD/*." if usd_strong else "Dólar fraco pressiona o par USD/*."

    if net > 0:
        bias = "BULLISH"
    elif net < 0:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    score = max(-1.0, min(1.0, net / 3.0))
    return {
        "symbol": symbol,
        "impact": impact,
        "bias": bias,
        "score": round(score, 2),
        "is_macro_usd": is_macro_usd,
        "analysis_source": "LOCAL_RULES",
        "ai_reason": reason,
    }


def _parse_pub_date(pub_raw: str) -> tuple[float, str]:
    raw = str(pub_raw or "").strip()
    if not raw:
        return time.time(), datetime.now().strftime("%d/%m %H:%M")
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp(), dt.astimezone().strftime("%d/%m %H:%M")
    except Exception:
        pass
    try:
        iso = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp(), dt.astimezone().strftime("%d/%m %H:%M")
    except Exception:
        return time.time(), datetime.now().strftime("%d/%m %H:%M")


def parse_rss_xml(xml_text: str, source: str, default_symbol: str) -> list[dict[str, Any]]:
    """Parse RSS 2.0 (<item>) or Atom (<entry>) XML feeds."""
    items: list[dict[str, Any]] = []
    if not xml_text.strip():
        return items
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    rss_nodes = root.findall(".//item")
    if rss_nodes:
        for node in rss_nodes[:10]:
            title = _clean_html(node.findtext("title") or "")
            if not title:
                continue
            link = (node.findtext("link") or "").strip()
            desc = _clean_html(node.findtext("description") or "")
            pub_ts, pub_str = _parse_pub_date(node.findtext("pubDate") or "")
            analysis = analyze_headline(title, desc, fallback_symbol=default_symbol)
            item_id = hashlib.sha1(f"{title}|{link}".encode("utf-8")).hexdigest()[:12]
            items.append(
                {
                    "id": item_id,
                    "title": title,
                    "source": source,
                    "link": link,
                    "published_at": pub_str,
                    "published_ts": pub_ts,
                    **analysis,
                }
            )
        return items

    atom_nodes = root.findall(f".//{_ATOM_NS}entry") or root.findall(".//entry")
    for node in atom_nodes[:10]:
        title_raw = node.findtext(f"{_ATOM_NS}title") or node.findtext("title") or ""
        title = _clean_html(title_raw)
        if not title:
            continue
        link_el = node.find(f"{_ATOM_NS}link")
        if link_el is None:
            link_el = node.find("link")
        link = (link_el.attrib.get("href") if link_el is not None else "") or (link_el.text if link_el is not None else "") or ""
        link = link.strip()
        desc_raw = (
            node.findtext(f"{_ATOM_NS}summary")
            or node.findtext("summary")
            or node.findtext(f"{_ATOM_NS}content")
            or node.findtext("content")
            or ""
        )
        desc = _clean_html(desc_raw)
        pub_raw = (
            node.findtext(f"{_ATOM_NS}updated")
            or node.findtext("updated")
            or node.findtext(f"{_ATOM_NS}published")
            or node.findtext("published")
            or ""
        )
        pub_ts, pub_str = _parse_pub_date(pub_raw)
        analysis = analyze_headline(title, desc, fallback_symbol=default_symbol)
        item_id = hashlib.sha1(f"{title}|{link}".encode("utf-8")).hexdigest()[:12]
        items.append(
            {
                "id": item_id,
                "title": title,
                "source": source,
                "link": link,
                "published_at": pub_str,
                "published_ts": pub_ts,
                **analysis,
            }
        )
    return items


def validate_rss_url(url: str) -> tuple[bool, str]:
    """Validate RSS feed URL against SSRF (only public http/https URLs allowed)."""
    raw = str(url or "").strip()
    if not raw:
        return False, "URL de feed vazia."
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return False, "Apenas URLs http:// ou https:// válidas são permitidas."
    host = parsed.hostname.strip().lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local"):
        return False, "Hosts locais/internos não são permitidos em feeds RSS."
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "Endereços IP privados ou reservados não são permitidos."
    except ValueError:
        try:
            for info in socket.getaddrinfo(host, None):
                ip_str = info[4][0]
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False, "Domínio resolve para endereço IP privado ou reservado."
        except OSError:
            pass
    return True, ""


def _recency_weight(published_ts: float, now_ts: float) -> float:
    age = max(0.0, now_ts - float(published_ts or now_ts))
    if age <= 6 * 3600:
        return 1.0
    if age <= 24 * 3600:
        return 0.6
    if age <= 72 * 3600:
        return 0.25
    return 0.1


class AINewsAnalyzer:
    """Optional semantic news analyzer via Gemini, OpenAI, Claude, OpenRouter, DeepSeek, Groq, xAI or Custom endpoint."""

    _OPENAI_COMPAT_URLS: dict[str, str] = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/chat/completions",
        "groq": "https://api.groq.com/openai/v1/chat/completions",
        "xai": "https://api.x.ai/v1/chat/completions",
    }

    def __init__(
        self,
        enabled: bool = False,
        provider: str = "gemini",
        api_key: str = "",
        model: str = DEFAULT_GEMINI_MODEL,
        base_url: str = "",
        http_poster: Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.provider = normalize_ai_provider(provider)
        default_m = str(AI_PROVIDER_MAP[self.provider]["default_model"])
        self.api_key = str(api_key or "").strip()
        self.model = str(model or default_m).strip() or default_m
        self.base_url = str(base_url or "").strip()
        self._http_poster = http_poster or self._default_post_json
        self._cache: dict[str, dict[str, Any]] = {}
        self.last_error: str = ""

    def _default_post_json(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore").strip()[:240]
            except Exception:
                pass
            raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc

    def configure(
        self,
        enabled: bool,
        provider: str,
        api_key: str,
        model: str = "",
        base_url: str = "",
        http_poster: Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        new_prov = normalize_ai_provider(provider)
        default_m = str(AI_PROVIDER_MAP[new_prov]["default_model"])
        new_key = str(api_key or "").strip()
        new_model = str(model or default_m).strip() or default_m
        new_base = str(base_url or "").strip()
        if (
            new_prov != self.provider
            or new_model != self.model
            or new_base != self.base_url
            or new_key != self.api_key
        ):
            self._cache.clear()
        self.enabled = bool(enabled)
        self.provider = new_prov
        self.api_key = new_key
        self.model = new_model
        self.base_url = new_base
        self.last_error = ""
        if http_poster is not None:
            self._http_poster = http_poster

    def _resolve_openai_compat_url(self) -> str:
        if self.provider in self._OPENAI_COMPAT_URLS:
            return self._OPENAI_COMPAT_URLS[self.provider]
        raw = str(self.base_url or "").strip().rstrip("/")
        ok, err = validate_rss_url(raw)
        if not ok:
            raise ValueError(f"URL base da IA inválida: {err}")
        if not raw.endswith("/chat/completions"):
            raw = f"{raw}/chat/completions"
        return raw

    def _call_provider(self, prompt: str) -> str:
        if self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(self.model)}:generateContent?key={urllib.parse.quote(self.api_key)}"
            resp = self._http_poster(
                url,
                {},
                {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                },
            )
            cands = resp.get("candidates") or []
            if cands and isinstance(cands[0], dict):
                parts = ((cands[0].get("content") or {}).get("parts")) or []
                if parts and isinstance(parts[0], dict):
                    return str(parts[0].get("text") or "")
            return ""

        if self.provider == "claude":
            resp = self._http_poster(
                "https://api.anthropic.com/v1/messages",
                {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                {
                    "model": self.model,
                    "max_tokens": 1024,
                    "temperature": 0.1,
                    "system": "Responda sempre exclusivamente com JSON válido.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            blocks = resp.get("content") or []
            texts = [str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("text")]
            return "\n".join(texts)

        url = self._resolve_openai_compat_url()
        req_headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            req_headers["HTTP-Referer"] = "https://quantix.hft"
            req_headers["X-Title"] = "Quantix HFT"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Responda sempre exclusivamente com JSON válido."},
                {"role": "user", "content": prompt},
            ],
        }
        model_low = self.model.lower()
        if not model_low.startswith(("o1", "o3", "o4", "gpt-5")):
            body["temperature"] = 0.1
        if self.provider == "openai" and not model_low.startswith("o1"):
            body["response_format"] = {"type": "json_object"}

        resp = self._http_poster(url, req_headers, body)
        choices = resp.get("choices") or []
        if choices and isinstance(choices[0], dict):
            return str(((choices[0].get("message") or {}).get("content")) or "")
        return ""

    def _build_prompt(self, pending: list[dict[str, Any]]) -> str:
        lines = "\n".join(
            f"ID={it['id']} SYMBOL_HINT={it.get('symbol', 'ALL')} TITLE={str(it.get('title', ''))[:160]}"
            for it in pending
        )
        return (
            "Você é um analista quantitativo de Forex, Índices, Ouro e Cripto.\n"
            "Classifique cada manchete abaixo em JSON (lista de objetos, ou objeto {\"items\": [...]}) com as chaves exatas:\n"
            "- id: string com o codigo da manchete\n"
            "- symbol: ativo mais afetado entre EURUSD, GBPUSD, USDJPY, XAUUSD, US100, US500, BTCUSD, ETHUSD ou ALL\n"
            "- impact: HIGH, MEDIUM ou LOW\n"
            "- bias: BULLISH (sobe o ativo), BEARISH (cai o ativo) ou NEUTRAL (lembre que dólar forte derruba EURUSD e XAUUSD!)\n"
            "- score: numero entre -1.0 e 1.0\n"
            "- reason: frase curta em portugues explicando o motivo\n\n"
            f"Manchetes:\n{lines}"
        )

    def enrich_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.enabled or not self.api_key or not items:
            return items

        out = [dict(it) for it in items]
        pending: list[dict[str, Any]] = []
        for idx, it in enumerate(out):
            iid = str(it.get("id") or "")
            cached = self._cache.get(iid)
            if cached is not None:
                out[idx].update(cached)
            elif len(pending) < 12:
                pending.append(it)

        if not pending:
            return out

        prompt = self._build_prompt(pending)

        try:
            raw_text = self._call_provider(prompt)
            parsed = _extract_json_payload(raw_text)
            rows = parsed.get("items") if isinstance(parsed, dict) else parsed
            if not isinstance(rows, list):
                return out

            source_tag = f"AI_{self.provider.upper()}"
            by_id: dict[str, dict[str, Any]] = {}
            for row in rows:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                bias = str(row.get("bias") or "NEUTRAL").upper()
                if bias not in ("BULLISH", "BEARISH", "NEUTRAL"):
                    bias = "NEUTRAL"
                imp = str(row.get("impact") or "MEDIUM").upper()
                if imp not in ("HIGH", "MEDIUM", "LOW"):
                    imp = "MEDIUM"
                sc = max(-1.0, min(1.0, float(row.get("score") or 0.0)))
                upd = {
                    "symbol": str(row.get("symbol") or "ALL").upper(),
                    "impact": imp,
                    "bias": bias,
                    "score": round(sc, 2),
                    "ai_reason": str(row.get("reason") or "").strip()[:180],
                    "analysis_source": source_tag,
                }
                by_id[str(row["id"])] = upd
                self._cache[str(row["id"])] = upd
                if len(self._cache) > 1000:
                    self._cache.clear()

            for idx, it in enumerate(out):
                if str(it.get("id") or "") in by_id:
                    out[idx].update(by_id[str(it["id"])])
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)
        return out

    def test_connection(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "provider": self.provider,
                "model": self.model,
                "error": "Informe a API Key antes de testar.",
            }
        started = time.time()
        try:
            prompt = self._build_prompt(
                [
                    {
                        "id": "test_1",
                        "symbol": "EURUSD",
                        "title": "Federal Reserve signals rate cut as inflation cools and US dollar drops",
                    }
                ]
            )
            raw_text = self._call_provider(prompt)
            parsed = _extract_json_payload(raw_text)
            rows = parsed.get("items") if isinstance(parsed, dict) else parsed
            if isinstance(parsed, dict) and "bias" in parsed and not isinstance(rows, list):
                rows = [parsed]
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
                raise ValueError("A IA respondeu, mas sem a lista JSON esperada.")
            row = rows[0]
            bias = str(row.get("bias") or "NEUTRAL").upper()
            if bias not in ("BULLISH", "BEARISH", "NEUTRAL"):
                bias = "NEUTRAL"
            imp = str(row.get("impact") or "MEDIUM").upper()
            if imp not in ("HIGH", "MEDIUM", "LOW"):
                imp = "MEDIUM"
            return {
                "ok": True,
                "provider": self.provider,
                "model": self.model,
                "symbol": str(row.get("symbol") or "EURUSD").upper(),
                "bias": bias,
                "impact": imp,
                "score": round(max(-1.0, min(1.0, float(row.get("score") or 0.0))), 2),
                "reason": str(row.get("reason") or "Conexão validada com sucesso.").strip()[:180],
                "latency_ms": max(1, int((time.time() - started) * 1000)),
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider": self.provider,
                "model": self.model,
                "error": str(exc),
            }


def _default_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()[:240]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc


_LIST_MODELS_SKIP_TOKENS = ("-tts", "-image", "lyria", "robotics", "nano-banana", "transcribe", "embedding")


def list_ai_provider_models(
    provider: str,
    api_key: str,
    base_url: str = "",
    http_getter: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prov = normalize_ai_provider(provider)
    key = str(api_key or "").strip()
    if not key:
        return {
            "ok": False,
            "provider": prov,
            "models": [],
            "error": "Informe a API Key para buscar os modelos disponíveis.",
        }

    getter = http_getter or _default_get_json
    try:
        models: list[str] = []
        if prov == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key)}"
            data = getter(url, {})
            for entry in data.get("models") or []:
                if not isinstance(entry, dict):
                    continue
                methods = entry.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue
                mid = str(entry.get("name") or "").replace("models/", "").strip()
                if not mid or any(tok in mid.lower() for tok in _LIST_MODELS_SKIP_TOKENS):
                    continue
                if mid not in models:
                    models.append(mid)
        elif prov == "claude":
            data = getter(
                "https://api.anthropic.com/v1/models",
                {"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
            models = sorted(
                {str(d.get("id") or "").strip() for d in (data.get("data") or []) if isinstance(d, dict) and d.get("id")}
            )
        else:
            endpoint_map = {
                "openai": "https://api.openai.com/v1/models",
                "openrouter": "https://openrouter.ai/api/v1/models",
                "deepseek": "https://api.deepseek.com/models",
                "groq": "https://api.groq.com/openai/v1/models",
                "xai": "https://api.x.ai/v1/models",
            }
            if prov in endpoint_map:
                url = endpoint_map[prov]
            else:
                raw = str(base_url or "").strip().rstrip("/")
                ok, err = validate_rss_url(raw)
                if not ok:
                    return {"ok": False, "provider": prov, "models": [], "error": f"URL base inválida: {err}"}
                if raw.endswith("/chat/completions"):
                    raw = raw[: -len("/chat/completions")]
                url = f"{raw}/models"
            data = getter(url, {"Authorization": f"Bearer {key}"})
            models = sorted(
                {str(d.get("id") or "").strip() for d in (data.get("data") or []) if isinstance(d, dict) and d.get("id")}
            )
        return {"ok": True, "provider": prov, "models": models[:150]}
    except Exception as exc:
        return {"ok": False, "provider": prov, "models": [], "error": str(exc)}


class NewsScout:
    """Periodic RSS/Atom news researcher that tracks seen items, feed health, optional AI & recency sentiment."""

    def __init__(self, fetcher: Callable[[str], str] | None = None) -> None:
        self._fetcher = fetcher or self._default_fetch
        self._seen_ids: set[str] = set()
        self.items: list[dict[str, Any]] = []
        self.feed_status: list[dict[str, Any]] = []
        self.last_scan_at: float = 0.0
        self.last_error: str = ""
        self._ai_analyzer = AINewsAnalyzer()

    def configure_ai(
        self,
        enabled: bool,
        provider: str,
        api_key: str,
        model: str = "",
        base_url: str = "",
        http_poster: Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._ai_analyzer.configure(
            enabled=enabled,
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            http_poster=http_poster,
        )

    def _default_fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 PradoHFT-NewsScout/2.0",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def scan(self, feeds: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Scan RSS/Atom feeds; returns (all_recent_items, newly_discovered_items)."""
        target_feeds = feeds or RSS_FEEDS
        collected: list[dict[str, Any]] = []
        errors: list[str] = []
        statuses: list[dict[str, Any]] = []
        now = time.time()
        for f in target_feeds:
            fid = str(f.get("feed_id") or "")
            source = str(f.get("source") or fid or "Fonte")
            try:
                xml_txt = self._fetcher(f["url"])
                parsed = parse_rss_xml(xml_txt, source=source, default_symbol=str(f.get("default_symbol") or "ALL"))
                collected.extend(parsed)
                statuses.append({"feed_id": fid, "source": source, "ok": True, "count": len(parsed), "error": "", "checked_at": now})
            except Exception as exc:
                err_txt = str(exc)
                errors.append(f"{source}: {err_txt}")
                statuses.append({"feed_id": fid, "source": source, "ok": False, "count": 0, "error": err_txt, "checked_at": now})

        self.feed_status = statuses
        self.last_scan_at = now
        if collected:
            collected.sort(key=lambda x: float(x.get("published_ts", 0.0)), reverse=True)
            deduped: list[dict[str, Any]] = []
            seen_now: set[str] = set()
            for it in collected:
                if it["id"] not in seen_now:
                    seen_now.add(it["id"])
                    deduped.append(it)
            self.items = deduped[:40]
            self.last_error = " | ".join(errors[:2]) if errors else ""
        elif errors:
            self.last_error = " | ".join(errors[:2])
        else:
            self.last_error = ""

        if self.items and self._ai_analyzer.enabled and self._ai_analyzer.api_key:
            self.items = self._ai_analyzer.enrich_items(self.items)

        new_items = [it for it in self.items if it["id"] not in self._seen_ids]
        for it in new_items:
            self._seen_ids.add(it["id"])
        if len(self._seen_ids) > 2000:
            self._seen_ids = {it["id"] for it in self.items}
        return self.items, new_items

    def summary_by_symbol(self, now_ts: float | None = None) -> dict[str, dict[str, Any]]:
        ref_now = time.time() if now_ts is None else float(now_ts)
        summary: dict[str, dict[str, Any]] = {}
        for it in self.items:
            sym = str(it.get("symbol", ""))
            if not sym:
                continue
            w = _recency_weight(float(it.get("published_ts") or ref_now), ref_now)
            entry = summary.setdefault(
                sym,
                {"symbol": sym, "count": 0, "high_impact": 0, "weighted_sum": 0.0, "weight_total": 0.0, "bias": "NEUTRAL"},
            )
            entry["count"] += 1
            if it.get("impact") == "HIGH":
                entry["high_impact"] += 1
            entry["weighted_sum"] += float(it.get("score", 0.0)) * w
            entry["weight_total"] += w
        for entry in summary.values():
            denom = max(1e-9, float(entry["weight_total"]))
            avg = float(entry["weighted_sum"]) / denom
            entry["avg_score"] = round(avg, 2)
            entry["bias"] = "BULLISH" if avg > 0.1 else ("BEARISH" if avg < -0.1 else "NEUTRAL")
        return summary


def _format_countdown(delta_sec: float) -> str:
    if delta_sec <= 0:
        return "Encerrado"
    mins = int(delta_sec // 60)
    if mins < 60:
        return f"em {max(1, mins)}m"
    hrs = mins // 60
    rem_m = mins % 60
    if hrs < 24:
        return f"em {hrs}h {rem_m:02d}m"
    days = hrs // 24
    return f"em {days}d {hrs % 24}h"


class EconomicCalendarScout:
    """Weekly public economic calendar fetcher with shared cache, disk persistence & anti-429 cooldown."""

    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    _SHARED_LOCK = threading.RLock()
    _SHARED_EVENTS: list[dict[str, Any]] = []
    _SHARED_FETCH_AT: float = 0.0
    _SHARED_COOLDOWN_UNTIL: float = 0.0
    _SHARED_LAST_ERROR: str = ""
    _SHARED_STATUS_NOTE: str = ""

    @classmethod
    def clear_shared_cache(cls) -> None:
        with cls._SHARED_LOCK:
            cls._SHARED_EVENTS = []
            cls._SHARED_FETCH_AT = 0.0
            cls._SHARED_COOLDOWN_UNTIL = 0.0
            cls._SHARED_LAST_ERROR = ""
            cls._SHARED_STATUS_NOTE = ""

    def __init__(
        self,
        fetcher: Callable[[str], str] | None = None,
        cache_sec: int = 1800,
        cache_path: Path | None = None,
        min_force_interval_sec: int = 300,
        rate_limit_cooldown_sec: int = 600,
    ) -> None:
        self._custom_fetcher = fetcher is not None
        self._fetcher = fetcher or self._default_fetch
        self.cache_sec = max(60, int(cache_sec))
        self.cache_path = cache_path
        self.min_force_interval_sec = max(0, int(min_force_interval_sec))
        self.rate_limit_cooldown_sec = max(60, int(rate_limit_cooldown_sec))
        self.events: list[dict[str, Any]] = []
        self.last_fetch_at: float = 0.0
        self.last_error: str = ""
        self.status_note: str = ""
        self._cooldown_until: float = 0.0
        self._hydrate_from_cache()

    def _hydrate_from_cache(self) -> None:
        if self.cache_path and self.cache_path.exists():
            try:
                raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and isinstance(raw.get("events"), list) and raw["events"]:
                    self.events = list(raw["events"])
                    self.last_fetch_at = float(raw.get("last_fetch_at") or 0.0)
                    self._cooldown_until = float(raw.get("cooldown_until") or 0.0)
            except Exception:
                pass
        if not self._custom_fetcher:
            with self._SHARED_LOCK:
                if self._SHARED_EVENTS and (not self.events or self._SHARED_FETCH_AT >= self.last_fetch_at):
                    self.events = list(self._SHARED_EVENTS)
                    self.last_fetch_at = self._SHARED_FETCH_AT
                    self._cooldown_until = self._SHARED_COOLDOWN_UNTIL
                    self.last_error = self._SHARED_LAST_ERROR
                    self.status_note = self._SHARED_STATUS_NOTE
                elif self.events and not self._SHARED_EVENTS:
                    self._SHARED_EVENTS = list(self.events)
                    self._SHARED_FETCH_AT = self.last_fetch_at
                    self._SHARED_COOLDOWN_UNTIL = self._cooldown_until

    def _persist_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {
                    "events": self.events,
                    "last_fetch_at": self.last_fetch_at,
                    "cooldown_until": self._cooldown_until,
                },
                ensure_ascii=False,
            )
            fd, tmp_name = tempfile.mkstemp(prefix=".cal_", suffix=".tmp", dir=str(self.cache_path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                os.replace(tmp_name, self.cache_path)
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
        except Exception:
            pass

    def _sync_shared(self) -> None:
        if not self._custom_fetcher:
            with self._SHARED_LOCK:
                self._SHARED_EVENTS = list(self.events)
                self._SHARED_FETCH_AT = self.last_fetch_at
                self._SHARED_COOLDOWN_UNTIL = self._cooldown_until
                self._SHARED_LAST_ERROR = self.last_error
                self._SHARED_STATUS_NOTE = self.status_note

    def _default_fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 Quantix-EconomicCalendar/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def fetch_week(self, force: bool = False) -> list[dict[str, Any]]:
        if not self._custom_fetcher:
            with self._SHARED_LOCK:
                if self._SHARED_EVENTS and not self.events:
                    self.events = list(self._SHARED_EVENTS)
                    self.last_fetch_at = self._SHARED_FETCH_AT
                    self._cooldown_until = self._SHARED_COOLDOWN_UNTIL
        now = time.time()
        if now < self._cooldown_until:
            if self.events:
                self.last_error = ""
                self.status_note = "Agenda exibida a partir do cache recente (proteção contra limite de consultas)."
            return self.events
        if self.events and self.last_fetch_at > 0:
            age = now - self.last_fetch_at
            if not force and age < self.cache_sec:
                return self.events
            if force and self.min_force_interval_sec > 0 and age < self.min_force_interval_sec:
                self.last_error = ""
                self.status_note = "Agenda já está atualizada (cache recente dos últimos minutos)."
                return self.events

        try:
            raw_txt = self._fetcher(self.CALENDAR_URL)
            data = json.loads(raw_txt or "[]")
            if not isinstance(data, list):
                raise ValueError("Formato inválido do calendário econômico.")
            parsed: list[dict[str, Any]] = []
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                date_str = str(item.get("date") or "").strip()
                ts = 0.0
                time_label = date_str
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        ts = dt.timestamp()
                        time_label = dt.astimezone().strftime("%d/%m %H:%M")
                    except Exception:
                        pass
                raw_imp = str(item.get("impact") or "Low").strip().upper()
                impact = "HIGH" if raw_imp == "HIGH" else ("MEDIUM" if raw_imp == "MEDIUM" else ("HOLIDAY" if raw_imp == "HOLIDAY" else "LOW"))
                currency = str(item.get("country") or item.get("currency") or "USD").strip().upper()
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                eid = hashlib.sha1(f"{currency}|{title}|{date_str}|{idx}".encode("utf-8")).hexdigest()[:12]
                parsed.append(
                    {
                        "id": eid,
                        "title": title,
                        "currency": currency,
                        "impact": impact,
                        "timestamp": ts,
                        "time_str": time_label,
                        "forecast": str(item.get("forecast") or "").strip(),
                        "previous": str(item.get("previous") or "").strip(),
                    }
                )
            parsed.sort(key=lambda x: float(x.get("timestamp") or 0.0))
            self.events = parsed[:120]
            self.last_fetch_at = now
            self.last_error = ""
            self.status_note = ""
            self._cooldown_until = 0.0
            self._persist_cache()
        except Exception as exc:
            msg = str(exc)
            is_429 = "429" in msg or "too many requests" in msg.lower()
            if is_429:
                self._cooldown_until = now + self.rate_limit_cooldown_sec
                if self.events:
                    self.last_error = ""
                    self.status_note = "Agenda exibida a partir do cache recente (proteção contra limite de consultas)."
                else:
                    self.last_error = "Fonte do calendário econômico temporariamente ocupada (limite de consultas). Nova atualização automática em alguns minutos."
                    self.status_note = ""
            else:
                self.last_error = f"Falha ao consultar calendário econômico: {exc}" if not self.events else ""
                if self.events:
                    self.status_note = "Exibindo agenda em cache recente."
                self.last_fetch_at = now
        self._sync_shared()
        return self.events

    @staticmethod
    def symbol_currencies(symbol: str) -> set[str]:
        sym = str(symbol or "").upper()
        if any(idx in sym for idx in ("US100", "US500", "US30", "NAS100", "SPX", "BTC", "ETH")):
            return {"USD"}
        if "XAU" in sym or "XAG" in sym:
            return {"USD"}
        if "DE40" in sym or "DAX" in sym:
            return {"EUR"}
        known = ("USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF")
        matched = {cur for cur in known if cur in sym}
        return matched or {"USD"}

    def get_active_shield_events(
        self,
        symbol: str,
        window_minutes: int = 15,
        now_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        ref_now = time.time() if now_ts is None else float(now_ts)
        win_sec = max(5, int(window_minutes)) * 60.0
        target_currencies = self.symbol_currencies(symbol)
        active: list[dict[str, Any]] = []
        for ev in self.events:
            if str(ev.get("impact") or "") != "HIGH":
                continue
            if str(ev.get("currency") or "").upper() not in target_currencies:
                continue
            ts = float(ev.get("timestamp") or 0.0)
            if ts <= 0:
                continue
            if abs(ts - ref_now) <= win_sec:
                active.append(
                    {
                        **ev,
                        "is_upcoming": ts > ref_now,
                        "countdown": "Agora" if abs(ts - ref_now) <= 60 else _format_countdown(ts - ref_now),
                    }
                )
        return active

    def snapshot_dict(self, now_ts: float | None = None, window_minutes: int = 15) -> dict[str, Any]:
        ref_now = time.time() if now_ts is None else float(now_ts)
        win_sec = max(5, int(window_minutes)) * 60.0
        enriched: list[dict[str, Any]] = []
        next_high: dict[str, Any] | None = None
        active_shield: list[dict[str, Any]] = []
        for ev in self.events:
            ts = float(ev.get("timestamp") or 0.0)
            delta = ts - ref_now if ts > 0 else -1.0
            is_up = delta > 0
            rec = {
                **ev,
                "is_upcoming": is_up,
                "countdown": _format_countdown(delta) if ts > 0 else "--",
            }
            enriched.append(rec)
            if is_up and ev.get("impact") == "HIGH" and (
                next_high is None or float(rec.get("timestamp") or 0.0) < float(next_high.get("timestamp") or 0.0)
            ):
                next_high = rec
            if ev.get("impact") == "HIGH" and ts > 0 and abs(ts - ref_now) <= win_sec:
                active_shield.append(rec)
        # Upcoming events first (ascending), followed by finished events (most recent first)
        enriched.sort(
            key=lambda x: (
                0 if x.get("is_upcoming") else 1,
                float(x.get("timestamp") or 0.0) if x.get("is_upcoming") else -float(x.get("timestamp") or 0.0),
            )
        )
        return {
            "events": enriched,
            "last_fetch_at": self.last_fetch_at,
            "last_error": self.last_error,
            "status_note": self.status_note,
            "next_high_impact": next_high,
            "active_shield_events": active_shield,
        }
