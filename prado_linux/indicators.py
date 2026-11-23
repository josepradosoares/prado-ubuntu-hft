from __future__ import annotations

import ast
import contextlib
import io
import math
import statistics
import sys
import time
from typing import Any

from prado_linux.flow_math import TickRecord, compute_flow_metrics, compute_intraday_vwap

INDICATOR_CATALOG: list[dict[str, Any]] = [
    # Tendência (7)
    {"id": "SMA", "name": "SMA (Média Móvel Simples)", "category": "Tendência", "default_params": {"period": 20}},
    {"id": "EMA", "name": "EMA (Cruzamento Rápida/Lenta)", "category": "Tendência", "default_params": {"fast": 9, "slow": 21}},
    {"id": "WMA", "name": "WMA (Média Móvel Ponderada)", "category": "Tendência", "default_params": {"period": 20}},
    {"id": "DEMA", "name": "DEMA (Dupla EMA)", "category": "Tendência", "default_params": {"period": 20}},
    {"id": "MACD", "name": "MACD (12, 26, 9)", "category": "Tendência", "default_params": {"fast": 12, "slow": 26, "signal": 9}},
    {"id": "ADX", "name": "ADX / +DI / -DI", "category": "Tendência", "default_params": {"period": 14, "min_adx": 20.0}},
    {"id": "PARABOLIC_SAR", "name": "Parabolic SAR", "category": "Tendência", "default_params": {"step": 0.02, "max_step": 0.2}},
    # Momento / Osciladores (7)
    {"id": "RSI", "name": "RSI (Índice de Força Relativa)", "category": "Momento", "default_params": {"period": 14, "oversold": 30.0, "overbought": 70.0}},
    {"id": "STOCHASTIC", "name": "Estocástico (%K / %D)", "category": "Momento", "default_params": {"period": 14, "oversold": 20.0, "overbought": 80.0}},
    {"id": "CCI", "name": "CCI (Commodity Channel Index)", "category": "Momento", "default_params": {"period": 20, "threshold": 100.0}},
    {"id": "WILLIAMS_R", "name": "Williams %R", "category": "Momento", "default_params": {"period": 14, "oversold": -80.0, "overbought": -20.0}},
    {"id": "ROC", "name": "ROC (Rate of Change)", "category": "Momento", "default_params": {"period": 12, "threshold": 0.0}},
    {"id": "MOMENTUM", "name": "Momentum", "category": "Momento", "default_params": {"period": 10}},
    {"id": "MFI", "name": "MFI (Money Flow Index)", "category": "Momento", "default_params": {"period": 14, "oversold": 25.0, "overbought": 75.0}},
    # Volatilidade / Canais (4)
    {"id": "BOLLINGER", "name": "Bandas de Bollinger", "category": "Volatilidade", "default_params": {"period": 20, "std_mult": 2.0}},
    {"id": "ATR", "name": "ATR (Filtro de Volatilidade)", "category": "Volatilidade", "default_params": {"period": 14}},
    {"id": "KELTNER", "name": "Canais de Keltner", "category": "Volatilidade", "default_params": {"period": 20, "atr_mult": 1.5}},
    {"id": "DONCHIAN", "name": "Canais de Donchian (Rompimento)", "category": "Volatilidade", "default_params": {"period": 20}},
    # Institucional / Fluxo (3)
    {"id": "VWAP", "name": "VWAP Intraday (±σ)", "category": "Institucional", "default_params": {"sigma_mult": 1.5}},
    {"id": "ZSCORE", "name": "Z-Score de Agressão", "category": "Institucional", "default_params": {"window": 60, "threshold": 1.8}},
    {"id": "IMBALANCE", "name": "Imbalance de Fluxo", "category": "Institucional", "default_params": {"window": 60, "threshold": 0.35}},
]

DEFAULT_PYTHON_STRATEGY_TEMPLATE = '''def evaluate(prices, ticks, params):
    """
    prices: lista de floats (preços mais recentes)
    ticks: lista de objetos TickRecord (effective_price(), tick_volume, time_msc)
    params: dicionário com parâmetros extras do robô
    Retorne "BUY", "SELL" ou "WAIT".
    """
    if len(prices) < 20:
        return "WAIT"
    ema_fast = sum(prices[-5:]) / 5.0
    ema_slow = sum(prices[-20:]) / 20.0
    if ema_fast > ema_slow * 1.0002:
        return "BUY"
    if ema_fast < ema_slow * 0.9998:
        return "SELL"
    return "WAIT"
'''


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    p = max(1, int(period))
    k = 2.0 / (p + 1.0)
    out = [float(values[0])]
    for v in values[1:]:
        out.append(float(v) * k + out[-1] * (1.0 - k))
    return out


