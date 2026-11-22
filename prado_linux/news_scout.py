"""Internet financial news & market research scout for Prado Institutional HFT (zero paid keys)."""
from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
import re
import time
from typing import Any, Callable
import urllib.request
import xml.etree.ElementTree as ET

RSS_FEEDS: list[dict[str, str]] = [
    {
        "source": "Yahoo Finance BTC",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US",
        "default_symbol": "cryBTCUSD",
    },
    {
        "source": "Yahoo Finance EURUSD",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=EURUSD=X&region=US&lang=en-US",
        "default_symbol": "frxEURUSD",
    },
    {
        "source": "Yahoo Finance Gold",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US",
        "default_symbol": "frxXAUUSD",
    },
    {
        "source": "Yahoo Finance S&P500",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
        "default_symbol": "OTC_SP500",
    },
]

HIGH_IMPACT_KEYWORDS = {
    "fed", "fomc", "powell", "cpi", "inflation", "payroll", "nfp", "interest rate",
    "rate cut", "rate hike", "ecb", "lagarde", "gdp", "sec", "etf", "hack", "exploit",
    "bankruptcy", "collapse", "crash", "emergency", "tariff", "war", "sanction",
    "recession", "unemployment", "halving", "ban",
}

BULLISH_KEYWORDS = {
    "surge", "surges", "rally", "rallies", "jump", "jumps", "soar", "soars", "gain",
    "gains", "rise", "rises", "bullish", "approve", "approved", "etf inflow", "rate cut",
    "dovish", "beat", "record high", "breakout", "rebound", "alta", "dispara", "sobe",
}

BEARISH_KEYWORDS = {
    "crash", "crashes", "plunge", "plunges", "drop", "drops", "fall", "falls", "slump",
    "bearish", "rate hike", "hawkish", "hack", "exploit", "bankruptcy", "collapse",
    "lawsuit", "ban", "recession", "inflation fears", "selloff", "sell-off", "queda", "desaba",
}

SYMBOL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cryBTCUSD", ("bitcoin", "btc", "crypto", "satoshi")),
    ("cryETHUSD", ("ethereum", "eth", "ether")),
    ("frxXAUUSD", ("gold", "xau", "bullion", "ouro")),
    ("frxEURUSD", ("eurusd", "eur/usd", "euro", "ecb", "lagarde")),
    ("frxGBPUSD", ("gbpusd", "gbp/usd", "pound", "sterling", "boe")),
    ("frxUSDJPY", ("usdjpy", "usd/jpy", "yen", "boj")),
    ("OTC_SP500", ("s&p 500", "sp500", "s&p", "wall street", "fed", "fomc", "cpi", "nfp", "payroll")),
    ("OTC_NDX", ("nasdaq", "tech stocks", "nvidia", "apple", "ai stocks")),
]


def _clean_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", txt).strip()


def infer_symbol(text: str, fallback: str = "cryBTCUSD") -> str:
    low = text.lower()
    for sym, kws in SYMBOL_KEYWORDS:
        if any(kw in low for kw in kws):
            return sym
    return fallback


def analyze_headline(title: str, summary: str = "", fallback_symbol: str = "cryBTCUSD") -> dict[str, Any]:
    """Classify headline impact (HIGH/MEDIUM/LOW), directional bias (BULLISH/BEARISH/NEUTRAL), and Deriv symbol."""
    combined = f"{title} {summary}".lower()
    bull_hits = sum(1 for kw in BULLISH_KEYWORDS if kw in combined)
    bear_hits = sum(1 for kw in BEARISH_KEYWORDS if kw in combined)
    high_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in combined)

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
    is_macro_usd = any(kw in combined for kw in ("fed", "fomc", "cpi", "nfp", "payroll", "powell", "interest rate"))
    return {
        "symbol": symbol,
        "impact": impact,
        "bias": bias,
        "score": round(score, 2),
        "is_macro_usd": is_macro_usd,
    }


def parse_rss_xml(xml_text: str, source: str, default_symbol: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not xml_text.strip():
        return items
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for node in root.findall(".//item")[:10]:
        title = _clean_html(node.findtext("title") or "")
        if not title:
            continue
        link = (node.findtext("link") or "").strip()
        desc = _clean_html(node.findtext("description") or "")
        pub_raw = (node.findtext("pubDate") or "").strip()
        pub_ts = time.time()
        pub_str = datetime.now().strftime("%H:%M:%S")
        if pub_raw:
            try:
                dt = parsedate_to_datetime(pub_raw)
                pub_ts = dt.timestamp()
                pub_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                pass
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


class NewsScout:
    """Periodic RSS news researcher that tracks seen items so each headline acts at most once."""

    def __init__(self, fetcher: Callable[[str], str] | None = None) -> None:
        self._fetcher = fetcher or self._default_fetch
        self._seen_ids: set[str] = set()
        self.items: list[dict[str, Any]] = []
        self.last_scan_at: float = 0.0
        self.last_error: str = ""

    def _default_fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 PradoHFT-NewsScout/1.0", "Accept": "application/rss+xml, application/xml"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def scan(self, feeds: list[dict[str, str]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Scan RSS feeds; returns (all_recent_items, newly_discovered_items)."""
        target_feeds = feeds or RSS_FEEDS
        collected: list[dict[str, Any]] = []
        errors: list[str] = []
        for f in target_feeds:
            try:
                xml_txt = self._fetcher(f["url"])
                parsed = parse_rss_xml(xml_txt, source=f["source"], default_symbol=f["default_symbol"])
                collected.extend(parsed)
            except Exception as exc:
                errors.append(f"{f['source']}: {exc}")

        self.last_scan_at = time.time()
        if collected:
            collected.sort(key=lambda x: float(x.get("published_ts", 0.0)), reverse=True)
            deduped: list[dict[str, Any]] = []
            seen_now: set[str] = set()
            for it in collected:
                if it["id"] not in seen_now:
                    seen_now.add(it["id"])
                    deduped.append(it)
            self.items = deduped[:40]
            self.last_error = ""
        elif errors:
            self.last_error = " | ".join(errors[:2])

        new_items = [it for it in self.items if it["id"] not in self._seen_ids]
        for it in new_items:
            self._seen_ids.add(it["id"])
        return self.items, new_items

    def summary_by_symbol(self) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for it in self.items:
            sym = str(it.get("symbol", ""))
            if not sym:
                continue
            entry = summary.setdefault(sym, {"symbol": sym, "count": 0, "high_impact": 0, "score_sum": 0.0, "bias": "NEUTRAL"})
            entry["count"] += 1
            if it.get("impact") == "HIGH":
                entry["high_impact"] += 1
            entry["score_sum"] += float(it.get("score", 0.0))
        for entry in summary.values():
            avg = entry["score_sum"] / max(1, entry["count"])
            entry["avg_score"] = round(avg, 2)
            entry["bias"] = "BULLISH" if avg > 0.1 else ("BEARISH" if avg < -0.1 else "NEUTRAL")
        return summary
