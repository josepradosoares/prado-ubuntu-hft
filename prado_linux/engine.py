"""Prado Institutional HFT Trading Engine, cTrader Open API Connector & Robot Fleet."""
from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import random
import threading
import time
from typing import Any
import uuid

from prado_linux.config import (
    MATH_BOT_TEMPLATES,
    PradoServerConfig,
    deduplicate_accounts,
    save_config,
)
from prado_linux.ctrader_client import (
    CTraderAuthError,
    CTraderClient,
    CTraderRateLimiter,
    CTraderRateLimitError,
    build_oauth_authorize_url,
    exchange_oauth_code,
    mask_secret,
)
from prado_linux.flow_math import (
    TICK_FLAG_BUY,
    TICK_FLAG_SELL,
    TickRecord,
    compute_flow_metrics,
    compute_intraday_vwap,
)
from prado_linux.indicators import (
    DEFAULT_PYTHON_STRATEGY_TEMPLATE,
    INDICATOR_CATALOG,
    evaluate_indicator_model,
    evaluate_python_model,
)
from prado_linux.news_scout import NewsScout, validate_rss_url


def normalize_tp_config(tp_mode: Any, tp_value: Any) -> tuple[str, float]:
    """Normalize per-bot Take Profit mode ('AUTO', 'USD', 'PCT', 'PIPS', 'TICKS') and value."""
    mode = str(tp_mode or "AUTO").strip().upper()
    if mode not in ("AUTO", "USD", "PCT", "PIPS", "TICKS"):
        return "AUTO", 0.0
    if mode == "AUTO":
        return "AUTO", 0.0
    defaults = {"USD": 2.0, "PCT": 0.25, "PIPS": 10.0, "TICKS": 10.0}
    try:
        val = float(tp_value)
    except (TypeError, ValueError):
        val = defaults[mode]
    if not math.isfinite(val) or val <= 0.0:
        val = defaults[mode]
    return mode, round(val, 4)


MAIN_CTRADER_SYMBOLS: list[dict[str, str]] = [
    {"name": "EURUSD", "category": "Forex Principais", "description": "EUR/USD Forex"},
    {"name": "GBPUSD", "category": "Forex Principais", "description": "GBP/USD Forex"},
    {"name": "USDJPY", "category": "Forex Principais", "description": "USD/JPY Forex"},
    {"name": "AUDUSD", "category": "Forex Principais", "description": "AUD/USD Forex"},
    {"name": "USDCAD", "category": "Forex Principais", "description": "USD/CAD Forex"},
    {"name": "XAUUSD", "category": "Metais & Commodities", "description": "Ouro Spot (XAU/USD)"},
    {"name": "US100", "category": "Índices Globais", "description": "Nasdaq 100 (US100)"},
    {"name": "US500", "category": "Índices Globais", "description": "S&P 500 (US500)"},
    {"name": "BTCUSD", "category": "Criptomoedas (24/7)", "description": "Bitcoin vs US Dollar (24/7)"},
    {"name": "ETHUSD", "category": "Criptomoedas (24/7)", "description": "Ethereum vs US Dollar (24/7)"},
]

EXTENDED_CTRADER_SYMBOLS: list[dict[str, str]] = MAIN_CTRADER_SYMBOLS + [
    {"name": "USDCHF", "category": "Forex Principais", "description": "USD/CHF Forex"},
    {"name": "NZDUSD", "category": "Forex Principais", "description": "NZD/USD Forex"},
    {"name": "EURJPY", "category": "Forex Cruzados", "description": "EUR/JPY Forex"},
    {"name": "GBPJPY", "category": "Forex Cruzados", "description": "GBP/JPY Forex"},
    {"name": "XAGUSD", "category": "Metais & Commodities", "description": "Prata Spot (XAG/USD)"},
    {"name": "US30", "category": "Índices Globais", "description": "Dow Jones 30 (US30)"},
    {"name": "DE40", "category": "Índices Globais", "description": "DAX 40 (DE40)"},
]

SYMBOL_SPECS: dict[str, dict[str, float]] = {
    "EURUSD": {"base": 1.0850, "pip_size": 0.0001, "contract_size": 100_000.0},
    "GBPUSD": {"base": 1.2650, "pip_size": 0.0001, "contract_size": 100_000.0},
    "AUDUSD": {"base": 0.6550, "pip_size": 0.0001, "contract_size": 100_000.0},
    "NZDUSD": {"base": 0.5950, "pip_size": 0.0001, "contract_size": 100_000.0},
    "USDCAD": {"base": 1.3950, "pip_size": 0.0001, "contract_size": 100_000.0},
    "USDCHF": {"base": 0.8850, "pip_size": 0.0001, "contract_size": 100_000.0},
    "USDJPY": {"base": 154.20, "pip_size": 0.01, "contract_size": 100_000.0},
    "EURJPY": {"base": 167.30, "pip_size": 0.01, "contract_size": 100_000.0},
    "GBPJPY": {"base": 195.10, "pip_size": 0.01, "contract_size": 100_000.0},
    "XAUUSD": {"base": 2655.0, "pip_size": 0.1, "contract_size": 100.0},
    "XAGUSD": {"base": 31.20, "pip_size": 0.01, "contract_size": 5000.0},
    "US500": {"base": 5950.0, "pip_size": 0.1, "contract_size": 1.0},
    "US100": {"base": 20850.0, "pip_size": 0.1, "contract_size": 1.0},
    "US30": {"base": 43800.0, "pip_size": 1.0, "contract_size": 1.0},
    "DE40": {"base": 19300.0, "pip_size": 0.1, "contract_size": 1.0},
    "BTCUSD": {"base": 94500.0, "pip_size": 1.0, "contract_size": 1.0},
    "ETHUSD": {"base": 3350.0, "pip_size": 0.1, "contract_size": 1.0},
}


def get_symbol_spec(symbol: str) -> dict[str, float]:
    sym = str(symbol or "EURUSD").upper()
    if sym in SYMBOL_SPECS:
        return SYMBOL_SPECS[sym]
    if "JPY" in sym:
        return {"base": 150.0, "pip_size": 0.01, "contract_size": 100_000.0}
    if "XAU" in sym:
        return {"base": 2650.0, "pip_size": 0.1, "contract_size": 100.0}
    if "BTC" in sym:
        return {"base": 94500.0, "pip_size": 1.0, "contract_size": 1.0}
    if "ETH" in sym:
        return {"base": 3350.0, "pip_size": 0.1, "contract_size": 1.0}
    return {"base": 1.1000, "pip_size": 0.0001, "contract_size": 100_000.0}


def estimate_cfd_pnl(symbol: str, is_buy: bool, entry_price: float, exit_price: float, lot_size: float) -> float:
    spec = get_symbol_spec(symbol)
    diff = (exit_price - entry_price) if is_buy else (entry_price - exit_price)
    raw = diff * float(lot_size) * spec["contract_size"]
    if symbol.upper().endswith("JPY") and exit_price > 0:
        raw = raw / exit_price
    elif symbol.upper().endswith("CHF") and exit_price > 0:
        raw = raw / exit_price
    elif symbol.upper().endswith("CAD") and exit_price > 0:
        raw = raw / exit_price
    return round(raw, 2)


