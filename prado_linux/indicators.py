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
    {
        "id": "SMA",
        "name": "SMA (Média Móvel Simples)",
        "category": "Tendência",
        "description": "Com Média Lenta = 0 compara Preço × Média; com Média Lenta > 0 (ex.: 50×200) opera cruzamento entre as duas SMAs.",
        "default_params": {"period": 20, "slow": 0, "crossover_only": 0},
    },
    {
        "id": "EMA",
        "name": "EMA (Cruzamento Rápida/Lenta)",
        "category": "Tendência",
        "description": "Compra quando a média rápida fica/cruza acima da lenta; vende abaixo.",
        "default_params": {"fast": 9, "slow": 21, "crossover_only": 0},
    },
    {
        "id": "WMA",
        "name": "WMA (Média Móvel Ponderada)",
        "category": "Tendência",
        "description": "Com Média Lenta = 0 compara Preço × WMA; com Média Lenta > 0 opera cruzamento entre duas WMAs.",
        "default_params": {"period": 20, "slow": 0, "crossover_only": 0},
    },
    {
        "id": "DEMA",
        "name": "DEMA (Dupla EMA)",
        "category": "Tendência",
        "description": "Média dupla com menor atraso; use Média Lenta = 0 (Preço × DEMA) ou > 0 para cruzar duas DEMAs.",
        "default_params": {"period": 20, "slow": 0, "crossover_only": 0},
    },
    {
        "id": "MACD",
        "name": "MACD (12, 26, 9)",
        "category": "Tendência",
        "description": "Mede força da tendência pelo histograma; compra acima de 0 (ou no cruzamento) e vende abaixo.",
        "default_params": {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 0},
    },
    {
        "id": "ADX",
        "name": "ADX / +DI / -DI",
        "category": "Tendência",
        "description": "Exige ADX ≥ mínimo; opera posição ou apenas o cruzamento de +DI sobre -DI.",
        "default_params": {"period": 14, "min_adx": 20.0, "crossover_only": 0},
    },
    {
        "id": "PARABOLIC_SAR",
        "name": "Parabolic SAR",
        "category": "Tendência",
        "description": "Acompanha tendência pelo SAR; opera posição atual ou apenas a virada (flip) dos pontos.",
        "default_params": {"step": 0.02, "max_step": 0.2, "crossover_only": 0},
    },
    # Momento / Osciladores (7)
    {
        "id": "RSI",
        "name": "RSI (Índice de Força Relativa)",
        "category": "Momento",
        "description": "Suporta 3 modos: Reversão (≤30/≥70), Tendência (>50/<50) ou Cruzamento (saindo de 30/70).",
        "default_params": {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 0},
    },
    {
        "id": "STOCHASTIC",
        "name": "Estocástico (%K / %D)",
        "category": "Momento",
        "description": "Oscilador de curto prazo; opera zona extrema (20/80) ou cruzamento de %K sobre %D na zona.",
        "default_params": {"period": 14, "d_period": 3, "oversold": 20.0, "overbought": 80.0, "crossover_only": 0},
    },
    {
        "id": "CCI",
        "name": "CCI (Commodity Channel Index)",
        "category": "Momento",
        "description": "Detecta desvios cíclicos extremos; compra ≤ -limite e vende ≥ +limite.",
        "default_params": {"period": 20, "threshold": 100.0},
    },
    {
        "id": "WILLIAMS_R",
        "name": "Williams %R",
        "category": "Momento",
        "description": "Mede posição do fechamento na máxima/mínima; compra ≤ -80 e vende ≥ -20.",
        "default_params": {"period": 14, "oversold": -80.0, "overbought": -20.0},
    },
    {
        "id": "ROC",
        "name": "ROC (Rate of Change)",
        "category": "Momento",
        "description": "Variação percentual do preço; compra se aceleração positiva > limite e vende se negativa.",
        "default_params": {"period": 12, "threshold": 0.0},
    },
    {
        "id": "MOMENTUM",
        "name": "Momentum",
        "category": "Momento",
        "description": "Diferença direta para o preço anterior; compra com momentum positivo e vende com negativo.",
        "default_params": {"period": 10},
    },
    {
        "id": "MFI",
        "name": "MFI (Money Flow Index)",
        "category": "Momento",
        "description": "RSI ponderado pelo volume; compra em fluxo sobrevendido e vende em sobrecomprado.",
        "default_params": {"period": 14, "oversold": 25.0, "overbought": 75.0},
    },
    # Volatilidade / Canais (4)
    {
        "id": "BOLLINGER",
        "name": "Bandas de Bollinger",
        "category": "Volatilidade",
        "description": "Retorno à média nas bandas externas; compra na banda inferior e vende na superior.",
        "default_params": {"period": 20, "std_mult": 2.0},
    },
    {
        "id": "ATR",
        "name": "ATR (Filtro de Volatilidade)",
        "category": "Volatilidade",
        "description": "Confirma presença de volatilidade (ATR > 0) e vota na direção do último movimento.",
        "default_params": {"period": 14},
    },
    {
        "id": "KELTNER",
        "name": "Canais de Keltner",
        "category": "Volatilidade",
        "description": "Envelope EMA ± ATR; compra ao tocar banda inferior e vende na banda superior.",
        "default_params": {"period": 20, "atr_mult": 1.5},
    },
    {
        "id": "DONCHIAN",
        "name": "Canais de Donchian (Rompimento)",
        "category": "Volatilidade",
        "description": "Segue rompimentos; compra acima da máxima da janela e vende abaixo da mínima.",
        "default_params": {"period": 20},
    },
    # Institucional / Fluxo (3)
    {
        "id": "VWAP",
        "name": "VWAP Intraday (±σ)",
        "category": "Institucional",
        "description": "Retorno ao preço justo institucional; compra em -k·σ e vende em +k·σ da VWAP.",
        "default_params": {"sigma_mult": 1.5},
    },
    {
        "id": "ZSCORE",
        "name": "Z-Score de Agressão",
        "category": "Institucional",
        "description": "Mede força estatística das agressões; compra em Z ≥ limite e vende em Z ≤ -limite.",
        "default_params": {"window": 60, "threshold": 1.8},
    },
    {
        "id": "IMBALANCE",
        "name": "Imbalance de Fluxo",
        "category": "Institucional",
        "description": "Saldo líquido comprador vs vendedor; compra com fluxo positivo forte e vende com negativo.",
        "default_params": {"window": 60, "threshold": 0.35},
    },
]