def _wma(values: list[float], period: int) -> float:
    p = max(1, min(len(values), int(period)))
    sub = values[-p:]
    weights = list(range(1, p + 1))
    denom = sum(weights)
    return sum(v * w for v, w in zip(sub, weights)) / max(1, denom)


def _true_ranges(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        return [0.0]
    return [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]


def evaluate_single_indicator(
    ind_id: str,
    ticks: list[TickRecord],
    params: dict[str, Any] | None = None,
) -> tuple[int, float]:
    """Evaluate one of the 21 indicators. Returns (vote in {-1, 0, +1}, numeric_value)."""
    p = params or {}
    prices = [float(t.effective_price()) for t in ticks if float(t.effective_price()) > 0]
    if len(prices) < 3:
        return 0, 0.0
    last = prices[-1]
    ind = str(ind_id or "").strip().upper()

    if ind == "SMA":
        period = max(2, int(p.get("period", 20)))
        if len(prices) < period:
            return 0, last
        val = sum(prices[-period:]) / period
        return (1 if last > val else (-1 if last < val else 0)), round(val, 6)

    if ind == "EMA":
        fast = max(2, int(p.get("fast", 9)))
        slow = max(fast + 1, int(p.get("slow", 21)))
        if len(prices) < slow:
            return 0, last
        ef = _ema_series(prices, fast)[-1]
        es = _ema_series(prices, slow)[-1]
        return (1 if ef > es else (-1 if ef < es else 0)), round(ef - es, 6)

    if ind == "WMA":
        period = max(2, int(p.get("period", 20)))
        if len(prices) < period:
            return 0, last
        val = _wma(prices, period)
        return (1 if last > val else (-1 if last < val else 0)), round(val, 6)

    if ind == "DEMA":
        period = max(2, int(p.get("period", 20)))
        if len(prices) < period:
            return 0, last
        e1 = _ema_series(prices, period)
        e2 = _ema_series(e1, period)
        val = 2.0 * e1[-1] - e2[-1]
        return (1 if last > val else (-1 if last < val else 0)), round(val, 6)

    if ind == "MACD":
        fast = max(2, int(p.get("fast", 12)))
        slow = max(fast + 1, int(p.get("slow", 26)))
        sig_p = max(2, int(p.get("signal", 9)))
        if len(prices) < slow + sig_p:
            return 0, 0.0
        ef = _ema_series(prices, fast)
        es = _ema_series(prices, slow)
        macd_line = [a - b for a, b in zip(ef, es)]
        sig_line = _ema_series(macd_line, sig_p)
        hist = macd_line[-1] - sig_line[-1]
        return (1 if hist > 0 else (-1 if hist < 0 else 0)), round(hist, 6)

    if ind == "ADX":
        period = max(2, int(p.get("period", 14)))
        min_adx = float(p.get("min_adx", 20.0))
        if len(prices) < period + 2:
            return 0, 0.0
        plus_dm = []
        minus_dm = []
        trs = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            plus_dm.append(diff if diff > 0 else 0.0)
            minus_dm.append(-diff if diff < 0 else 0.0)
            trs.append(abs(diff) if abs(diff) > 0 else 1e-9)
        tr_sum = sum(trs[-period:])
        p_di = 100.0 * sum(plus_dm[-period:]) / max(1e-9, tr_sum)
        m_di = 100.0 * sum(minus_dm[-period:]) / max(1e-9, tr_sum)
        dx = 100.0 * abs(p_di - m_di) / max(1e-9, p_di + m_di)
        if dx < min_adx:
            return 0, round(dx, 2)
        return (1 if p_di > m_di else (-1 if m_di > p_di else 0)), round(dx, 2)

    if ind == "PARABOLIC_SAR":
        step = float(p.get("step", 0.02))
        max_step = float(p.get("max_step", 0.2))
        bull = prices[-1] >= prices[0]
        sar = prices[0]
        ep = prices[0]
        af = step
        for pr in prices[1:]:
            sar = sar + af * (ep - sar)
            if bull:
                if pr > ep:
                    ep = pr
                    af = min(max_step, af + step)
                if pr < sar:
                    bull = False
                    sar = ep
                    ep = pr
                    af = step
            else:
                if pr < ep:
                    ep = pr
                    af = min(max_step, af + step)
                if pr > sar:
                    bull = True
                    sar = ep
                    ep = pr
                    af = step
        return (1 if last > sar else -1), round(sar, 6)

    if ind == "RSI":
        period = max(2, int(p.get("period", 14)))
        oversold = float(p.get("oversold", 30.0))
        overbought = float(p.get("overbought", 70.0))
        if len(prices) < period + 1:
            return 0, 50.0
        deltas = [prices[i] - prices[i - 1] for i in range(-period, 0)]
        gains = sum(d for d in deltas if d > 0) / period
        losses = sum(-d for d in deltas if d < 0) / period
        if losses == 0:
            rsi = 100.0 if gains > 0 else 50.0
        else:
            rs = gains / losses
            rsi = 100.0 - (100.0 / (1.0 + rs))
        if rsi <= oversold:
            return 1, round(rsi, 2)
        if rsi >= overbought:
            return -1, round(rsi, 2)
        return 0, round(rsi, 2)

    if ind == "STOCHASTIC":
        period = max(2, int(p.get("period", 14)))
        oversold = float(p.get("oversold", 20.0))
        overbought = float(p.get("overbought", 80.0))
        if len(prices) < period:
            return 0, 50.0
        win = prices[-period:]
        hi, lo = max(win), min(win)
        k = 50.0 if hi == lo else 100.0 * (last - lo) / (hi - lo)
        if k <= oversold:
            return 1, round(k, 2)
        if k >= overbought:
            return -1, round(k, 2)
        return 0, round(k, 2)

    if ind == "CCI":
        period = max(2, int(p.get("period", 20)))
        thresh = float(p.get("threshold", 100.0))
        if len(prices) < period:
            return 0, 0.0
        win = prices[-period:]
        mean_v = sum(win) / period
        md = sum(abs(x - mean_v) for x in win) / period
        cci = 0.0 if md == 0 else (last - mean_v) / (0.015 * md)
        if cci <= -thresh:
            return 1, round(cci, 2)
        if cci >= thresh:
            return -1, round(cci, 2)
        return 0, round(cci, 2)

    if ind == "WILLIAMS_R":
        period = max(2, int(p.get("period", 14)))
        oversold = float(p.get("oversold", -80.0))
        overbought = float(p.get("overbought", -20.0))
        if len(prices) < period:
            return 0, -50.0
        win = prices[-period:]
        hi, lo = max(win), min(win)
        wr = -50.0 if hi == lo else -100.0 * (hi - last) / (hi - lo)
        if wr <= oversold:
            return 1, round(wr, 2)
        if wr >= overbought:
            return -1, round(wr, 2)
        return 0, round(wr, 2)

    if ind == "ROC":
        period = max(1, int(p.get("period", 12)))
        thresh = float(p.get("threshold", 0.0))
        if len(prices) <= period:
            return 0, 0.0
        prev = prices[-period - 1]
        roc = 0.0 if prev == 0 else ((last - prev) / prev) * 100.0
        if roc > thresh:
            return 1, round(roc, 4)
        if roc < -thresh:
            return -1, round(roc, 4)
        return 0, round(roc, 4)

    if ind == "MOMENTUM":
        period = max(1, int(p.get("period", 10)))
        if len(prices) <= period:
            return 0, 0.0
        mom = last - prices[-period - 1]
        return (1 if mom > 0 else (-1 if mom < 0 else 0)), round(mom, 6)

    if ind == "MFI":
        period = max(2, int(p.get("period", 14)))
        oversold = float(p.get("oversold", 25.0))
        overbought = float(p.get("overbought", 75.0))
        if len(ticks) < period + 1:
            return 0, 50.0
        pos_flow = 0.0
        neg_flow = 0.0
        for i in range(-period, 0):
            cur_p = float(ticks[i].effective_price())
            prev_p = float(ticks[i - 1].effective_price())
            vol = max(1.0, float(getattr(ticks[i], "tick_volume", 1.0) or 1.0))
            if cur_p >= prev_p:
                pos_flow += cur_p * vol
            else:
                neg_flow += cur_p * vol
        if neg_flow == 0:
            mfi = 100.0 if pos_flow > 0 else 50.0
        else:
            mfi = 100.0 - (100.0 / (1.0 + pos_flow / neg_flow))
        if mfi <= oversold:
            return 1, round(mfi, 2)
        if mfi >= overbought:
            return -1, round(mfi, 2)
        return 0, round(mfi, 2)

    if ind == "BOLLINGER":
        period = max(2, int(p.get("period", 20)))
        mult = float(p.get("std_mult", 2.0))
        if len(prices) < period:
            return 0, last
        win = prices[-period:]
        mid = sum(win) / period
        sd = statistics.pstdev(win) if len(win) > 1 else 0.0
        upper = mid + mult * sd
        lower = mid - mult * sd
        if last <= lower and sd > 0:
            return 1, round(lower, 6)
        if last >= upper and sd > 0:
            return -1, round(upper, 6)
        return 0, round(mid, 6)

    if ind == "ATR":
        period = max(2, int(p.get("period", 14)))
        trs = _true_ranges(prices)
        atr = sum(trs[-period:]) / max(1, min(period, len(trs)))
        # Volatility filter: votes with short-term price direction when ATR > 0
        if atr <= 0 or len(prices) < 2:
            return 0, 0.0
        return (1 if prices[-1] > prices[-2] else (-1 if prices[-1] < prices[-2] else 0)), round(atr, 6)

    if ind == "KELTNER":
        period = max(2, int(p.get("period", 20)))
        mult = float(p.get("atr_mult", 1.5))
        if len(prices) < period:
            return 0, last
        mid = _ema_series(prices, period)[-1]
        trs = _true_ranges(prices)
        atr = sum(trs[-period:]) / max(1, min(period, len(trs)))
        upper = mid + mult * atr
        lower = mid - mult * atr
        if last <= lower and atr > 0:
            return 1, round(lower, 6)
        if last >= upper and atr > 0:
            return -1, round(upper, 6)
        return 0, round(mid, 6)

    if ind == "DONCHIAN":
        period = max(2, int(p.get("period", 20)))
        if len(prices) < period + 1:
            return 0, last
        win = prices[-period - 1 : -1]
        hi, lo = max(win), min(win)
        if last > hi:
            return 1, round(hi, 6)
        if last < lo:
            return -1, round(lo, 6)
        return 0, round((hi + lo) / 2.0, 6)

    if ind == "VWAP":
        sigma_mult = float(p.get("sigma_mult", 1.5))
        vb = compute_intraday_vwap(ticks)
        if vb.std_dev <= 0:
            return 0, round(vb.vwap, 6)
        if last <= vb.vwap - sigma_mult * vb.std_dev:
            return 1, round(vb.vwap, 6)
        if last >= vb.vwap + sigma_mult * vb.std_dev:
            return -1, round(vb.vwap, 6)
        return 0, round(vb.vwap, 6)

    if ind == "ZSCORE":
        win = max(10, int(p.get("window", 60)))
        thresh = float(p.get("threshold", 1.8))
        vb = compute_intraday_vwap(ticks)
        flow = compute_flow_metrics(ticks, vb, window_size=win, z_threshold=thresh)
        z = flow.aggression_zscore
        if z >= thresh:
            return 1, round(z, 4)
        if z <= -thresh:
            return -1, round(z, 4)
        return 0, round(z, 4)

    if ind == "IMBALANCE":
        win = max(10, int(p.get("window", 60)))
        thresh = float(p.get("threshold", 0.35))
        vb = compute_intraday_vwap(ticks)
        flow = compute_flow_metrics(ticks, vb, window_size=win, imbalance_threshold=thresh)
        imb = flow.imbalance_ratio
        if imb >= thresh:
            return 1, round(imb, 4)
        if imb <= -thresh:
            return -1, round(imb, 4)
        return 0, round(imb, 4)

    return 0, 0.0


def evaluate_indicator_model(
    ticks: list[TickRecord],
    indicators_cfg: list[dict[str, Any]],
    combine_mode: str = "MAJORITY",
) -> dict[str, Any]:
    """Evaluate a list of configured indicators and combine votes into BUY / SELL / WAIT."""
    if not indicators_cfg:
        return {"signal": "WAIT", "buy_votes": 0, "sell_votes": 0, "details": []}

    details: list[dict[str, Any]] = []
    buy_votes = 0
    sell_votes = 0
    for item in indicators_cfg:
        ind_id = str(item.get("id", "")).strip().upper()
        params = dict(item.get("params") or {})
        vote, value = evaluate_single_indicator(ind_id, ticks, params)
        if vote > 0:
            buy_votes += 1
        elif vote < 0:
            sell_votes += 1
        details.append({"id": ind_id, "vote": vote, "value": value})

    total = len(indicators_cfg)
    mode = str(combine_mode or "MAJORITY").strip().upper()
    signal = "WAIT"
    if mode == "ALL":
        if buy_votes == total:
            signal = "BUY"
        elif sell_votes == total:
            signal = "SELL"
    else:
        if buy_votes > sell_votes and buy_votes >= max(1, math.ceil(total / 2.0)):
            signal = "BUY"
        elif sell_votes > buy_votes and sell_votes >= max(1, math.ceil(total / 2.0)):
            signal = "SELL"

    return {
        "signal": signal,
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "total": total,
        "details": details,
    }


_FORBIDDEN_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Delete,
    ast.With,
    ast.AsyncWith,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.Try,
    ast.Raise,
)

