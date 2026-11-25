from __future__ import annotations

from prado_linux.flow_math import TickRecord
from prado_linux.indicators import (
    DEFAULT_PYTHON_STRATEGY_TEMPLATE,
    INDICATOR_CATALOG,
    _ema_series,
    _true_ranges,
    _wma,
    evaluate_indicator_model,
    evaluate_python_model,
    evaluate_single_indicator,
)


def _ticks_from_prices(prices: list[float], volumes: list[float] | None = None) -> list[TickRecord]:
    out: list[TickRecord] = []
    for idx, price in enumerate(prices):
        vol = volumes[idx] if volumes is not None else 10.0
        out.append(
            TickRecord(
                time_msc=1_700_000_000_000 + idx * 1000,
                bid=price - 0.0001,
                ask=price + 0.0001,
                last=price,
                volume_real=vol,
                tick_volume=vol,
            )
        )
    return out


def test_helper_series_functions() -> None:
    assert _ema_series([], 10) == []
    ema = _ema_series([10.0, 12.0, 14.0], 3)
    assert len(ema) == 3
    assert ema[0] == 10.0
    assert ema[-1] > ema[0]

    assert _wma([10.0, 20.0, 30.0], 3) == (10 * 1 + 20 * 2 + 30 * 3) / 6
    assert _true_ranges([10.0]) == [0.0]
    assert _true_ranges([10.0, 12.5, 11.0]) == [2.5, 1.5]


def test_single_indicator_short_and_unknown() -> None:
    short = _ticks_from_prices([1.0, 1.1])
    assert evaluate_single_indicator("SMA", short) == (0, 0.0)
    normal = _ticks_from_prices([1.0 + i * 0.01 for i in range(40)])
    assert evaluate_single_indicator("UNKNOWN_IND", normal) == (0, 0.0)


def test_trend_indicators_bull_bear_and_insufficient() -> None:
    short = _ticks_from_prices([10.0, 10.1, 10.2, 10.3])
    up = _ticks_from_prices([100.0 + i * 1.5 for i in range(50)])
    down = _ticks_from_prices([200.0 - i * 1.5 for i in range(50)])
    flat = _ticks_from_prices([100.0] * 50)
    choppy = _ticks_from_prices([100.0 + (1.0 if i % 2 == 0 else -1.0) for i in range(40)])

    for ind in ("SMA", "EMA", "WMA", "DEMA", "MACD", "ADX"):
        assert evaluate_single_indicator(ind, short)[0] == 0

    assert evaluate_single_indicator("SMA", up, {"period": 10})[0] == 1
    assert evaluate_single_indicator("SMA", down, {"period": 10})[0] == -1
    assert evaluate_single_indicator("SMA", flat, {"period": 10})[0] == 0

    assert evaluate_single_indicator("EMA", up, {"fast": 5, "slow": 12})[0] == 1
    assert evaluate_single_indicator("EMA", down, {"fast": 5, "slow": 12})[0] == -1
    assert evaluate_single_indicator("EMA", flat, {"fast": 5, "slow": 12})[0] == 0

    assert evaluate_single_indicator("WMA", up, {"period": 10})[0] == 1
    assert evaluate_single_indicator("WMA", down, {"period": 10})[0] == -1

    assert evaluate_single_indicator("DEMA", up, {"period": 10})[0] == 1
    assert evaluate_single_indicator("DEMA", down, {"period": 10})[0] == -1

    assert evaluate_single_indicator("MACD", up, {"fast": 5, "slow": 10, "signal": 4})[0] == 1
    assert evaluate_single_indicator("MACD", down, {"fast": 5, "slow": 10, "signal": 4})[0] == -1

    assert evaluate_single_indicator("ADX", up, {"period": 10, "min_adx": 20.0})[0] == 1
    assert evaluate_single_indicator("ADX", down, {"period": 10, "min_adx": 20.0})[0] == -1
    assert evaluate_single_indicator("ADX", choppy, {"period": 10, "min_adx": 20.0})[0] == 0

    # Parabolic SAR bull, bear, and trend reversal transitions
    rev_down = _ticks_from_prices([100 + i for i in range(15)] + [115 - i * 3 for i in range(15)])
    rev_up = _ticks_from_prices([150 - i for i in range(15)] + [135 + i * 3 for i in range(15)])
    assert evaluate_single_indicator("PARABOLIC_SAR", up)[0] == 1
    assert evaluate_single_indicator("PARABOLIC_SAR", down)[0] == -1
    assert evaluate_single_indicator("PARABOLIC_SAR", rev_down)[0] in (-1, 1)
    assert evaluate_single_indicator("PARABOLIC_SAR", rev_up)[0] in (-1, 1)