class CTraderUniversalConnector:
    """Connects directly to cTrader Open API (100% Python, port 5036) with Simulation fallback."""

    def __init__(self, cfg: PradoServerConfig) -> None:
        self.cfg = cfg
        self.rate_limiter = CTraderRateLimiter()
        self._client: CTraderClient | None = None
        self._client_auth: dict[str, Any] = {}
        self.connected: bool = False
        self.connection_state: str = (
            "DISCONNECTED" if cfg.connection_mode.upper() != "SIMULATION" else "CONNECTED"
        )
        self.auth_state: str = "UNAUTHENTICATED"
        self.backend_name: str = (
            "CTRADER_DISCONNECTED" if cfg.connection_mode.upper() != "SIMULATION" else "SIMULATION_FEED"
        )
        self.last_error: str = ""
        self.last_tick_at: float = 0.0
        self._sim_ticks: dict[str, list[TickRecord]] = {}
        self._sim_positions: list[dict[str, Any]] = []
        self._sim_deals_history: list[dict[str, Any]] = []
        self._live_deals_history: list[dict[str, Any]] = []
        self._sim_daily_pnl: float = 0.0
        self._sim_balance: float = 10_000.0
        self._tick_cache: dict[str, tuple[float, list[TickRecord]]] = {}
        self._symbols_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._balance_cache: tuple[float, float] | None = None
        self._positions_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._position_bot_map: dict[str, str] = {}
        self._recorded_deal_tickets: set[str] = set()
        self._last_order_ts: dict[str, float] = {}
        self._last_ping_at: float = time.time()

    def connect(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        account_id: str | None = None,
        is_live: bool | None = None,
    ) -> tuple[bool, str]:
        cid = (client_id if client_id is not None else self.cfg.ctrader_client_id).strip()
        csec = (client_secret if client_secret is not None else self.cfg.ctrader_client_secret).strip()
        tok = (access_token if access_token is not None else self.cfg.ctrader_access_token).strip()
        rtok = (refresh_token if refresh_token is not None else self.cfg.ctrader_refresh_token).strip()
        acc_id = (account_id if account_id is not None else self.cfg.active_account_id).strip()
        if acc_id.startswith("ct_"):
            acc_id = acc_id[3:]
        want_live = (
            bool(is_live)
            if is_live is not None
            else (self.cfg.active_account_type.upper() == "REAL")
        )
        mode = self.cfg.connection_mode.upper()

        if self._client is not None:
            self._client.close()
            self._client = None

        if mode != "SIMULATION" and cid and csec and tok:
            self.connection_state = "CONNECTING"
            try:
                client = CTraderClient(
                    client_id=cid,
                    client_secret=csec,
                    access_token=tok,
                    refresh_token=rtok,
                    account_id=acc_id,
                    is_live=want_live,
                    preferred_account_type=self.cfg.active_account_type,
                    rate_limiter=self.rate_limiter,
                )
                auth = client.authorize()
                self._client = client
                self._client_auth = auth
                self.connected = True
                self.connection_state = "CONNECTED"
                self.auth_state = "AUTHENTICATED"
                self.backend_name = "CTRADER_LIVE_API"
                self.last_error = ""
                self._last_ping_at = time.time()
                self._balance_cache = (time.time(), float(auth.get("balance", 0.0)))
                env_str = "DEMO" if auth.get("is_virtual") else "REAL"
                return (
                    True,
                    f"Conectado à cTrader [{env_str}] — {auth.get('broker_name', 'cTrader')} Conta {auth.get('loginid')} ({auth.get('balance')} {auth.get('currency', 'USD')}).",
                )
            except CTraderAuthError as exc:
                self._client = None
                self._client_auth = {}
                self.auth_state = exc.auth_state
                self.connection_state = "ERROR"
                self.last_error = str(exc)
                self.connected = False
                self.backend_name = "CTRADER_DISCONNECTED"
                return False, f"Erro ao conectar na cTrader: {exc}"
            except Exception as exc:
                self._client = None
                self._client_auth = {}
                err_msg = str(exc)
                if "RateLimit" in err_msg or "FREQUENCY" in err_msg:
                    self.auth_state = "UNAUTHENTICATED"
                else:
                    self.auth_state = "TOKEN_INVALID"
                self.connection_state = "ERROR"
                self.last_error = err_msg
                self.connected = False
                self.backend_name = "CTRADER_DISCONNECTED"
                return False, f"Erro ao conectar na cTrader: {err_msg}"

        self._client = None
        self._client_auth = {}
        if mode != "SIMULATION":
            self.connected = False
            self.connection_state = "DISCONNECTED"
            self.auth_state = "UNAUTHENTICATED"
            self.backend_name = "CTRADER_DISCONNECTED"
            return (
                False,
                "Credenciais cTrader não conectadas. Configure Client ID, Client Secret e autorize via OAuth em 'Configuração cTrader'.",
            )

        self.connected = True
        self.connection_state = "CONNECTED"
        self.auth_state = "AUTHENTICATED"
        self.backend_name = "SIMULATION_FEED"
        self._tick_cache.clear()
        return True, "Modo Simulação Quant (CFD Lotes) Ativo."

    def discover_broker_symbols(self, mode: str = "PRINCIPAIS") -> list[dict[str, Any]]:
        mode_upper = mode.upper()
        client = self._client
        if client is not None and self.cfg.connection_mode.upper() != "SIMULATION":
            now = time.time()
            if self._symbols_cache and (now - self._symbols_cache[0]) < 60.0:
                syms = self._symbols_cache[1]
            else:
                try:
                    syms = client.get_active_symbols()
                    if syms:
                        self._symbols_cache = (now, syms)
                except Exception as exc:
                    self.last_error = f"Erro listando ativos cTrader: {exc}"
                    syms = []
            if syms:
                if mode_upper == "PRINCIPAIS":
                    main_set = {m["name"] for m in MAIN_CTRADER_SYMBOLS}
                    filtered = [s for s in syms if s["name"] in main_set]
                    if filtered:
                        return filtered
                return syms[:500]

        source = MAIN_CTRADER_SYMBOLS if mode_upper == "PRINCIPAIS" else EXTENDED_CTRADER_SYMBOLS
        seen = {item["name"] for item in source}
        result = [dict(item, visible=True) for item in source]
        for cat_name, syms in self.cfg.custom_categories.items():
            for sym in syms:
                if sym not in seen:
                    seen.add(sym)
                    result.append(
                        {
                            "name": sym,
                            "category": cat_name,
                            "description": f"Ativo {sym} ({cat_name})",
                            "visible": True,
                        }
                    )
        return result

    def _compute_data_state(self, now: float | None = None) -> str:
        t = time.time() if now is None else now
        if self.last_tick_at <= 0:
            return "NO_DATA"
        if (t - self.last_tick_at) > 15.0:
            return "STALE"
        return "LIVE"

    def _compute_trading_state(self, account_mode: str, rl_status: dict[str, Any]) -> str:
        if self.cfg.connection_mode.upper() == "SIMULATION":
            return "READY" if self.connected else "BLOCKED"
        if not self.connected or self.connection_state != "CONNECTED":
            return "BLOCKED"
        if self.auth_state != "AUTHENTICATED":
            return "BLOCKED"
        if rl_status.get("state") == "BLOCKED":
            return "BLOCKED"
        if account_mode == "REAL" and not getattr(self.cfg, "allow_real_trading", False):
            return "BLOCKED"
        return "READY"

    def get_account_summary(self) -> dict[str, Any]:
        now = time.time()
        rl_status = self.rate_limiter.status(now)
        data_state = self._compute_data_state(now)
        masked_cid = mask_secret(self.cfg.ctrader_client_id or "", 4, 4)

        if self._client is not None:
            try:
                auth = self._client_auth
                if not auth:
                    auth = self._client.authorize()
                    self._client_auth = auth

                bal = float(auth.get("balance", 0.0))
                if self._balance_cache is None or (now - self._balance_cache[0]) >= 10.0:
                    try:
                        fresh_bal = self._client.get_balance()
                        if fresh_bal is not None:
                            bal = fresh_bal
                            self._balance_cache = (now, bal)
                    except CTraderAuthError:
                        raise
                    except CTraderRateLimitError as exc:
                        self.last_error = str(exc)
                    except Exception:
                        pass
                else:
                    bal = self._balance_cache[1]

                positions = self.get_open_positions()
                floating = sum(float(p.get("profit", 0.0)) for p in positions)
                realized = round(
                    sum(float(d.get("profit", 0.0)) for d in self._live_deals_history), 2
                )
                is_virt = bool(auth.get("is_virtual", 1))
                acc_mode = "DEMO" if is_virt else "REAL"
                trading_state = self._compute_trading_state(acc_mode, rl_status)
                ws_host = "live.ctraderapi.com:5036" if not is_virt else "demo.ctraderapi.com:5036"
                return {
                    "backend": self.backend_name,
                    "connected": True,
                    "account_type": acc_mode,
                    "account_mode": acc_mode,
                    "connection_state": self.connection_state,
                    "auth_state": self.auth_state,
                    "data_state": data_state,
                    "trading_state": trading_state,
                    "rate_limit": rl_status,
                    "masked_client_id": masked_cid,
                    "broker_name": str(auth.get("broker_name", "cTrader")),
                    "leverage": int(auth.get("leverage", 100) or 100),
                    "last_tick_at": self.last_tick_at,
                    "active_account_id": self.cfg.active_account_id,
                    "login": str(auth.get("loginid", "---")),
                    "server": f"cTrader Open API ({ws_host})",
                    "name": str(auth.get("fullname", "Conta cTrader")),
                    "currency": str(auth.get("currency", "USD")),
                    "balance": round(bal, 2),
                    "equity": round(bal + floating, 2),
                    "profit": round(floating, 2),
                    "daily_realized": realized,
                    "margin_free": round(bal + floating, 2),
                    "status_note": self.last_error,
                }
            except CTraderAuthError as exc:
                self.auth_state = exc.auth_state
                self.connection_state = "ERROR"
                self.connected = False
                self.last_error = str(exc)
            except Exception as exc:
                self.last_error = str(exc)

        if self.cfg.connection_mode.upper() != "SIMULATION":
            acc_mode = self.cfg.active_account_type.upper() or "DEMO"
            return {
                "backend": "CTRADER_DISCONNECTED",
                "connected": False,
                "account_type": acc_mode,
                "account_mode": acc_mode,
                "connection_state": self.connection_state,
                "auth_state": self.auth_state,
                "data_state": data_state,
                "trading_state": "BLOCKED",
                "rate_limit": rl_status,
                "masked_client_id": masked_cid,
                "broker_name": "cTrader",
                "leverage": 0,
                "last_tick_at": self.last_tick_at,
                "active_account_id": self.cfg.active_account_id,
                "login": "DESCONECTADO",
                "server": self.last_error or "Aguardando credenciais/token cTrader Open API",
                "name": "Conta cTrader Desconectada",
                "currency": "USD",
                "balance": 0.0,
                "equity": 0.0,
                "profit": 0.0,
                "daily_realized": 0.0,
                "margin_free": 0.0,
                "status_note": self.last_error,
            }

        floating = sum(p.get("profit", 0.0) for p in self._sim_positions)
        acc_mode = self.cfg.active_account_type.upper() or "DEMO"
        return {
            "backend": self.backend_name,
            "connected": self.connected,
            "account_type": acc_mode,
            "account_mode": acc_mode,
            "connection_state": "CONNECTED",
            "auth_state": "AUTHENTICATED",
            "data_state": data_state if data_state != "NO_DATA" else "LIVE",
            "trading_state": "READY",
            "rate_limit": rl_status,
            "masked_client_id": masked_cid,
            "broker_name": "Simulador cTrader",
            "leverage": 100,
            "last_tick_at": self.last_tick_at or now,
            "active_account_id": self.cfg.active_account_id,
            "login": "CT-DEMO-SIM" if acc_mode == "DEMO" else "CT-LIVE-SIM",
            "server": "cTrader Quant Simulador (Lotes CFD)",
            "name": f"Mesa cTrader ({acc_mode})",
            "currency": "USD",
            "balance": round(self._sim_balance + self._sim_daily_pnl, 2),
            "equity": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "profit": round(floating, 2),
            "daily_realized": round(self._sim_daily_pnl, 2),
            "margin_free": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "status_note": self.last_error,
        }

    TIMEFRAME_GRANULARITIES: dict[str, int] = {
        "TICKS": 0,
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D1": 86400,
    }

    _PERIOD_SECONDS: dict[str, int] = {
        "1D": 86400,
        "1W": 7 * 86400,
        "1M": 30 * 86400,
        "1Y": 365 * 86400,
        "2Y": 730 * 86400,
        "ALL_TIME": 5 * 365 * 86400,
    }

    def fetch_backtest_history(
        self,
        symbol: str,
        count: int,
        timeframe: str = "TICKS",
        period: str = "CUSTOM",
    ) -> tuple[list[TickRecord], str]:
        """Fetch real cTrader historical ticks or trendbars for backtesting."""
        tf = str(timeframe or "TICKS").strip().upper()
        per = str(period or "CUSTOM").strip().upper()
        target_count = max(120, int(count))
        if per in self._PERIOD_SECONDS:
            sec = self._PERIOD_SECONDS[per]
            gran_for_calc = 86400 if tf == "MN1" else self.TIMEFRAME_GRANULARITIES.get(tf, 0)
            if gran_for_calc > 0:
                target_count = max(120, min(5000, sec // gran_for_calc))
            else:
                target_count = min(5000, max(400, sec // 2))

        if self.cfg.connection_mode.upper() == "SIMULATION":
            return [], "SIMULATION"
        client = self._client
        if client is None:
            return [], "SIMULATION_FALLBACK"
        try:
            if tf == "MN1":
                daily = client.get_ticks_history(symbol, count=min(5000, max(target_count, 360)), granularity=86400)
                if not daily:
                    return [], "SIMULATION_FALLBACK"
                monthly: dict[tuple[int, int], TickRecord] = {}
                for tk in daily:
                    dt = datetime.fromtimestamp(tk.time_msc / 1000.0)
                    monthly[(dt.year, dt.month)] = tk
                bars = [monthly[k] for k in sorted(monthly.keys())]
                return (bars, "CTRADER_REAL") if len(bars) >= 12 else ([], "SIMULATION_FALLBACK")
            gran = self.TIMEFRAME_GRANULARITIES.get(tf, 0)
            records = client.get_ticks_history(symbol, count=target_count, granularity=gran)
            if len(records) >= 45:
                return records, "CTRADER_REAL"
        except Exception as exc:
            self.last_error = f"Aviso backtest histórico ({symbol}/{tf}): {exc}"
        return [], "SIMULATION_FALLBACK"

    def fetch_ticks(self, symbol: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
        now = time.time()
        gran = int(granularity or 0)
        if self.cfg.connection_mode.upper() == "SIMULATION":
            ticks_sim = self._generate_sim_ticks(symbol)
            if ticks_sim:
                self.last_tick_at = now
            return ticks_sim

        cache_key = symbol if gran <= 0 else f"{symbol}:{gran}"
        cached = self._tick_cache.get(cache_key)
        if cached and (now - cached[0]) < 4.0 and len(cached[1]) >= min(count, 40):
            return cached[1]
        client = self._client
        if client is not None:
            try:
                ticks = client.get_ticks_history(symbol, count=min(500, count), granularity=gran)
                if ticks:
                    self._tick_cache[cache_key] = (now, ticks)
                    self.last_tick_at = now
                    return ticks
            except Exception as exc:
                if cached:
                    return cached[1]
                self.last_error = f"Erro lendo cotações cTrader ({symbol}): {exc}"
        return cached[1] if cached else []

    def _generate_sim_ticks(self, symbol: str) -> list[TickRecord]:
        spec = get_symbol_spec(symbol)
        base_price = spec["base"]
        spread = spec["pip_size"] * 1.2
        step_scale = base_price * 0.00025
        history = self._sim_ticks.get(symbol)
        now_msc = int(time.time() * 1000)

        if not history:
            history = []
            p = base_price
            rng = random.Random(hash(symbol) & 0xFFFFFFFF)
            for i in range(240):
                drift = math.sin(i / 18.0) * step_scale * 0.6 + rng.uniform(-step_scale, step_scale)
                p = max(step_scale, p + drift)
                flag = TICK_FLAG_BUY if drift >= 0 else TICK_FLAG_SELL
                vol = rng.randint(5, 85)
                history.append(
                    TickRecord(
                        time_msc=now_msc - (240 - i) * 1000,
                        bid=round(p - spread * 0.5, 6),
                        ask=round(p + spread * 0.5, 6),
                        last=round(p, 6),
                        volume_real=0.0,
                        tick_volume=float(vol),
                        flags=flag,
                    )
                )
            self._sim_ticks[symbol] = history

        last_p = history[-1].effective_price()
        for _ in range(3):
            wave = math.sin(time.time() / 7.0 + (hash(symbol) % 10)) * step_scale * 0.85
            noise = random.uniform(-step_scale * 0.7, step_scale * 0.7)
            delta = wave + noise
            new_p = max(step_scale, last_p + delta)
            flag = TICK_FLAG_BUY if delta >= 0 else TICK_FLAG_SELL
            vol = random.randint(10, 140)
            history.append(
                TickRecord(
                    time_msc=int(time.time() * 1000),
                    bid=round(new_p - spread * 0.5, 6),
                    ask=round(new_p + spread * 0.5, 6),
                    last=round(new_p, 6),
                    volume_real=0.0,
                    tick_volume=float(vol),
                    flags=flag,
                )
            )
            last_p = new_p

        if len(history) > 600:
            self._sim_ticks[symbol] = history[-600:]
        return self._sim_ticks[symbol]

    def _record_live_deal(
        self,
        ticket: str | int,
        symbol: str,
        side: str,
        volume: float,
        price_open: float,
        price_close: float,
        profit: float,
        reason: str,
        bot_name: str,
        comment: str = "",
    ) -> bool:
        tid = str(ticket)
        if tid and tid in self._recorded_deal_tickets:
            return False
        if tid:
            self._recorded_deal_tickets.add(tid)
        ts_str = datetime.now().strftime("%H:%M:%S")
        bname = bot_name or comment or "cTrader"
        self._live_deals_history.insert(
            0,
            {
                "ticket": tid,
                "time": ts_str,
                "time_str": ts_str,
                "symbol": symbol or "--",
                "type": side or "BUY",
                "side": side or "BUY",
                "volume": float(volume or 0.0),
                "price_open": float(price_open or 0.0),
                "price_close": float(price_close or 0.0),
                "profit": round(float(profit or 0.0), 2),
                "reason": reason,
                "comment": comment or bname,
                "bot_name": bname,
            },
        )
        return True

    def sync_closed_deals(self) -> list[dict[str, Any]]:
        if self.cfg.connection_mode.upper() == "SIMULATION" or self._client is None:
            return []
        pop_fn = getattr(self._client, "pop_closed_deals", None)
        if not callable(pop_fn):
            return []
        closed_deals = pop_fn()
        if not closed_deals:
            return []
        recorded: list[dict[str, Any]] = []
        closed_ids: set[str] = set()
        for deal in closed_deals:
            pid = str(deal.get("ticket") or "")
            if not pid:
                continue
            closed_ids.add(pid)
            sym = str(deal.get("symbol") or "--")
            bname = self._position_bot_map.get(pid) or str(deal.get("bot_name") or "") or next(
                (str(b.get("name", "")) for b in self.cfg.bots if b.get("symbol") == sym and b.get("name")),
                "cTrader",
            )
            if self._record_live_deal(
                ticket=pid,
                symbol=sym,
                side=str(deal.get("side") or "BUY"),
                volume=float(deal.get("volume") or 0.0),
                price_open=float(deal.get("price_open") or 0.0),
                price_close=float(deal.get("price_close") or 0.0),
                profit=float(deal.get("profit") or 0.0),
                reason=str(deal.get("reason") or "CTRADER_AUTO_CLOSE"),
                bot_name=bname,
                comment=bname,
            ):
                recorded.append(self._live_deals_history[0])
        if closed_ids and self._positions_cache is not None:
            ts_c, cached_list = self._positions_cache
            self._positions_cache = (
                ts_c,
                [p for p in cached_list if str(p.get("ticket")) not in closed_ids],
            )
        if recorded:
            self._balance_cache = None
        return recorded

    def get_open_positions(self) -> list[dict[str, Any]]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._client is None:
                return []
            now = time.time()
            cache_ttl = 4.0
            if self._positions_cache and (now - self._positions_cache[0]) < cache_ttl:
                return self._positions_cache[1]
            try:
                pos = self._client.get_open_positions()
                for item in pos:
                    pid_str = str(item.get("ticket", ""))
                    bname = self._position_bot_map.get(pid_str) or item.get("bot_name") or next(
                        (str(b.get("name", "")) for b in self.cfg.bots if b.get("symbol") == item.get("symbol") and b.get("name")),
                        "cTrader",
                    )
                    item["bot_name"] = bname
                    item["comment"] = item.get("comment") or bname
                self._positions_cache = (now, pos)
                return pos
            except CTraderRateLimitError as exc:
                self.last_error = str(exc)
                return self._positions_cache[1] if self._positions_cache else []
            except Exception as exc:
                self.last_error = f"Erro lendo posições cTrader: {exc}"
                return self._positions_cache[1] if self._positions_cache else []

        for pos in list(self._sim_positions):
            sym = pos["symbol"]
            ticks = self._sim_ticks.get(sym)
            if ticks:
                curr = ticks[-1].effective_price()
                pos["price_current"] = round(curr, 6)
                is_buy = pos["type"] == "BUY"
                pos["profit"] = estimate_cfd_pnl(sym, is_buy, pos["price_open"], curr, float(pos["volume"]))

                hit_tp = (curr >= pos["tp"]) if is_buy else (curr <= pos["tp"])
                hit_sl = (curr <= pos["sl"]) if is_buy else (curr >= pos["sl"])
                if (pos["tp"] > 0 and hit_tp) or (pos["sl"] > 0 and hit_sl):
                    self._sim_daily_pnl += pos["profit"]
                    self._sim_deals_history.insert(
                        0,
                        {
                            "ticket": pos["ticket"],
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "time_str": datetime.now().strftime("%H:%M:%S"),
                            "symbol": sym,
                            "type": pos["type"],
                            "side": pos["type"],
                            "volume": pos["volume"],
                            "price_open": pos["price_open"],
                            "price_close": round(curr, 6),
                            "profit": pos["profit"],
                            "reason": "TAKE_PROFIT" if hit_tp else "STOP_LOSS",
                            "comment": pos.get("comment", ""),
                            "bot_name": pos.get("bot_name") or pos.get("comment", ""),
                        },
                    )
                    self._sim_positions.remove(pos)
        return list(self._sim_positions)

    def place_order(
        self,
        symbol: str,
        action: str,
        lot_size: float,
        price: float,
        sl_points: float,
        tp_points: float,
        bot_name: str = "PradoBot",
        allow_multi_same_symbol: bool = False,
        max_levels_override: int = 0,
        tp_mode: str = "AUTO",
        tp_value: float = 0.0,
    ) -> tuple[bool, str]:
        now = time.time()
        lots = max(0.01, round(float(lot_size or 0.01), 4))
        max_lot = float(getattr(self.cfg, "max_lot_per_trade", 1.0) or 1.0)
        if lots > max_lot:
            return False, f"Volume {lots:.2f} lote(s) excede o limite máximo por operação ({max_lot:.2f})."

        raw_interval = getattr(self.cfg, "min_order_interval_sec", 3.0)
        min_interval = 3.0 if raw_interval is None else float(raw_interval)
        last_ts = self._last_order_ts.get(symbol, 0.0)
        if (now - last_ts) < min_interval:
            return False, f"Intervalo mínimo entre operações ativo para {symbol}"

        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._client is None or not self.connected or self.auth_state != "AUTHENTICATED":
                return False, f"Negociação bloqueada: cTrader desconectada ou não autenticada ({self.auth_state})"
            is_virt = bool(self._client_auth.get("is_virtual", 1))
            if not is_virt and not getattr(self.cfg, "allow_real_trading", False):
                return False, "Negociação em conta REAL bloqueada por padrão de segurança."
            rl = self.rate_limiter.status(now)
            if rl.get("state") == "BLOCKED":
                return False, f"Negociação bloqueada por RateLimit ({rl.get('cooldown_seconds')}s)"
            data_state = self._compute_data_state(now)
            if data_state != "LIVE":
                return False, f"Negociação bloqueada: cotações indisponíveis/desatualizadas ({data_state}) para {symbol}."

        open_positions = self.get_open_positions()
        max_concurrent = int(getattr(self.cfg, "max_concurrent_trades", 5) or 5)
        if allow_multi_same_symbol and max_levels_override > 0:
            max_concurrent = max(max_concurrent, max_levels_override)
        if len(open_positions) >= max_concurrent:
            return False, f"Limite de operações simultâneas atingido ({len(open_positions)}/{max_concurrent})."

        max_total_lots = float(getattr(self.cfg, "max_total_lots", 5.0) or 5.0)
        current_lots = sum(float(p.get("volume", 0.0)) for p in open_positions)
        if (current_lots + lots) > max_total_lots:
            return False, f"Exposição total ({current_lots + lots:.2f} lotes) excede o limite ({max_total_lots:.2f} lotes)."

        if not allow_multi_same_symbol and any(p.get("symbol") == symbol for p in open_positions):
            return False, f"Posição já aberta em {symbol} (bloqueio de ordem duplicada)."

        self._last_order_ts[symbol] = now
        is_buy = action.startswith("BUY")
        spec = get_symbol_spec(symbol)
        # Mandatory SL guard for CFD margin protection
        eff_sl_pts = float(sl_points or 0.0)
        if eff_sl_pts <= 0.0:
            eff_sl_pts = max(price * 0.0020, spec["pip_size"] * 20.0)

        norm_tp_mode, norm_tp_val = normalize_tp_config(tp_mode, tp_value)
        eff_tp_pts = float(tp_points or 0.0)
        if norm_tp_mode == "USD":
            denom = max(1e-6, lots * spec["contract_size"])
            usd_dist = norm_tp_val / denom
            if symbol.upper().endswith(("JPY", "CHF", "CAD")) and price > 0:
                usd_dist *= price
            eff_tp_pts = max(spec["pip_size"], usd_dist)
        elif norm_tp_mode == "PCT":
            eff_tp_pts = max(spec["pip_size"], price * (norm_tp_val / 100.0))
        elif norm_tp_mode in ("PIPS", "TICKS"):
            eff_tp_pts = max(spec["pip_size"], norm_tp_val * spec["pip_size"])
        elif eff_tp_pts <= 0.0:
            eff_tp_pts = eff_sl_pts * 1.8

        if self._client is not None:
            ok, msg = self._client.place_market_order(
                symbol=symbol,
                is_buy=is_buy,
                lots=lots,
                sl_points=eff_sl_pts,
                tp_points=eff_tp_pts,
                label=bot_name,
                comment=f"{bot_name[:14]}_{action}",
            )
            if ok:
                pid = self._client.last_order_lifecycle.get("position_id") or self._client.last_order_lifecycle.get("order_id")
                if pid is not None:
                    pid_str = str(pid)
                    self._position_bot_map[pid_str] = bot_name
                    side_str = "BUY" if is_buy else "SELL"
                    sl_price = round(price - eff_sl_pts, 6) if is_buy else round(price + eff_sl_pts, 6)
                    tp_price = round(price + eff_tp_pts, 6) if is_buy else round(price - eff_tp_pts, 6)
                    new_pos = {
                        "ticket": pid_str,
                        "symbol": symbol,
                        "type": side_str,
                        "side": side_str,
                        "volume": lots,
                        "price_open": round(price, 6),
                        "price_current": round(price, 6),
                        "sl": sl_price,
                        "tp": tp_price,
                        "profit": 0.0,
                        "bot_name": bot_name,
                        "comment": f"{bot_name[:14]}_{action}",
                    }
                    if self._positions_cache is not None:
                        cache_ts, cached_pos = self._positions_cache
                        if not any(str(p.get("ticket")) == pid_str for p in cached_pos):
                            self._positions_cache = (cache_ts, [*cached_pos, new_pos])
                    else:
                        self._positions_cache = (now, [new_pos])
            return ok, msg

        sl = round(price - eff_sl_pts, 6) if is_buy else round(price + eff_sl_pts, 6)
        tp = round(price + eff_tp_pts, 6) if is_buy else round(price - eff_tp_pts, 6)
        ticket = int(time.time() * 1000) % 100_000_000
        side_str = "BUY" if is_buy else "SELL"
        self._sim_positions.append(
            {
                "ticket": ticket,
                "symbol": symbol,
                "type": side_str,
                "side": side_str,
                "volume": lots,
                "price_open": round(price, 6),
                "price_current": round(price, 6),
                "sl": sl,
                "tp": tp,
                "profit": 0.0,
                "bot_name": bot_name,
                "comment": f"{bot_name[:14]}_{action}",
            }
        )
        return True, f"[{bot_name}] Ordem {action} ({lots:.2f} lote) aberta em {symbol}"

    def close_all_positions(self, reason: str = "MANUAL_PANIC_FLATTEN") -> tuple[int, str]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._client is None:
                return 0, "cTrader desconectada: nenhuma posição ativa para encerrar."
            self._positions_cache = None
            positions = self.get_open_positions()
            closed = 0
            errors: list[str] = []
            for p in positions:
                try:
                    ok, err_msg = self._client.close_position(str(p["ticket"]), volume_raw=p.get("volume_raw"))
                except Exception as exc:
                    ok, err_msg = False, str(exc)
                if ok:
                    closed += 1
                    self._record_live_deal(
                        ticket=p["ticket"],
                        symbol=p["symbol"],
                        side=p.get("side", p.get("type", "BUY")),
                        volume=float(p.get("volume", 0.0)),
                        price_open=float(p.get("price_open", 0.0)),
                        price_close=float(p.get("price_current", 0.0)),
                        profit=float(p.get("profit", 0.0)),
                        reason=reason,
                        bot_name=str(p.get("bot_name") or p.get("comment") or "cTrader"),
                        comment=str(p.get("comment", "")),
                    )
                else:
                    errors.append(err_msg)
            self._positions_cache = (time.time(), []) if not errors else None
            self._balance_cache = None
            if errors and closed == 0:
                return 0, f"[cTrader] Falha ao zerar posições: {errors[0]}"
            suffix = f" ({len(errors)} erro(s))" if errors else ""
            return closed, f"[cTrader] {closed} posição(ões) encerrada(s) ({reason}){suffix}."

        count = len(self._sim_positions)
        for p in self._sim_positions:
            pnl = float(p.get("profit", 0.0))
            self._sim_daily_pnl += pnl
            ts_str = datetime.now().strftime("%H:%M:%S")
            self._sim_deals_history.insert(
                0,
                {
                    "ticket": p["ticket"],
                    "time": ts_str,
                    "time_str": ts_str,
                    "symbol": p["symbol"],
                    "type": p["type"],
                    "side": p["type"],
                    "volume": p["volume"],
                    "price_open": p["price_open"],
                    "price_close": p["price_current"],
                    "profit": pnl,
                    "reason": reason,
                    "comment": p.get("comment", ""),
                    "bot_name": p.get("bot_name") or p.get("comment", ""),
                },
            )
        self._sim_positions.clear()
        return count, f"{count} posição(ões) zerada(s) ({reason})."

    def close_single_position(self, ticket: int | str) -> tuple[bool, str]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._client is None:
                return False, "cTrader desconectada: não é possível encerrar posição."
            self._positions_cache = None
            positions = self.get_open_positions()
            matched = next((p for p in positions if str(p.get("ticket")) == str(ticket)), None)
            try:
                ok, msg = self._client.close_position(
                    str(ticket),
                    volume_raw=matched.get("volume_raw") if matched else None,
                )
            except Exception as exc:
                self._positions_cache = None
                return False, f"[cTrader] Erro ao encerrar #{ticket}: {exc}"
            self._balance_cache = None
            if ok:
                if self._positions_cache is not None:
                    ts_c, cached_list = self._positions_cache
                    self._positions_cache = (
                        ts_c,
                        [p for p in cached_list if str(p.get("ticket")) != str(ticket)],
                    )
                self._record_live_deal(
                    ticket=str(ticket),
                    symbol=matched["symbol"] if matched else "--",
                    side=matched.get("side", matched.get("type", "BUY")) if matched else "BUY",
                    volume=float(matched.get("volume", 0.0)) if matched else 0.0,
                    price_open=float(matched.get("price_open", 0.0)) if matched else 0.0,
                    price_close=float(matched.get("price_current", 0.0)) if matched else 0.0,
                    profit=float(matched.get("profit", 0.0)) if matched else 0.0,
                    reason="FECHAMENTO_MANUAL",
                    bot_name=str(matched.get("bot_name") or matched.get("comment") or "cTrader") if matched else "cTrader",
                    comment=str(matched.get("comment", "")) if matched else "cTrader",
                )
            else:
                self._positions_cache = None
            return ok, msg

        for p in list(self._sim_positions):
            if str(p["ticket"]) == str(ticket):
                pnl = float(p.get("profit", 0.0))
                self._sim_daily_pnl += pnl
                ts_str = datetime.now().strftime("%H:%M:%S")
                self._sim_deals_history.insert(
                    0,
                    {
                        "ticket": p["ticket"],
                        "time": ts_str,
                        "time_str": ts_str,
                        "symbol": p["symbol"],
                        "type": p["type"],
                        "side": p["type"],
                        "volume": p["volume"],
                        "price_open": p["price_open"],
                        "price_close": p["price_current"],
                        "profit": pnl,
                        "reason": "FECHAMENTO_MANUAL",
                        "comment": p.get("comment", ""),
                        "bot_name": p.get("bot_name") or p.get("comment", ""),
                    },
                )
                self._sim_positions.remove(p)
                return True, f"Posição #{ticket} ({p['symbol']}) encerrada com resultado {pnl:+.2f}."
        return False, f"Posição #{ticket} não encontrada."


class PradoTradingService:
    """Background daemon that manages cTrader Accounts/OAuth, Symbols/Categories, and the Running Robot Fleet."""

    def __init__(self, cfg: PradoServerConfig, config_path: Path) -> None:
        self.cfg = cfg
        self.config_path = config_path
        self.connector = CTraderUniversalConnector(cfg)
        self.connector.connect()
        self.news_scout = NewsScout()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._latest_snapshot: dict[str, Any] = {}
        self._event_log: list[dict[str, str]] = []
        self._log_event("SYSTEM", "Motor Prado Institutional HFT (cTrader Open API) inicializado.")

    def _log_event(self, category: str, message: str) -> None:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "category": category,
            "message": message,
        }
        self._event_log.insert(0, entry)
        if len(self._event_log) > 80:
            self._event_log = self._event_log[:80]

    def reconnect_broker(self) -> tuple[bool, str]:
        with self._lock:
            self.connector.cfg = self.cfg
            ok, msg = self.connector.connect()
            self._log_event("CTRADER_CONNECT", msg)
            return ok, msg

    def start_ctrader_oauth(self, default_redirect_uri: str) -> tuple[bool, str, str]:
        with self._lock:
            cid = (self.cfg.ctrader_client_id or "").strip()
            csec = (self.cfg.ctrader_client_secret or "").strip()
            if not cid or not csec:
                return False, "", "Salve primeiro o Client ID e o Client Secret obtidos em https://openapi.ctrader.com/apps."
            ruri = (self.cfg.ctrader_redirect_uri or default_redirect_uri).strip()
            if not self.cfg.ctrader_redirect_uri and ruri:
                self.cfg.ctrader_redirect_uri = ruri
                save_config(self.cfg, self.config_path)
            auth_url = build_oauth_authorize_url(cid, ruri)
            return True, auth_url, ruri

    def complete_ctrader_oauth(
        self,
        code: str,
        redirect_uri: str,
        http_transport: Any = None,
    ) -> tuple[bool, str]:
        with self._lock:
            cid = (self.cfg.ctrader_client_id or "").strip()
            csec = (self.cfg.ctrader_client_secret or "").strip()
            ruri = (self.cfg.ctrader_redirect_uri or redirect_uri).strip()
            if not cid or not csec:
                return False, "Client ID e Client Secret cTrader não configurados."
            try:
                tok_data = exchange_oauth_code(cid, csec, code, ruri, http_transport=http_transport)
            except Exception as exc:
                self._log_event("CTRADER_OAUTH", f"Falha OAuth: {exc}")
                return False, str(exc)

            self.cfg.ctrader_access_token = tok_data["access_token"]
            self.cfg.ctrader_refresh_token = tok_data["refresh_token"]
            self.cfg.ctrader_token_expires_at = time.time() + float(tok_data.get("expires_in", 2592000))
            self.cfg.connection_mode = "CTRADER_CLOUD"

            ok, conn_msg = self.connector.connect(
                client_id=cid,
                client_secret=csec,
                access_token=self.cfg.ctrader_access_token,
                refresh_token=self.cfg.ctrader_refresh_token,
            )
            if ok and self.connector._client is not None:
                self._sync_ctrader_accounts_locked()
            save_config(self.cfg, self.config_path)
            self._log_event("CTRADER_OAUTH", f"Autorização OAuth concluída. {conn_msg}")
            return ok, conn_msg

    def save_ctrader_account(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        with self._lock:
            req_id = str(payload.get("account_id") or "").strip()
            existing = next((a for a in self.cfg.accounts if req_id and a.get("account_id") == req_id), None)
            acc_id = existing["account_id"] if existing else (req_id or f"ct_{uuid.uuid4().hex[:8]}")

            tok_in = str(payload.get("access_token", "")).strip()
            if tok_in == "********" or not tok_in:
                access_tok = str(existing.get("access_token", "")) if existing else str(self.cfg.ctrader_access_token or "")
            else:
                access_tok = tok_in

            rtok_in = str(payload.get("refresh_token", "")).strip()
            if rtok_in == "********" or not rtok_in:
                refresh_tok = str(existing.get("refresh_token", "")) if existing else str(self.cfg.ctrader_refresh_token or "")
            else:
                refresh_tok = rtok_in

            cid = str(payload.get("client_id") or (existing.get("client_id", "") if existing else "") or self.cfg.ctrader_client_id or "").strip()
            csec_in = str(payload.get("client_secret") or "").strip()
            csec = (
                str(existing.get("client_secret", "")) if existing else str(self.cfg.ctrader_client_secret or "")
            ) if (csec_in == "********" or not csec_in) else csec_in

            acc_type = str(payload.get("account_type") or (existing.get("account_type", "DEMO") if existing else "DEMO")).upper()
            if acc_type not in ("DEMO", "REAL"):
                acc_type = "DEMO"
            is_live = acc_type == "REAL"
            label = str(payload.get("label") or (existing.get("label") if existing else f"cTrader {acc_type}")).strip()
            lot_sz = max(0.01, float(payload.get("default_lot_size") or self.cfg.default_lot_size or 0.01))
            conn_mode = str(payload.get("connection_mode") or "CTRADER_CLOUD").upper()
            ctid_acc = str(payload.get("ctid_account_id") or (existing.get("ctid_account_id", "") if existing else "")).strip()

            acc_record: dict[str, Any] = {
                "account_id": acc_id,
                "ctid_account_id": ctid_acc,
                "trader_login": str(payload.get("trader_login") or (existing.get("trader_login", "---") if existing else "---")),
                "account_type": acc_type,
                "is_live": is_live,
                "broker_name": str(payload.get("broker_name") or (existing.get("broker_name", "cTrader") if existing else "cTrader")),
                "label": label,
                "client_id": cid,
                "client_secret": csec,
                "access_token": access_tok,
                "refresh_token": refresh_tok,
                "default_lot_size": lot_sz,
                "connection_mode": conn_mode,
                "created_at": existing.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if existing else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if existing:
                existing.update(acc_record)
            else:
                self.cfg.accounts.append(acc_record)

            self.cfg.accounts = deduplicate_accounts(self.cfg.accounts)
            self.cfg.active_account_id = acc_id
            self.cfg.active_account_type = acc_type
            if cid:
                self.cfg.ctrader_client_id = cid
            if csec:
                self.cfg.ctrader_client_secret = csec
            if access_tok:
                self.cfg.ctrader_access_token = access_tok
            if refresh_tok:
                self.cfg.ctrader_refresh_token = refresh_tok
            self.cfg.default_lot_size = lot_sz
            self.cfg.connection_mode = conn_mode

            ok, conn_msg = self.connector.connect(
                client_id=cid or self.cfg.ctrader_client_id,
                client_secret=csec or self.cfg.ctrader_client_secret,
                access_token=access_tok,
                refresh_token=refresh_tok,
                account_id=ctid_acc or acc_id,
                is_live=is_live,
            )
            if ok and self.connector._client_auth:
                auth = self.connector._client_auth
                acc_record["ctid_account_id"] = str(auth.get("ctid_account_id", ctid_acc))
                acc_record["trader_login"] = str(auth.get("loginid", "---"))
                acc_record["broker_name"] = str(auth.get("broker_name", "cTrader"))
                acc_record["account_type"] = "DEMO" if auth.get("is_virtual") else "REAL"
                acc_record["is_live"] = not bool(auth.get("is_virtual"))
                acc_record["balance"] = float(auth.get("balance", 0.0))
                acc_record["currency"] = str(auth.get("currency", "USD"))
                self.cfg.active_account_type = acc_record["account_type"]

            save_config(self.cfg, self.config_path)
            self._log_event("CTRADER_VAULT", f"Conta '{label}' salva. {conn_msg}")
            return acc_record, conn_msg

    def select_active_account(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            target = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            if not target:
                return None
            self.cfg.active_account_id = str(target["account_id"])
            self.cfg.active_account_type = str(target.get("account_type", "DEMO"))
            if target.get("client_id"):
                self.cfg.ctrader_client_id = str(target["client_id"])
            if target.get("client_secret"):
                self.cfg.ctrader_client_secret = str(target["client_secret"])
            if target.get("access_token"):
                self.cfg.ctrader_access_token = str(target["access_token"])
            if target.get("refresh_token"):
                self.cfg.ctrader_refresh_token = str(target["refresh_token"])
            self.cfg.default_lot_size = float(target.get("default_lot_size", 0.01))
            self.cfg.connection_mode = str(target.get("connection_mode", "CTRADER_CLOUD"))
            self.connector._balance_cache = None
            self.connector._positions_cache = None
            save_config(self.cfg, self.config_path)
            ok, msg = self.connector.connect(
                client_id=self.cfg.ctrader_client_id,
                client_secret=self.cfg.ctrader_client_secret,
                access_token=self.cfg.ctrader_access_token,
                refresh_token=self.cfg.ctrader_refresh_token,
                account_id=str(target.get("ctid_account_id") or target["account_id"]),
                is_live=bool(target.get("is_live", self.cfg.active_account_type == "REAL")),
            )
            self._log_event("ACCOUNT_SWITCH", f"Conta ativa alterada para [{self.cfg.active_account_type}] {target.get('label')} — {msg}")
            return {
                k: ("********" if k in ("access_token", "refresh_token", "client_secret") and v else v)
                for k, v in target.items()
            }

    def delete_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts = [a for a in self.cfg.accounts if a.get("account_id") != account_id]
            if self.cfg.active_account_id == account_id:
                self.cfg.active_account_id = ""
                self.cfg.ctrader_access_token = ""
                self.connector.connect(access_token="")
            save_config(self.cfg, self.config_path)
            self._log_event("CTRADER_VAULT", f"Conta '{account_id}' removida.")
            return self.cfg.accounts

    def clear_all_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts.clear()
            self.cfg.active_account_id = ""
            self.cfg.ctrader_access_token = ""
            self.connector.connect(access_token="")
            save_config(self.cfg, self.config_path)
            self._log_event("CTRADER_VAULT", "Todas as contas cTrader foram removidas.")
            return self.cfg.accounts

    def save_custom_category(self, category_name: str, symbols: list[str]) -> dict[str, list[str]]:
        with self._lock:
            clean_name = category_name.strip()
            clean_syms = [s.strip() for s in symbols if s.strip()]
            if clean_name and clean_syms:
                self.cfg.custom_categories[clean_name] = clean_syms
                for s in clean_syms:
                    if s not in self.cfg.active_symbols:
                        self.cfg.active_symbols.append(s)
                save_config(self.cfg, self.config_path)
                self._log_event("CATEGORY", f"Categoria '{clean_name}' salva com {len(clean_syms)} ativo(s).")
            return dict(self.cfg.custom_categories)

    def delete_custom_category(self, category_name: str) -> dict[str, list[str]]:
        with self._lock:
            if category_name in self.cfg.custom_categories:
                self.cfg.custom_categories.pop(category_name, None)
                save_config(self.cfg, self.config_path)
                self._log_event("CATEGORY", f"Categoria '{category_name}' apagada.")
            return dict(self.cfg.custom_categories)

    def create_bot(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            req_bot_id = str(payload.get("bot_id") or "").strip()
            existing_bot = next((b for b in self.cfg.bots if req_bot_id and b.get("bot_id") == req_bot_id), None)
            bot_id = existing_bot["bot_id"] if existing_bot else (req_bot_id or f"bot_{uuid.uuid4().hex[:8]}")

            symbol = str(payload.get("symbol", existing_bot.get("symbol", "EURUSD") if existing_bot else "EURUSD")).strip()
            account_id = str(payload.get("account_id", self.cfg.active_account_id or "default")).strip()
            acc_obj = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            account_type = str(acc_obj.get("account_type", self.cfg.active_account_type)) if acc_obj else self.cfg.active_account_type
            account_label = acc_obj["label"] if acc_obj else f"cTrader {account_type}"

            template_id = str(
                payload.get("bot_template_id")
                or payload.get("template_id")
                or (existing_bot.get("bot_template_id", "WALL_STREET_HYBRID_BOTH") if existing_bot else "WALL_STREET_HYBRID_BOTH")
            ).strip()
            tpl = next((t for t in self.get_all_templates() if t.get("template_id") == template_id), MATH_BOT_TEMPLATES[0])
            tpl_name = str(tpl.get("name") or template_id)
            tpl_formula = str(tpl.get("formula") or "")
            tpl_op_mode = str(tpl.get("operation_mode") or ("CUSTOM" if tpl.get("is_custom") else "BOTH"))
            tpl_window = tpl.get("window_ticks")
            tpl_z = tpl.get("zscore_threshold")
            tpl_imb = tpl.get("imbalance_threshold")
            tpl_rev = tpl.get("revert_sigma")
            tpl_sl = tpl.get("sl_sigma_mult")
            tpl_tp = tpl.get("tp_sigma_mult")
            auto_start = bool(payload.get("auto_start", True))

            bot_status = (
                existing_bot.get("status", "RUNNING")
                if existing_bot and "auto_start" not in payload
                else ("RUNNING" if auto_start else "STOPPED")
            )
            raw_tp_mode = payload.get("tp_mode", existing_bot.get("tp_mode", "AUTO") if existing_bot else "AUTO")
            raw_tp_val = payload.get("tp_value", existing_bot.get("tp_value", 0.0) if existing_bot else 0.0)
            norm_tp_mode, norm_tp_val = normalize_tp_config(raw_tp_mode, raw_tp_val)

            lot_val = float(payload.get("lot_size") if payload.get("lot_size") is not None else self.cfg.default_lot_size)
            lot_val = max(0.01, round(lot_val, 4))

            bot_record: dict[str, Any] = {
                "bot_id": bot_id,
                "name": str(payload.get("name") or (existing_bot.get("name") if existing_bot else f"{tpl_name.split('—')[0].strip()} ({symbol})")).strip(),
                "bot_template_id": template_id,
                "bot_template_name": tpl_name,
                "template_id": template_id,
                "template_name": tpl_name,
                "formula": tpl_formula,
                "account_id": account_id,
                "account_type": account_type,
                "account_label": account_label,
                "symbol": symbol,
                "category": str(payload.get("category") or (existing_bot.get("category") if existing_bot else "cTrader")).strip(),
                "operation_mode": str(payload.get("operation_mode") or tpl_op_mode),
                "lot_size": lot_val,
                "window_ticks": int(payload.get("window_ticks") or (tpl_window if tpl_window is not None else 120)),
                "zscore_threshold": float(payload.get("zscore_threshold") if payload.get("zscore_threshold") is not None else (tpl_z if tpl_z is not None else 1.8)),
                "imbalance_threshold": float(payload.get("imbalance_threshold") if payload.get("imbalance_threshold") is not None else (tpl_imb if tpl_imb is not None else 0.35)),
                "revert_sigma": float(payload.get("revert_sigma") if payload.get("revert_sigma") is not None else (tpl_rev if tpl_rev is not None else 2.0)),
                "sl_sigma_mult": float(payload.get("sl_sigma_mult") or (tpl_sl if tpl_sl is not None else 1.0)),
                "tp_sigma_mult": float(payload.get("tp_sigma_mult") or (tpl_tp if tpl_tp is not None else 1.8)),
                "tp_mode": norm_tp_mode,
                "tp_value": norm_tp_val,
                "grid_direction": str(payload.get("grid_direction") or (existing_bot.get("grid_direction") if existing_bot else tpl.get("grid_direction", "BUY_ONLY"))).upper(),
                "grid_step_points": max(0.00001, float(payload.get("grid_step_points") or (existing_bot.get("grid_step_points") if existing_bot else tpl.get("grid_step_points", 0.0020)))),
                "grid_tp_points": max(0.00001, float(payload.get("grid_tp_points") or (existing_bot.get("grid_tp_points") if existing_bot else tpl.get("grid_tp_points", 0.0020)))),
                "max_grid_levels": max(1, min(20, int(payload.get("max_grid_levels") or (existing_bot.get("max_grid_levels") if existing_bot else tpl.get("max_grid_levels", 5))))),
                "grid_anchor_price": float(existing_bot.get("grid_anchor_price", 0.0)) if existing_bot else 0.0,
                "loss_guard_enabled": bool(payload["loss_guard_enabled"]) if "loss_guard_enabled" in payload else bool(existing_bot.get("loss_guard_enabled", False) if existing_bot else False),
                "max_loss_usd": max(0.5, float(payload.get("max_loss_usd") or (existing_bot.get("max_loss_usd") if existing_bot else 20.0))),
                "news_assisted": bool(payload["news_assisted"]) if "news_assisted" in payload else bool(existing_bot.get("news_assisted", False) if existing_bot else False),
                "timeframe": (
                    str(payload["timeframe"]).strip().upper()
                    if str(payload.get("timeframe") or "").strip().upper() in self.connector.TIMEFRAME_GRANULARITIES
                    else str(existing_bot.get("timeframe", "TICKS") if existing_bot else "TICKS").upper()
                ),
                "realized_pnl": float(existing_bot.get("realized_pnl", 0.0)) if existing_bot else 0.0,
                "floating_pnl": float(existing_bot.get("floating_pnl", 0.0)) if existing_bot else 0.0,
                "total_pnl": float(existing_bot.get("total_pnl", 0.0)) if existing_bot else 0.0,
                "correlated_basket": list(payload.get("correlated_basket") or self.cfg.correlated_basket),
                "status": bot_status,
                "active": bot_status == "RUNNING",
                "last_error": "",
                "last_signal": existing_bot.get("last_signal", "WAIT") if existing_bot else "WAIT",
                "last_regime": existing_bot.get("last_regime", "NEUTRAL") if existing_bot else "NEUTRAL",
                "last_price": existing_bot.get("last_price", 0.0) if existing_bot else 0.0,
                "vwap": existing_bot.get("vwap", 0.0) if existing_bot else 0.0,
                "aggression_zscore": existing_bot.get("aggression_zscore", 0.0) if existing_bot else 0.0,
                "imbalance_ratio": existing_bot.get("imbalance_ratio", 0.0) if existing_bot else 0.0,
                "trades_executed": existing_bot.get("trades_executed", 0) if existing_bot else 0,
                "created_at": existing_bot.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if existing_bot else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if existing_bot:
                existing_bot.update(bot_record)
            else:
                self.cfg.bots.append(bot_record)

            if symbol not in self.cfg.active_symbols:
                self.cfg.active_symbols.append(symbol)
            save_config(self.cfg, self.config_path)
            self._log_event("BOT_FLEET", f"Robô '{bot_record['name']}' ({symbol} | {bot_record['lot_size']} lote) salvo.")
            return bot_record

    def control_bot(self, bot_id: str, action: str) -> dict[str, Any] | None:
        with self._lock:
            act = action.upper()
            for idx, b in enumerate(self.cfg.bots):
                if b.get("bot_id") == bot_id:
                    if act == "START":
                        b["status"] = "RUNNING"
                        b["active"] = True
                        b["last_error"] = ""
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) iniciado.")
                    elif act == "PAUSE":
                        b["status"] = "PAUSED"
                        b["active"] = False
                        b["last_signal"] = "PAUSED_MANUAL"
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) pausado (posições existentes mantidas).")
                    elif act == "RESUME":
                        b["status"] = "RUNNING"
                        b["active"] = True
                        b["last_error"] = ""
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) retomado.")
                    elif act == "STOP":
                        b["status"] = "STOPPED"
                        b["active"] = False
                        b["last_signal"] = "STOPPED_MANUAL"
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) parado com segurança.")
                    elif act in ("FIRE_BUY", "FIRE_SELL"):
                        acc_now = self.connector.get_account_summary()
                        cur_pnl = float(acc_now.get("profit", 0.0)) + float(acc_now.get("daily_realized", 0.0))
                        is_locked = (
                            self.cfg.max_daily_loss_money > 0
                            and cur_pnl <= -abs(self.cfg.max_daily_loss_money)
                        )
                        if is_locked:
                            b["last_signal"] = "RISK_LOCKED"
                            self._log_event("RISK_GUARD", f"Ordem manual bloqueada em '{b.get('name')}': trava de perda diária atingida ({cur_pnl:.2f}).")
                            return b
                        sym = str(b.get("symbol", "EURUSD"))
                        ticks = self.connector.fetch_ticks(sym, count=120)
                        vwap_b = compute_intraday_vwap(ticks)
                        last_p = ticks[-1].effective_price() if ticks else get_symbol_spec(sym)["base"]
                        bw = max(vwap_b.std_dev, abs(last_p) * 0.0020, 1e-4)
                        ord_act = "BUY_FLOW" if act == "FIRE_BUY" else "SELL_FLOW"
                        ok, msg = self.connector.place_order(
                            symbol=sym,
                            action=ord_act,
                            lot_size=float(b.get("lot_size", self.cfg.default_lot_size)),
                            price=last_p,
                            sl_points=round(bw * float(b.get("sl_sigma_mult", 1.0)), 6),
                            tp_points=round(bw * float(b.get("tp_sigma_mult", 1.8)), 6),
                            bot_name=str(b.get("name", "PradoBot")),
                            tp_mode=str(b.get("tp_mode", "AUTO")),
                            tp_value=float(b.get("tp_value", 0.0) or 0.0),
                        )
                        if ok:
                            b["trades_executed"] = int(b.get("trades_executed", 0)) + 1
                        self._log_event("BOT_EXEC", msg)
                    elif act == "DELETE":
                        removed = self.cfg.bots.pop(idx)
                        save_config(self.cfg, self.config_path)
                        if self._latest_snapshot is not None:
                            self._latest_snapshot["bots"] = list(self.cfg.bots)
                        self._log_event("BOT_FLEET", f"Robô '{removed['name']}' apagado.")
                        return removed
                    save_config(self.cfg, self.config_path)
                    if self._latest_snapshot is not None:
                        self._latest_snapshot["bots"] = list(self.cfg.bots)
                    return b
            return None

    def delete_all_bots(self) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.bots.clear()
            save_config(self.cfg, self.config_path)
            if self._latest_snapshot is not None:
                self._latest_snapshot["bots"] = []
            self._log_event("BOT_FLEET", "Frota de robôs limpa.")
            return self.cfg.bots

    def _sync_ctrader_accounts_locked(self) -> tuple[bool, str]:
        if self.connector._client is None:
            return False, "Conecte Client ID, Client Secret e autorize via OAuth primeiro em Configuração cTrader."
        try:
            remote_accounts = self.connector._client.list_accounts()
        except Exception as exc:
            return False, f"Erro ao sincronizar contas da cTrader: {exc}"
        if not remote_accounts:
            return False, "Nenhuma conta cTrader retornada para este Access Token."

        synced_count = 0
        for acc in remote_accounts:
            ctid = str(acc.get("ctid_account_id") or "").strip()
            acc_id = str(acc.get("account_id") or (f"ct_{ctid}" if ctid else "")).strip()
            if not acc_id:
                continue
            acc_type = str(acc.get("account_type", "DEMO")).upper()
            is_live = bool(acc.get("is_live", acc_type == "REAL"))
            existing = next(
                (
                    a for a in self.cfg.accounts
                    if a.get("account_id") == acc_id or (ctid and str(a.get("ctid_account_id", "")) == ctid)
                ),
                None,
            )
            if existing is not None:
                existing["account_type"] = acc_type
                existing["is_live"] = is_live
                existing["ctid_account_id"] = ctid
                existing["trader_login"] = str(acc.get("trader_login", existing.get("trader_login", ctid)))
                existing["broker_name"] = str(acc.get("broker_name", existing.get("broker_name", "cTrader")))
                existing["client_id"] = self.cfg.ctrader_client_id
                existing["client_secret"] = self.cfg.ctrader_client_secret
                existing["access_token"] = self.cfg.ctrader_access_token
                existing["refresh_token"] = self.cfg.ctrader_refresh_token
            else:
                self.cfg.accounts.append(
                    {
                        "account_id": acc_id,
                        "ctid_account_id": ctid,
                        "trader_login": str(acc.get("trader_login", ctid)),
                        "account_type": acc_type,
                        "is_live": is_live,
                        "broker_name": str(acc.get("broker_name", "cTrader")),
                        "label": str(acc.get("label") or f"cTrader {acc_type} ({ctid})"),
                        "client_id": self.cfg.ctrader_client_id,
                        "client_secret": self.cfg.ctrader_client_secret,
                        "access_token": self.cfg.ctrader_access_token,
                        "refresh_token": self.cfg.ctrader_refresh_token,
                        "default_lot_size": self.cfg.default_lot_size,
                        "connection_mode": "CTRADER_CLOUD",
                        "balance": float(acc.get("balance", 0.0)),
                        "currency": str(acc.get("currency", "USD")),
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            synced_count += 1

        self.cfg.accounts = deduplicate_accounts(self.cfg.accounts)
        if not any(a.get("account_id") == self.cfg.active_account_id for a in self.cfg.accounts) and self.cfg.accounts:
            demo = next((a for a in self.cfg.accounts if a.get("account_type") == "DEMO"), self.cfg.accounts[0])
            self.cfg.active_account_id = demo["account_id"]
            self.cfg.active_account_type = demo["account_type"]
        return True, f"{synced_count} conta(s) cTrader sincronizada(s) com sucesso."

    def sync_ctrader_accounts(self) -> tuple[bool, str, list[dict[str, Any]]]:
        with self._lock:
            if not self.cfg.ctrader_access_token:
                msg = "Nenhum Access Token cTrader salvo em Configuração cTrader."
                self._log_event("CTRADER_VAULT", msg)
                return False, msg, list(self.cfg.accounts)
            if self.connector._client is None:
                ok_conn, msg_conn = self.connector.connect()
                if not ok_conn and self.connector._client is None:
                    self._log_event("CTRADER_VAULT", msg_conn)
                    return False, msg_conn, list(self.cfg.accounts)
            ok, msg = self._sync_ctrader_accounts_locked()
            if ok:
                save_config(self.cfg, self.config_path)
            self._log_event("CTRADER_VAULT", msg)
            return ok, msg, list(self.cfg.accounts)

    _ALLOWED_CONFIG_UPDATE_FIELDS = frozenset({
        "admin_password_hash",
        "ctrader_client_id",
        "ctrader_client_secret",
        "ctrader_redirect_uri",
        "ctrader_access_token",
        "ctrader_refresh_token",
        "ctrader_token_expires_at",
        "connection_mode",
        "active_account_id",
        "active_account_type",
        "default_lot_size",
        "symbol_selection_mode",
        "custom_categories",
        "auto_trading_enabled",
        "allow_real_trading",
        "operation_mode",
        "active_symbols",
        "correlated_basket",
        "window_ticks",
        "zscore_threshold",
        "imbalance_threshold",
        "revert_sigma",
        "correlation_block_threshold",
        "poll_interval_sec",
        "sl_sigma_mult",
        "tp_sigma_mult",
        "max_daily_loss_money",
        "daily_target_money",
        "max_lot_per_trade",
        "max_concurrent_trades",
        "max_total_lots",
        "min_order_interval_sec",
        "news_bot_enabled",
        "news_pause_grid_on_high_impact",
        "news_auto_trade_enabled",
        "news_lot_size",
        "news_poll_interval_sec",
    })

    def update_config(self, updates: dict[str, Any]) -> PradoServerConfig:
        with self._lock:
            for key, val in updates.items():
                if key in self._ALLOWED_CONFIG_UPDATE_FIELDS and hasattr(self.cfg, key):
                    setattr(self.cfg, key, val)
            if any(
                k in updates
                for k in (
                    "ctrader_client_id",
                    "ctrader_client_secret",
                    "ctrader_access_token",
                    "ctrader_refresh_token",
                    "connection_mode",
                )
            ):
                ok, msg = self.connector.connect()
                self._log_event("CTRADER_CONFIG", msg)
                if ok and self.connector._client is not None:
                    s_ok, s_msg = self._sync_ctrader_accounts_locked()
                    if s_ok:
                        self._log_event("CTRADER_VAULT", s_msg)
            save_config(self.cfg, self.config_path)
            self._log_event("CONFIG", "Configurações operacionais atualizadas.")
            return self.cfg

    def flatten_all(self, reason: str = "ZERAR_TUDO_WEB") -> tuple[int, str]:
        with self._lock:
            count, msg = self.connector.close_all_positions(reason)
            self._log_event("RISK_GUARD", msg)
            return count, msg

    def close_position(self, ticket: int | str) -> tuple[bool, str]:
        with self._lock:
            ok, msg = self.connector.close_single_position(ticket)
            self._log_event("POSITION_CLOSE", msg)
            return ok, msg

    def reset_daily_risk_lock(self) -> dict[str, Any]:
        with self._lock:
            self.connector._sim_daily_pnl = 0.0
            self.connector._sim_positions.clear()
            if self.cfg.max_daily_loss_money < 2000.0:
                self.cfg.max_daily_loss_money = 5000.0
                save_config(self.cfg, self.config_path)
            self._log_event("RISK_GUARD", "Limite diário destravado.")
            return {"ok": True, "max_daily_loss_money": self.cfg.max_daily_loss_money}

    def get_all_templates(self) -> list[dict[str, Any]]:
        native = [{**t, "is_custom": False} for t in MATH_BOT_TEMPLATES]
        custom = [{**t, "is_custom": True} for t in self.cfg.custom_templates]
        return native + custom

    def save_custom_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            tid = str(payload.get("template_id") or "").strip() or f"CUSTOM_{uuid.uuid4().hex[:8].upper()}"
            if any(t["template_id"] == tid for t in MATH_BOT_TEMPLATES):
                raise ValueError("Não é permitido sobrescrever modelos nativos.")
            mode = str(payload.get("custom_mode") or "INDICATORS").strip().upper()
            if mode not in ("INDICATORS", "PYTHON"):
                mode = "INDICATORS"
            name = str(payload.get("name") or "Modelo Customizado").strip()
            indicators_cfg = list(payload.get("indicators") or [])
            combine_mode = str(payload.get("combine_mode") or "MAJORITY").strip().upper()
            python_code = str(payload.get("python_code") or DEFAULT_PYTHON_STRATEGY_TEMPLATE)
            if mode == "INDICATORS":
                ind_names = ", ".join(str(i.get("id", "")) for i in indicators_cfg) or "Sem indicadores"
                formula = f"Indicadores ({combine_mode}): {ind_names}"
            else:
                formula = "Python Customizado: def evaluate(prices, ticks, params)"

            rec: dict[str, Any] = {
                "template_id": tid,
                "name": name,
                "operation_mode": "CUSTOM",
                "custom_mode": mode,
                "is_custom": True,
                "formula": formula,
                "description": str(payload.get("description") or "Modelo matemático criado pelo usuário.").strip(),
                "window_ticks": max(20, int(payload.get("window_ticks") or 120)),
                "zscore_threshold": float(payload.get("zscore_threshold") or 1.8),
                "imbalance_threshold": float(payload.get("imbalance_threshold") or 0.35),
                "revert_sigma": float(payload.get("revert_sigma") or 2.0),
                "sl_sigma_mult": float(payload.get("sl_sigma_mult") or 1.0),
                "tp_sigma_mult": float(payload.get("tp_sigma_mult") or 1.8),
                "indicators": indicators_cfg,
                "combine_mode": combine_mode,
                "python_code": python_code,
            }
            existing = next((t for t in self.cfg.custom_templates if t.get("template_id") == tid), None)
            if existing is not None:
                existing.update(rec)
            else:
                self.cfg.custom_templates.append(rec)
            save_config(self.cfg, self.config_path)
            self._log_event("TEMPLATE", f"Modelo matemático '{name}' ({mode}) salvo.")
            return rec

    def delete_custom_template(self, template_id: str) -> bool:
        with self._lock:
            if any(t["template_id"] == template_id for t in MATH_BOT_TEMPLATES):
                raise ValueError("Modelos nativos não podem ser excluídos.")
            before = len(self.cfg.custom_templates)
            self.cfg.custom_templates = [t for t in self.cfg.custom_templates if t.get("template_id") != template_id]
            removed = len(self.cfg.custom_templates) < before
            if removed:
                save_config(self.cfg, self.config_path)
                self._log_event("TEMPLATE", f"Modelo customizado '{template_id}' removido.")
            return removed

    def test_custom_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or "EURUSD").strip()
        timeframe = str(payload.get("timeframe") or "TICKS").strip().upper()
        gran = self.connector.TIMEFRAME_GRANULARITIES.get(timeframe, 0)
        ticks = self.connector.fetch_ticks(symbol, count=200, granularity=gran)
        if not ticks:
            ticks = self.connector._generate_sim_ticks(symbol)
        prices = [float(t.effective_price()) for t in ticks]
        mode = str(payload.get("custom_mode") or "INDICATORS").strip().upper()
        if mode == "PYTHON":
            res = evaluate_python_model(
                str(payload.get("python_code") or ""),
                prices=prices,
                ticks=ticks,
                params=dict(payload.get("params") or {}),
            )
            res["symbol"] = symbol
            res["ticks_count"] = len(ticks)
            return res
        ind_res = evaluate_indicator_model(
            ticks,
            list(payload.get("indicators") or []),
            combine_mode=str(payload.get("combine_mode") or "MAJORITY"),
        )
        return {
            "ok": True,
            "symbol": symbol,
            "ticks_count": len(ticks),
            "signal": ind_res["signal"],
            "buy_votes": ind_res["buy_votes"],
            "sell_votes": ind_res["sell_votes"],
            "details": ind_res["details"],
            "elapsed_ms": 0.0,
            "stdout": "",
            "error": "",
        }

    def _evaluate_custom_template(
        self,
        tpl: dict[str, Any],
        ticks: list[TickRecord],
        params: dict[str, Any] | None = None,
    ) -> str:
        mode = str(tpl.get("custom_mode") or "").strip().upper()
        if mode == "PYTHON":
            prices = [float(t.effective_price()) for t in ticks]
            res = evaluate_python_model(str(tpl.get("python_code") or ""), prices, ticks, params or {})
            if not res["ok"]:
                return "WAIT"
            sig = res["signal"]
            return "BUY_FLOW" if sig == "BUY" else ("SELL_FLOW" if sig == "SELL" else "WAIT")
        if mode == "INDICATORS":
            res = evaluate_indicator_model(
                ticks,
                list(tpl.get("indicators") or []),
                combine_mode=str(tpl.get("combine_mode") or "MAJORITY"),
            )
            sig = res["signal"]
            return "BUY_FLOW" if sig == "BUY" else ("SELL_FLOW" if sig == "SELL" else "WAIT")
        return ""

    def get_chart_series(self, symbol: str, timeframe: str = "TICKS") -> list[dict[str, Any]]:
        gran = self.connector.TIMEFRAME_GRANULARITIES.get(str(timeframe or "TICKS").strip().upper(), 0)
        ticks = self.connector.fetch_ticks(symbol, count=180, granularity=gran)
        if not ticks:
            return []
        points: list[dict[str, Any]] = []
        pv_sum = 0.0
        v_sum = 0.0
        prices: list[float] = []
        last_t = 0
        for tk in ticks:
            p = float(tk.effective_price())
            vol = float(tk.tick_volume or 1.0)
            pv_sum += p * vol
            v_sum += vol
            vwap = pv_sum / max(v_sum, 1e-9)
            prices.append(p)
            mean_p = sum(prices) / len(prices)
            var = sum((x - mean_p) ** 2 for x in prices) / max(len(prices), 1)
            std = math.sqrt(var)
            t = int(tk.time_msc // 1000)
            if t <= last_t:
                t = last_t + 1
            last_t = t
            points.append(
                {
                    "time": t,
                    "price": round(p, 6),
                    "vwap": round(vwap, 6),
                    "upper_2": round(vwap + 2.0 * std, 6),
                    "lower_2": round(vwap - 2.0 * std, 6),
                }
            )
        return points

    def _run_single_backtest_locked(self, symbol: str, params: dict[str, Any]) -> dict[str, Any]:
        template_id = str(params.get("bot_template_id") or params.get("template_id") or "WALL_STREET_HYBRID_BOTH").strip()
        tpl = next((t for t in self.get_all_templates() if t.get("template_id") == template_id), MATH_BOT_TEMPLATES[0])
        tpl_window = tpl.get("window_ticks")
        tpl_z = tpl.get("zscore_threshold")
        tpl_imb = tpl.get("imbalance_threshold")
        tpl_rev = tpl.get("revert_sigma")
        tpl_sl = tpl.get("sl_sigma_mult")
        tpl_tp = tpl.get("tp_sigma_mult")

        timeframe = str(params.get("timeframe") or "TICKS").strip().upper()
        period = str(params.get("period") or "CUSTOM").strip().upper()
        tick_count = max(120, min(5000, int(params.get("tick_count") or 800)))
        initial_capital = float(params.get("initial_capital") or 10000.0)
        lot_size = max(0.01, float(params.get("lot_size") or self.cfg.default_lot_size or 0.01))
        window_ticks = int(params.get("window_ticks") or (tpl_window if tpl_window is not None else 120))
        z_thresh = float(params.get("zscore_threshold") if params.get("zscore_threshold") is not None else (tpl_z if tpl_z is not None else 1.8))
        imb_thresh = float(params.get("imbalance_threshold") if params.get("imbalance_threshold") is not None else (tpl_imb if tpl_imb is not None else 0.35))
        rev_sigma = float(params.get("revert_sigma") if params.get("revert_sigma") is not None else (tpl_rev if tpl_rev is not None else 2.0))
        sl_mult = float(params.get("sl_sigma_mult") or (tpl_sl if tpl_sl is not None else 1.0))
        tp_mult = float(params.get("tp_sigma_mult") or (tpl_tp if tpl_tp is not None else 1.8))
        op_mode = str(params.get("operation_mode") or tpl.get("operation_mode") or ("CUSTOM" if tpl.get("is_custom") else "BOTH"))

        ticks, data_source = self.connector.fetch_backtest_history(symbol, tick_count, timeframe=timeframe, period=period)
        if not ticks:
            sim_count = tick_count if period == "CUSTOM" else 1200
            ticks = self._build_backtest_tick_series(symbol, sim_count)
        balance = initial_capital
        peak_balance = initial_capital
        max_drawdown = 0.0
        trades: list[dict[str, Any]] = []
        open_pos: dict[str, Any] | None = None
        grid_anchor = 0.0

        step_stride = max(1, len(ticks) // 250)
        for idx in range(40, len(ticks), step_stride):
            sub_ticks = ticks[: idx + 1]
            curr_price = sub_ticks[-1].effective_price()

            if open_pos is not None:
                is_buy = open_pos["type"] == "BUY"
                hit_tp = (curr_price >= open_pos["tp"]) if is_buy else (curr_price <= open_pos["tp"])
                hit_sl = (curr_price <= open_pos["sl"]) if is_buy else (curr_price >= open_pos["sl"])
                if hit_tp or hit_sl or idx >= len(ticks) - step_stride:
                    pnl = estimate_cfd_pnl(symbol, is_buy, open_pos["entry"], curr_price, lot_size)
                    balance = round(balance + pnl, 2)
                    peak_balance = max(peak_balance, balance)
                    max_drawdown = max(max_drawdown, round(peak_balance - balance, 2))
                    trades.append(
                        {
                            "id": len(trades) + 1,
                            "type": open_pos["type"],
                            "signal": open_pos["signal"],
                            "entry": round(open_pos["entry"], 6),
                            "exit": round(curr_price, 6),
                            "pnl": pnl,
                            "result": "WIN" if pnl >= 0 else "LOSS",
                            "equity_after": balance,
                        }
                    )
                    open_pos = None

            if open_pos is None and idx < len(ticks) - step_stride * 2:
                vwap_b = compute_intraday_vwap(sub_ticks)
                flow = compute_flow_metrics(
                    sub_ticks,
                    vwap_b,
                    window_size=min(window_ticks, len(sub_ticks)),
                    z_threshold=z_thresh,
                    imbalance_threshold=imb_thresh,
                    revert_sigma=rev_sigma,
                    sl_sigma_mult=sl_mult,
                    tp_sigma_mult=tp_mult,
                    operation_mode=op_mode,
                )
                act = flow.recommended_action
                if tpl.get("is_custom"):
                    custom_act = self._evaluate_custom_template(tpl, sub_ticks, params)
                    if custom_act:
                        act = custom_act
                elif op_mode == "GRID_LINEAR" or template_id == "GRID_LINEAR_HFT":
                    step_pts = max(float(params.get("grid_step_points") or tpl.get("grid_step_points") or 0.0020), curr_price * 0.0005)
                    grid_dir = str(params.get("grid_direction") or tpl.get("grid_direction") or "BUY_ONLY").upper()
                    if grid_anchor <= 0.0:
                        grid_anchor = curr_price
                        act = "SELL_FLOW" if grid_dir == "SELL_ONLY" else "BUY_FLOW"
                    elif abs(curr_price - grid_anchor) >= step_pts:
                        prev_anchor = grid_anchor
                        grid_anchor = curr_price
                        if grid_dir == "SELL_ONLY":
                            act = "SELL_FLOW"
                        elif grid_dir == "BOTH":
                            act = "SELL_FLOW" if curr_price > prev_anchor else "BUY_FLOW"
                        else:
                            act = "BUY_FLOW"
                if act in ("BUY_FLOW", "SELL_FLOW", "BUY_REVERT_VWAP", "SELL_REVERT_VWAP"):
                    is_b = act.startswith("BUY")
                    sl_pts = max(flow.sl_points, curr_price * 0.0005)
                    tp_pts = max(flow.tp_points, curr_price * 0.0009)
                    open_pos = {
                        "type": "BUY" if is_b else "SELL",
                        "signal": act,
                        "entry": curr_price,
                        "sl": (curr_price - sl_pts) if is_b else (curr_price + sl_pts),
                        "tp": (curr_price + tp_pts) if is_b else (curr_price - tp_pts),
                    }

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        gross_profit = round(sum(t["pnl"] for t in wins), 2)
        gross_loss = round(abs(sum(t["pnl"] for t in losses)), 2)
        net_profit = round(balance - initial_capital, 2)
        win_rate = round((len(wins) / len(trades)) * 100.0, 2) if trades else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.9 if gross_profit > 0 else 1.0)

        report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_source": data_source,
            "bot_template_id": template_id,
            "bot_template_name": str(tpl.get("name") or template_id),
            "template_name": str(tpl.get("name") or template_id),
            "formula": str(tpl.get("formula") or ""),
            "operation_mode": op_mode,
            "ticks_processed": len(ticks),
            "initial_capital": round(initial_capital, 2),
            "final_equity": round(balance, 2),
            "final_capital": round(balance, 2),
            "net_profit": net_profit,
            "return_pct": round((net_profit / initial_capital) * 100.0, 2) if initial_capital > 0 else 0.0,
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": win_rate,
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "max_drawdown": round(max_drawdown, 2),
            "trades": trades[-30:],
            "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.cfg.backtest_history.insert(0, {k: v for k, v in report.items() if k != "trades"})
        self.cfg.backtest_history = self.cfg.backtest_history[:15]
        return report

    def run_mathematical_backtest(self, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            raw_symbol = str(params.get("symbol") or "EURUSD").strip()
            if raw_symbol.upper() == "ALL":
                targets: list[str] = []
                for s in list(self.cfg.active_symbols) + [str(b.get("symbol") or "") for b in self.cfg.bots]:
                    if s and s not in targets:
                        targets.append(s)
                if not targets:
                    targets = ["EURUSD"]
                reports = [self._run_single_backtest_locked(sym, params) for sym in targets]
                save_config(self.cfg, self.config_path)
                total_trades = sum(r["total_trades"] for r in reports)
                total_wins = sum(r["winning_trades"] for r in reports)
                total_losses = sum(r["losing_trades"] for r in reports)
                net_profit = round(sum(r["net_profit"] for r in reports), 2)
                initial_cap = float(reports[0]["initial_capital"]) if reports else 10000.0
                max_dd = round(max((r["max_drawdown"] for r in reports), default=0.0), 2)
                win_rate = round((total_wins / total_trades) * 100.0, 2) if total_trades else 0.0
                sources = {r["data_source"] for r in reports}
                summary = {
                    "symbol": f"TODOS ({len(reports)})",
                    "timeframe": reports[0]["timeframe"] if reports else "TICKS",
                    "data_source": "CTRADER_REAL" if sources == {"CTRADER_REAL"} else ("SIMULATION" if "CTRADER_REAL" not in sources else "MISTO"),
                    "bot_template_id": reports[0]["bot_template_id"],
                    "bot_template_name": reports[0]["bot_template_name"],
                    "template_name": reports[0]["template_name"],
                    "formula": reports[0]["formula"],
                    "operation_mode": reports[0]["operation_mode"],
                    "ticks_processed": sum(r["ticks_processed"] for r in reports),
                    "initial_capital": initial_cap,
                    "final_equity": round(initial_cap + net_profit, 2),
                    "final_capital": round(initial_cap + net_profit, 2),
                    "net_profit": net_profit,
                    "return_pct": round((net_profit / initial_cap) * 100.0, 2) if initial_cap > 0 else 0.0,
                    "total_trades": total_trades,
                    "winning_trades": total_wins,
                    "losing_trades": total_losses,
                    "win_rate_pct": win_rate,
                    "win_rate": win_rate,
                    "gross_profit": round(sum(r["gross_profit"] for r in reports), 2),
                    "gross_loss": round(sum(r["gross_loss"] for r in reports), 2),
                    "profit_factor": 1.0,
                    "max_drawdown": max_dd,
                    "trades": [],
                    "per_symbol": [{k: v for k, v in r.items() if k != "trades"} for r in reports],
                    "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self._log_event("BACKTEST", f"Backtest em TODOS ({len(reports)} ativos): {total_trades} trades | Lucro: {net_profit:+.2f}")
                return summary

            report = self._run_single_backtest_locked(raw_symbol, params)
            save_config(self.cfg, self.config_path)
            self._log_event("BACKTEST", f"Backtest em {raw_symbol} ({report['timeframe']}/{report['data_source']}): {report['total_trades']} trades | Lucro: {report['net_profit']:+.2f} | WinRate: {report['win_rate']}%")
            return report

    def _build_backtest_tick_series(self, symbol: str, count: int) -> list[TickRecord]:
        base_price = get_symbol_spec(symbol)["base"]
        step = base_price * 0.0005
        rng = random.Random(42 + (hash(symbol) & 0xFFFF))
        out: list[TickRecord] = []
        p = base_price
        now_msc = int(time.time() * 1000)
        for i in range(count):
            phase = i % 180
            if phase < 75:
                delta = step * 0.95 + rng.uniform(-step * 0.15, step * 0.45)
                flag = TICK_FLAG_BUY
                vol = rng.randint(80, 240)
            elif phase < 150:
                delta = -step * 0.85 + rng.uniform(-step * 0.45, step * 0.15)
                flag = TICK_FLAG_SELL
                vol = rng.randint(70, 220)
            else:
                delta = math.sin(i / 4.0) * step * 0.5
                flag = TICK_FLAG_BUY if delta >= 0 else TICK_FLAG_SELL
                vol = rng.randint(15, 65)
            p = max(step, p + delta)
            out.append(TickRecord(now_msc - (count - i) * 1000, p, p, p, 0.0, float(vol), flag))
        return out

    @staticmethod
    def _estimate_tick_step(symbol: str, ticks: list[TickRecord]) -> float:
        spec = get_symbol_spec(symbol)
        if len(ticks) < 2:
            return spec["pip_size"]
        prices = [float(t.effective_price()) for t in ticks[-40:]]
        deltas = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        non_zero = [d for d in deltas if d > 1e-9]
        return min(non_zero) if non_zero else spec["pip_size"]

    def _check_bot_tick_take_profit(
        self,
        bot: dict[str, Any],
        ticks: list[TickRecord],
        positions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Close open positions for a bot in TICKS/PIPS mode when price moves >= target distance in profit."""
        norm_mode, norm_val = normalize_tp_config(bot.get("tp_mode", "AUTO"), bot.get("tp_value", 0.0))
        if norm_mode not in ("TICKS", "PIPS") or norm_val <= 0.0 or not ticks:
            return positions
        bsym = str(bot.get("symbol", "EURUSD"))
        unit = get_symbol_spec(bsym)["pip_size"] if norm_mode == "PIPS" else self._estimate_tick_step(bsym, ticks)
        if unit <= 0.0:
            return positions

        last_price = float(ticks[-1].effective_price())
        target_dist = norm_val * unit
        bname = str(bot.get("name", ""))
        bprefix = bname[:14]

        closed_any = False
        for p in list(positions):
            if p.get("symbol") != bsym:
                continue
            belongs = (
                (bname and str(p.get("bot_name", "")) == bname)
                or (bprefix and str(p.get("comment", "")).startswith(bprefix))
                or (not p.get("bot_name") and not p.get("comment"))
            )
            if not belongs:
                continue
            entry = float(p.get("price_open", 0.0) or 0.0)
            profit = float(p.get("profit", 0.0) or 0.0)
            if entry <= 0.0 or profit <= 0.0:
                continue
            ptype = str(p.get("type", "")).upper()
            hit_tp = (ptype == "BUY" and last_price >= entry + target_dist - 1e-9) or (
                ptype == "SELL" and last_price <= entry - target_dist + 1e-9
            )
            if hit_tp:
                ok_c, msg_c = self.connector.close_single_position(p["ticket"])
                if ok_c:
                    closed_any = True
                    bot["last_signal"] = "TICK_SCALP_TP"
                    self._log_event("BOT_TICK_TP", f"[{bname}] {msg_c}")
        if closed_any:
            return self.connector.get_open_positions()
        return positions

    def _evaluate_grid_bot(
        self,
        bot: dict[str, Any],
        last_price: float,
        positions: list[dict[str, Any]],
        risk_locked: bool,
    ) -> list[dict[str, Any]]:
        bsym = str(bot.get("symbol", "EURUSD"))
        grid_dir = str(bot.get("grid_direction", "BUY_ONLY")).upper()
        if grid_dir not in ("BUY_ONLY", "SELL_ONLY", "BOTH"):
            grid_dir = "BUY_ONLY"
        grid_step = max(0.00001, float(bot.get("grid_step_points", 0.0020) or 0.0020))
        grid_tp = max(0.00001, float(bot.get("grid_tp_points", 0.0020) or 0.0020))
        max_levels = max(1, min(20, int(bot.get("max_grid_levels", 5) or 5)))
        bot_name = str(bot.get("name", "PradoBot"))

        bot_positions = [
            p for p in positions
            if p.get("symbol") == bsym
            and (not p.get("comment") or str(p.get("comment", "")).startswith(bot_name[:14]))
        ]

        closed_any = False
        if bot.get("status") == "RUNNING" and self.cfg.auto_trading_enabled and not risk_locked:
            for p in list(bot_positions):
                entry = float(p.get("price_open", 0.0) or 0.0)
                if entry <= 0:
                    continue
                ptype = str(p.get("type", "")).upper()
                hit_tp = (ptype == "BUY" and last_price >= entry + grid_tp) or (
                    ptype == "SELL" and last_price <= entry - grid_tp
                )
                if hit_tp:
                    ok_c, msg_c = self.connector.close_single_position(p["ticket"])
                    if ok_c:
                        closed_any = True
                        self._log_event("GRID_TP", f"[{bot_name}] {msg_c}")
            if closed_any:
                positions = self.connector.get_open_positions()
                bot_positions = [
                    p for p in positions
                    if p.get("symbol") == bsym
                    and (not p.get("comment") or str(p.get("comment", "")).startswith(bot_name[:14]))
                ]

        bot["last_regime"] = f"GRID_{grid_dir} ({len(bot_positions)}/{max_levels})"
        signal = "GRID_WAIT" if (bot.get("status") == "RUNNING" and self.cfg.auto_trading_enabled) else "PAUSED"

        if (
            bot.get("status") == "RUNNING"
            and self.cfg.auto_trading_enabled
            and not risk_locked
            and len(bot_positions) < max_levels
            and last_price > 0
        ):
            anchor = float(bot.get("grid_anchor_price", 0.0) or 0.0)
            if anchor <= 0.0:
                bot["grid_anchor_price"] = last_price
                anchor = last_price

            buy_entries = [float(p["price_open"]) for p in bot_positions if str(p.get("type", "")).upper() == "BUY"]
            sell_entries = [float(p["price_open"]) for p in bot_positions if str(p.get("type", "")).upper() == "SELL"]

            want_buy = False
            want_sell = False
            if grid_dir in ("BUY_ONLY", "BOTH"):
                if not buy_entries:
                    want_buy = (grid_dir == "BUY_ONLY" and len(bot_positions) == 0) or (last_price <= anchor - grid_step)
                elif last_price <= min(buy_entries) - grid_step:
                    want_buy = True

            if not want_buy and grid_dir in ("SELL_ONLY", "BOTH"):
                if not sell_entries:
                    want_sell = (grid_dir == "SELL_ONLY" and len(bot_positions) == 0) or (last_price >= anchor + grid_step)
                elif last_price >= max(sell_entries) + grid_step:
                    want_sell = True

            if want_buy or want_sell:
                if time.time() < float(bot.get("_unavailable_until", 0.0) or 0.0):
                    signal = "UNAVAILABLE"
                else:
                    action = "BUY_GRID" if want_buy else "SELL_GRID"
                    signal = action
                    ok, msg = self.connector.place_order(
                        symbol=bsym,
                        action=action,
                        lot_size=float(bot.get("lot_size", self.cfg.default_lot_size)),
                        price=last_price,
                        sl_points=grid_step * max_levels,
                        tp_points=grid_tp,
                        bot_name=bot_name,
                        allow_multi_same_symbol=True,
                        max_levels_override=max_levels,
                    )
                    if ok:
                        bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                        bot["grid_anchor_price"] = last_price
                        bot["last_error"] = ""
                        bot.pop("_unavailable_until", None)
                        self._log_event("BOT_EXEC", msg)
                        positions = self.connector.get_open_positions()
                    elif "ratelimit" in msg.lower():
                        signal = "RATE_LIMITED"
                        bot["last_error"] = msg
                        self._log_event("BOT_RATE_LIMIT", msg)
                    elif self._is_symbol_unavailable_msg(msg):
                        signal = "UNAVAILABLE"
                        bot["last_error"] = msg
                        bot["_unavailable_until"] = time.time() + 60.0
                        self._log_event("BOT_SYMBOL_UNAVAILABLE", msg)
            elif bot.get("status") == "RUNNING" and (
                "ratelimit" in str(bot.get("last_error", "")).lower()
                or (
                    self._is_symbol_unavailable_msg(str(bot.get("last_error", "")))
                    and time.time() >= float(bot.get("_unavailable_until", 0.0) or 0.0)
                )
            ):
                bot["last_error"] = ""

        bot["last_signal"] = signal
        return positions

    def _news_snapshot_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(getattr(self.cfg, "news_bot_enabled", False)),
            "pause_grid_on_high_impact": bool(getattr(self.cfg, "news_pause_grid_on_high_impact", False)),
            "auto_trade_enabled": bool(getattr(self.cfg, "news_auto_trade_enabled", False)),
            "lot_size": float(getattr(self.cfg, "news_lot_size", 0.01)),
            "last_scan_at": self.news_scout.last_scan_at,
            "last_error": self.news_scout.last_error,
            "feeds": list(getattr(self.cfg, "news_feeds", [])),
            "items": list(self.news_scout.items),
            "summary_by_symbol": self.news_scout.summary_by_symbol(),
        }

    def save_news_feed(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        with self._lock:
            feed_id = str(payload.get("feed_id") or "").strip() or f"feed_{uuid.uuid4().hex[:8]}"
            source = str(payload.get("source") or "Feed Personalizado").strip()
            url = str(payload.get("url") or "").strip()
            default_symbol = str(payload.get("default_symbol") or "BTCUSD").strip()
            if not url:
                return list(self.cfg.news_feeds)
            ok_url, url_err = validate_rss_url(url)
            if not ok_url:
                raise ValueError(url_err)
            existing = next((f for f in self.cfg.news_feeds if f.get("feed_id") == feed_id), None)
            rec = {"feed_id": feed_id, "source": source, "url": url, "default_symbol": default_symbol}
            if existing is not None:
                existing.update(rec)
            else:
                self.cfg.news_feeds.append(rec)
            save_config(self.cfg, self.config_path)
            self._log_event("NEWS_FEED", f"Fonte '{source}' ({default_symbol}) salva.")
            return list(self.cfg.news_feeds)

    def delete_news_feed(self, feed_id: str) -> list[dict[str, str]]:
        with self._lock:
            self.cfg.news_feeds = [f for f in self.cfg.news_feeds if f.get("feed_id") != feed_id]
            save_config(self.cfg, self.config_path)
            self._log_event("NEWS_FEED", f"Fonte '{feed_id}' removida.")
            return list(self.cfg.news_feeds)

    def reset_news_feeds(self) -> list[dict[str, str]]:
        from prado_linux.news_scout import DEFAULT_NEWS_FEEDS

        with self._lock:
            self.cfg.news_feeds = [dict(f) for f in DEFAULT_NEWS_FEEDS]
            save_config(self.cfg, self.config_path)
            self._log_event("NEWS_FEED", "Fontes padrão de notícias restauradas.")
            return list(self.cfg.news_feeds)

    def _process_news_items(
        self,
        new_items: list[dict[str, Any]],
        positions: list[dict[str, Any]],
        risk_locked: bool,
    ) -> tuple[list[dict[str, Any]], set[str]]:
        just_paused_ids: set[str] = set()
        if not new_items:
            return positions, just_paused_ids
        pause_grid = bool(getattr(self.cfg, "news_pause_grid_on_high_impact", True))
        auto_trade = bool(getattr(self.cfg, "news_auto_trade_enabled", False))
        lot_sz = float(getattr(self.cfg, "news_lot_size", 0.01) or 0.01)
        config_dirty = False

        for item in new_items:
            if item.get("impact") != "HIGH":
                continue
            sym = str(item.get("symbol", "BTCUSD"))
            is_macro = bool(item.get("is_macro_usd", False))
            title = str(item.get("title", ""))

            if pause_grid:
                for b in self.cfg.bots:
                    is_grid = b.get("template_id") == "GRID_LINEAR_HFT" or str(b.get("operation_mode", "")).upper() == "GRID_LINEAR"
                    if not is_grid or b.get("status") != "RUNNING":
                        continue
                    if is_macro or b.get("symbol") == sym:
                        b["status"] = "PAUSED"
                        b["active"] = False
                        b["last_signal"] = "PAUSED_NEWS"
                        just_paused_ids.add(str(b.get("bot_id", "")))
                        config_dirty = True
                        self._log_event(
                            "NEWS_GUARD",
                            f"Robô Grid '{b.get('name')}' pausado por notícia de alto impacto ({sym}): {title[:90]}",
                        )

            bias = str(item.get("bias", "NEUTRAL"))
            if (
                auto_trade
                and self.cfg.auto_trading_enabled
                and not risk_locked
                and bias in ("BULLISH", "BEARISH")
            ):
                if not any(p.get("symbol") == sym for p in positions):
                    ticks = self.connector.fetch_ticks(sym, count=20)
                    last_p = ticks[-1].effective_price() if ticks else get_symbol_spec(sym)["base"]
                    action = "BUY_NEWS" if bias == "BULLISH" else "SELL_NEWS"
                    ok, msg = self.connector.place_order(
                        symbol=sym,
                        action=action,
                        lot_size=lot_sz,
                        price=last_p,
                        sl_points=max(last_p * 0.002, get_symbol_spec(sym)["pip_size"] * 15),
                        tp_points=max(last_p * 0.004, get_symbol_spec(sym)["pip_size"] * 30),
                        bot_name="NewsScout",
                    )
                    self._log_event("NEWS_EXEC", f"[{sym} | {bias}] {msg}")
                    if ok:
                        positions = self.connector.get_open_positions()
        if config_dirty:
            save_config(self.cfg, self.config_path)
        return positions, just_paused_ids

    def _auto_resume_news_paused_bots(self, skip_bot_ids: set[str] | None = None) -> None:
        summary = self.news_scout.summary_by_symbol()
        all_info = summary.get("ALL") or {}
        pause_grid = bool(getattr(self.cfg, "news_pause_grid_on_high_impact", False))
        skip = skip_bot_ids or set()
        changed = False
        for b in self.cfg.bots:
            if str(b.get("bot_id", "")) in skip:
                continue
            if b.get("status") != "PAUSED" or b.get("last_signal") != "PAUSED_NEWS":
                continue
            bsym = str(b.get("symbol", ""))
            sym_info = summary.get(bsym) or {}
            high_cnt = int(sym_info.get("high_impact", 0) or 0)
            bias = str(sym_info.get("bias") or all_info.get("bias") or "NEUTRAL")
            gdir = str(b.get("grid_direction", "BOTH")).upper()
            favorable = (gdir == "BUY_ONLY" and bias == "BULLISH") or (
                gdir == "SELL_ONLY" and bias == "BEARISH"
            )
            if not pause_grid or high_cnt == 0 or bias == "NEUTRAL" or favorable:
                b["status"] = "RUNNING"
                b["active"] = True
                b["last_signal"] = "RESUMED_NEWS"
                changed = True
                self._log_event(
                    "NEWS_GUARD",
                    f"Robô '{b.get('name')}' reativado automaticamente após mudança na notícia ({bsym} | Viés: {bias}).",
                )
        if changed:
            save_config(self.cfg, self.config_path)

    def scan_news(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            poll_sec = max(30, int(getattr(self.cfg, "news_poll_interval_sec", 90) or 90))
            if force or (now - self.news_scout.last_scan_at) >= poll_sec:
                _, new_items = self.news_scout.scan(feeds=self.cfg.news_feeds)
                just_paused_ids: set[str] = set()
                if getattr(self.cfg, "news_bot_enabled", False) and (
                    getattr(self.cfg, "news_pause_grid_on_high_impact", False)
                    or getattr(self.cfg, "news_auto_trade_enabled", False)
                ) and new_items:
                    positions = self.connector.get_open_positions()
                    acc_now = self.connector.get_account_summary()
                    cur_pnl = float(acc_now.get("profit", 0.0)) + float(acc_now.get("daily_realized", 0.0))
                    is_risk_locked = (
                        (self.cfg.max_daily_loss_money > 0 and cur_pnl <= -abs(self.cfg.max_daily_loss_money))
                        or (self.cfg.daily_target_money > 0 and cur_pnl >= abs(self.cfg.daily_target_money))
                    )
                    _, just_paused_ids = self._process_news_items(new_items, positions, risk_locked=is_risk_locked)
                self._auto_resume_news_paused_bots(skip_bot_ids=just_paused_ids)
                self._log_event("NEWS_SCOUT", f"Pesquisa de notícias concluída ({len(self.news_scout.items)} manchete(s)).")
            return self._news_snapshot_dict()

    @staticmethod
    def _is_symbol_unavailable_msg(msg: str) -> bool:
        low = (msg or "").lower()
        return any(
            marker in low
            for marker in (
                "indisponível",
                "market_closed",
                "trading_disabled",
                "symbol_not_found",
                "não encontrado",
            )
        )

    def step_once(self) -> dict[str, Any]:
        with self._lock:
            now_step = time.time()
            # Controlled heartbeat ping & reconnection for live cTrader WebSocket
            if (
                self.cfg.connection_mode.upper() != "SIMULATION"
                and self.connector._client is not None
                and (now_step - self.connector._last_ping_at) >= 20.0
            ):
                self.connector._last_ping_at = now_step
                if not self.connector._client.ping():
                    self.connector.connection_state = "RECONNECTING"
                    self.connector.connected = False
                    self._log_event("CTRADER_WS", "Conexão WebSocket interrompida. Iniciando reconexão controlada...")
                    if self.connector._client.reconnect():
                        self.connector.connection_state = "CONNECTED"
                        self.connector.connected = True
                        self._log_event("CTRADER_WS", "Reconexão WebSocket cTrader concluída.")
                    else:
                        self.connector.connection_state = "DISCONNECTED"
                        self.connector.auth_state = self.connector._client.auth_state
                        self.connector.backend_name = "CTRADER_DISCONNECTED"
                        self._log_event("CTRADER_WS", f"Falha na reconexão cTrader: {self.connector._client.last_error}")

            corr_scores: list[float] = []
            for corr_sym in self.cfg.correlated_basket:
                c_ticks = self.connector.fetch_ticks(corr_sym, count=150)
                if len(c_ticks) >= 5:
                    c_vwap = compute_intraday_vwap(c_ticks)
                    c_flow = compute_flow_metrics(
                        c_ticks,
                        c_vwap,
                        window_size=min(80, len(c_ticks)),
                        z_threshold=self.cfg.zscore_threshold,
                        imbalance_threshold=self.cfg.imbalance_threshold,
                    )
                    corr_scores.append(c_flow.imbalance_ratio)
            corr_bias = round(sum(corr_scores) / len(corr_scores), 4) if corr_scores else 0.0

            self.connector.sync_closed_deals()
            positions = self.connector.get_open_positions()
            acc = self.connector.get_account_summary()
            current_pnl = float(acc.get("profit", 0.0)) + float(acc.get("daily_realized", 0.0))
            risk_locked = False
            risk_status = "Operacional normal"
            if self.cfg.max_daily_loss_money > 0 and current_pnl <= -abs(self.cfg.max_daily_loss_money):
                risk_locked = True
                risk_status = f"Trava de perda diária ({current_pnl:.2f})"
                if positions:
                    self.connector.close_all_positions("MAX_DAILY_LOSS_GUARD")
            elif self.cfg.daily_target_money > 0 and current_pnl >= abs(self.cfg.daily_target_money):
                risk_locked = True
                risk_status = f"Meta diária atingida ({current_pnl:.2f})"

            monitored_symbols = list(self.cfg.active_symbols)
            for b in self.cfg.bots:
                bsym = b.get("symbol")
                if bsym and bsym not in monitored_symbols:
                    monitored_symbols.append(bsym)

            symbols_data: dict[str, Any] = {}
            for sym in monitored_symbols:
                ticks = self.connector.fetch_ticks(sym, count=200)
                vwap_bands = compute_intraday_vwap(ticks)
                flow = compute_flow_metrics(
                    ticks,
                    vwap_bands,
                    window_size=self.cfg.window_ticks,
                    z_threshold=self.cfg.zscore_threshold,
                    imbalance_threshold=self.cfg.imbalance_threshold,
                    revert_sigma=self.cfg.revert_sigma,
                    sl_sigma_mult=self.cfg.sl_sigma_mult,
                    tp_sigma_mult=self.cfg.tp_sigma_mult,
                    operation_mode=self.cfg.operation_mode,
                )
                action = flow.recommended_action
                if action in ("BUY_FLOW", "BUY_REVERT_VWAP") and corr_bias <= -abs(self.cfg.correlation_block_threshold):
                    action = "WAIT_CORRELATION_BLOCK"
                elif action in ("SELL_FLOW", "SELL_REVERT_VWAP") and corr_bias >= abs(self.cfg.correlation_block_threshold):
                    action = "WAIT_CORRELATION_BLOCK"

                last_price = ticks[-1].effective_price() if ticks else 0.0
                distance_sigma = (
                    round((last_price - vwap_bands.vwap) / vwap_bands.std_dev, 2)
                    if vwap_bands.std_dev > 0
                    else 0.0
                )
                symbols_data[sym] = {
                    "symbol": sym,
                    "last_price": round(last_price, 6),
                    "price": round(last_price, 6),
                    "vwap": round(vwap_bands.vwap, 6),
                    "std_dev": round(vwap_bands.std_dev, 6),
                    "upper_1": round(vwap_bands.upper_1, 6),
                    "lower_1": round(vwap_bands.lower_1, 6),
                    "upper_2": round(vwap_bands.upper_2, 6),
                    "lower_2": round(vwap_bands.lower_2, 6),
                    "distance_sigma": distance_sigma,
                    "sigma_distance": distance_sigma,
                    "imbalance_ratio": round(flow.imbalance_ratio, 4),
                    "imbalance": round(flow.imbalance_ratio, 4),
                    "aggression_zscore": round(flow.aggression_zscore, 4),
                    "zscore": round(flow.aggression_zscore, 4),
                    "correlation_bias": corr_bias,
                    "regime": flow.regime,
                    "action": action,
                    "signal": action,
                }

            active_deals = (
                self.connector._sim_deals_history
                if self.cfg.connection_mode.upper() == "SIMULATION"
                else self.connector._live_deals_history
            )
            for bot in self.cfg.bots:
                try:
                    bsym = bot.get("symbol", "")
                    if not bsym:
                        raise ValueError("Robô sem símbolo configurado")
                    if self.cfg.connection_mode.upper() != "SIMULATION":
                        bot_acc_type = str(bot.get("account_type", "") or "").strip().upper()
                        active_acc_type = str(acc.get("account_type", "") or "").strip().upper()
                        if bot_acc_type in ("DEMO", "REAL") and active_acc_type in ("DEMO", "REAL") and bot_acc_type != active_acc_type:
                            bot["last_signal"] = "ACCOUNT_MISMATCH"
                            continue
                        bot_acc_id = str(bot.get("account_id", "") or "").strip()
                        active_acc_id = str(self.cfg.active_account_id or "").strip()
                        if bot_acc_id and active_acc_id and bot_acc_id != active_acc_id:
                            bot["last_signal"] = "ACCOUNT_MISMATCH"
                            continue
                    bname = str(bot.get("name", ""))
                    bprefix = bname[:14]
                    realized_bot = sum(
                        float(d.get("profit", 0.0))
                        for d in active_deals
                        if (bname and str(d.get("bot_name", "")) == bname)
                        or (bprefix and str(d.get("comment", "")).startswith(bprefix))
                        or (not d.get("bot_name") and d.get("symbol") == bsym)
                    )
                    floating_bot = sum(
                        float(p.get("profit", 0.0))
                        for p in positions
                        if (bname and str(p.get("bot_name", "")) == bname)
                        or (bprefix and str(p.get("comment", "")).startswith(bprefix))
                        or (not p.get("bot_name") and p.get("symbol") == bsym)
                    )
                    total_bot = round(realized_bot + floating_bot, 2)
                    bot["realized_pnl"] = round(realized_bot, 2)
                    bot["floating_pnl"] = round(floating_bot, 2)
                    bot["total_pnl"] = total_bot

                    if (
                        bot.get("loss_guard_enabled")
                        and float(bot.get("max_loss_usd", 0.0) or 0.0) > 0
                        and bot.get("status") == "RUNNING"
                        and total_bot <= -abs(float(bot["max_loss_usd"]))
                    ):
                        bot["status"] = "PAUSED"
                        bot["active"] = False
                        bot["last_signal"] = "PAUSED_MAX_LOSS"
                        save_config(self.cfg, self.config_path)
                        self._log_event(
                            "BOT_RISK_GUARD",
                            f"Robô '{bname}' pausado automaticamente: perda (${total_bot:.2f}) atingiu a trava (-${abs(float(bot['max_loss_usd'])):.2f}).",
                        )
                        continue

                    bot_tf = str(bot.get("timeframe", "TICKS")).strip().upper()
                    bot_gran = self.connector.TIMEFRAME_GRANULARITIES.get(bot_tf, 0)
                    ticks = self.connector.fetch_ticks(bsym, count=200, granularity=bot_gran)
                    vwap_bands = compute_intraday_vwap(ticks)
                    bot_flow = compute_flow_metrics(
                        ticks,
                        vwap_bands,
                        window_size=int(bot.get("window_ticks", self.cfg.window_ticks)),
                        z_threshold=float(bot.get("zscore_threshold", self.cfg.zscore_threshold)),
                        imbalance_threshold=float(bot.get("imbalance_threshold", self.cfg.imbalance_threshold)),
                        revert_sigma=float(bot.get("revert_sigma", self.cfg.revert_sigma)),
                        sl_sigma_mult=float(bot.get("sl_sigma_mult", self.cfg.sl_sigma_mult)),
                        tp_sigma_mult=float(bot.get("tp_sigma_mult", self.cfg.tp_sigma_mult)),
                        operation_mode=str(bot.get("operation_mode", "BOTH")),
                    )
                    last_price = ticks[-1].effective_price() if ticks else 0.0
                    bot_action = bot_flow.recommended_action

                    bot["last_price"] = round(last_price, 6)
                    bot["vwap"] = round(vwap_bands.vwap, 6)
                    bot["aggression_zscore"] = round(bot_flow.aggression_zscore, 4)
                    bot["imbalance_ratio"] = round(bot_flow.imbalance_ratio, 4)
                    bot["active"] = bot.get("status") == "RUNNING"
                    bot["template_id"] = bot.get("template_id") or bot.get("bot_template_id", "")
                    bot["template_name"] = bot.get("template_name") or bot.get("bot_template_name", "")

                    custom_tpl = next(
                        (t for t in self.cfg.custom_templates if t.get("template_id") == bot["template_id"]),
                        None,
                    )
                    if custom_tpl is not None:
                        custom_act = self._evaluate_custom_template(custom_tpl, ticks, bot)
                        if custom_act:
                            bot_action = custom_act

                    if bot["template_id"] == "GRID_LINEAR_HFT" or str(bot.get("operation_mode", "")).upper() == "GRID_LINEAR":
                        positions = self._evaluate_grid_bot(bot, last_price, positions, risk_locked)
                        continue

                    is_bot_active = bot.get("status") == "RUNNING" and self.cfg.auto_trading_enabled and not risk_locked
                    if is_bot_active:
                        positions = self._check_bot_tick_take_profit(bot, ticks, positions)

                    bot["last_regime"] = bot_flow.regime
                    if bot.get("status") == "RUNNING":
                        bot["last_signal"] = bot_action if self.cfg.auto_trading_enabled else "AUTO_PAUSED"

                    if bot.get("news_assisted"):
                        if not is_bot_active:
                            continue
                        news_summary = self.news_scout.summary_by_symbol()
                        news_info = news_summary.get(bsym) or {}
                        if not news_info or news_info.get("bias") == "NEUTRAL":
                            all_info = news_summary.get("ALL") or {}
                            if all_info.get("bias") in ("BULLISH", "BEARISH"):
                                news_info = all_info
                        news_bias = str(news_info.get("bias", "NEUTRAL"))
                        bot_pos = [
                            p for p in positions
                            if p.get("symbol") == bsym
                            and (
                                str(p.get("bot_name", "")) == bname
                                or (bprefix and str(p.get("comment", "")).startswith(bprefix))
                                or not p.get("bot_name")
                            )
                        ]
                        if bot_pos:
                            for p in list(bot_pos):
                                p_profit = float(p.get("profit", 0.0) or 0.0)
                                p_is_buy = str(p.get("type", "")).upper() == "BUY"
                                flipped_against = (p_is_buy and news_bias == "BEARISH") or (
                                    not p_is_buy and news_bias == "BULLISH"
                                )
                                if flipped_against and p_profit > 0:
                                    ok_ex, msg_ex = self.connector.close_single_position(p["ticket"])
                                    if ok_ex:
                                        bot["last_signal"] = "NEWS_TECH_EXIT"
                                        self._log_event("BOT_NEWS_EXIT", f"[{bname}] {msg_ex}")
                                        positions = self.connector.get_open_positions()
                                else:
                                    bot["last_signal"] = "HOLD_NEWS_PROFIT"
                        elif (
                            bot.get("status") == "RUNNING"
                            and self.cfg.auto_trading_enabled
                            and not risk_locked
                        ):
                            chosen_action = ""
                            if news_bias == "BULLISH" and not bot_action.startswith("SELL"):
                                chosen_action = "BUY_NEWS_HYBRID"
                            elif news_bias == "BEARISH" and not bot_action.startswith("BUY"):
                                chosen_action = "SELL_NEWS_HYBRID"
                            elif bot_action in ("BUY_FLOW", "BUY_REVERT_VWAP") and news_bias != "BEARISH":
                                chosen_action = bot_action
                            elif bot_action in ("SELL_FLOW", "SELL_REVERT_VWAP") and news_bias != "BULLISH":
                                chosen_action = bot_action

                            if chosen_action and not any(p["symbol"] == bsym for p in positions):
                                if time.time() < float(bot.get("_unavailable_until", 0.0) or 0.0):
                                    bot["last_signal"] = "UNAVAILABLE"
                                    continue
                                bot["last_signal"] = chosen_action
                                ok, msg = self.connector.place_order(
                                    symbol=bsym,
                                    action=chosen_action,
                                    lot_size=float(bot.get("lot_size", self.cfg.default_lot_size)),
                                    price=last_price,
                                    sl_points=bot_flow.sl_points,
                                    tp_points=bot_flow.tp_points * 2.5,
                                    bot_name=bname or "PradoBot",
                                    tp_mode=str(bot.get("tp_mode", "AUTO")),
                                    tp_value=float(bot.get("tp_value", 0.0) or 0.0),
                                )
                                if ok:
                                    bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                                    bot["last_error"] = ""
                                    bot.pop("_unavailable_until", None)
                                    self._log_event("BOT_NEWS_EXEC", msg)
                                    positions = self.connector.get_open_positions()
                                elif "ratelimit" in msg.lower():
                                    bot["last_signal"] = "RATE_LIMITED"
                                    bot["last_error"] = msg
                                    self._log_event("BOT_RATE_LIMIT", msg)
                                elif self._is_symbol_unavailable_msg(msg):
                                    bot["last_signal"] = "UNAVAILABLE"
                                    bot["last_error"] = msg
                                    bot["_unavailable_until"] = time.time() + 60.0
                                    self._log_event("BOT_SYMBOL_UNAVAILABLE", msg)
                        continue

                    if (
                        bot.get("status") == "RUNNING"
                        and self.cfg.auto_trading_enabled
                        and not risk_locked
                        and bot_action in ("BUY_FLOW", "SELL_FLOW", "BUY_REVERT_VWAP", "SELL_REVERT_VWAP")
                    ):
                        if time.time() < float(bot.get("_unavailable_until", 0.0) or 0.0):
                            bot["last_signal"] = "UNAVAILABLE"
                            continue
                        has_pos = any(p["symbol"] == bsym for p in positions)
                        if not has_pos:
                            ok, msg = self.connector.place_order(
                                symbol=bsym,
                                action=bot_action,
                                lot_size=float(bot.get("lot_size", self.cfg.default_lot_size)),
                                price=last_price,
                                sl_points=bot_flow.sl_points,
                                tp_points=bot_flow.tp_points,
                                bot_name=str(bot.get("name", "PradoBot")),
                                tp_mode=str(bot.get("tp_mode", "AUTO")),
                                tp_value=float(bot.get("tp_value", 0.0) or 0.0),
                            )
                            if ok:
                                bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                                bot["last_error"] = ""
                                bot.pop("_unavailable_until", None)
                                self._log_event("BOT_EXEC", msg)
                                positions = self.connector.get_open_positions()
                            elif "ratelimit" in msg.lower():
                                bot["last_signal"] = "RATE_LIMITED"
                                bot["last_error"] = msg
                                self._log_event("BOT_RATE_LIMIT", msg)
                            elif self._is_symbol_unavailable_msg(msg):
                                bot["last_signal"] = "UNAVAILABLE"
                                bot["last_error"] = msg
                                bot["_unavailable_until"] = time.time() + 60.0
                                self._log_event("BOT_SYMBOL_UNAVAILABLE", msg)
                    elif bot.get("status") == "RUNNING" and (
                        "ratelimit" in str(bot.get("last_error", "")).lower()
                        or (
                            self._is_symbol_unavailable_msg(str(bot.get("last_error", "")))
                            and time.time() >= float(bot.get("_unavailable_until", 0.0) or 0.0)
                        )
                    ):
                        bot["last_error"] = ""
                except CTraderRateLimitError as rl_exc:
                    bot["last_signal"] = "RATE_LIMITED"
                    bot["last_error"] = str(rl_exc)
                    self._log_event("BOT_RATE_LIMIT", f"Cooldown temporário no robô '{bot.get('name', bot.get('bot_id', '?'))}': {rl_exc}")
                except Exception as bot_exc:
                    bot["status"] = "ERROR"
                    bot["active"] = False
                    bot["last_error"] = str(bot_exc)
                    self._log_event("BOT_ERROR", f"Erro isolado no robô '{bot.get('name', bot.get('bot_id', '?'))}': {bot_exc}")

            if getattr(self.cfg, "news_bot_enabled", False):
                poll_sec = max(30, int(getattr(self.cfg, "news_poll_interval_sec", 90) or 90))
                if (time.time() - self.news_scout.last_scan_at) >= poll_sec:
                    _, new_items = self.news_scout.scan(feeds=self.cfg.news_feeds)
                    if (
                        getattr(self.cfg, "news_pause_grid_on_high_impact", False)
                        or getattr(self.cfg, "news_auto_trade_enabled", False)
                    ) and new_items:
                        positions, just_paused_ids = self._process_news_items(new_items, positions, risk_locked)
                        self._auto_resume_news_paused_bots(skip_bot_ids=just_paused_ids)

            if len(self.connector._sim_deals_history) > 500:
                del self.connector._sim_deals_history[500:]
            if len(self.connector._live_deals_history) > 500:
                del self.connector._live_deals_history[500:]

            active_deals = (
                self.connector._sim_deals_history
                if self.cfg.connection_mode.upper() == "SIMULATION"
                else self.connector._live_deals_history
            )
            self._latest_snapshot = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account": acc,
                "accounts": [
                    {
                        k: ("********" if k in ("access_token", "refresh_token", "client_secret") and v else v)
                        for k, v in a.items()
                    }
                    for a in self.cfg.accounts
                ],
                "categories": self.cfg.custom_categories,
                "bots": list(self.cfg.bots),
                "risk_status": risk_status,
                "risk_locked": risk_locked,
                "correlation_bias": corr_bias,
                "basket_bias": corr_bias,
                "auto_trading_enabled": self.cfg.auto_trading_enabled,
                "operation_mode": self.cfg.operation_mode,
                "positions": positions,
                "deals_history": list(active_deals[:40]),
                "symbols": symbols_data,
                "news": self._news_snapshot_dict(),
                "events": list(self._event_log[:30]),
                "logs": [
                    {"time": e["time"], "module": e["category"], "message": e["message"]}
                    for e in self._event_log[:40]
                ],
            }
            return self._latest_snapshot

    def get_snapshot(self) -> dict[str, Any]:
        if not self._latest_snapshot:
            return self.step_once()
        return self._latest_snapshot

    def start_background_loop(self) -> None:
        if self._running:
            return
        self._running = True

        def _loop() -> None:
            while self._running:
                try:
                    self.step_once()
                except Exception as exc:
                    self._log_event("ERROR", f"Erro no ciclo HFT: {exc}")
                time.sleep(max(0.5, float(self.cfg.poll_interval_sec)))

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_background_loop(self) -> None:
        self._running = False