READY_MADE_RECIPES: list[dict[str, Any]] = [
    {
        "id": "RECIPE_EMA_ADX_TREND",
        "name": "Cruzamento EMA 9×21 + Filtro ADX",
        "style": "Tendência",
        "markets": "US100, XAUUSD, EURUSD",
        "recommended_timeframe": "M5",
        "description": "Entra no cruzamento das EMAs 9×21 apenas quando o ADX confirma tendência firme (≥ 20).",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "EMA", "params": {"fast": 9, "slow": 21, "crossover_only": 1}},
            {"id": "ADX", "params": {"period": 14, "min_adx": 20.0}},
        ],
    },
    {
        "id": "RECIPE_MACRO_MICRO_EMA",
        "name": "Tendência Macro (EMA 50×200) + Gatilho (EMA 9×21)",
        "style": "Tendência",
        "markets": "US100, US500, XAUUSD",
        "recommended_timeframe": "M5",
        "description": "Usa EMA 50×200 para filtrar a direção principal e o cruzamento EMA 9×21 como gatilho de entrada.",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "EMA", "params": {"fast": 50, "slow": 200, "crossover_only": 0}},
            {"id": "EMA", "params": {"fast": 9, "slow": 21, "crossover_only": 1}},
        ],
    },
    {
        "id": "RECIPE_MACD_RSI_TREND",
        "name": "MACD Cruzamento + Força RSI > 50",
        "style": "Momentum",
        "markets": "EURUSD, GBPUSD, US100",
        "recommended_timeframe": "M5",
        "description": "Captura viradas do histograma MACD confirmadas pelo RSI em modo Tendência (> 50 compra, < 50 vende).",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1}},
            {"id": "RSI", "params": {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 1}},
        ],
    },
    {
        "id": "RECIPE_DONCHIAN_ADX_BREAKOUT",
        "name": "Rompimento Donchian + ADX",
        "style": "Rompimento",
        "markets": "US100, XAUUSD, BTCUSD",
        "recommended_timeframe": "M15",
        "description": "Opera rompimentos de máxima/mínima dos últimos 20 candles filtrados por ADX ≥ 22.",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "DONCHIAN", "params": {"period": 20}},
            {"id": "ADX", "params": {"period": 14, "min_adx": 22.0}},
        ],
    },
    {
        "id": "RECIPE_BOLLINGER_RSI_REVERT",
        "name": "Reversão Bollinger + RSI 30/70",
        "style": "Reversão",
        "markets": "EURUSD, GBPUSD, USDCHF",
        "recommended_timeframe": "M5",
        "description": "Compra toques na banda inferior de Bollinger com RSI sobrevendido (≤ 30) e vende nos extremos opostos.",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "BOLLINGER", "params": {"period": 20, "std_mult": 2.0}},
            {"id": "RSI", "params": {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 0}},
        ],
    },
    {
        "id": "RECIPE_STOCH_VWAP_REVERT",
        "name": "Reversão Estocástico + VWAP ±1.5σ",
        "style": "Reversão",
        "markets": "EURUSD, XAUUSD",
        "recommended_timeframe": "M5",
        "description": "Busca retorno à VWAP quando o preço estica ±1.5σ e o Estocástico marca exaustão (20/80).",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "STOCHASTIC", "params": {"period": 14, "oversold": 20.0, "overbought": 80.0}},
            {"id": "VWAP", "params": {"sigma_mult": 1.5}},
        ],
    },
    {
        "id": "RECIPE_PSAR_EMA_PULLBACK",
        "name": "Pullback Parabolic SAR + SMA 21",
        "style": "Pullback",
        "markets": "US100, XAUUSD, GBPUSD",
        "recommended_timeframe": "M5",
        "description": "Entra em continuação de movimento quando Parabolic SAR e preço ficam do mesmo lado da SMA 21.",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "PARABOLIC_SAR", "params": {"step": 0.02, "max_step": 0.2}},
            {"id": "SMA", "params": {"period": 21, "crossover_only": 0}},
        ],
    },
    {
        "id": "RECIPE_INSTITUTIONAL_FLOW",
        "name": "Scalping Institucional (VWAP + Z-Score + Fluxo)",
        "style": "Scalping Fluxo",
        "markets": "XAUUSD, US100, BTCUSD",
        "recommended_timeframe": "M1",
        "description": "Combina VWAP, Z-Score de agressão e Imbalance por maioria para surfar acelerações rápidas de fluxo.",
        "combine_mode": "MAJORITY",
        "indicators": [
            {"id": "VWAP", "params": {"sigma_mult": 1.5}},
            {"id": "ZSCORE", "params": {"window": 60, "threshold": 1.8}},
            {"id": "IMBALANCE", "params": {"window": 60, "threshold": 0.35}},
        ],
    },
    {
        "id": "RECIPE_GOLDEN_CROSS_SMA_ADX",
        "name": "Golden Cross SMA 50×200 + Filtro ADX",
        "style": "Tendência",
        "markets": "US100, US500, XAUUSD",
        "recommended_timeframe": "H1",
        "description": "Clássico institucional de tendência longa: entra no cruzamento da SMA 50 sobre a SMA 200 confirmado por ADX ≥ 20.",
        "combine_mode": "ALL",
        "indicators": [
            {"id": "SMA", "params": {"period": 50, "slow": 200, "crossover_only": 1}},
            {"id": "ADX", "params": {"period": 14, "min_adx": 20.0, "crossover_only": 0}},
        ],
    },
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