def test_momentum_and_oscillator_indicators() -> None:
    short = _ticks_from_prices([10.0, 10.1, 10.2, 10.3])
    up = _ticks_from_prices([100.0 + i * 2.0 for i in range(30)])
    down = _ticks_from_prices([200.0 - i * 2.0 for i in range(30)])
    flat = _ticks_from_prices([100.0] * 30)
    mid_wave = _ticks_from_prices([100.0 + (2.0 if i % 2 == 0 else 0.0) for i in range(30)])

    for ind in ("RSI", "STOCHASTIC", "CCI", "WILLIAMS_R", "ROC", "MOMENTUM", "MFI"):
        assert evaluate_single_indicator(ind, short)[0] == 0

    # RSI: all gains -> overbought (-1), all losses -> oversold (+1), flat -> neutral (0)
    assert evaluate_single_indicator("RSI", up, {"period": 10}) == (-1, 100.0)
    assert evaluate_single_indicator("RSI", down, {"period": 10}) == (1, 0.0)
    assert evaluate_single_indicator("RSI", flat, {"period": 10}) == (0, 50.0)
    assert evaluate_single_indicator("RSI", mid_wave, {"period": 10})[0] == 0

    # STOCHASTIC
    assert evaluate_single_indicator("STOCHASTIC", up, {"period": 10})[0] == -1
    assert evaluate_single_indicator("STOCHASTIC", down, {"period": 10})[0] == 1
    assert evaluate_single_indicator("STOCHASTIC", flat, {"period": 10}) == (0, 50.0)
    mid_stoch = _ticks_from_prices([100.0] * 10 + [110.0, 90.0, 100.0, 100.0, 100.0])
    assert evaluate_single_indicator("STOCHASTIC", mid_stoch, {"period": 5})[0] == 0

    # CCI
    assert evaluate_single_indicator("CCI", up, {"period": 10})[0] == -1
    assert evaluate_single_indicator("CCI", down, {"period": 10})[0] == 1
    assert evaluate_single_indicator("CCI", flat, {"period": 10}) == (0, 0.0)

    # WILLIAMS_R
    assert evaluate_single_indicator("WILLIAMS_R", up, {"period": 10})[0] == -1
    assert evaluate_single_indicator("WILLIAMS_R", down, {"period": 10})[0] == 1
    assert evaluate_single_indicator("WILLIAMS_R", flat, {"period": 10}) == (0, -50.0)
    assert evaluate_single_indicator("WILLIAMS_R", mid_stoch, {"period": 5})[0] == 0

    # ROC & MOMENTUM
    assert evaluate_single_indicator("ROC", up, {"period": 5, "threshold": 0.1})[0] == 1
    assert evaluate_single_indicator("ROC", down, {"period": 5, "threshold": 0.1})[0] == -1
    assert evaluate_single_indicator("ROC", flat, {"period": 5, "threshold": 0.1}) == (0, 0.0)

    assert evaluate_single_indicator("MOMENTUM", up, {"period": 5})[0] == 1
    assert evaluate_single_indicator("MOMENTUM", down, {"period": 5})[0] == -1
    assert evaluate_single_indicator("MOMENTUM", flat, {"period": 5}) == (0, 0.0)

    # MFI
    assert evaluate_single_indicator("MFI", up, {"period": 10}) == (-1, 100.0)
    assert evaluate_single_indicator("MFI", down, {"period": 10}) == (1, 0.0)
    assert evaluate_single_indicator("MFI", mid_wave, {"period": 10})[0] == 0


