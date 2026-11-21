"""Prado Institutional HFT Trading Engine & Multi-Mode MT5 Connector for Ubuntu & Windows."""
from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path
import random
import threading
import time
from typing import Any

from prado_linux.config import PradoServerConfig, save_config
from prado_linux.flow_math import (
    TICK_FLAG_BUY,
    TICK_FLAG_SELL,
    TickRecord,
    compute_flow_metrics,
    compute_intraday_vwap,
)


class MT5UniversalConnector:
    """Connects to MetaTrader 5 natively (Windows), via Wine/RPyC Bridge (Ubuntu), or Simulation fallback."""

    def __init__(self, cfg: PradoServerConfig) -> None:
        self.cfg = cfg
        self._mt5: Any = None
        self.connected: bool = False
        self.backend_name: str = "DISCONNECTED"
        self.last_error: str = ""
        self._sim_ticks: dict[str, list[TickRecord]] = {}
        self._sim_positions: list[dict[str, Any]] = []
        self._sim_daily_pnl: float = 0.0
        self._sim_balance: float = 100_000.0

    def connect(self) -> tuple[bool, str]:
        mode = self.cfg.mt5_connection_mode.upper()

        # If simulation mode or no MT5 login configured yet, start straight in fast Quant Simulation mode
        if mode == "SIMULATION" or not self.cfg.mt5_login.strip():
            self._mt5 = None
            self.connected = True
            self.backend_name = "SIMULATION_FEED"
            return (
                True,
                "Modo Simulacao Quant Ativo (Configure Login/Senha/Servidor do MT5 no painel para conectar a corretora).",
            )

        # 1. Try Native MetaTrader5 module (Windows or Wine Python)
        if mode in ("AUTO_MT5_WINE", "NATIVE_MT5"):
            try:
                import MetaTrader5 as mt5  # type: ignore

                init_kwargs: dict[str, Any] = {}
                if self.cfg.mt5_terminal_path:
                    init_kwargs["path"] = self.cfg.mt5_terminal_path
                if self.cfg.mt5_login and self.cfg.mt5_Login_int() > 0 if hasattr(self.cfg, "mt5_Login_int") else self.cfg.mt5_login.isdigit():
                    init_kwargs["login"] = int(self.cfg.mt5_login)
                if self.cfg.mt5_password:
                    init_kwargs["password"] = self.cfg.mt5_password
                if self.cfg.mt5_server:
                    init_kwargs["server"] = self.cfg.mt5_server

                ok = mt5.initialize(**init_kwargs) if init_kwargs else mt5.initialize()
                if ok:
                    if self.cfg.mt5_login.isdigit() and self.cfg.mt5_password and self.cfg.mt5_server:
                        mt5.login(
                            login=int(self.cfg.mt5_login),
                            password=self.cfg.mt5_password,
                            server=self.cfg.mt5_server,
                        )
                    self._mt5 = mt5
                    self.connected = True
                    self.backend_name = "MT5_NATIVE"
                    self.last_error = ""
                    return True, "Conectado ao terminal MetaTrader 5 nativo com sucesso."
                else:
                    self.last_error = f"MT5 Initialize falhou: {mt5.last_error()}"
            except Exception as exc:
                self.last_error = f"Modulo nativo MT5 indisponivel: {exc}"

            # 2. Try Ubuntu Wine RPyC Bridge (mt5linux / rpyc running inside Wine Python on Ubuntu)
            try:
                import rpyc  # type: ignore

                conn = rpyc.classic.connect(self.cfg.rpyc_host, self.cfg.rpyc_port)
                mt5_remote = conn.modules.MetaTrader5
                init_kwargs = {}
                if self.cfg.mt5_login.isdigit():
                    init_kwargs["login"] = int(self.cfg.mt5_login)
                if self.cfg.mt5_password:
                    init_kwargs["password"] = self.cfg.mt5_password
                if self.cfg.mt5_server:
                    init_kwargs["server"] = self.cfg.mt5_server

                ok = mt5_remote.initialize(**init_kwargs) if init_kwargs else mt5_remote.initialize()
                if ok:
                    self._mt5 = mt5_remote
                    self.connected = True
                    self.backend_name = "UBUNTU_WINE_MT5_BRIDGE"
                    self.last_error = ""
                    return True, f"Conectado ao MT5 Headless no Ubuntu ({self.cfg.rpyc_host}:{self.cfg.rpyc_port})."
            except Exception as exc:
                self.last_error = f"Wine RPyC Bridge ({self.cfg.rpyc_host}:{self.cfg.rpyc_port}) aguardando: {exc}"

        # 3. Fallback / Simulation Mode so Web UI & Engine always work out-of-the-box
        self._mt5 = None
        self.connected = True
        self.backend_name = "SIMULATION_FEED"
        msg = (
            "Modo Simulacao Quant Ativo (Configure Login/Senha/Servidor do MT5 para operar em conta real/demo)."
            if not self.cfg.mt5_login
            else f"Modo Simulacao Quant Ativo ({self.last_error})"
        )
        return True, msg

    def get_account_summary(self) -> dict[str, Any]:
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
            "login": self.cfg.mt5_login or "SIM-990011",
            "server": self.cfg.mt5_server or "Prado-Ubuntu-QuantSim",
            "name": "Prado Institutional HFT Desk",
            "currency": "BRL/USD",
            "balance": round(self._sim_balance + self._sim_daily_pnl, 2),
            "equity": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "profit": round(floating, 2),
            "daily_realized": round(self._sim_daily_pnl, 2),
            "margin_free": round(self._sim_balance + self._sim_daily_pnl + floating, 2),
            "status_note": self.last_error,
        }

    def fetch_ticks(self, symbol: str, count: int = 1500) -> list[TickRecord]:
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
            "PETR4": 38.45,
            "VALE3": 61.20,
            "BTCUSD#": 94500.0,
            "US100Cash#": 20850.0,
            "EURUSD": 1.0540,
            "Crypto_10#": 4200.0,
        }
        base_price = base_map.get(symbol, 100.0)
        step_scale = base_price * 0.00025
        is_b3 = symbol in ("WIN$N", "WDO$N", "PETR4", "VALE3")

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

        # Append 3 new ticks on each step
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

        # Update floating profit for simulated positions
        for pos in self._sim_positions:
            sym = pos["symbol"]
            ticks = self._sim_ticks.get(sym)
            if ticks:
                curr = ticks[-1].effective_price()
                pos["price_current"] = round(curr, 6)
                diff = (curr - pos["price_open"]) if pos["type"] == "BUY" else (pos["price_open"] - curr)
                pos["profit"] = round(diff * pos["volume"] * 10.0, 2)
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
    ) -> tuple[bool, str]:
        is_buy = action.startswith("BUY")
        sl = round(price - sl_points, 6) if is_buy else round(price + sl_points, 6)
        tp = round(price + tp_points, 6) if is_buy else round(price - tp_points, 6)

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
                    "comment": f"Prado_{action}",
                    "type_time": self._mt5.ORDER_TIME_GTC,
                    "type_filling": self._mt5.ORDER_FILLING_RETURN,
                }
                res = self._mt5.order_send(req)
                if res and getattr(res, "retcode", 0) in (10008, 10009):
                    return True, f"Ordem {action} executada em {symbol} @ {exec_price}"
                return False, f"Falha order_send em {symbol}: {getattr(res, 'comment', res)}"
            except Exception as exc:
                return False, f"Excecao order_send: {exc}"

        # Simulated order execution
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
                "comment": f"Prado_{action}",
            }
        )
        return True, f"[SIM] Ordem {action} aberta em {symbol} @ {price} (SL={sl}, TP={tp})"

    def close_all_positions(self, reason: str = "MANUAL_PANIC_FLATTEN") -> tuple[int, str]:
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
            self._sim_daily_pnl += float(p.get("profit", 0.0))
        self._sim_positions.clear()
        return count, f"{count} posicao(oes) zerada(s) ({reason})."


