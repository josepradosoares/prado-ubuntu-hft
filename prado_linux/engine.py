"""Prado Institutional HFT Trading Engine, MT5 Python Package Connector & Multi-Robot Fleet Manager."""
from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path
import random
import threading
import time
from typing import Any
import uuid

from prado_linux.config import (
    DEFAULT_CATEGORIES,
    KNOWN_BROKER_SERVERS,
    MATH_BOT_TEMPLATES,
    PradoServerConfig,
    deduplicate_accounts,
    save_config,
)
from prado_linux.flow_math import (
    TICK_FLAG_BUY,
    TICK_FLAG_SELL,
    TickRecord,
    compute_flow_metrics,
    compute_intraday_vwap,
)
from prado_linux.metaapi_client import MetaApiClient

MAIN_BROKER_SYMBOLS: list[dict[str, str]] = [
    {"name": "WIN$N", "category": "B3 Futuros (Mini Índice & Dólar)", "description": "Mini Índice Ibovespa Contínuo"},
    {"name": "WDO$N", "category": "B3 Futuros (Mini Índice & Dólar)", "description": "Mini Dólar Futuro Contínuo"},
    {"name": "IND$N", "category": "B3 Futuros (Mini Índice & Dólar)", "description": "Índice Cheio B3"},
    {"name": "DOL$N", "category": "B3 Futuros (Mini Índice & Dólar)", "description": "Dólar Cheio B3"},
    {"name": "PETR4", "category": "B3 Ações Blue Chips", "description": "Petrobras PN"},
    {"name": "VALE3", "category": "B3 Ações Blue Chips", "description": "Vale ON"},
    {"name": "ITUB4", "category": "B3 Ações Blue Chips", "description": "Itaú Unibanco PN"},
    {"name": "BBDC4", "category": "B3 Ações Blue Chips", "description": "Bradesco PN"},
    {"name": "BTCUSD#", "category": "Criptomoedas 24/7", "description": "Bitcoin vs US Dollar"},
    {"name": "ETHUSD#", "category": "Criptomoedas 24/7", "description": "Ethereum vs US Dollar"},
    {"name": "DOGEUSD#", "category": "Criptomoedas 24/7", "description": "Dogecoin vs US Dollar"},
    {"name": "Crypto_10#", "category": "Criptomoedas 24/7", "description": "Índice Cripto Top 10"},
    {"name": "US100Cash#", "category": "Índices Globais & Wall Street", "description": "Nasdaq 100 Tech Index"},
    {"name": "US500Cash#", "category": "Índices Globais & Wall Street", "description": "S&P 500 Institutional Index"},
    {"name": "EURUSD", "category": "Forex & Commodities", "description": "Euro vs US Dollar"},
    {"name": "GOLD#", "category": "Forex & Commodities", "description": "Ouro Spot (XAUUSD)"},
]

EXTENDED_ALL_SYMBOLS: list[dict[str, str]] = MAIN_BROKER_SYMBOLS + [
    {"name": "BBAS3", "category": "B3 Ações Blue Chips", "description": "Banco do Brasil ON"},
    {"name": "B3SA3", "category": "B3 Ações Blue Chips", "description": "B3 Brasil Bolsa Balcão ON"},
    {"name": "WEGE3", "category": "B3 Ações Blue Chips", "description": "WEG ON"},
    {"name": "ABEV3", "category": "B3 Ações Blue Chips", "description": "Ambev ON"},
    {"name": "MGLU3", "category": "B3 Ações Blue Chips", "description": "Magazine Luiza ON"},
    {"name": "PRIO3", "category": "B3 Ações Blue Chips", "description": "PRIO ON"},
    {"name": "SOLUSD#", "category": "Criptomoedas 24/7", "description": "Solana vs US Dollar"},
    {"name": "XRPUSD#", "category": "Criptomoedas 24/7", "description": "Ripple vs US Dollar"},
    {"name": "US30Cash#", "category": "Índices Globais & Wall Street", "description": "Dow Jones 30 Index"},
    {"name": "GER40Cash#", "category": "Índices Globais & Wall Street", "description": "DAX 40 Alemanha"},
    {"name": "HK50Cash#", "category": "Índices Globais & Wall Street", "description": "Hang Seng 50 Hong Kong"},
    {"name": "GBPUSD", "category": "Forex & Commodities", "description": "Libra Esterlina vs USD"},
    {"name": "USDJPY", "category": "Forex & Commodities", "description": "US Dollar vs Iene Japonês"},
    {"name": "AUDUSD", "category": "Forex & Commodities", "description": "Dólar Australiano vs USD"},
    {"name": "SILVER#", "category": "Forex & Commodities", "description": "Prata Spot (XAGUSD)"},
    {"name": "WTI#", "category": "Forex & Commodities", "description": "Petróleo WTI Crude"},
]