def test_volatility_and_institutional_indicators() -> None:
    short = _ticks_from_prices([10.0, 10.1, 10.2])
    flat = _ticks_from_prices([100.0] * 30)
    spike_up = _ticks_from_prices([100.0 + (0.01 * (i % 3)) for i in range(29)] + [120.0])
    spike_down = _ticks_from_prices([100.0 + (0.01 * (i % 3)) for i in range(29)] + [80.0])
    inside = _ticks_from_prices([100.0 + (1.0 if i % 2 == 0 else -1.0) for i in range(29)] + [100.0])

    # BOLLINGER
    assert evaluate_single_indicator("BOLLINGER", short, {"period": 10})[0] == 0
    assert evaluate_single_indicator("BOLLINGER", spike_up, {"period": 20, "std_mult": 1.5})[0] == -1
    assert evaluate_single_indicator("BOLLINGER", spike_down, {"period": 20, "std_mult": 1.5})[0] == 1
    assert evaluate_single_indicator("BOLLINGER", inside, {"period": 20, "std_mult": 2.0})[0] == 0

    # ATR
    assert evaluate_single_indicator("ATR", flat)[0] == 0
    assert evaluate_single_indicator("ATR", spike_up)[0] == 1
    assert evaluate_single_indicator("ATR", spike_down)[0] == -1

    # KELTNER
    assert evaluate_single_indicator("KELTNER", short, {"period": 10})[0] == 0
    assert evaluate_single_indicator("KELTNER", spike_up, {"period": 15, "atr_mult": 1.0})[0] == -1
    assert evaluate_single_indicator("KELTNER", spike_down, {"period": 15, "atr_mult": 1.0})[0] == 1
    assert evaluate_single_indicator("KELTNER", inside, {"period": 15, "atr_mult": 2.0})[0] == 0

    # DONCHIAN
    assert evaluate_single_indicator("DONCHIAN", short, {"period": 10})[0] == 0
    assert evaluate_single_indicator("DONCHIAN", spike_up, {"period": 15})[0] == 1
    assert evaluate_single_indicator("DONCHIAN", spike_down, {"period": 15})[0] == -1
    assert evaluate_single_indicator("DONCHIAN", inside, {"period": 15})[0] == 0

    # VWAP
    assert evaluate_single_indicator("VWAP", flat)[0] == 0
    assert evaluate_single_indicator("VWAP", spike_up, {"sigma_mult": 1.0})[0] == -1
    assert evaluate_single_indicator("VWAP", spike_down, {"sigma_mult": 1.0})[0] == 1
    assert evaluate_single_indicator("VWAP", inside, {"sigma_mult": 2.0})[0] == 0

    # ZSCORE & IMBALANCE
    up_flow = _ticks_from_prices([100.0 + i * 0.5 for i in range(40)], volumes=[5.0] * 35 + [200.0] * 5)
    down_flow = _ticks_from_prices([200.0 - i * 0.5 for i in range(40)], volumes=[5.0] * 35 + [200.0] * 5)
    assert evaluate_single_indicator("ZSCORE", flat, {"window": 20, "threshold": 1.5})[0] == 0
    assert evaluate_single_indicator("ZSCORE", up_flow, {"window": 20, "threshold": 0.5})[0] in (-1, 0, 1)
    assert evaluate_single_indicator("ZSCORE", down_flow, {"window": 20, "threshold": 0.5})[0] in (-1, 0, 1)

    assert evaluate_single_indicator("IMBALANCE", flat, {"window": 20, "threshold": 0.3})[0] == 0
    assert evaluate_single_indicator("IMBALANCE", up_flow, {"window": 20, "threshold": 0.2})[0] == 1
    assert evaluate_single_indicator("IMBALANCE", down_flow, {"window": 20, "threshold": 0.2})[0] == -1


