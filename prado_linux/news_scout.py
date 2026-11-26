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
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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
        "feed_id": "fxstreet_forex",
        "source": "FXStreet Forex News (EN)",
        "url": "https://www.fxstreet.com/rss/news",
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


def _clean_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", txt).strip()


def _has_keyword(text_lower: str, kw: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text_lower))


def infer_symbol(text: str, fallback: str = "BTCUSD") -> str:
    low = text.lower()
    for sym, kws in SYMBOL_KEYWORDS:
        if any(_has_keyword(low, kw) for kw in kws):
            return sym
    return fallback


def analyze_headline(title: str, summary: str = "", fallback_symbol: str = "BTCUSD") -> dict[str, Any]:
    """Classify headline impact (HIGH/MEDIUM/LOW), directional bias (BULLISH/BEARISH/NEUTRAL), and cTrader symbol."""
    combined = f"{title} {summary}".lower()
    bull_hits = sum(1 for kw in BULLISH_KEYWORDS if _has_keyword(combined, kw))
    bear_hits = sum(1 for kw in BEARISH_KEYWORDS if _has_keyword(combined, kw))
    high_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if _has_keyword(combined, kw))

    if high_hits >= 1 or abs(bull_hits - bear_hits) >= 2:
        impact = "HIGH"
    elif bull_hits > 0 or bear_hits > 0:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    net = bull_hits - bear_hits
    if net > 0:
        bias = "BULLISH"
    elif net < 0:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    score = max(-1.0, min(1.0, net / 3.0))
    symbol = infer_symbol(combined, fallback=fallback_symbol)
    is_macro_usd = any(
        _has_keyword(combined, kw)
        for kw in ("fed", "fomc", "cpi", "nfp", "payroll", "powell", "interest rate", "taxa de juros", "corte de juros", "inflação", "inflacao")
    )
    return {
        "symbol": symbol,
        "impact": impact,
        "bias": bias,
        "score": round(score, 2),
        "is_macro_usd": is_macro_usd,
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


class NewsScout:
    """Periodic RSS/Atom news researcher that tracks seen items, feed health and recency-weighted sentiment."""

    def __init__(self, fetcher: Callable[[str], str] | None = None) -> None:
        self._fetcher = fetcher or self._default_fetch
        self._seen_ids: set[str] = set()
        self.items: list[dict[str, Any]] = []
        self.feed_status: list[dict[str, Any]] = []
        self.last_scan_at: float = 0.0
        self.last_error: str = ""

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

    def snapshot_dict(self, now_ts: float | None = None) -> dict[str, Any]:
        ref_now = time.time() if now_ts is None else float(now_ts)
        enriched: list[dict[str, Any]] = []
        next_high: dict[str, Any] | None = None
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
        }
