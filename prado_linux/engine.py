"""Prado Institutional HFT Trading Engine, Deriv WebSocket Multipliers Connector & Robot Fleet."""
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
from prado_linux.deriv_client import (
    DerivAuthError,
    DerivClient,
    DerivRateLimiter,
    DerivRateLimitError,
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
    """Normalize per-bot Take Profit mode ('AUTO', 'USD', 'PCT', 'TICKS') and value."""
    mode = str(tp_mode or "AUTO").strip().upper()
    if mode not in ("AUTO", "USD", "PCT", "TICKS"):
        return "AUTO", 0.0
    if mode == "AUTO":
        return "AUTO", 0.0
    defaults = {"USD": 0.5, "PCT": 10.0, "TICKS": 2.0}
    try:
        val = float(tp_value)
    except (TypeError, ValueError):
        val = defaults[mode]
    if not math.isfinite(val) or val <= 0.0:
        val = defaults[mode]
    return mode, round(val, 4)


MAIN_DERIV_SYMBOLS: list[dict[str, str]] = [
    {"name": "R_100", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 100 Index (24/7)"},
    {"name": "R_75", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 75 Index (24/7)"},
    {"name": "R_50", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 50 Index (24/7)"},
    {"name": "R_25", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 25 Index (24/7)"},
    {"name": "R_10", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 10 Index (24/7)"},
    {"name": "1HZ100V", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 100 (1s) Index"},
    {"name": "1HZ10V", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 10 (1s) Index"},
    {"name": "frxEURUSD", "category": "Forex Principais", "description": "EUR/USD Forex"},
    {"name": "frxGBPUSD", "category": "Forex Principais", "description": "GBP/USD Forex"},
    {"name": "frxXAUUSD", "category": "Ouro & Commodities", "description": "Ouro Spot (XAU/USD)"},
    {"name": "cryBTCUSD", "category": "Criptomoedas (24/7)", "description": "Bitcoin vs US Dollar (24/7)"},
    {"name": "cryETHUSD", "category": "Criptomoedas (24/7)", "description": "Ethereum vs US Dollar (24/7)"},
]

EXTENDED_ALL_SYMBOLS: list[dict[str, str]] = MAIN_DERIV_SYMBOLS + [
    {"name": "1HZ25V", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 25 (1s) Index"},
    {"name": "1HZ50V", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 50 (1s) Index"},
    {"name": "1HZ75V", "category": "Índices Sintéticos Volatility (24/7)", "description": "Volatility 75 (1s) Index"},
    {"name": "frxUSDJPY", "category": "Forex Principais", "description": "USD/JPY Forex"},
    {"name": "frxAUDUSD", "category": "Forex Principais", "description": "AUD/USD Forex"},
    {"name": "frxUSDCAD", "category": "Forex Principais", "description": "USD/CAD Forex"},
    {"name": "frxXAGUSD", "category": "Ouro & Commodities", "description": "Prata Spot (XAG/USD)"},
    {"name": "BOOM500", "category": "Índices Crash & Boom", "description": "Boom 500 Index"},
    {"name": "BOOM1000", "category": "Índices Crash & Boom", "description": "Boom 1000 Index"},
    {"name": "CRASH500", "category": "Índices Crash & Boom", "description": "Crash 500 Index"},
    {"name": "CRASH1000", "category": "Índices Crash & Boom", "description": "Crash 1000 Index"},
]


class DerivUniversalConnector:
    """Connects directly to Deriv WebSocket API (100% Python, zero MT5) with Simulation fallback."""

    def __init__(self, cfg: PradoServerConfig) -> None:
        self.cfg = cfg
        self.rate_limiter = DerivRateLimiter()
        self._deriv: DerivClient | None = None
        self._public_deriv: DerivClient | None = None
        self._deriv_auth: dict[str, Any] = {}
        self.connected: bool = False
        self.connection_state: str = (
            "DISCONNECTED" if cfg.connection_mode.upper() != "SIMULATION" else "CONNECTED"
        )
        self.auth_state: str = "UNAUTHENTICATED"
        self.backend_name: str = (
            "DERIV_DISCONNECTED" if cfg.connection_mode.upper() != "SIMULATION" else "SIMULATION_FEED"
        )
        self.last_error: str = ""
        self.last_tick_at: float = 0.0
        self._sim_ticks: dict[str, list[TickRecord]] = {}
        self._sim_positions: list[dict[str, Any]] = []
        self._sim_deals_history: list[dict[str, Any]] = []
        self._deriv_deals_history: list[dict[str, Any]] = []
        self._sim_daily_pnl: float = 0.0
        self._sim_balance: float = 10_000.0
        self._tick_cache: dict[str, tuple[float, list[TickRecord]]] = {}
        self._symbols_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._balance_cache: tuple[float, float] | None = None
        self._positions_cache: tuple[float, list[dict[str, Any]]] | None = None
        self._contract_bot_map: dict[str, str] = {}
        self._last_order_ts: dict[str, float] = {}
        self._last_ping_at: float = 0.0

    def connect(self, token: str | None = None, app_id: str | None = None) -> tuple[bool, str]:
        target_token = (token if token is not None else self.cfg.deriv_token).strip()
        target_app = (app_id if app_id is not None else self.cfg.deriv_app_id).strip() or "1089"
        mode = self.cfg.connection_mode.upper()

        if self._deriv is not None:
            self._deriv.close()
            self._deriv = None

        if mode != "SIMULATION" and target_token:
            self.connection_state = "CONNECTING"
            try:
                client = DerivClient(
                    token=target_token,
                    app_id=target_app,
                    rate_limiter=self.rate_limiter,
                    preferred_account_type=self.cfg.active_account_type,
                )
                auth = client.authorize()
                self._deriv = client
                self._deriv_auth = auth
                self.connected = True
                self.connection_state = "CONNECTED"
                self.auth_state = "AUTHENTICATED"
                self.backend_name = "DERIV_LIVE_API"
                self.last_error = ""
                self._balance_cache = (time.time(), float(auth.get("balance", 0.0)))
                env_str = "DEMO" if auth.get("is_virtual") else "REAL"
                return (
                    True,
                    f"Conectado à Deriv [{env_str}] — Conta {auth.get('loginid')} ({auth.get('balance')} {auth.get('currency', 'USD')}).",
                )
            except DerivAuthError as exc:
                self._deriv = None
                self._deriv_auth = {}
                self.auth_state = exc.auth_state
                self.connection_state = "ERROR"
                self.last_error = str(exc)
                self.connected = False
                self.backend_name = "DERIV_DISCONNECTED"
                return False, f"Erro ao conectar na Deriv: {exc}"
            except Exception as exc:
                self._deriv = None
                self._deriv_auth = {}
                err_msg = str(exc)
                if target_token.startswith("pat_") and target_app == "1089":
                    self.auth_state = "APP_ID_MISMATCH"
                    err_msg = (
                        "Token 'pat_...' não é aceito com App ID 1089. "
                        "Gere um token clássico em app.deriv.com/account/api-token OU use seu App ID de developers.deriv.com."
                    )
                elif "RateLimit" in err_msg or "429" in err_msg:
                    self.auth_state = "UNAUTHENTICATED"
                else:
                    self.auth_state = "TOKEN_INVALID"
                self.connection_state = "ERROR"
                self.last_error = err_msg
                if mode != "SIMULATION":
                    self.connected = False
                    self.backend_name = "DERIV_DISCONNECTED"
                    return False, f"Erro ao conectar na Deriv: {err_msg}"

        self._deriv = None
        self._deriv_auth = {}
        if mode != "SIMULATION":
            self.connected = False
            self.connection_state = "DISCONNECTED"
            self.auth_state = "UNAUTHENTICATED"
            self.backend_name = "DERIV_DISCONNECTED"
            return (
                False,
                "Nenhum token Deriv válido conectado. Cole seu token na aba 'Tokens e Contas Deriv'.",
            )

        self.connected = True
        self.connection_state = "CONNECTED"
        self.auth_state = "AUTHENTICATED"
        self.backend_name = "SIMULATION_FEED"
        self._tick_cache.clear()
        return (
            True,
            "Modo Simulação Quant Ativo.",
        )

    def _get_public_deriv(self) -> DerivClient:
        app_id = (self.cfg.deriv_app_id or "1089").strip() or "1089"
        if self._public_deriv is None or self._public_deriv.app_id != app_id:
            if self._public_deriv is not None:
                self._public_deriv.close()
            self._public_deriv = DerivClient(token="", app_id=app_id, rate_limiter=self.rate_limiter)
        return self._public_deriv

    def discover_broker_symbols(self, mode: str = "PRINCIPAIS") -> list[dict[str, Any]]:
        mode_upper = mode.upper()
        client = self._deriv
        if client is None and self.cfg.connection_mode.upper() != "SIMULATION":
            client = self._get_public_deriv()
        if client is not None:
            now = time.time()
            if self._symbols_cache and (now - self._symbols_cache[0]) < 60.0:
                syms = self._symbols_cache[1]
            else:
                try:
                    syms = client.get_active_symbols()
                    if syms:
                        self._symbols_cache = (now, syms)
                except Exception as exc:
                    self.last_error = f"Erro listando ativos Deriv: {exc}"
                    syms = []
            if syms:
                if mode_upper == "PRINCIPAIS":
                    main_set = {m["name"] for m in MAIN_DERIV_SYMBOLS}
                    filtered = [s for s in syms if s["name"] in main_set]
                    if filtered:
                        return filtered
                return syms[:500]

        source = MAIN_DERIV_SYMBOLS if mode_upper == "PRINCIPAIS" else EXTENDED_ALL_SYMBOLS
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
        masked_app = mask_secret(self.cfg.deriv_app_id or "1089", 2, 2)

        if self._deriv is not None:
            try:
                auth = self._deriv_auth
                if not auth:
                    auth = self._deriv.authorize()
                    self._deriv_auth = auth

                bal = float(auth.get("balance", 0.0))
                if self._balance_cache is None or (now - self._balance_cache[0]) >= 10.0:
                    try:
                        fresh_bal = self._deriv.get_balance()
                        if fresh_bal is not None:
                            bal = fresh_bal
                            self._balance_cache = (now, bal)
                    except DerivAuthError:
                        raise
                    except DerivRateLimitError as exc:
                        self.last_error = str(exc)
                    except Exception:
                        pass
                else:
                    bal = self._balance_cache[1]

                positions = self.get_open_positions()
                floating = sum(float(p.get("profit", 0.0)) for p in positions)
                deriv_daily_realized = round(
                    sum(float(d.get("profit", 0.0)) for d in self._deriv_deals_history), 2
                )
                is_virt = bool(auth.get("is_virtual", 1))
                acc_mode = "DEMO" if is_virt else "REAL"
                trading_state = self._compute_trading_state(acc_mode, rl_status)
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
                    "masked_app_id": masked_app,
                    "last_tick_at": self.last_tick_at,
                    "active_account_id": self.cfg.active_account_id,
                    "login": str(auth.get("loginid", "---")),
                    "server": "Deriv API (REST + OTP WS)",
                    "name": str(auth.get("fullname", "Conta Deriv")),
                    "currency": str(auth.get("currency", "USD")),
                    "balance": round(bal, 2),
                    "equity": round(bal + floating, 2),
                    "profit": round(floating, 2),
                    "daily_realized": deriv_daily_realized,
                    "margin_free": round(bal, 2),
                    "status_note": self.last_error,
                }
            except DerivAuthError as exc:
                self.auth_state = exc.auth_state
                self.connection_state = "ERROR"
                self.connected = False
                self.last_error = str(exc)
            except Exception as exc:
                self.last_error = str(exc)

        if self.cfg.connection_mode.upper() != "SIMULATION":
            acc_mode = self.cfg.active_account_type.upper() or "DEMO"
            return {
                "backend": "DERIV_DISCONNECTED",
                "connected": False,
                "account_type": acc_mode,
                "account_mode": acc_mode,
                "connection_state": self.connection_state,
                "auth_state": self.auth_state,
                "data_state": data_state,
                "trading_state": "BLOCKED",
                "rate_limit": rl_status,
                "masked_app_id": masked_app,
                "last_tick_at": self.last_tick_at,
                "active_account_id": self.cfg.active_account_id,
                "login": "DESCONECTADO",
                "server": self.last_error or "Aguardando token válido da Deriv",
                "name": "Conta Deriv Desconectada",
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
            "masked_app_id": masked_app,
            "last_tick_at": self.last_tick_at or now,
            "active_account_id": self.cfg.active_account_id,
            "login": "VRTC-SIM" if acc_mode == "DEMO" else "CR-SIM",
            "server": "Deriv Quant Simulador",
            "name": f"Mesa Deriv ({acc_mode})",
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
        "H1": 3600,
    }

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
        if cached and (now - cached[0]) < 8.0 and len(cached[1]) >= min(count, 40):
            return cached[1]
        client = self._deriv
        if client is None:
            client = self._get_public_deriv()
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
                if self._deriv is not None:
                    self.last_error = f"Erro lendo ticks Deriv ({symbol}): {exc}"
        ticks_sim = self._generate_sim_ticks(symbol)
        if ticks_sim and self.cfg.connection_mode.upper() == "SIMULATION":
            self.last_tick_at = now
        return ticks_sim

    def _generate_sim_ticks(self, symbol: str) -> list[TickRecord]:
        base_map = {
            "R_100": 1850.0,
            "R_75": 42500.0,
            "R_50": 145.0,
            "R_25": 2350.0,
            "R_10": 6500.0,
            "1HZ100V": 1240.0,
            "1HZ10V": 9100.0,
            "frxEURUSD": 1.0540,
            "frxGBPUSD": 1.2620,
            "frxXAUUSD": 2655.0,
            "cryBTCUSD": 94500.0,
            "cryETHUSD": 3350.0,
        }
        base_price = base_map.get(symbol, 100.0)
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
                        bid=round(p, 6),
                        ask=round(p, 6),
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
                    bid=round(new_p, 6),
                    ask=round(new_p, 6),
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

    def get_open_positions(self) -> list[dict[str, Any]]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._deriv is None:
                return []
            now = time.time()
            if self._positions_cache and (now - self._positions_cache[0]) < 5.0:
                return self._positions_cache[1]
            try:
                pos = self._deriv.get_open_contracts()
                for item in pos:
                    cid_str = str(item.get("ticket", ""))
                    bname = self._contract_bot_map.get(cid_str) or next(
                        (str(b.get("name", "")) for b in self.cfg.bots if b.get("symbol") == item.get("symbol") and b.get("name")),
                        "Deriv",
                    )
                    item["bot_name"] = bname
                    item["comment"] = item.get("comment") or bname
                self._positions_cache = (now, pos)
                return pos
            except Exception as exc:
                self.last_error = f"Erro lendo posições Deriv: {exc}"
                return self._positions_cache[1] if self._positions_cache else []

        for pos in list(self._sim_positions):
            sym = pos["symbol"]
            ticks = self._sim_ticks.get(sym)
            if ticks:
                curr = ticks[-1].effective_price()
                pos["price_current"] = round(curr, 6)
                is_buy = pos["type"] == "BUY"
                pct_move = ((curr - pos["price_open"]) / max(pos["price_open"], 1e-6)) if is_buy else ((pos["price_open"] - curr) / max(pos["price_open"], 1e-6))
                mult = int(pos.get("multiplier", 100))
                pos["profit"] = round(pct_move * float(pos["volume"]) * mult, 2)

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
                            "bot_name": pos.get("comment", ""),
                        },
                    )
                    self._sim_positions.remove(pos)
        return list(self._sim_positions)

    def place_order(
        self,
        symbol: str,
        action: str,
        stake: float,
        price: float,
        sl_points: float,
        tp_points: float,
        multiplier: int = 100,
        bot_name: str = "PradoBot",
        allow_multi_same_symbol: bool = False,
        max_levels_override: int = 0,
        tp_usd_mult: float = 0.9,
        tp_mode: str = "AUTO",
        tp_value: float = 0.0,
    ) -> tuple[bool, str]:
        now = time.time()
        max_stake = float(getattr(self.cfg, "max_stake_per_trade", 100.0) or 100.0)
        if float(stake) > max_stake:
            return False, f"Stake ${stake:.2f} excede o limite máximo por operação (${max_stake:.2f})."

        raw_interval = getattr(self.cfg, "min_order_interval_sec", 3.0)
        min_interval = 3.0 if raw_interval is None else float(raw_interval)
        last_ts = self._last_order_ts.get(symbol, 0.0)
        if (now - last_ts) < min_interval:
            return False, f"Intervalo mínimo entre operações ativo para {symbol}"

        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._deriv is None or not self.connected or self.auth_state != "AUTHENTICATED":
                return False, f"Negociação bloqueada: Deriv desconectada ou não autenticada ({self.auth_state})"
            is_virt = bool(self._deriv_auth.get("is_virtual", 1))
            if not is_virt and not getattr(self.cfg, "allow_real_trading", False):
                return False, "Negociação em conta REAL bloqueada por padrão de segurança."
            rl = self.rate_limiter.status(now)
            if rl.get("state") == "BLOCKED":
                return False, f"Negociação bloqueada por RateLimit ({rl.get('cooldown_seconds')}s)"
            data_state = self._compute_data_state(now)
            if data_state != "LIVE":
                return False, f"Negociação bloqueada: dados de mercado indisponíveis/desatualizados ({data_state}) para {symbol}."

        open_positions = self.get_open_positions()
        max_concurrent = int(getattr(self.cfg, "max_concurrent_trades", 5) or 5)
        if allow_multi_same_symbol and max_levels_override > 0:
            max_concurrent = max(max_concurrent, max_levels_override)
        if len(open_positions) >= max_concurrent:
            return False, f"Limite de operações simultâneas atingido ({len(open_positions)}/{max_concurrent})."

        max_exposure = float(getattr(self.cfg, "max_total_exposure_usd", 500.0) or 500.0)
        current_exposure = sum(float(p.get("volume", 0.0)) for p in open_positions)
        if (current_exposure + float(stake)) > max_exposure:
            return False, f"Exposição total (${current_exposure + float(stake):.2f}) excede o limite (${max_exposure:.2f})."

        if not allow_multi_same_symbol and any(p.get("symbol") == symbol for p in open_positions):
            return False, f"Posição já aberta em {symbol} (bloqueio de ordem duplicada)."

        self._last_order_ts[symbol] = now
        is_buy = action.startswith("BUY")
        if self._deriv is not None:
            norm_tp_mode, norm_tp_val = normalize_tp_config(tp_mode, tp_value)
            sl_usd = round(max(1.0, stake * 0.5), 2)
            if norm_tp_mode == "USD":
                tp_usd = round(max(0.05, norm_tp_val), 2)
            elif norm_tp_mode == "PCT":
                tp_usd = round(max(0.05, float(stake) * (norm_tp_val / 100.0)), 2)
            else:
                tp_usd = round(max(1.5, stake * tp_usd_mult), 2)
            ok, msg = self._deriv.place_multiplier_order(
                symbol=symbol,
                is_buy=is_buy,
                stake=stake,
                multiplier=multiplier,
                sl_amount=sl_usd,
                tp_amount=tp_usd,
            )
            if ok:
                cid = self._deriv.last_order_lifecycle.get("contract_id")
                if cid is not None:
                    self._contract_bot_map[str(cid)] = bot_name
            self._positions_cache = None
            return ok, msg

        sl = round(price - sl_points, 6) if is_buy else round(price + sl_points, 6)
        tp = round(price + tp_points, 6) if is_buy else round(price - tp_points, 6)
        ticket = int(time.time() * 1000) % 100_000_000
        side_str = "BUY" if is_buy else "SELL"
        self._sim_positions.append(
            {
                "ticket": ticket,
                "symbol": symbol,
                "type": side_str,
                "side": side_str,
                "volume": float(stake),
                "multiplier": int(multiplier),
                "price_open": round(price, 6),
                "price_current": round(price, 6),
                "sl": sl,
                "tp": tp,
                "profit": 0.0,
                "bot_name": bot_name,
                "comment": f"{bot_name[:14]}_{action}",
            }
        )
        return True, f"[{bot_name}] Multiplier {action} ({multiplier}x) aberto em {symbol} (Stake=${stake})"

    def close_all_positions(self, reason: str = "MANUAL_PANIC_FLATTEN") -> tuple[int, str]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._deriv is None:
                return 0, "Deriv desconectada: nenhuma posição ativa para encerrar."
            self._positions_cache = None
            positions = self.get_open_positions()
            closed = 0
            errors: list[str] = []
            for p in positions:
                try:
                    ok, err_msg = self._deriv.close_contract(str(p["ticket"]))
                except Exception as exc:
                    ok, err_msg = False, str(exc)
                if ok:
                    closed += 1
                    ts_str = datetime.now().strftime("%H:%M:%S")
                    self._deriv_deals_history.insert(
                        0,
                        {
                            "ticket": p["ticket"],
                            "time": ts_str,
                            "time_str": ts_str,
                            "symbol": p["symbol"],
                            "type": p.get("type", p.get("side", "BUY")),
                            "side": p.get("side", p.get("type", "BUY")),
                            "volume": p.get("volume", 0.0),
                            "price_open": p.get("price_open", 0.0),
                            "price_close": p.get("price_current", 0.0),
                            "profit": float(p.get("profit", 0.0)),
                            "reason": reason,
                            "comment": p.get("comment", ""),
                            "bot_name": p.get("comment", "Deriv"),
                        },
                    )
                else:
                    errors.append(err_msg)
            self._positions_cache = None
            self._balance_cache = None
            if errors and closed == 0:
                return 0, f"[Deriv] Falha ao zerar posições: {errors[0]}"
            suffix = f" ({len(errors)} erro(s))" if errors else ""
            return closed, f"[Deriv] {closed} contrato(s) encerrado(s) ({reason}){suffix}."

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
                    "bot_name": p.get("comment", ""),
                },
            )
        self._sim_positions.clear()
        return count, f"{count} posição(ões) zerada(s) ({reason})."

    def close_single_position(self, ticket: int | str) -> tuple[bool, str]:
        if self.cfg.connection_mode.upper() != "SIMULATION":
            if self._deriv is None:
                return False, "Deriv desconectada: não é possível encerrar contrato."
            self._positions_cache = None
            positions = self.get_open_positions()
            matched = next((p for p in positions if str(p.get("ticket")) == str(ticket)), None)
            try:
                ok, msg = self._deriv.close_contract(str(ticket))
            except Exception as exc:
                self._positions_cache = None
                return False, f"[Deriv] Erro ao encerrar #{ticket}: {exc}"
            self._positions_cache = None
            self._balance_cache = None
            if ok:
                ts_str = datetime.now().strftime("%H:%M:%S")
                self._deriv_deals_history.insert(
                    0,
                    {
                        "ticket": str(ticket),
                        "time": ts_str,
                        "time_str": ts_str,
                        "symbol": matched["symbol"] if matched else "--",
                        "type": matched.get("type", "BUY") if matched else "BUY",
                        "side": matched.get("side", "BUY") if matched else "BUY",
                        "volume": matched.get("volume", 0.0) if matched else 0.0,
                        "price_open": matched.get("price_open", 0.0) if matched else 0.0,
                        "price_close": matched.get("price_current", 0.0) if matched else 0.0,
                        "profit": float(matched.get("profit", 0.0)) if matched else 0.0,
                        "reason": "FECHAMENTO_MANUAL",
                        "comment": matched.get("comment", "") if matched else "Deriv",
                        "bot_name": matched.get("comment", "Deriv") if matched else "Deriv",
                    },
                )
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
                        "bot_name": p.get("comment", ""),
                    },
                )
                self._sim_positions.remove(p)
                return True, f"Contrato #{ticket} ({p['symbol']}) encerrado com resultado {pnl:+.2f}."
        return False, f"Contrato #{ticket} não encontrado."


class PradoTradingService:
    """Background daemon that manages Deriv Tokens, Symbols/Categories, and the Running Robot Fleet."""

    def __init__(self, cfg: PradoServerConfig, config_path: Path) -> None:
        self.cfg = cfg
        self.config_path = config_path
        self.connector = DerivUniversalConnector(cfg)
        self.connector.connect()
        self.news_scout = NewsScout()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._latest_snapshot: dict[str, Any] = {}
        self._event_log: list[dict[str, str]] = []
        self._log_event("SYSTEM", "Motor Prado Institutional HFT (Deriv Multipliers) inicializado.")

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
            self._log_event("DERIV_CONNECT", msg)
            return ok, msg

    def save_deriv_account(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        with self._lock:
            req_id = str(payload.get("account_id") or "").strip()
            existing = next((a for a in self.cfg.accounts if req_id and a.get("account_id") == req_id), None)
            acc_id = existing["account_id"] if existing else (req_id or f"deriv_{uuid.uuid4().hex[:8]}")

            token_in = str(payload.get("deriv_token", "")).strip()
            if token_in == "********" or not token_in:
                token = str(existing.get("deriv_token", "")) if existing else str(self.cfg.deriv_token or "")
            else:
                token = token_in

            app_id = str(payload.get("deriv_app_id") or (existing.get("deriv_app_id", "") if existing else "") or self.cfg.deriv_app_id or "1089").strip()
            acc_type = str(payload.get("account_type") or (existing.get("account_type", "DEMO") if existing else "DEMO")).upper()
            if acc_type not in ("DEMO", "REAL"):
                acc_type = "DEMO"
            label = str(payload.get("label") or (existing.get("label") if existing else f"Deriv {acc_type}")).strip()
            stake = float(payload.get("default_stake_usd") or self.cfg.default_stake_usd)
            mult = int(payload.get("default_multiplier") or self.cfg.default_multiplier)
            conn_mode = str(payload.get("connection_mode") or "DERIV_CLOUD").upper()

            acc_record: dict[str, Any] = {
                "account_id": acc_id,
                "account_type": acc_type,
                "label": label,
                "deriv_token": token,
                "deriv_app_id": app_id,
                "default_stake_usd": stake,
                "default_multiplier": mult,
                "connection_mode": conn_mode,
                "loginid": existing.get("loginid", "---") if existing else "---",
                "created_at": existing.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) if existing else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if existing:
                existing.update(acc_record)
            else:
                self.cfg.accounts.append(acc_record)

            self.cfg.accounts = deduplicate_accounts(self.cfg.accounts)
            self.cfg.active_account_id = acc_id
            self.cfg.active_account_type = acc_type
            self.cfg.deriv_token = token
            self.cfg.deriv_app_id = app_id
            self.cfg.default_stake_usd = stake
            self.cfg.default_multiplier = mult
            self.cfg.connection_mode = conn_mode

            ok, conn_msg = self.connector.connect(token=token, app_id=app_id)
            if ok and self.connector._deriv_auth:
                auth = self.connector._deriv_auth
                acc_record["loginid"] = str(auth.get("loginid", "---"))
                acc_record["account_type"] = "DEMO" if auth.get("is_virtual") else "REAL"
                self.cfg.active_account_type = acc_record["account_type"]

            save_config(self.cfg, self.config_path)
            self._log_event("TOKEN_VAULT", f"Token '{label}' salvo. {conn_msg}")
            return acc_record, conn_msg

    def select_active_account(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            target = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            if not target:
                return None
            self.cfg.active_account_id = str(target["account_id"])
            self.cfg.active_account_type = str(target.get("account_type", "DEMO"))
            self.cfg.deriv_token = str(target.get("deriv_token", ""))
            self.cfg.deriv_app_id = str(target.get("deriv_app_id", "1089"))
            self.cfg.default_stake_usd = float(target.get("default_stake_usd", 10.0))
            self.cfg.default_multiplier = int(target.get("default_multiplier", 100))
            self.cfg.connection_mode = str(target.get("connection_mode", "DERIV_CLOUD"))
            self.connector._balance_cache = None
            self.connector._positions_cache = None
            save_config(self.cfg, self.config_path)
            ok, msg = self.connector.connect(token=self.cfg.deriv_token, app_id=self.cfg.deriv_app_id)
            self._log_event("ACCOUNT_SWITCH", f"Token ativo alterado para [{self.cfg.active_account_type}] {target.get('label')} — {msg}")
            return {k: ("********" if k == "deriv_token" and v else v) for k, v in target.items()}

    def delete_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts = [a for a in self.cfg.accounts if a.get("account_id") != account_id]
            if self.cfg.active_account_id == account_id:
                self.cfg.active_account_id = ""
                self.cfg.deriv_token = ""
                self.connector.connect(token="")
            save_config(self.cfg, self.config_path)
            self._log_event("TOKEN_VAULT", f"Token/Conta '{account_id}' removido.")
            return self.cfg.accounts

    def clear_all_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts.clear()
            self.cfg.active_account_id = ""
            self.cfg.deriv_token = ""
            self.connector.connect(token="")
            save_config(self.cfg, self.config_path)
            self._log_event("TOKEN_VAULT", "Todos os tokens/contas foram removidos.")
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

            symbol = str(payload.get("symbol", existing_bot.get("symbol", "R_100") if existing_bot else "R_100")).strip()
            account_id = str(payload.get("account_id", self.cfg.active_account_id or "default")).strip()
            acc_obj = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            account_type = str(acc_obj.get("account_type", self.cfg.active_account_type)) if acc_obj else self.cfg.active_account_type
            account_label = acc_obj["label"] if acc_obj else f"Deriv {account_type}"

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
                "category": str(payload.get("category") or (existing_bot.get("category") if existing_bot else "Deriv")).strip(),
                "operation_mode": str(payload.get("operation_mode") or tpl_op_mode),
                "lot_size": float(payload.get("lot_size") if payload.get("lot_size") is not None else self.cfg.default_stake_usd),
                "multiplier": int(payload.get("multiplier") if payload.get("multiplier") is not None else self.cfg.default_multiplier),
                "window_ticks": int(payload.get("window_ticks") or (tpl_window if tpl_window is not None else 120)),
                "zscore_threshold": float(payload.get("zscore_threshold") if payload.get("zscore_threshold") is not None else (tpl_z if tpl_z is not None else 1.8)),
                "imbalance_threshold": float(payload.get("imbalance_threshold") if payload.get("imbalance_threshold") is not None else (tpl_imb if tpl_imb is not None else 0.35)),
                "revert_sigma": float(payload.get("revert_sigma") if payload.get("revert_sigma") is not None else (tpl_rev if tpl_rev is not None else 2.0)),
                "sl_sigma_mult": float(payload.get("sl_sigma_mult") or (tpl_sl if tpl_sl is not None else 1.0)),
                "tp_sigma_mult": float(payload.get("tp_sigma_mult") or (tpl_tp if tpl_tp is not None else 1.8)),
                "tp_mode": norm_tp_mode,
                "tp_value": norm_tp_val,
                "grid_direction": str(payload.get("grid_direction") or (existing_bot.get("grid_direction") if existing_bot else tpl.get("grid_direction", "BUY_ONLY"))).upper(),
                "grid_step_points": max(0.0001, float(payload.get("grid_step_points") or (existing_bot.get("grid_step_points") if existing_bot else tpl.get("grid_step_points", 1.5)))),
                "grid_tp_points": max(0.0001, float(payload.get("grid_tp_points") or (existing_bot.get("grid_tp_points") if existing_bot else tpl.get("grid_tp_points", 1.5)))),
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
            self._log_event("BOT_FLEET", f"Robô '{bot_record['name']}' ({symbol} | Stake ${bot_record['lot_size']} | {bot_record['multiplier']}x) salvo.")
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
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) pausado (contratos existentes mantidos).")
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
                        sym = str(b.get("symbol", "R_100"))
                        ticks = self.connector.fetch_ticks(sym, count=120)
                        vwap_b = compute_intraday_vwap(ticks)
                        last_p = ticks[-1].effective_price() if ticks else 100.0
                        bw = max(vwap_b.std_dev, abs(last_p) * 0.0020, 1e-4)
                        ord_act = "BUY_FLOW" if act == "FIRE_BUY" else "SELL_FLOW"
                        ok, msg = self.connector.place_order(
                            symbol=sym,
                            action=ord_act,
                            stake=float(b.get("lot_size", self.cfg.default_stake_usd)),
                            price=last_p,
                            sl_points=round(bw * float(b.get("sl_sigma_mult", 1.0)), 6),
                            tp_points=round(bw * float(b.get("tp_sigma_mult", 1.8)), 6),
                            multiplier=int(b.get("multiplier", self.cfg.default_multiplier)),
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

    def _sync_deriv_accounts_locked(self) -> tuple[bool, str]:
        if self.connector._deriv is None:
            return False, "Conecte um Token e App ID válidos primeiro em Configuração Deriv."
        try:
            remote_accounts = self.connector._deriv.list_accounts()
        except Exception as exc:
            return False, f"Erro ao sincronizar contas da Deriv: {exc}"
        if not remote_accounts:
            return False, "Nenhuma conta retornada pela Deriv para este token."

        synced_count = 0
        for acc in remote_accounts:
            loginid = str(acc.get("account_id") or acc.get("loginid") or "").strip()
            if not loginid or loginid == "---":
                continue
            raw_type = str(acc.get("account_type", "")).lower()
            acc_type = "DEMO" if (raw_type == "demo" or acc.get("is_virtual") in (1, True)) else "REAL"
            existing = next(
                (a for a in self.cfg.accounts if str(a.get("loginid", "")) == loginid or a.get("account_id") == f"deriv_{loginid}"),
                None,
            )
            if existing is not None:
                existing["account_type"] = acc_type
                existing["deriv_token"] = self.cfg.deriv_token
                existing["deriv_app_id"] = self.cfg.deriv_app_id
                existing["loginid"] = loginid
                existing["balance"] = float(acc.get("balance", existing.get("balance", 0.0)))
                existing["currency"] = str(acc.get("currency", existing.get("currency", "USD")))
            else:
                self.cfg.accounts.append(
                    {
                        "account_id": f"deriv_{loginid}",
                        "account_type": acc_type,
                        "label": f"Deriv {acc_type.title()} ({loginid})",
                        "deriv_token": self.cfg.deriv_token,
                        "deriv_app_id": self.cfg.deriv_app_id,
                        "default_stake_usd": self.cfg.default_stake_usd,
                        "default_multiplier": self.cfg.default_multiplier,
                        "connection_mode": "DERIV_CLOUD",
                        "loginid": loginid,
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
        return True, f"{synced_count} conta(s) Deriv sincronizada(s) com sucesso."

    def sync_deriv_accounts(self) -> tuple[bool, str, list[dict[str, Any]]]:
        with self._lock:
            if not self.cfg.deriv_token:
                msg = "Nenhum token salvo em Configuração Deriv."
                self._log_event("TOKEN_VAULT", msg)
                return False, msg, list(self.cfg.accounts)
            if self.connector._deriv is None:
                ok_conn, msg_conn = self.connector.connect(
                    token=self.cfg.deriv_token,
                    app_id=self.cfg.deriv_app_id,
                )
                if not ok_conn and self.connector._deriv is None:
                    self._log_event("TOKEN_VAULT", msg_conn)
                    return False, msg_conn, list(self.cfg.accounts)
            ok, msg = self._sync_deriv_accounts_locked()
            if ok:
                save_config(self.cfg, self.config_path)
            self._log_event("TOKEN_VAULT", msg)
            return ok, msg, list(self.cfg.accounts)

    _ALLOWED_CONFIG_UPDATE_FIELDS = frozenset({
        "admin_password_hash",
        "deriv_token",
        "deriv_app_id",
        "connection_mode",
        "active_account_id",
        "active_account_type",
        "default_stake_usd",
        "default_multiplier",
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
        "max_stake_per_trade",
        "max_concurrent_trades",
        "max_total_exposure_usd",
        "min_order_interval_sec",
        "news_bot_enabled",
        "news_pause_grid_on_high_impact",
        "news_auto_trade_enabled",
        "news_stake_usd",
        "news_multiplier",
        "news_poll_interval_sec",
    })

    def update_config(self, updates: dict[str, Any]) -> PradoServerConfig:
        with self._lock:
            for key, val in updates.items():
                if key in self._ALLOWED_CONFIG_UPDATE_FIELDS and hasattr(self.cfg, key):
                    setattr(self.cfg, key, val)
            if any(k in updates for k in ("deriv_token", "deriv_app_id", "connection_mode")):
                ok, msg = self.connector.connect()
                self._log_event("DERIV_CONFIG", msg)
                if ok and self.connector._deriv is not None:
                    s_ok, s_msg = self._sync_deriv_accounts_locked()
                    if s_ok:
                        self._log_event("TOKEN_VAULT", s_msg)
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
        symbol = str(payload.get("symbol") or "R_100").strip()
        timeframe = str(payload.get("timeframe") or "TICKS").strip().upper()
        gran = self.connector.TIMEFRAME_GRANULARITIES.get(timeframe, 0)
        ticks = self.connector.fetch_ticks(symbol, count=200, granularity=gran)
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

    def run_mathematical_backtest(self, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            symbol = str(params.get("symbol") or "R_100").strip()
            template_id = str(params.get("bot_template_id") or params.get("template_id") or "WALL_STREET_HYBRID_BOTH").strip()
            tpl = next((t for t in self.get_all_templates() if t.get("template_id") == template_id), MATH_BOT_TEMPLATES[0])
            tpl_window = tpl.get("window_ticks")
            tpl_z = tpl.get("zscore_threshold")
            tpl_imb = tpl.get("imbalance_threshold")
            tpl_rev = tpl.get("revert_sigma")
            tpl_sl = tpl.get("sl_sigma_mult")
            tpl_tp = tpl.get("tp_sigma_mult")

            tick_count = max(120, min(5000, int(params.get("tick_count") or 800)))
            initial_capital = float(params.get("initial_capital") or 10000.0)
            stake = float(params.get("lot_size") or self.cfg.default_stake_usd)
            multiplier = int(params.get("multiplier") or self.cfg.default_multiplier)
            window_ticks = int(params.get("window_ticks") or (tpl_window if tpl_window is not None else 120))
            z_thresh = float(params.get("zscore_threshold") if params.get("zscore_threshold") is not None else (tpl_z if tpl_z is not None else 1.8))
            imb_thresh = float(params.get("imbalance_threshold") if params.get("imbalance_threshold") is not None else (tpl_imb if tpl_imb is not None else 0.35))
            rev_sigma = float(params.get("revert_sigma") if params.get("revert_sigma") is not None else (tpl_rev if tpl_rev is not None else 2.0))
            sl_mult = float(params.get("sl_sigma_mult") or (tpl_sl if tpl_sl is not None else 1.0))
            tp_mult = float(params.get("tp_sigma_mult") or (tpl_tp if tpl_tp is not None else 1.8))
            op_mode = str(params.get("operation_mode") or tpl.get("operation_mode") or ("CUSTOM" if tpl.get("is_custom") else "BOTH"))

            ticks = self._build_backtest_tick_series(symbol, tick_count)
            balance = initial_capital
            peak_balance = initial_capital
            max_drawdown = 0.0
            trades: list[dict[str, Any]] = []
            open_pos: dict[str, Any] | None = None

            step_stride = max(1, tick_count // 250)
            for idx in range(40, len(ticks), step_stride):
                sub_ticks = ticks[: idx + 1]
                curr_price = sub_ticks[-1].effective_price()

                if open_pos is not None:
                    is_buy = open_pos["type"] == "BUY"
                    hit_tp = (curr_price >= open_pos["tp"]) if is_buy else (curr_price <= open_pos["tp"])
                    hit_sl = (curr_price <= open_pos["sl"]) if is_buy else (curr_price >= open_pos["sl"])
                    if hit_tp or hit_sl or idx >= len(ticks) - step_stride:
                        pct = ((curr_price - open_pos["entry"]) / open_pos["entry"]) if is_buy else ((open_pos["entry"] - curr_price) / open_pos["entry"])
                        pnl = round(pct * stake * multiplier, 2)
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
            save_config(self.cfg, self.config_path)
            self._log_event("BACKTEST", f"Backtest em {symbol}: {len(trades)} trades | Lucro: {net_profit:+.2f} | WinRate: {win_rate}%")
            return report

    def _build_backtest_tick_series(self, symbol: str, count: int) -> list[TickRecord]:
        base_price = 1850.0 if symbol == "R_100" else 1000.0
        step = base_price * 0.0005
        rng = random.Random(42 + (hash(symbol) & 0xFFFF))
        out: list[TickRecord] = []
        p = base_price
        now_msc = int(time.time() * 1000)
        for i in range(count):
            phase = i % 90
            if phase < 30:
                delta = step * 0.85 + rng.uniform(-step * 0.2, step * 0.4)
                flag = TICK_FLAG_BUY
                vol = rng.randint(60, 220)
            elif phase < 60:
                delta = -step * 0.75 + rng.uniform(-step * 0.4, step * 0.2)
                flag = TICK_FLAG_SELL
                vol = rng.randint(50, 190)
            else:
                delta = math.sin(i / 4.0) * step * 0.5
                flag = TICK_FLAG_BUY if delta >= 0 else TICK_FLAG_SELL
                vol = rng.randint(15, 65)
            p = max(step, p + delta)
            out.append(TickRecord(now_msc - (count - i) * 1000, p, p, p, 0.0, float(vol), flag))
        return out

    @staticmethod
    def _estimate_tick_step(ticks: list[TickRecord]) -> float:
        """Estimate the minimum non-zero price increment from recent ticks."""
        if len(ticks) < 2:
            return 0.0
        prices = [float(t.effective_price()) for t in ticks[-40:]]
        deltas = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        non_zero = [d for d in deltas if d > 1e-9]
        return min(non_zero) if non_zero else 0.0

    def _check_bot_tick_take_profit(
        self,
        bot: dict[str, Any],
        ticks: list[TickRecord],
        positions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Close open positions for a bot in TICKS mode when price moves >= tp_value ticks in profit."""
        norm_mode, norm_val = normalize_tp_config(bot.get("tp_mode", "AUTO"), bot.get("tp_value", 0.0))
        if norm_mode != "TICKS" or norm_val <= 0.0 or not ticks:
            return positions
        tick_step = self._estimate_tick_step(ticks)
        if tick_step <= 0.0:
            return positions

        last_price = float(ticks[-1].effective_price())
        target_dist = norm_val * tick_step
        bsym = str(bot.get("symbol", "R_100"))
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
        bsym = str(bot.get("symbol", "R_100"))
        grid_dir = str(bot.get("grid_direction", "BUY_ONLY")).upper()
        if grid_dir not in ("BUY_ONLY", "SELL_ONLY", "BOTH"):
            grid_dir = "BUY_ONLY"
        grid_step = max(0.0001, float(bot.get("grid_step_points", 1.5) or 1.5))
        grid_tp = max(0.0001, float(bot.get("grid_tp_points", 1.5) or 1.5))
        max_levels = max(1, min(20, int(bot.get("max_grid_levels", 5) or 5)))
        bot_name = str(bot.get("name", "PradoBot"))

        bot_positions = [
            p for p in positions
            if p.get("symbol") == bsym
            and (not p.get("comment") or str(p.get("comment", "")).startswith(bot_name[:14]))
        ]

        # 1. Close individual grid levels that reached take-profit distance (only when running & auto-trading active)
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

        # 2. Open new grid level if bot is active and below max_levels
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
                action = "BUY_GRID" if want_buy else "SELL_GRID"
                signal = action
                ok, msg = self.connector.place_order(
                    symbol=bsym,
                    action=action,
                    stake=float(bot.get("lot_size", self.cfg.default_stake_usd)),
                    price=last_price,
                    sl_points=grid_step * max_levels,
                    tp_points=grid_tp,
                    multiplier=int(bot.get("multiplier", self.cfg.default_multiplier)),
                    bot_name=bot_name,
                    allow_multi_same_symbol=True,
                    max_levels_override=max_levels,
                )
                if ok:
                    bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                    bot["grid_anchor_price"] = last_price
                    self._log_event("BOT_EXEC", msg)
                    positions = self.connector.get_open_positions()

        bot["last_signal"] = signal
        return positions

    def _news_snapshot_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(getattr(self.cfg, "news_bot_enabled", False)),
            "pause_grid_on_high_impact": bool(getattr(self.cfg, "news_pause_grid_on_high_impact", False)),
            "auto_trade_enabled": bool(getattr(self.cfg, "news_auto_trade_enabled", False)),
            "stake_usd": float(getattr(self.cfg, "news_stake_usd", 5.0)),
            "multiplier": int(getattr(self.cfg, "news_multiplier", 100)),
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
            default_symbol = str(payload.get("default_symbol") or "cryBTCUSD").strip()
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
        stake = float(getattr(self.cfg, "news_stake_usd", 5.0) or 5.0)
        mult = int(getattr(self.cfg, "news_multiplier", 100) or 100)
        config_dirty = False

        for item in new_items:
            if item.get("impact") != "HIGH":
                continue
            sym = str(item.get("symbol", "cryBTCUSD"))
            is_macro = bool(item.get("is_macro_usd", False))
            title = str(item.get("title", ""))

            # 1. Pause active Grid Linear bots on high-impact news to avoid range breakout losses
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

            # 2. Open directional order in favor of high-impact bullish/bearish news
            bias = str(item.get("bias", "NEUTRAL"))
            if (
                auto_trade
                and self.cfg.auto_trading_enabled
                and not risk_locked
                and bias in ("BULLISH", "BEARISH")
            ):
                if not any(p.get("symbol") == sym for p in positions):
                    ticks = self.connector.fetch_ticks(sym, count=20)
                    last_p = ticks[-1].effective_price() if ticks else 100.0
                    action = "BUY_NEWS" if bias == "BULLISH" else "SELL_NEWS"
                    ok, msg = self.connector.place_order(
                        symbol=sym,
                        action=action,
                        stake=stake,
                        price=last_p,
                        sl_points=max(last_p * 0.002, 0.5),
                        tp_points=max(last_p * 0.004, 1.0),
                        multiplier=mult,
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

    def step_once(self) -> dict[str, Any]:
        with self._lock:
            now_step = time.time()
            # Controlled heartbeat ping & reconnection for live Deriv WebSocket
            if (
                self.cfg.connection_mode.upper() != "SIMULATION"
                and self.connector._deriv is not None
                and (now_step - self.connector._last_ping_at) >= 30.0
            ):
                self.connector._last_ping_at = now_step
                if not self.connector._deriv.ping():
                    self.connector.connection_state = "RECONNECTING"
                    self.connector.connected = False
                    self._log_event("DERIV_WS", "Conexão WebSocket interrompida. Iniciando reconexão controlada...")
                    if self.connector._deriv.reconnect():
                        self.connector.connection_state = "CONNECTED"
                        self.connector.connected = True
                        self._log_event("DERIV_WS", "Reconexão WebSocket Deriv concluída.")
                    else:
                        self.connector.connection_state = "DISCONNECTED"
                        self.connector.auth_state = self.connector._deriv.auth_state
                        self.connector.backend_name = "DERIV_DISCONNECTED"
                        self._log_event("DERIV_WS", f"Falha na reconexão Deriv: {self.connector._deriv.last_error}")

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
                else self.connector._deriv_deals_history
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

                    # Per-bot News + Technical hybrid decision (only when enabled on THIS bot)
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
                                bot["last_signal"] = chosen_action
                                ok, msg = self.connector.place_order(
                                    symbol=bsym,
                                    action=chosen_action,
                                    stake=float(bot.get("lot_size", self.cfg.default_stake_usd)),
                                    price=last_price,
                                    sl_points=bot_flow.sl_points,
                                    tp_points=bot_flow.tp_points * 3.0,
                                    multiplier=int(bot.get("multiplier", self.cfg.default_multiplier)),
                                    bot_name=bname or "PradoBot",
                                    tp_usd_mult=2.5,
                                    tp_mode=str(bot.get("tp_mode", "AUTO")),
                                    tp_value=float(bot.get("tp_value", 0.0) or 0.0),
                                )
                                if ok:
                                    bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                                    self._log_event("BOT_NEWS_EXEC", msg)
                                    positions = self.connector.get_open_positions()
                        continue

                    if (
                        bot.get("status") == "RUNNING"
                        and self.cfg.auto_trading_enabled
                        and not risk_locked
                        and bot_action in ("BUY_FLOW", "SELL_FLOW", "BUY_REVERT_VWAP", "SELL_REVERT_VWAP")
                    ):
                        has_pos = any(p["symbol"] == bsym for p in positions)
                        if not has_pos:
                            ok, msg = self.connector.place_order(
                                symbol=bsym,
                                action=bot_action,
                                stake=float(bot.get("lot_size", self.cfg.default_stake_usd)),
                                price=last_price,
                                sl_points=bot_flow.sl_points,
                                tp_points=bot_flow.tp_points,
                                multiplier=int(bot.get("multiplier", self.cfg.default_multiplier)),
                                bot_name=str(bot.get("name", "PradoBot")),
                                tp_mode=str(bot.get("tp_mode", "AUTO")),
                                tp_value=float(bot.get("tp_value", 0.0) or 0.0),
                            )
                            if ok:
                                bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                                self._log_event("BOT_EXEC", msg)
                                positions = self.connector.get_open_positions()
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
            if len(self.connector._deriv_deals_history) > 500:
                del self.connector._deriv_deals_history[500:]

            active_deals = (
                self.connector._sim_deals_history
                if self.cfg.connection_mode.upper() == "SIMULATION"
                else self.connector._deriv_deals_history
            )
            self._latest_snapshot = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account": acc,
                "accounts": [
                    {k: ("********" if k == "deriv_token" and v else v) for k, v in a.items()}
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
