"""Universal VWAP and Order Flow math engine for B3, Forex, Indices, and Crypto."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

TICK_FLAG_BID = 2
TICK_FLAG_ASK = 4
TICK_FLAG_LAST = 8
TICK_FLAG_VOLUME = 16
TICK_FLAG_BUY = 32
TICK_FLAG_SELL = 64


@dataclass(frozen=True)
class TickRecord:
    time_msc: int
    bid: float
    ask: float
    last: float
    volume_real: float
    tick_volume: float
    flags: int = 0

    def effective_price(self) -> float:
        if self.last > 0.0:
            return self.last
        if self.bid > 0.0 and self.ask > 0.0:
            return 0.5 * (self.bid + self.ask)
        return max(self.bid, self.ask, 0.0)

    def effective_volume(self, use_real: bool) -> float:
        if use_real and self.volume_real > 0.0:
            return float(self.volume_real)
        if self.tick_volume > 0.0:
            return float(self.tick_volume)
        return 1.0


@dataclass(frozen=True)
class VWAPBands:
    vwap: float
    std_dev: float
    upper_1: float
    lower_1: float
    upper_2: float
    lower_2: float
    total_volume: float
    is_real_volume: bool


@dataclass(frozen=True)
class FlowMetrics:
    buy_volume: float
    sell_volume: float
    delta_volume: float
    imbalance_ratio: float
    aggression_zscore: float
    regime: str
    recommended_action: str
    sl_points: float
    tp_points: float


def compute_intraday_vwap(ticks: Sequence[TickRecord]) -> VWAPBands:
    if not ticks:
        return VWAPBands(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)

    is_real = any(t.volume_real > 0.0 for t in ticks)
    total_pv = 0.0
    total_p2v = 0.0
    total_vol = 0.0

    for t in ticks:
        p = t.effective_price()
        if p <= 0.0:
            continue
        v = t.effective_volume(is_real)
        total_pv += p * v
        total_p2v += (p * p) * v
        total_vol += v

    if total_vol <= 0.0:
        return VWAPBands(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, is_real)

    vwap = total_pv / total_vol
    variance = max(0.0, (total_p2v / total_vol) - (vwap * vwap))
    std_dev = math.sqrt(variance)

    return VWAPBands(
        vwap=vwap,
        std_dev=std_dev,
        upper_1=vwap + std_dev,
        lower_1=vwap - std_dev,
        upper_2=vwap + 2.0 * std_dev,
        lower_2=vwap - 2.0 * std_dev,
        total_volume=total_vol,
        is_real_volume=is_real,
    )


def _classify_tick_side(tick: TickRecord, prev_price: float, prev_side: int) -> int:
    has_buy = bool(tick.flags & TICK_FLAG_BUY)
    has_sell = bool(tick.flags & TICK_FLAG_SELL)
    if has_buy and has_sell:
        return 0
    if has_buy:
        return 1
    if has_sell:
        return -1

    price = tick.effective_price()
    if tick.bid > 0.0 and tick.ask > 0.0 and tick.last > 0.0:
        mid = 0.5 * (tick.bid + tick.ask)
        if tick.last > mid:
            return 1
        if tick.last < mid:
            return -1

    if price > prev_price:
        return 1
    if price < prev_price:
        return -1
    return prev_side


def compute_flow_metrics(
    ticks: Sequence[TickRecord],
    vwap_bands: VWAPBands,
    window_size: int = 120,
    z_threshold: float = 1.8,
    imbalance_threshold: float = 0.35,
    revert_sigma: float = 2.0,
    sl_sigma_mult: float = 1.0,
    tp_sigma_mult: float = 1.8,
    operation_mode: str = "BOTH",
) -> FlowMetrics:
    if not ticks or vwap_bands.total_volume <= 0.0:
        return FlowMetrics(0.0, 0.0, 0.0, 0.0, 0.0, "NEUTRAL", "WAIT", 0.0, 0.0)

    is_real = vwap_bands.is_real_volume
    signed_volumes: list[float] = []
    prev_price = ticks[0].effective_price()
    prev_side = 0

    for t in ticks:
        p = t.effective_price()
        side = _classify_tick_side(t, prev_price, prev_side)
        v = t.effective_volume(is_real)
        signed_volumes.append(side * v)
        if side != 0:
            prev_side = side
        if p > 0.0:
            prev_price = p

    recent = ticks[-window_size:] if len(ticks) > window_size else ticks
    recent_signed = signed_volumes[-window_size:] if len(signed_volumes) > window_size else signed_volumes

    buy_vol = 0.0
    sell_vol = 0.0
    for sv, t in zip(recent_signed, recent):
        v = t.effective_volume(is_real)
        if sv > 0:
            buy_vol += v
        elif sv < 0:
            sell_vol += v
        else:
            buy_vol += 0.5 * v
            sell_vol += 0.5 * v

    delta_vol = buy_vol - sell_vol
    total_recent = buy_vol + sell_vol
    imbalance = (delta_vol / total_recent) if total_recent > 0.0 else 0.0

    if len(signed_volumes) >= 4:
        mean_all = sum(signed_volumes) / len(signed_volumes)
        var_all = sum((x - mean_all) ** 2 for x in signed_volumes) / len(signed_volumes)
        std_all = math.sqrt(max(var_all, 1e-9))
        recent_mean = sum(recent_signed) / len(recent_signed)
        z_score = (recent_mean - mean_all) / (std_all / math.sqrt(max(1, len(recent_signed) // 4)))
    else:
        z_score = 0.0

    last_price = ticks[-1].effective_price()
    band_width = max(vwap_bands.std_dev, abs(last_price) * 0.0020, 1e-6)
    sl_points = round(band_width * sl_sigma_mult, 6)
    tp_points = round(band_width * tp_sigma_mult, 6)

    upper_revert = vwap_bands.vwap + revert_sigma * vwap_bands.std_dev
    lower_revert = vwap_bands.vwap - revert_sigma * vwap_bands.std_dev

    regime = "NEUTRAL"
    action = "WAIT"

    allow_trend = operation_mode in ("BOTH", "TREND_ONLY")
    allow_revert = operation_mode in ("BOTH", "REVERT_ONLY")

    # 1. Fala 1 ("Trem Institucional" / Wall Street Broker FIX VWAP Algo Flow)
    if allow_trend and z_score >= z_threshold and imbalance >= imbalance_threshold and last_price >= vwap_bands.vwap:
        regime = "INSTITUTIONAL_TREND_UP"
        action = "BUY_FLOW"
    elif allow_trend and z_score <= -z_threshold and imbalance <= -imbalance_threshold and last_price <= vwap_bands.vwap:
        regime = "INSTITUTIONAL_TREND_DOWN"
        action = "SELL_FLOW"
    # 2. Fala 2 ("Giro HFT na Média" / Non-Directional Liquidity Provision at +-2 Sigma)
    elif allow_revert and last_price >= upper_revert and imbalance <= 0.0:
        regime = "HFT_MEAN_REVERSION"
        action = "SELL_REVERT_VWAP"
    elif allow_revert and last_price <= lower_revert and imbalance >= 0.0:
        regime = "HFT_MEAN_REVERSION"
        action = "BUY_REVERT_VWAP"

    return FlowMetrics(
        buy_volume=buy_vol,
        sell_volume=sell_vol,
        delta_volume=delta_vol,
        imbalance_ratio=imbalance,
        aggression_zscore=z_score,
        regime=regime,
        recommended_action=action,
        sl_points=sl_points,
        tp_points=tp_points,
    )