_FORBIDDEN_NAMES = frozenset({
    "eval",
    "exec",
    "compile",
    "open",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "breakpoint",
    "input",
    "__import__",
})


def _validate_python_strategy_ast(tree: ast.AST) -> None:
    """Reject dangerous AST constructs, imports, and dunder/private attribute access."""
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError(f"Construção Python não permitida na estratégia: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError(f"Acesso a atributo privado/dunder não permitido: {node.attr}")
        if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id in _FORBIDDEN_NAMES):
            raise ValueError(f"Identificador não permitido na estratégia: {node.id}")


def evaluate_python_model(
    code: str,
    prices: list[float],
    ticks: list[TickRecord],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and run user-supplied Python strategy code safely with AST checks and step/time limits."""
    src = str(code or "").strip()
    if not src:
        return {"ok": False, "signal": "WAIT", "elapsed_ms": 0.0, "stdout": "", "error": "Código Python vazio."}

    t0 = time.perf_counter()
    try:
        tree = ast.parse(src)
        _validate_python_strategy_ast(tree)
    except SyntaxError as exc:
        return {
            "ok": False,
            "signal": "WAIT",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "stdout": "",
            "error": f"Erro de sintaxe na linha {exc.lineno}: {exc.msg}",
        }
    except ValueError as exc:
        return {
            "ok": False,
            "signal": "WAIT",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "stdout": "",
            "error": str(exc),
        }

    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "pow": pow,
        "print": print,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    env: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "math": math,
        "statistics": statistics,
    }
    stdout_buf = io.StringIO()
    steps = 0
    deadline = t0 + 0.5
    prev_trace = sys.gettrace()

    def _trace_guard(frame: Any, event: str, arg: Any) -> Any:
        nonlocal steps
        if frame.f_code.co_filename == "<custom_strategy>":
            steps += 1
            if steps > 50_000 or time.perf_counter() > deadline:
                raise TimeoutError("Estratégia Python excedeu o limite de execução (50k passos / 500ms).")
        return _trace_guard

    try:
        with contextlib.redirect_stdout(stdout_buf):
            sys.settrace(_trace_guard)
            exec(compile(tree, "<custom_strategy>", "exec"), env, env)
            fn = env.get("evaluate")
            if not callable(fn):
                return {
                    "ok": False,
                    "signal": "WAIT",
                    "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "stdout": stdout_buf.getvalue()[:1000],
                    "error": "O código deve definir a função `def evaluate(prices, ticks, params):`.",
                }
            raw_sig = fn(list(prices), list(ticks), dict(params or {}))
    except Exception as exc:
        return {
            "ok": False,
            "signal": "WAIT",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "stdout": stdout_buf.getvalue()[:1000],
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        sys.settrace(prev_trace)

    norm = str(raw_sig or "WAIT").strip().upper()
    if norm not in ("BUY", "SELL", "WAIT"):
        norm = "WAIT"
    return {
        "ok": True,
        "signal": norm,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "stdout": stdout_buf.getvalue()[:1000],
        "error": "",
    }