def _crossover_or_position_vote(
    curr_diff: float,
    prev_diff: float,
    crossover_only: bool,
    display_value: float,
) -> tuple[int, float]:
    """Return +1/-1/0 either on zero-crossing only or on current positive/negative position."""
    val = round(display_value, 6)
    if crossover_only:
        if prev_diff <= 0.0 and curr_diff > 0.0:
            return 1, val
        if prev_diff >= 0.0 and curr_diff < 0.0:
            return -1, val
        return 0, val
    return (1 if curr_diff > 0.0 else (-1 if curr_diff < 0.0 else 0)), val


def _dema_series(values: list[float], period: int) -> list[float]:
    e1 = _ema_series(values, period)
    e2 = _ema_series(e1, period)
    return [2.0 * a - b for a, b in zip(e1, e2)]


def _calc_rsi(prices: list[float], period: int) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(-period, 0)]
    gains = sum(d for d in deltas if d > 0) / period
    losses = sum(-d for d in deltas if d < 0) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = gains / losses
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_stoch_k(prices: list[float], period: int) -> float:
    win = prices[-period:]
    hi, lo = max(win), min(win)
    if hi == lo:
        return 50.0
    return 100.0 * (prices[-1] - lo) / (hi - lo)


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

    if ind in ("SMA", "WMA", "DEMA"):
        period = max(2, int(p.get("period", 20)))
        slow = max(0, int(p.get("slow", 0) or 0))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        req_p = max(period + 1, slow) if slow > 0 else period
        if len(prices) < req_p + (1 if crossover_only else 0):
            return 0, last

        if ind == "SMA":
            fast_cur = sum(prices[-period:]) / period
            fast_prev = sum(prices[-period - 1 : -1]) / period if crossover_only else 0.0
            slow_cur = sum(prices[-req_p:]) / req_p if slow > 0 else fast_cur
            slow_prev = sum(prices[-req_p - 1 : -1]) / req_p if (slow > 0 and crossover_only) else 0.0
        elif ind == "WMA":
            fast_cur = _wma(prices, period)
            fast_prev = _wma(prices[:-1], period) if crossover_only else 0.0
            slow_cur = _wma(prices, req_p) if slow > 0 else fast_cur
            slow_prev = _wma(prices[:-1], req_p) if (slow > 0 and crossover_only) else 0.0
        else:
            f_series = _dema_series(prices, period)
            fast_cur = f_series[-1]
            fast_prev = f_series[-2] if crossover_only else 0.0
            if slow > 0:
                s_series = _dema_series(prices, req_p)
                slow_cur = s_series[-1]
                slow_prev = s_series[-2] if crossover_only else 0.0
            else:
                slow_cur = fast_cur
                slow_prev = fast_prev

        if slow > 0:
            curr_diff = fast_cur - slow_cur
            prev_diff = fast_prev - slow_prev
            return _crossover_or_position_vote(curr_diff, prev_diff, crossover_only, curr_diff)

        curr_diff = last - fast_cur
        prev_diff = prices[-2] - fast_prev
        return _crossover_or_position_vote(curr_diff, prev_diff, crossover_only, fast_cur)

    if ind == "EMA":
        fast = max(2, int(p.get("fast", 9)))
        slow = max(fast + 1, int(p.get("slow", 21)))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        if len(prices) < slow + (1 if crossover_only else 0):
            return 0, last
        ef_series = _ema_series(prices, fast)
        es_series = _ema_series(prices, slow)
        curr_diff = ef_series[-1] - es_series[-1]
        prev_diff = (ef_series[-2] - es_series[-2]) if crossover_only else 0.0
        return _crossover_or_position_vote(curr_diff, prev_diff, crossover_only, curr_diff)

    if ind == "MACD":
        fast = max(2, int(p.get("fast", 12)))
        slow = max(fast + 1, int(p.get("slow", 26)))
        sig_p = max(2, int(p.get("signal", 9)))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        if len(prices) < slow + sig_p + (1 if crossover_only else 0):
            return 0, 0.0
        ef = _ema_series(prices, fast)
        es = _ema_series(prices, slow)
        macd_line = [a - b for a, b in zip(ef, es)]
        sig_line = _ema_series(macd_line, sig_p)
        hist = macd_line[-1] - sig_line[-1]
        prev_hist = (macd_line[-2] - sig_line[-2]) if crossover_only else 0.0
        return _crossover_or_position_vote(hist, prev_hist, crossover_only, hist)

    if ind == "ADX":
        period = max(2, int(p.get("period", 14)))
        min_adx = float(p.get("min_adx", 20.0))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        if len(prices) < period + 2 + (1 if crossover_only else 0):
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
        if crossover_only:
            prev_tr = sum(trs[-period - 1 : -1])
            prev_p = 100.0 * sum(plus_dm[-period - 1 : -1]) / max(1e-9, prev_tr)
            prev_m = 100.0 * sum(minus_dm[-period - 1 : -1]) / max(1e-9, prev_tr)
            prev_diff = prev_p - prev_m
            curr_diff = p_di - m_di
            if prev_diff <= 0.0 and curr_diff > 0.0:
                return 1, round(dx, 2)
            if prev_diff >= 0.0 and curr_diff < 0.0:
                return -1, round(dx, 2)
            return 0, round(dx, 2)
        return (1 if p_di > m_di else (-1 if m_di > p_di else 0)), round(dx, 2)

    if ind == "PARABOLIC_SAR":
        step = float(p.get("step", 0.02))
        max_step = float(p.get("max_step", 0.2))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        bull = prices[-1] >= prices[0]
        sar = prices[0]
        ep = prices[0]
        af = step
        prev_side = 1 if prices[0] >= sar else -1
        curr_side = prev_side
        for pr in prices[1:]:
            prev_side = curr_side
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
            curr_side = 1 if pr > sar else -1
        if crossover_only:
            if prev_side < 0 and curr_side > 0:
                return 1, round(sar, 6)
            if prev_side > 0 and curr_side < 0:
                return -1, round(sar, 6)
            return 0, round(sar, 6)
        return (1 if last > sar else -1), round(sar, 6)

    if ind == "RSI":
        period = max(2, int(p.get("period", 14)))
        oversold = float(p.get("oversold", 30.0))
        overbought = float(p.get("overbought", 70.0))
        trend_mode = int(p.get("trend_mode", 0) or 0)
        if len(prices) < period + (2 if trend_mode == 2 else 1):
            return 0, 50.0
        rsi = _calc_rsi(prices, period)
        if trend_mode == 1:
            if rsi > 50.0:
                return 1, round(rsi, 2)
            if rsi < 50.0:
                return -1, round(rsi, 2)
            return 0, round(rsi, 2)
        if trend_mode == 2:
            prev_rsi = _calc_rsi(prices[:-1], period)
            if prev_rsi <= oversold and rsi > oversold:
                return 1, round(rsi, 2)
            if prev_rsi >= overbought and rsi < overbought:
                return -1, round(rsi, 2)
            return 0, round(rsi, 2)
        if rsi <= oversold:
            return 1, round(rsi, 2)
        if rsi >= overbought:
            return -1, round(rsi, 2)
        return 0, round(rsi, 2)

    if ind == "STOCHASTIC":
        period = max(2, int(p.get("period", 14)))
        d_period = max(2, int(p.get("d_period", 3) or 3))
        oversold = float(p.get("oversold", 20.0))
        overbought = float(p.get("overbought", 80.0))
        crossover_only = bool(int(p.get("crossover_only", 0) or 0))
        if not crossover_only:
            if len(prices) < period:
                return 0, 50.0
            k = _calc_stoch_k(prices, period)
            if k <= oversold:
                return 1, round(k, 2)
            if k >= overbought:
                return -1, round(k, 2)
            return 0, round(k, 2)
        if len(prices) < period + d_period:
            return 0, 50.0
        k_vals = [
            _calc_stoch_k(prices[: idx + 1], period)
            for idx in range(len(prices) - d_period - 1, len(prices))
        ]
        prev_k = k_vals[-2]
        curr_k = k_vals[-1]
        prev_d = sum(k_vals[-d_period - 1 : -1]) / d_period
        curr_d = sum(k_vals[-d_period:]) / d_period
        if prev_k <= prev_d and curr_k > curr_d and (prev_k <= oversold or curr_k <= oversold):
            return 1, round(curr_k, 2)
        if prev_k >= prev_d and curr_k < curr_d and (prev_k >= overbought or curr_k >= overbought):
            return -1, round(curr_k, 2)
        return 0, round(curr_k, 2)

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


def required_bars_for_indicators(indicators_cfg: list[dict[str, Any]] | None) -> int:
    """Compute minimum historical bars/ticks needed so long-period indicators (e.g., EMA 200) evaluate reliably."""
    if not indicators_cfg:
        return 200
    max_p = 0
    for item in indicators_cfg:
        p = item.get("params") or {}
        ind_id = str(item.get("id", "")).strip().upper()
        for key in ("period", "slow", "fast", "window"):
            try:
                val = int(float(p.get(key, 0) or 0))
            except (TypeError, ValueError):
                val = 0
            if val > max_p:
                max_p = val
        if ind_id == "MACD":
            try:
                slow_v = int(float(p.get("slow", 26) or 26))
                sig_v = int(float(p.get("signal", 9) or 9))
                if slow_v + sig_v > max_p:
                    max_p = slow_v + sig_v
            except (TypeError, ValueError):
                pass
    return min(1000, max(200, max_p + 40))


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