def test_evaluate_indicator_model_modes() -> None:
    assert len(INDICATOR_CATALOG) == 21
    up = _ticks_from_prices([100.0 + i * 1.5 for i in range(40)])
    down = _ticks_from_prices([200.0 - i * 1.5 for i in range(40)])

    assert evaluate_indicator_model(up, [])["signal"] == "WAIT"

    cfg = [
        {"id": "SMA", "params": {"period": 10}},
        {"id": "EMA", "params": {"fast": 5, "slow": 12}},
        {"id": "MOMENTUM", "params": {"period": 5}},
    ]
    res_buy = evaluate_indicator_model(up, cfg, combine_mode="ALL")
    assert res_buy["signal"] == "BUY"
    assert res_buy["buy_votes"] == 3

    res_sell = evaluate_indicator_model(down, cfg, combine_mode="ALL")
    assert res_sell["signal"] == "SELL"
    assert res_sell["sell_votes"] == 3

    # Mixed votes: SMA (+1) vs RSI (-1 on uptrend)
    mixed = [
        {"id": "SMA", "params": {"period": 10}},
        {"id": "RSI", "params": {"period": 10}},
    ]
    assert evaluate_indicator_model(up, mixed, combine_mode="ALL")["signal"] == "WAIT"
    assert evaluate_indicator_model(up, mixed, combine_mode="MAJORITY")["signal"] == "WAIT"

    res_maj_buy = evaluate_indicator_model(up, cfg, combine_mode="MAJORITY")
    assert res_maj_buy["signal"] == "BUY"
    res_maj_sell = evaluate_indicator_model(down, cfg, combine_mode="MAJORITY")
    assert res_maj_sell["signal"] == "SELL"


def test_evaluate_python_model_paths() -> None:
    ticks = _ticks_from_prices([100.0 + i * 0.5 for i in range(30)])
    prices = [t.effective_price() for t in ticks]

    # Empty & syntax error
    assert not evaluate_python_model("", prices, ticks)["ok"]
    syn = evaluate_python_model("def evaluate(:\n pass", prices, ticks)
    assert not syn["ok"] and "sintaxe" in syn["error"].lower()

    # Security AST checks
    assert not evaluate_python_model("import os\ndef evaluate(p,t,a): return 'BUY'", prices, ticks)["ok"]
    assert not evaluate_python_model("def evaluate(p,t,a): return p.__class__", prices, ticks)["ok"]
    assert not evaluate_python_model("def evaluate(p,t,a): return open('x')", prices, ticks)["ok"]
    assert not evaluate_python_model("def evaluate(p,t,a): _x = 1; return 'WAIT'", prices, ticks)["ok"]

    # Missing evaluate function
    missing = evaluate_python_model("x = 42", prices, ticks)
    assert not missing["ok"] and "evaluate" in missing["error"]

    # Runtime exception
    boom = evaluate_python_model("def evaluate(p,t,a): return 1 / 0", prices, ticks)
    assert not boom["ok"] and "ZeroDivisionError" in boom["error"]

    # Step limit guard
    loop = evaluate_python_model("def evaluate(p,t,a):\n while True:\n  pass", prices, ticks)
    assert not loop["ok"] and "TimeoutError" in loop["error"]

    # Default template + BUY/SELL/unknown normalization + stdout
    tpl_res = evaluate_python_model(DEFAULT_PYTHON_STRATEGY_TEMPLATE, prices, ticks)
    assert tpl_res["ok"] and tpl_res["signal"] == "BUY"

    sell_res = evaluate_python_model(
        "def evaluate(p,t,a):\n print('hello')\n return 'sell'",
        prices,
        ticks,
    )
    assert sell_res["ok"] and sell_res["signal"] == "SELL" and "hello" in sell_res["stdout"]

    norm_res = evaluate_python_model("def evaluate(p,t,a): return 'UNKNOWN'", prices, ticks)
    assert norm_res["ok"] and norm_res["signal"] == "WAIT"