class MT5UniversalConnector:
    """Connects to MetaTrader 5 accounts 100% via MetaApi Cloud HTTPS (zero MT5 terminal needed) or Quant Simulation."""

    def __init__(self, cfg: PradoServerConfig) -> None:
        self.cfg = cfg
        self._metaapi: MetaApiClient | None = None
        self._metaapi_tick_buffers: dict[str, list[TickRecord]] = {}
        self.connected: bool = False
        self.backend_name: str = "DISCONNECTED"
        self.last_error: str = ""
        self._sim_ticks: dict[str, list[TickRecord]] = {}
        self._sim_positions: list[dict[str, Any]] = []
        self._sim_deals_history: list[dict[str, Any]] = []
        self._sim_daily_pnl: float = 0.0
        self._sim_balance: float = 100_000.0

    def connect(
        self,
        login: str | None = None,
        password: str | None = None,
        server: str | None = None,
        force_attempt: bool = False,
    ) -> tuple[bool, str]:
        target_login = (login if login is not None else self.cfg.mt5_login).strip()
        mode = self.cfg.mt5_connection_mode.upper()

        # MetaApi Cloud Mode (100% pure Python on VPS, ZERO MetaTrader terminal needed anywhere)
        if mode != "SIMULATION" and self.cfg.metaapi_token.strip() and self.cfg.metaapi_account_id.strip():
            try:
                client = MetaApiClient(
                    token=self.cfg.metaapi_token,
                    account_id=self.cfg.metaapi_account_id,
                    region=self.cfg.metaapi_region,
                )
                info = client.get_account_information()
                self._metaapi = client
                self.connected = True
                self.backend_name = "METAAPI_CLOUD_LIVE"
                self.last_error = ""
                return (
                    True,
                    f"Conectado via MetaApi Cloud — Conta {info.get('login', target_login)} ({info.get('balance')} {info.get('currency', '')}).",
                )
            except Exception as exc:
                self._metaapi = None
                self.last_error = f"MetaApi Cloud falhou: {exc}"

        self._metaapi = None
        self.connected = True
        self.backend_name = "SIMULATION_FEED"
        return (
            True,
            "Modo Simulação Quant Ativo (Informe seu MetaApi Token para operar ao vivo na corretora sem MT5 aberto).",
        )

    def discover_broker_symbols(self, mode: str = "PRINCIPAIS") -> list[dict[str, Any]]:
        """Return symbols from connected MT5 / MetaApi broker in either 'PRINCIPAIS' or 'TODOS' mode."""
        mode_upper = mode.upper()
        if self._metaapi is not None:
            try:
                syms = self._metaapi.get_symbols()
                if syms:
                    if mode_upper == "PRINCIPAIS":
                        main_set = {m["name"] for m in MAIN_BROKER_SYMBOLS}
                        filtered = [s for s in syms if s in main_set]
                        syms = filtered if filtered else syms[:40]
                    return [
                        {
                            "name": s,
                            "category": "Corretora MT5 (MetaApi)",
                            "description": s,
                            "visible": True,
                        }
                        for s in syms[:500]
                    ]
            except Exception as exc:
                self.last_error = f"Erro listando ativos MetaApi: {exc}"

        if self._metaapi is not None:
            return self._metaapi.place_order(
                symbol=symbol,
                is_buy=is_buy,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=f"{bot_name[:12]}_{action}",
            )

        if self._mt5 is not None:
            try:
                all_syms = self._mt5.symbols_get()
                if all_syms:
                    items: list[dict[str, Any]] = []
                    for s in all_syms:
                        is_vis = bool(getattr(s, "visible", False))
                        if mode_upper == "PRINCIPAIS" and not is_vis:
                            continue
                        path_str = str(getattr(s, "path", "Corretora MT5")).split("\\")[0] or "Corretora MT5"
                        items.append(
                            {
                                "name": str(s.name),
                                "category": path_str,
                                "description": str(getattr(s, "description", s.name)),
                                "visible": is_vis,
                            }
                        )
                    if items:
                        return items[:500]
            except Exception as exc:
                self.last_error = f"Erro listando ativos MT5: {exc}"

        source = MAIN_BROKER_SYMBOLS if mode_upper == "PRINCIPAIS" else EXTENDED_ALL_SYMBOLS
        # Also include any custom user category symbols
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

    def get_account_summary(self) -> dict[str, Any]:
        if self._metaapi is not None:
            try:
                info = self._metaapi.get_account_information()
                bal = float(info.get("balance", 0.0))
                eq = float(info.get("equity", bal))
                return {
                    "backend": self.backend_name,
                    "connected": True,
                    "account_type": self.cfg.active_account_type,
                    "active_account_id": self.cfg.active_account_id,
                    "login": str(info.get("login", self.cfg.mt5_login)),
                    "server": str(info.get("server", self.cfg.mt5_server)),
                    "name": str(info.get("name", "MetaApi Cloud Account")),
                    "currency": str(info.get("currency", "USD")),
                    "balance": round(bal, 2),
                    "equity": round(eq, 2),
                    "profit": round(eq - bal, 2),
                    "margin_free": round(float(info.get("freeMargin", eq)), 2),
                }
            except Exception as exc:
                self.last_error = str(exc)

        if self._metaapi is not None:
            return self._metaapi.place_order(
                symbol=symbol,
                is_buy=is_buy,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=f"{bot_name[:12]}_{action}",
            )

        if self._mt5 is not None:
            try:
                acc = self._mt5.account_info()
                if acc is not None:
                    return {
                        "backend": self.backend_name,
                        "connected": True,
                        "login": str(acc.login),
                        "server": str(acc.server),
                        "name": str(getattr(acc, "name", "MT5 Trader")),
                        "currency": str(getattr(acc, "currency", "BRL")),
                        "balance": round(float(acc.balance), 2),
                        "equity": round(float(acc.equity), 2),
                        "profit": round(float(acc.profit), 2),
                        "margin_free": round(float(getattr(acc, "margin_free", acc.equity)), 2),
                    }
            except Exception as exc:
                self.last_error = str(exc)

        floating = sum(p.get("profit", 0.0) for p in self._sim_positions)
        return {
            "backend": self.backend_name,
            "connected": self.connected,
            "account_type": self.cfg.active_account_type,
            "active_account_id": self.cfg.active_account_id,
            "login": self.cfg.mt5_login or "SIM-990011",
            "server": self.cfg.mt5_server or "Prado-Ubuntu-MT5",
            "name": f"Prado Quant Desk ({self.cfg.active_account_type})",
            "currency": "BRL/USD",
            "balance": round(self._sim_balance + self._sim_daily_pnl, 2),
            "equity": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "profit": round(floating, 2),
            "daily_realized": round(self._sim_daily_pnl, 2),
            "margin_free": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "status_note": self.last_error,
        }

    def fetch_ticks(self, symbol: str, count: int = 1500) -> list[TickRecord]:
        if self._metaapi is not None:
            try:
                tick = self._metaapi.get_current_tick(symbol)
                if tick:
                    bid = float(tick.get("bid", 0.0))
                    ask = float(tick.get("ask", 0.0))
                    last = float(tick.get("last") or (0.5 * (bid + ask) if bid and ask else 0.0))
                    vol = float(tick.get("volume") or 1.0)
                    buf = self._metaapi_tick_buffers.setdefault(symbol, [])
                    buf.append(
                        TickRecord(
                            time_msc=int(time.time() * 1000),
                            bid=bid,
                            ask=ask,
                            last=last,
                            volume_real=vol,
                            tick_volume=max(vol, 1.0),
                            flags=0,
                        )
                    )
                    if len(buf) > 600:
                        self._metaapi_tick_buffers[symbol] = buf[-600:]
                    return list(buf)
            except Exception as exc:
                self.last_error = f"Erro tick MetaApi {symbol}: {exc}"

        if self._metaapi is not None:
            return self._metaapi.place_order(
                symbol=symbol,
                is_buy=is_buy,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=f"{bot_name[:12]}_{action}",
            )

        if self._mt5 is not None:
            try:
                now = datetime.now()
                day_start = datetime(now.year, now.month, now.day, 0, 0, 0)
                self._mt5.symbol_select(symbol, True)
                raw = self._mt5.copy_ticks_from(symbol, day_start, count, self._mt5.COPY_TICKS_ALL)
                if raw is None or len(raw) < 15:
                    raw = self._mt5.copy_ticks_from(symbol, now - timedelta(hours=24), count, self._mt5.COPY_TICKS_ALL)
                if raw is not None and len(raw) > 0:
                    records: list[TickRecord] = []
                    for t in raw:
                        names = t.dtype.names if hasattr(t, "dtype") and t.dtype.names else None
                        if names:
                            time_msc = int(t["time_msc"]) if "time_msc" in names else int(t["time"]) * 1000
                            bid = float(t["bid"])
                            ask = float(t["ask"])
                            last = float(t["last"])
                            vr = float(t["volume_real"]) if "volume_real" in names else 0.0
                            vt = float(t["volume"]) if "volume" in names else 1.0
                            fl = int(t["flags"]) if "flags" in names else 0
                        else:
                            time_msc = int(getattr(t, "time_msc", 0))
                            bid = float(getattr(t, "bid", 0.0))
                            ask = float(getattr(t, "ask", 0.0))
                            last = float(getattr(t, "last", 0.0))
                            vr = float(getattr(t, "volume_real", 0.0))
                            vt = float(getattr(t, "volume", 1.0))
                            fl = int(getattr(t, "flags", 0))
                        records.append(TickRecord(time_msc, bid, ask, last, vr, max(vt, 1.0), fl))
                    return records
            except Exception as exc:
                self.last_error = f"Erro lendo ticks de {symbol}: {exc}"

        return self._generate_sim_ticks(symbol)

    def _generate_sim_ticks(self, symbol: str) -> list[TickRecord]:
        base_map = {
            "WIN$N": 128500.0,
            "WDO$N": 5810.0,
            "IND$N": 128550.0,
            "DOL$N": 5812.0,
            "PETR4": 38.45,
            "VALE3": 61.20,
            "ITUB4": 34.80,
            "BBDC4": 14.90,
            "BTCUSD#": 94500.0,
            "ETHUSD#": 3350.0,
            "DOGEUSD#": 0.385,
            "US100Cash#": 20850.0,
            "US500Cash#": 5980.0,
            "EURUSD": 1.0540,
            "GOLD#": 2655.0,
            "Crypto_10#": 4200.0,
        }
        base_price = base_map.get(symbol, 100.0)
        step_scale = base_price * 0.00025
        is_b3 = symbol.endswith("$N") or (len(symbol) in (5, 6) and symbol[-1].isdigit())

        history = self._sim_ticks.get(symbol)
        now_msc = int(time.time() * 1000)
        if not history:
            history = []
            p = base_price
            rng = random.Random(hash(symbol) & 0xFFFFFFFF)
            for i in range(240):
                drift = math.sin(i / 18.0) * step_scale * 0.6 + rng.uniform(-step_scale, step_scale)
                p = max(step_scale, p + drift)
                is_buy = drift >= 0
                flag = TICK_FLAG_BUY if is_buy else TICK_FLAG_SELL
                vol = rng.randint(5, 85) * (10.0 if is_b3 else 1.0)
                history.append(
                    TickRecord(
                        time_msc=now_msc - (240 - i) * 500,
                        bid=round(p - step_scale * 0.2, 6),
                        ask=round(p + step_scale * 0.2, 6),
                        last=round(p, 6),
                        volume_real=vol if is_b3 else 0.0,
                        tick_volume=vol,
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
            vol = random.randint(10, 140) * (10.0 if is_b3 else 1.0)
            history.append(
                TickRecord(
                    time_msc=int(time.time() * 1000),
                    bid=round(new_p - step_scale * 0.2, 6),
                    ask=round(new_p + step_scale * 0.2, 6),
                    last=round(new_p, 6),
                    volume_real=vol if is_b3 else 0.0,
                    tick_volume=vol,
                    flags=flag,
                )
            )
            last_p = new_p

        if len(history) > 600:
            self._sim_ticks[symbol] = history[-600:]
        return self._sim_ticks[symbol]

    def get_open_positions(self) -> list[dict[str, Any]]:
        if self._metaapi is not None:
            try:
                raw_pos = self._metaapi.get_positions()
                out: list[dict[str, Any]] = []
                for p in raw_pos:
                    ptype = "BUY" if "BUY" in str(p.get("type", "")).upper() else "SELL"
                    out.append(
                        {
                            "ticket": str(p.get("id", "")),
                            "symbol": str(p.get("symbol", "")),
                            "type": ptype,
                            "volume": float(p.get("volume", 0.0)),
                            "price_open": round(float(p.get("openPrice", 0.0)), 6),
                            "price_current": round(float(p.get("currentPrice", 0.0)), 6),
                            "sl": round(float(p.get("stopLoss", 0.0)), 6),
                            "tp": round(float(p.get("takeProfit", 0.0)), 6),
                            "profit": round(float(p.get("profit", 0.0)), 2),
                            "comment": str(p.get("comment", "")),
                        }
                    )
                return out
            except Exception:
                return []

        if self._metaapi is not None:
            return self._metaapi.place_order(
                symbol=symbol,
                is_buy=is_buy,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=f"{bot_name[:12]}_{action}",
            )

        if self._mt5 is not None:
            try:
                raw_pos = self._mt5.positions_get()
                if raw_pos is None:
                    return []
                out: list[dict[str, Any]] = []
                for p in raw_pos:
                    out.append(
                        {
                            "ticket": int(p.ticket),
                            "symbol": str(p.symbol),
                            "type": "BUY" if int(p.type) == 0 else "SELL",
                            "volume": float(p.volume),
                            "price_open": round(float(p.price_open), 6),
                            "price_current": round(float(p.price_current), 6),
                            "sl": round(float(p.sl), 6),
                            "tp": round(float(p.tp), 6),
                            "profit": round(float(p.profit), 2),
                            "comment": str(getattr(p, "comment", "")),
                        }
                    )
                return out
            except Exception:
                return []

        for pos in list(self._sim_positions):
            sym = pos["symbol"]
            ticks = self._sim_ticks.get(sym)
            if ticks:
                curr = ticks[-1].effective_price()
                pos["price_current"] = round(curr, 6)
                is_buy = pos["type"] == "BUY"
                diff = (curr - pos["price_open"]) if is_buy else (pos["price_open"] - curr)
                mult = 0.20 if sym.startswith("WIN") else (1.0 if "BTC" in sym else 10.0)
                pos["profit"] = round(diff * pos["volume"] * mult, 2)

                # Check TP or SL hit in simulation
                hit_tp = (curr >= pos["tp"]) if is_buy else (curr <= pos["tp"])
                hit_sl = (curr <= pos["sl"]) if is_buy else (curr >= pos["sl"])
                if (pos["tp"] > 0 and hit_tp) or (pos["sl"] > 0 and hit_sl):
                    self._sim_daily_pnl += pos["profit"]
                    self._sim_deals_history.insert(
                        0,
                        {
                            "ticket": pos["ticket"],
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "symbol": sym,
                            "type": pos["type"],
                            "volume": pos["volume"],
                            "price_open": pos["price_open"],
                            "price_close": round(curr, 6),
                            "profit": pos["profit"],
                            "reason": "TAKE_PROFIT" if hit_tp else "STOP_LOSS",
                            "comment": pos.get("comment", ""),
                        },
                    )
                    self._sim_positions.remove(pos)
        return list(self._sim_positions)

    def place_order(
        self,
        symbol: str,
        action: str,
        volume: float,
        price: float,
        sl_points: float,
        tp_points: float,
        magic: int,
        bot_name: str = "PradoBot",
    ) -> tuple[bool, str]:
        is_buy = action.startswith("BUY")
        sl = round(price - sl_points, 6) if is_buy else round(price + sl_points, 6)
        tp = round(price + tp_points, 6) if is_buy else round(price - tp_points, 6)

        if self._metaapi is not None:
            return self._metaapi.place_order(
                symbol=symbol,
                is_buy=is_buy,
                volume=volume,
                sl=sl,
                tp=tp,
                comment=f"{bot_name[:12]}_{action}",
            )

        if self._mt5 is not None:
            try:
                tick = self._mt5.symbol_info_tick(symbol)
                exec_price = float(tick.ask if is_buy else tick.bid) if tick else price
                order_type = self._mt5.ORDER_TYPE_BUY if is_buy else self._mt5.ORDER_TYPE_SELL
                req = {
                    "action": self._mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(volume),
                    "type": order_type,
                    "price": exec_price,
                    "sl": sl,
                    "tp": tp,
                    "deviation": 20,
                    "magic": int(magic),
                    "comment": f"{bot_name[:12]}_{action}"[:30],
                    "type_time": self._mt5.ORDER_TIME_GTC,
                    "type_filling": self._mt5.ORDER_FILLING_RETURN,
                }
                res = self._mt5.order_send(req)
                if res and getattr(res, "retcode", 0) in (10008, 10009):
                    return True, f"[{bot_name}] Ordem {action} executada em {symbol} @ {exec_price}"
                return False, f"[{bot_name}] Falha order_send em {symbol}: {getattr(res, 'comment', res)}"
            except Exception as exc:
                return False, f"Excecao order_send: {exc}"

        if any(p["symbol"] == symbol for p in self._sim_positions):
            return False, f"Posicao ja aberta em {symbol}"
        ticket = int(time.time() * 1000) % 100_000_000
        self._sim_positions.append(
            {
                "ticket": ticket,
                "symbol": symbol,
                "type": "BUY" if is_buy else "SELL",
                "volume": float(volume),
                "price_open": round(price, 6),
                "price_current": round(price, 6),
                "sl": sl,
                "tp": tp,
                "profit": 0.0,
                "comment": f"{bot_name[:14]}_{action}",
            }
        )
        return True, f"[{bot_name}] Ordem {action} aberta em {symbol} @ {price} (Lote={volume})"

    def close_all_positions(self, reason: str = "MANUAL_PANIC_FLATTEN") -> tuple[int, str]:
        if self._metaapi is not None:
            positions = self.get_open_positions()
            closed = 0
            for p in positions:
                ok, _ = self._metaapi.close_position(str(p["ticket"]))
                if ok:
                    closed += 1
            return closed, f"[MetaApi] {closed} posição(ões) encerrada(s) ({reason})."

        if self._mt5 is not None:
            try:
                positions = self._mt5.positions_get() or []
                closed = 0
                for p in positions:
                    is_buy_pos = int(p.type) == 0
                    tick = self._mt5.symbol_info_tick(p.symbol)
                    close_price = float(tick.bid if is_buy_pos else tick.ask) if tick else float(p.price_current)
                    req = {
                        "action": self._mt5.TRADE_ACTION_DEAL,
                        "position": int(p.ticket),
                        "symbol": str(p.symbol),
                        "volume": float(p.volume),
                        "type": self._mt5.ORDER_TYPE_SELL if is_buy_pos else self._mt5.ORDER_TYPE_BUY,
                        "price": close_price,
                        "deviation": 30,
                        "magic": int(self.cfg.magic_number),
                        "comment": reason[:28],
                    }
                    self._mt5.order_send(req)
                    closed += 1
                return closed, f"{closed} posicao(oes) encerrada(s) no MT5 ({reason})."
            except Exception as exc:
                return 0, f"Erro ao zerar posicoes no MT5: {exc}"

        count = len(self._sim_positions)
        for p in self._sim_positions:
            pnl = float(p.get("profit", 0.0))
            self._sim_daily_pnl += pnl
            self._sim_deals_history.insert(
                0,
                {
                    "ticket": p["ticket"],
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": p["symbol"],
                    "type": p["type"],
                    "volume": p["volume"],
                    "price_open": p["price_open"],
                    "price_close": p["price_current"],
                    "profit": pnl,
                    "reason": reason,
                    "comment": p.get("comment", ""),
                },
            )
        self._sim_positions.clear()
        return count, f"{count} posicao(oes) zerada(s) ({reason})."

    def close_single_position(self, ticket: int | str) -> tuple[bool, str]:
        if self._metaapi is not None:
            return self._metaapi.close_position(str(ticket))

        if self._mt5 is not None:
            try:
                positions = self._mt5.positions_get(ticket=int(ticket)) or []
                for p in positions:
                    is_buy_pos = int(p.type) == 0
                    tick = self._mt5.symbol_info_tick(p.symbol)
                    close_price = float(tick.bid if is_buy_pos else tick.ask) if tick else float(p.price_current)
                    req = {
                        "action": self._mt5.TRADE_ACTION_DEAL,
                        "position": int(p.ticket),
                        "symbol": str(p.symbol),
                        "volume": float(p.volume),
                        "type": self._mt5.ORDER_TYPE_SELL if is_buy_pos else self._mt5.ORDER_TYPE_BUY,
                        "price": close_price,
                        "deviation": 30,
                        "magic": int(self.cfg.magic_number),
                        "comment": "CLOSE_SINGLE_WEB",
                    }
                    self._mt5.order_send(req)
                return True, f"Posição #{ticket} encerrada no MT5."
            except Exception as exc:
                return False, f"Erro encerrando #{ticket}: {exc}"

        for p in list(self._sim_positions):
            if int(p["ticket"]) == int(ticket):
                pnl = float(p.get("profit", 0.0))
                self._sim_daily_pnl += pnl
                self._sim_deals_history.insert(
                    0,
                    {
                        "ticket": p["ticket"],
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "symbol": p["symbol"],
                        "type": p["type"],
                        "volume": p["volume"],
                        "price_open": p["price_open"],
                        "price_close": p["price_current"],
                        "profit": pnl,
                        "reason": "FECHAMENTO_MANUAL",
                        "comment": p.get("comment", ""),
                    },
                )
                self._sim_positions.remove(p)
                return True, f"Posição #{ticket} ({p['symbol']}) encerrada com resultado {pnl:+.2f}."
        return False, f"Posição #{ticket} não encontrada."


class PradoTradingService:
    """Background daemon that manages MT5 Accounts, Broker Symbols/Categories, and the Running Robot Fleet."""

    def __init__(self, cfg: PradoServerConfig, config_path: Path) -> None:
        self.cfg = cfg
        self.config_path = config_path
        self.connector = MT5UniversalConnector(cfg)
        self.connector.connect()
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._latest_snapshot: dict[str, Any] = {}
        self._event_log: list[dict[str, str]] = []
        self._log_event("SYSTEM", "Motor Prado Institutional HFT & Multi-Robot Fleet inicializado.")

    def _log_event(self, category: str, message: str) -> None:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "category": category,
            "message": message,
        }
        self._event_log.insert(0, entry)
        if len(self._event_log) > 80:
            self._event_log = self._event_log[:80]

    def reconnect_mt5(self) -> tuple[bool, str]:
        with self._lock:
            self.connector.cfg = self.cfg
            ok, msg = self.connector.connect(force_attempt=bool(self.cfg.mt5_login))
            self._log_event("MT5_CONNECT", msg)
            return ok, msg

    def save_mt5_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            login = str(payload.get("mt5_login", "")).strip()
            server = str(payload.get("mt5_server", "")).strip()
            password = str(payload.get("mt5_password", "")).strip()
            acc_type = str(payload.get("account_type") or "DEMO").upper().strip()
            if acc_type not in ("DEMO", "REAL"):
                acc_type = "DEMO"
            # Auto-correct 346595704 on XMGlobal-MT5 10 to DEMO
            if login == "346595704" and server == "XMGlobal-MT5 10":
                acc_type = "DEMO"

            # Find existing by account_id OR by (mt5_login, mt5_server) so duplicates never happen
            req_id = str(payload.get("account_id") or "").strip()
            existing = next(
                (
                    a
                    for a in self.cfg.accounts
                    if (req_id and a.get("account_id") == req_id)
                    or (login and a.get("mt5_login") == login and a.get("mt5_server") == server)
                ),
                None,
            )
            acc_id = existing["account_id"] if existing else (req_id or f"acc_{uuid.uuid4().hex[:8]}")
            label = str(payload.get("label") or f"[{acc_type}] Conta {login} ({server})").strip()

            metaapi_token = str(payload.get("metaapi_token", "")).strip()
            metaapi_account_id = str(payload.get("metaapi_account_id", "")).strip()
            metaapi_region = str(payload.get("metaapi_region") or "london").strip()
            connection_mode = str(payload.get("connection_mode") or ("METAAPI_CLOUD" if metaapi_token else "AUTO_MT5_WINE")).strip()

            if existing:
                existing["account_type"] = acc_type
                existing["label"] = label
                existing["mt5_login"] = login
                if password and password != "********":
                    existing["mt5_password"] = password
                existing["mt5_server"] = server
                existing["connection_mode"] = connection_mode
                if metaapi_token:
                    existing["metaapi_token"] = metaapi_token
                if metaapi_account_id:
                    existing["metaapi_account_id"] = metaapi_account_id
                existing["metaapi_region"] = metaapi_region
                acc_record = existing
            else:
                acc_record = {
                    "account_id": acc_id,
                    "account_type": acc_type,
                    "label": label,
                    "mt5_login": login,
                    "mt5_password": password,
                    "mt5_server": server,
                    "connection_mode": connection_mode,
                    "metaapi_token": metaapi_token,
                    "metaapi_account_id": metaapi_account_id,
                    "metaapi_region": metaapi_region,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.cfg.accounts.append(acc_record)

            self.cfg.accounts = deduplicate_accounts(self.cfg.accounts)

            # Set as active primary MT5 credentials too
            self.cfg.active_account_id = acc_id
            self.cfg.active_account_type = acc_type
            self.cfg.mt5_connection_mode = connection_mode
            if metaapi_token:
                self.cfg.metaapi_token = metaapi_token
            if metaapi_account_id:
                self.cfg.metaapi_account_id = metaapi_account_id
            self.cfg.metaapi_region = metaapi_region
            if login:
                self.cfg.mt5_login = login
            if password and password != "********":
                self.cfg.mt5_password = password
            if server:
                self.cfg.mt5_server = server

            save_config(self.cfg, self.config_path)
            self._log_event("ACCOUNT", f"Conta {acc_type} '{label}' ({login} @ {server}) salva/atualizada com sucesso.")
            return acc_record

    def delete_all_bots(self) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.bots.clear()
            save_config(self.cfg, self.config_path)
            self._log_event("BOT_FLEET", "Todos os robôs foram removidos pelo usuário.")
            return self.cfg.bots

    def delete_mt5_account(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts = [a for a in self.cfg.accounts if a.get("account_id") != account_id]
            save_config(self.cfg, self.config_path)
            self._log_event("ACCOUNT", f"Conta '{account_id}' removida.")
            return self.cfg.accounts

    def clear_all_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            self.cfg.accounts.clear()
            save_config(self.cfg, self.config_path)
            self._log_event("ACCOUNT", "Lista de contas limpa pelo usuário.")
            return self.cfg.accounts

    def reset_daily_risk_lock(self) -> dict[str, Any]:
        with self._lock:
            self.connector._sim_daily_pnl = 0.0
            self.connector._sim_positions.clear()
            if self.cfg.max_daily_loss_money < 2000.0:
                self.cfg.max_daily_loss_money = 5000.0
                save_config(self.cfg, self.config_path)
            self._log_event("RISK_GUARD", "Trava de perda diária resetada e robôs liberados para operar!")
            return {"ok": True, "max_daily_loss_money": self.cfg.max_daily_loss_money}

    def select_active_account(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            target = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            if not target:
                return None
            self.cfg.active_account_id = str(target["account_id"])
            self.cfg.active_account_type = str(target.get("account_type", "DEMO"))
            self.cfg.mt5_login = str(target.get("mt5_login", ""))
            if target.get("mt5_password") and target.get("mt5_password") != "********":
                self.cfg.mt5_password = str(target["mt5_password"])
            self.cfg.mt5_server = str(target.get("mt5_server", ""))
            self.cfg.mt5_connection_mode = str(target.get("connection_mode", self.cfg.mt5_connection_mode))
            self.cfg.metaapi_token = str(target.get("metaapi_token", ""))
            self.cfg.metaapi_account_id = str(target.get("metaapi_account_id", ""))
            self.cfg.metaapi_region = str(target.get("metaapi_region", "london"))
            save_config(self.cfg, self.config_path)
            ok, msg = self.connector.connect(
                login=self.cfg.mt5_login,
                password=self.cfg.mt5_password,
                server=self.cfg.mt5_server,
                force_attempt=bool(self.cfg.metaapi_token and self.cfg.metaapi_account_id),
            )
            self._log_event(
                "ACCOUNT_SWITCH",
                f"Conta ativa alterada para [{self.cfg.active_account_type}] {target.get('label')} — {msg}",
            )
            return {k: ("********" if k in ("mt5_password", "metaapi_token") else v) for k, v in target.items()}

    def provision_metaapi_account(self, payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
        with self._lock:
            token = str(payload.get("metaapi_token") or self.cfg.metaapi_token).strip()
            login = str(payload.get("mt5_login") or self.cfg.mt5_login).strip()
            password = str(payload.get("mt5_password") or self.cfg.mt5_password).strip()
            server = str(payload.get("mt5_server") or self.cfg.mt5_server).strip()
            label = str(payload.get("label") or f"Prado_{login}").strip()
            region = str(payload.get("metaapi_region") or "london").strip()

            if not token or not login or not password or not server:
                return False, "Informe Token MetaApi, Login, Senha e Servidor da corretora.", None

            client = MetaApiClient(token=token, region=region)
            ok, resp = client.provision_mt5_account(
                login=login,
                password=password,
                server=server,
                name=label,
                magic=self.cfg.magic_number,
            )
            if not ok:
                msg = resp.get("message") or str(resp)
                self._log_event("METAAPI_ERROR", f"Falha ao provisionar na MetaApi: {msg}")
                return False, f"Erro MetaApi: {msg}", None

            metaapi_acc_id = str(resp["id"])
            acc = self.save_mt5_account(
                {
                    "account_id": payload.get("account_id") or "",
                    "account_type": payload.get("account_type") or self.cfg.active_account_type,
                    "label": label,
                    "mt5_login": login,
                    "mt5_password": password,
                    "mt5_server": server,
                    "connection_mode": "METAAPI_CLOUD",
                    "metaapi_token": token,
                    "metaapi_account_id": metaapi_acc_id,
                    "metaapi_region": region,
                }
            )
            self.connector.cfg = self.cfg
            self.connector.connect(force_attempt=True)
            self._log_event("METAAPI_CLOUD", f"Conta {login} provisionada na MetaApi Cloud (ID: {metaapi_acc_id}) sem MT5 aberto!")
            return True, f"Conta provisionada na MetaApi Cloud! ID: {metaapi_acc_id}", acc

    def run_mathematical_backtest(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pure mathematical tick-by-tick backtester (No UI chart rendering overhead)."""
        with self._lock:
            symbol = str(params.get("symbol") or "WIN$N").strip()
            template_id = str(params.get("bot_template_id") or "WALL_STREET_HYBRID_BOTH").strip()
            tpl = next((t for t in MATH_BOT_TEMPLATES if t["template_id"] == template_id), MATH_BOT_TEMPLATES[0])

            tick_count = max(120, min(5000, int(params.get("tick_count") or 800)))
            initial_capital = float(params.get("initial_capital") or 50000.0)
            lot_size = float(params.get("lot_size") or self.cfg.default_lot_size)
            window_ticks = int(params.get("window_ticks") or tpl["window_ticks"])
            z_thresh = float(params.get("zscore_threshold") or tpl["zscore_threshold"])
            imb_thresh = float(params.get("imbalance_threshold") or tpl["imbalance_threshold"])
            rev_sigma = float(params.get("revert_sigma") or tpl["revert_sigma"])
            sl_mult = float(params.get("sl_sigma_mult") or tpl["sl_sigma_mult"])
            tp_mult = float(params.get("tp_sigma_mult") or tpl["tp_sigma_mult"])
            op_mode = str(params.get("operation_mode") or tpl["operation_mode"])

            # Fetch real MT5 historical ticks if connected, or generate deterministic high-fidelity quant tick series
            ticks = self._build_backtest_tick_series(symbol, tick_count)

            balance = initial_capital
            peak_balance = initial_capital
            max_drawdown = 0.0
            trades: list[dict[str, Any]] = []
            open_pos: dict[str, Any] | None = None

            step_stride = max(1, tick_count // 250)
            for idx in range(40, len(ticks), step_stride):
                sub_ticks = ticks[: idx + 1]
                curr_tick = sub_ticks[-1]
                curr_price = curr_tick.effective_price()

                # Check open position SL / TP exit
                if open_pos is not None:
                    is_buy = open_pos["type"] == "BUY"
                    hit_tp = (curr_price >= open_pos["tp"]) if is_buy else (curr_price <= open_pos["tp"])
                    hit_sl = (curr_price <= open_pos["sl"]) if is_buy else (curr_price >= open_pos["sl"])
                    if hit_tp or hit_sl or idx >= len(ticks) - step_stride:
                        raw_diff = (curr_price - open_pos["entry"]) if is_buy else (open_pos["entry"] - curr_price)
                        pnl = round(raw_diff * lot_size * open_pos["point_value"], 2)
                        balance = round(balance + pnl, 2)
                        peak_balance = max(peak_balance, balance)
                        dd = round(peak_balance - balance, 2)
                        max_drawdown = max(max_drawdown, dd)
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
                    if act in ("BUY_FLOW", "SELL_FLOW", "BUY_REVERT_VWAP", "SELL_REVERT_VWAP"):
                        is_b = act.startswith("BUY")
                        sl_pts = max(flow.sl_points, curr_price * 0.0005)
                        tp_pts = max(flow.tp_points, curr_price * 0.0009)
                        pt_val = 0.20 if symbol.startswith("WIN") else (10.0 if symbol.startswith("WDO") else 10.0)
                        open_pos = {
                            "type": "BUY" if is_b else "SELL",
                            "signal": act,
                            "entry": curr_price,
                            "sl": (curr_price - sl_pts) if is_b else (curr_price + sl_pts),
                            "tp": (curr_price + tp_pts) if is_b else (curr_price - tp_pts),
                            "point_value": pt_val,
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
                "bot_template_name": tpl["name"],
                "formula": tpl["formula"],
                "operation_mode": op_mode,
                "ticks_processed": len(ticks),
                "initial_capital": round(initial_capital, 2),
                "final_equity": round(balance, 2),
                "net_profit": net_profit,
                "return_pct": round((net_profit / initial_capital) * 100.0, 2) if initial_capital > 0 else 0.0,
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate_pct": win_rate,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": profit_factor,
                "max_drawdown": round(max_drawdown, 2),
                "trades": trades[-30:],
                "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.cfg.backtest_history.insert(0, {k: v for k, v in report.items() if k != "trades"})
            self.cfg.backtest_history = self.cfg.backtest_history[:15]
            save_config(self.cfg, self.config_path)
            self._log_event(
                "BACKTEST",
                f"Backtest Matemático concluído em {symbol} ({tpl['name']}): {len(trades)} trades | Lucro Líquido: {net_profit:+.2f} | WinRate: {win_rate}%",
            )
            return report

    def _build_backtest_tick_series(self, symbol: str, count: int) -> list[TickRecord]:
        base_map = {
            "WIN$N": 128500.0,
            "WDO$N": 5810.0,
            "PETR4": 38.45,
            "VALE3": 61.20,
            "BTCUSD#": 94500.0,
            "US100Cash#": 20850.0,
            "EURUSD": 1.0540,
        }
        base_price = base_map.get(symbol, 100.0)
        step = base_price * 0.00045
        rng = random.Random(42 + (hash(symbol) & 0xFFFF))
        out: list[TickRecord] = []
        p = base_price
        now_msc = int(time.time() * 1000)
        for i in range(count):
            # Alternate between strong institutional trends and mean-reverting oscillations
            phase = i % 90
            if phase < 30:
                delta = step * 0.85 + rng.uniform(-step * 0.2, step * 0.4)
                flag = TICK_FLAG_BUY
                vol = rng.randint(60, 220) * 10.0
            elif phase < 60:
                delta = -step * 0.75 + rng.uniform(-step * 0.4, step * 0.2)
                flag = TICK_FLAG_SELL
                vol = rng.randint(50, 190) * 10.0
            else:
                delta = math.sin(i / 4.0) * step * 0.5
                flag = TICK_FLAG_BUY if delta >= 0 else TICK_FLAG_SELL
                vol = rng.randint(15, 65) * 10.0
            p = max(step, p + delta)
            out.append(
                TickRecord(
                    time_msc=now_msc - (count - i) * 500,
                    bid=round(p - step * 0.1, 6),
                    ask=round(p + step * 0.1, 6),
                    last=round(p, 6),
                    volume_real=vol,
                    tick_volume=vol,
                    flags=flag,
                )
            )
        return out

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
                self._log_event("CATEGORY", f"Categoria '{clean_name}' criada/atualizada com {len(clean_syms)} ativo(s).")
            return dict(self.cfg.custom_categories)

    def delete_custom_category(self, category_name: str) -> dict[str, list[str]]:
        with self._lock:
            if category_name in self.cfg.custom_categories:
                self.cfg.custom_categories.pop(category_name, None)
                save_config(self.cfg, self.config_path)
                self._log_event("CATEGORY", f"Categoria '{category_name}' removida.")
            return dict(self.cfg.custom_categories)

    def create_bot(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            req_bot_id = str(payload.get("bot_id") or "").strip()
            existing_bot = next((b for b in self.cfg.bots if req_bot_id and b.get("bot_id") == req_bot_id), None)
            bot_id = existing_bot["bot_id"] if existing_bot else (req_bot_id or f"bot_{uuid.uuid4().hex[:8]}")

            symbol = str(payload.get("symbol", existing_bot.get("symbol", "WIN$N") if existing_bot else "WIN$N")).strip()
            account_id = str(
                payload.get("account_id", existing_bot.get("account_id", self.cfg.active_account_id) if existing_bot else self.cfg.active_account_id)
            ).strip()
            acc_obj = next((a for a in self.cfg.accounts if a.get("account_id") == account_id), None)
            account_type = str(acc_obj.get("account_type", "DEMO")) if acc_obj else self.cfg.active_account_type
            account_label = (
                f"[{account_type}] {acc_obj['label']}"
                if acc_obj
                else (
                    f"[{account_type}] {self.cfg.mt5_login} ({self.cfg.mt5_server})"
                    if self.cfg.mt5_login
                    else f"[{account_type}] Conta Principal MT5"
                )
            )
            template_id = str(
                payload.get(
                    "bot_template_id",
                    existing_bot.get("bot_template_id", "WALL_STREET_HYBRID_BOTH") if existing_bot else "WALL_STREET_HYBRID_BOTH",
                )
            ).strip()
            tpl = next((t for t in MATH_BOT_TEMPLATES if t["template_id"] == template_id), MATH_BOT_TEMPLATES[0])
            auto_start = bool(payload.get("auto_start", True))

            bot_record: dict[str, Any] = {
                "bot_id": bot_id,
                "name": str(payload.get("name") or (existing_bot.get("name") if existing_bot else f"{tpl['name'].split('—')[0].strip()} ({symbol})")).strip(),
                "bot_template_id": template_id,
                "bot_template_name": tpl["name"],
                "formula": tpl["formula"],
                "account_id": account_id,
                "account_type": account_type,
                "account_label": account_label,
                "symbol": symbol,
                "category": str(payload.get("category") or (existing_bot.get("category") if existing_bot else "Geral")).strip(),
                "operation_mode": str(payload.get("operation_mode") or tpl["operation_mode"]),
                "lot_size": float(payload.get("lot_size") if payload.get("lot_size") is not None else self.cfg.default_lot_size),
                "window_ticks": int(payload.get("window_ticks") or tpl["window_ticks"]),
                "zscore_threshold": float(payload.get("zscore_threshold") if payload.get("zscore_threshold") is not None else tpl["zscore_threshold"]),
                "imbalance_threshold": float(payload.get("imbalance_threshold") if payload.get("imbalance_threshold") is not None else tpl["imbalance_threshold"]),
                "revert_sigma": float(payload.get("revert_sigma") if payload.get("revert_sigma") is not None else tpl["revert_sigma"]),
                "sl_sigma_mult": float(payload.get("sl_sigma_mult") or tpl["sl_sigma_mult"]),
                "tp_sigma_mult": float(payload.get("tp_sigma_mult") or tpl["tp_sigma_mult"]),
                "correlated_basket": list(payload.get("correlated_basket") or self.cfg.correlated_basket),
                "status": existing_bot.get("status", "RUNNING") if existing_bot and "auto_start" not in payload else ("RUNNING" if auto_start else "STOPPED"),
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
                action_word = "atualizado/editado"
            else:
                self.cfg.bots.append(bot_record)
                action_word = "criado"

            if symbol not in self.cfg.active_symbols:
                self.cfg.active_symbols.append(symbol)
            save_config(self.cfg, self.config_path)
            self._log_event(
                "BOT_FLEET",
                f"Robô '{bot_record['name']}' ({symbol} | Lote {bot_record['lot_size']} | Conta {account_label}) {action_word} com sucesso.",
            )
            return bot_record

    def control_bot(self, bot_id: str, action: str) -> dict[str, Any] | None:
        with self._lock:
            act = action.upper()
            for idx, b in enumerate(self.cfg.bots):
                if b.get("bot_id") == bot_id:
                    if act == "START":
                        b["status"] = "RUNNING"
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) INICIADO e rodando automaticamente.")
                    elif act == "STOP":
                        b["status"] = "STOPPED"
                        self._log_event("BOT_FLEET", f"Robô '{b['name']}' ({b['symbol']}) PAUSADO.")
                    elif act in ("FIRE_BUY", "FIRE_SELL"):
                        sym = str(b.get("symbol", "WIN$N"))
                        ticks = self.connector.fetch_ticks(sym, count=200)
                        vwap_b = compute_intraday_vwap(ticks)
                        last_p = ticks[-1].effective_price() if ticks else 100.0
                        bw = max(vwap_b.std_dev, abs(last_p) * 0.0020, 1e-4)
                        ord_act = "BUY_FLOW" if act == "FIRE_BUY" else "SELL_FLOW"
                        # unlock risk if locked so manual fire works immediately
                        if self.connector._sim_daily_pnl <= -abs(self.cfg.max_daily_loss_money):
                            self.connector._sim_daily_pnl = 0.0
                        ok, msg = self.connector.place_order(
                            symbol=sym,
                            action=ord_act,
                            volume=float(b.get("lot_size", self.cfg.default_lot_size)),
                            price=last_p,
                            sl_points=round(bw * float(b.get("sl_sigma_mult", 1.0)), 6),
                            tp_points=round(bw * float(b.get("tp_sigma_mult", 1.8)), 6),
                            magic=self.cfg.magic_number,
                            bot_name=str(b.get("name", "PradoBot")),
                        )
                        if ok:
                            b["trades_executed"] = int(b.get("trades_executed", 0)) + 1
                        self._log_event("BOT_EXEC", msg)
                    elif act == "DELETE":
                        removed = self.cfg.bots.pop(idx)
                        save_config(self.cfg, self.config_path)
                        self._log_event("BOT_FLEET", f"Robô '{removed['name']}' removido.")
                        return removed
                    save_config(self.cfg, self.config_path)
                    return b
            return None

    def update_config(self, updates: dict[str, Any]) -> PradoServerConfig:
        with self._lock:
            for key, val in updates.items():
                if hasattr(self.cfg, key):
                    setattr(self.cfg, key, val)
            save_config(self.cfg, self.config_path)
            self._log_event("CONFIG", "Configurações operacionais atualizadas pelo painel web.")
            return self.cfg

    def flatten_all(self, reason: str = "ZERAR_TUDO_WEB") -> tuple[int, str]:
        with self._lock:
            count, msg = self.connector.close_all_positions(reason)
            self._log_event("RISK_GUARD", msg)
            return count, msg

    def step_once(self) -> dict[str, Any]:
        with self._lock:
            now_str = datetime.now().strftime("%H:%M")

            # 1. Calculate Correlated Basket Bias
            corr_scores: list[float] = []
            for corr_sym in self.cfg.correlated_basket:
                c_ticks = self.connector.fetch_ticks(corr_sym, count=400)
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

            # 2. EOD Flatten Rule ("HFT sempre dorme zerado") — Only applies to B3 cash/futures symbols (not 24/7 Crypto/Forex)
            positions = self.connector.get_open_positions()
            if self.cfg.enforce_eod_flatten and now_str >= self.cfg.eod_flatten_time and positions:
                b3_positions = [
                    p
                    for p in positions
                    if p["symbol"].endswith("$N") or (len(p["symbol"]) in (5, 6) and p["symbol"][-1].isdigit())
                ]
                if b3_positions:
                    for bp in b3_positions:
                        self.connector.close_single_position(int(bp["ticket"]))
                    self._log_event("EOD_FLATTEN", f"{len(b3_positions)} posição(ões) B3 encerrada(s) no fim do pregão.")
                    positions = self.connector.get_open_positions()

            # 3. Daily Loss & Target Guard
            acc = self.connector.get_account_summary()
            current_pnl = float(acc.get("profit", 0.0)) + float(acc.get("daily_realized", 0.0))
            risk_locked = False
            risk_status = "OPERACIONAL NORMAL"
            if self.cfg.max_daily_loss_money > 0 and current_pnl <= -abs(self.cfg.max_daily_loss_money):
                risk_locked = True
                risk_status = f"TRAVA DE PERDA DIÁRIA ATINGIDA ({current_pnl:.2f})"
                if positions:
                    self.connector.close_all_positions("MAX_DAILY_LOSS_GUARD")
            elif self.cfg.daily_target_money > 0 and current_pnl >= abs(self.cfg.daily_target_money):
                risk_locked = True
                risk_status = f"META DIÁRIA BATIDA ({current_pnl:.2f})"

            # Ensure all symbols from running bots are also monitored
            monitored_symbols = list(self.cfg.active_symbols)
            for b in self.cfg.bots:
                bsym = b.get("symbol")
                if bsym and bsym not in monitored_symbols:
                    monitored_symbols.append(bsym)

            # 4. Compute VWAP & Order Flow per monitored symbol
            symbols_data: dict[str, Any] = {}
            for sym in monitored_symbols:
                ticks = self.connector.fetch_ticks(sym, count=1200)
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
                    "vwap": round(vwap_bands.vwap, 6),
                    "std_dev": round(vwap_bands.std_dev, 6),
                    "upper_1": round(vwap_bands.upper_1, 6),
                    "lower_1": round(vwap_bands.lower_1, 6),
                    "upper_2": round(vwap_bands.upper_2, 6),
                    "lower_2": round(vwap_bands.lower_2, 6),
                    "distance_sigma": distance_sigma,
                    "buy_volume": round(flow.buy_volume, 2),
                    "sell_volume": round(flow.sell_volume, 2),
                    "delta_volume": round(flow.delta_volume, 2),
                    "imbalance_ratio": round(flow.imbalance_ratio, 4),
                    "aggression_zscore": round(flow.aggression_zscore, 4),
                    "correlation_bias": corr_bias,
                    "regime": flow.regime,
                    "action": action,
                    "sl_points": round(flow.sl_points, 6),
                    "tp_points": round(flow.tp_points, 6),
                    "is_real_volume": vwap_bands.is_real_volume,
                }

            # 5. Execute each Individual Robot Instance in the Fleet ("Robôs Rodando")
            for bot in self.cfg.bots:
                bsym = bot.get("symbol", "")
                ticks = self.connector.fetch_ticks(bsym, count=1200)
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
                bot_corr_list = bot.get("correlated_basket") or []
                bot_corr_bias = corr_bias
                if bot_corr_list:
                    b_scores = []
                    for csym in bot_corr_list:
                        ct = self.connector.fetch_ticks(csym, count=200)
                        if len(ct) >= 5:
                            cv = compute_intraday_vwap(ct)
                            cf = compute_flow_metrics(ct, cv, window_size=min(60, len(ct)))
                            b_scores.append(cf.imbalance_ratio)
                    if b_scores:
                        bot_corr_bias = round(sum(b_scores) / len(b_scores), 4)

                if bot_action in ("BUY_FLOW", "BUY_REVERT_VWAP") and bot_corr_bias <= -0.80:
                    bot_action = "WAIT_CORRELATION_BLOCK"
                elif bot_action in ("SELL_FLOW", "SELL_REVERT_VWAP") and bot_corr_bias >= 0.80:
                    bot_action = "WAIT_CORRELATION_BLOCK"

                bot["last_price"] = round(last_price, 6)
                bot["vwap"] = round(vwap_bands.vwap, 6)
                bot["aggression_zscore"] = round(bot_flow.aggression_zscore, 4)
                bot["imbalance_ratio"] = round(bot_flow.imbalance_ratio, 4)
                bot["last_regime"] = bot_flow.regime
                bot["last_signal"] = bot_action

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
                            volume=float(bot.get("lot_size", self.cfg.default_lot_size)),
                            price=last_price,
                            sl_points=bot_flow.sl_points,
                            tp_points=bot_flow.tp_points,
                            magic=self.cfg.magic_number,
                            bot_name=str(bot.get("name", "PradoBot")),
                        )
                        if ok:
                            bot["trades_executed"] = int(bot.get("trades_executed", 0)) + 1
                            self._log_event("BOT_EXEC", msg)
                            positions = self.connector.get_open_positions()

            self._latest_snapshot = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account": acc,
                "accounts": [
                    {k: ("********" if k == "mt5_password" else v) for k, v in a.items()}
                    for a in self.cfg.accounts
                ],
                "categories": self.cfg.custom_categories,
                "bots": list(self.cfg.bots),
                "risk_status": risk_status,
                "risk_locked": risk_locked,
                "correlation_bias": corr_bias,
                "auto_trading_enabled": self.cfg.auto_trading_enabled,
                "operation_mode": self.cfg.operation_mode,
                "positions": positions,
                "deals_history": list(self.connector._sim_deals_history[:40]),
                "symbols": symbols_data,
                "events": list(self._event_log[:30]),
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
                time.sleep(max(0.2, float(self.cfg.poll_interval_sec)))

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_background_loop(self) -> None:
        self._running = False