class PradoTradingService:
    """Background daemon that computes VWAP, Order Flow Z-Score, Multi-Asset Correlation, and Risk Guard."""

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
        self._log_event("SYSTEM", "Motor Prado Institutional HFT inicializado.")

    def _log_event(self, category: str, message: str) -> None:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "category": category,
            "message": message,
        }
        self._event_log.insert(0, entry)
        if len(self._event_log) > 60:
            self._event_log = self._event_log[:60]

    def reconnect_mt5(self) -> tuple[bool, str]:
        with self._lock:
            self.connector.cfg = self.cfg
            ok, msg = self.connector.connect()
            self._log_event("MT5_CONNECT", msg)
            return ok, msg

    def update_config(self, updates: dict[str, Any]) -> PradoServerConfig:
        with self._lock:
            for key, val in updates.items():
                if hasattr(self.cfg, key):
                    setattr(self.cfg, key, val)
            save_config(self.cfg, self.config_path)
            self._log_event("CONFIG", "Configuracoes operacionais atualizadas pelo painel web.")
            return self.cfg

    def flatten_all(self, reason: str = "ZERAR_TUDO_WEB") -> tuple[int, str]:
        with self._lock:
            count, msg = self.connector.close_all_positions(reason)
            self._log_event("RISK_GUARD", msg)
            return count, msg

    def step_once(self) -> dict[str, Any]:
        with self._lock:
            now_str = datetime.now().strftime("%H:%M")

            # 1. Calculate Correlated Basket Bias (e.g. PETR4 + VALE3 + Crypto_10#)
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

            # 2. Check EOD Flatten Rule ("HFT sempre dorme zerado")
            positions = self.connector.get_open_positions()
            if self.cfg.enforce_eod_flatten and now_str >= self.cfg.eod_flatten_time and positions:
                cnt, msg = self.connector.close_all_positions("EOD_HFT_DORME_ZERADO")
                if cnt > 0:
                    self._log_event("EOD_FLATTEN", msg)
                positions = self.connector.get_open_positions()

            # 3. Check Daily Loss & Daily Target Guard
            acc = self.connector.get_account_summary()
            current_pnl = float(acc.get("profit", 0.0)) + float(acc.get("daily_realized", 0.0))
            risk_locked = False
            risk_status = "OPERACIONAL NORMAL"
            if self.cfg.max_daily_loss_money > 0 and current_pnl <= -abs(self.cfg.max_daily_loss_money):
                risk_locked = True
                risk_status = f"TRAVA DE PERDA DIARIA ATINGIDA ({current_pnl:.2f})"
                if positions:
                    self.connector.close_all_positions("MAX_DAILY_LOSS_GUARD")
            elif self.cfg.daily_target_money > 0 and current_pnl >= abs(self.cfg.daily_target_money):
                risk_locked = True
                risk_status = f"META DIARIA BATIDA ({current_pnl:.2f})"

            # 4. Compute VWAP & Order Flow per active symbol
            symbols_data: dict[str, Any] = {}
            for sym in self.cfg.active_symbols:
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

                # Auto-dispatch order if auto_trading_enabled and signal triggered
                if (
                    self.cfg.auto_trading_enabled
                    and not risk_locked
                    and action in ("BUY_FLOW", "SELL_FLOW", "BUY_REVERT_VWAP", "SELL_REVERT_VWAP")
                ):
                    has_pos = any(p["symbol"] == sym for p in positions)
                    if not has_pos:
                        ok, msg = self.connector.place_order(
                            symbol=sym,
                            action=action,
                            volume=self.cfg.default_lot_size,
                            price=last_price,
                            sl_points=flow.sl_points,
                            tp_points=flow.tp_points,
                            magic=self.cfg.magic_number,
                        )
                        if ok:
                            self._log_event("ORDER_EXEC", msg)
                            positions = self.connector.get_open_positions()

            self._latest_snapshot = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account": acc,
                "risk_status": risk_status,
                "risk_locked": risk_locked,
                "correlation_bias": corr_bias,
                "auto_trading_enabled": self.cfg.auto_trading_enabled,
                "operation_mode": self.cfg.operation_mode,
                "positions": positions,
                "symbols": symbols_data,
                "events": list(self._event_log[:25]),
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
