from __future__ import annotations

import json
from pathlib import Path

import pytest

from prado_linux.config import load_config
from prado_linux.engine import PradoTradingService
from prado_linux.flow_math import TickRecord
from prado_linux.indicators import (
    INDICATOR_CATALOG,
    evaluate_indicator_model,
    evaluate_single_indicator,
)
from prado_linux.supabase_store import SupabaseConfig, SupabaseStore
from prado_linux.web_app import PradoWebApp


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


def _sim_service(tmp_path: Path) -> PradoTradingService:
    cfg_path = tmp_path / "cfg.json"
    cfg = load_config(cfg_path)
    cfg.connection_mode = "SIMULATION"
    cfg.active_symbols = ["EURUSD", "US100"]
    return PradoTradingService(cfg, config_path=cfg_path)


def _login_headers(app: PradoWebApp, password: str = "prado2026") -> dict[str, str]:
    code, _, hdrs = app.handle_request(
        "POST",
        "/api/login",
        {"Content-Type": "application/json"},
        json.dumps({"username": "admin", "password": password}).encode("utf-8"),
    )
    assert code == 200
    return {"Cookie": hdrs["Set-Cookie"], "Content-Type": "application/json"}


def test_macd_crossover_only_mode() -> None:
    down_then_turn = [120.0 - i * 0.4 for i in range(45)]
    strong_up = _ticks_from_prices([100.0 + i * 1.2 for i in range(50)])
    assert evaluate_single_indicator("MACD", strong_up, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 0})[0] == 1
    assert evaluate_single_indicator("MACD", strong_up, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1})[0] == 0

    prices = list(down_then_turn)
    crossed_up_at: int | None = None
    for _ in range(30):
        prices.append(prices[-1] + 0.55)
        ticks = _ticks_from_prices(prices)
        vote, _ = evaluate_single_indicator("MACD", ticks, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1})
        if vote == 1:
            crossed_up_at = len(prices)
            break
    assert crossed_up_at is not None
    prices.append(prices[-1] + 0.55)
    next_ticks = _ticks_from_prices(prices)
    assert evaluate_single_indicator("MACD", next_ticks, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1})[0] == 0
    assert evaluate_single_indicator("MACD", next_ticks, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 0})[0] == 1

    crossed_down_at: int | None = None
    for _ in range(40):
        prices.append(prices[-1] - 0.85)
        ticks = _ticks_from_prices(prices)
        vote, _ = evaluate_single_indicator("MACD", ticks, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1})
        if vote == -1:
            crossed_down_at = len(prices)
            break
    assert crossed_down_at is not None
    prices.append(prices[-1] - 0.85)
    after_down = _ticks_from_prices(prices)
    assert evaluate_single_indicator("MACD", after_down, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 1})[0] == 0
    assert evaluate_single_indicator("MACD", after_down, {"fast": 12, "slow": 26, "signal": 9, "crossover_only": 0})[0] == -1


def test_rsi_trend_mode_and_reversion_mode() -> None:
    mild_up_prices = [100.0]
    for i in range(1, 35):
        mild_up_prices.append(mild_up_prices[-1] + (0.5 if i % 2 == 0 else -0.35))
    mild_up_ticks = _ticks_from_prices(mild_up_prices)

    vote_rev, rsi_val = evaluate_single_indicator(
        "RSI", mild_up_ticks, {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 0}
    )
    assert 50.0 < rsi_val < 70.0
    assert vote_rev == 0

    vote_trend, rsi_trend_val = evaluate_single_indicator(
        "RSI", mild_up_ticks, {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 1}
    )
    assert rsi_trend_val == rsi_val
    assert vote_trend == 1

    mild_down_prices = [100.0]
    for i in range(1, 35):
        mild_down_prices.append(mild_down_prices[-1] + (-0.5 if i % 2 == 0 else 0.35))
    mild_down_ticks = _ticks_from_prices(mild_down_prices)
    v_rev_d, r_d = evaluate_single_indicator("RSI", mild_down_ticks, {"period": 14, "trend_mode": 0})
    assert 30.0 < r_d < 50.0
    assert v_rev_d == 0
    assert evaluate_single_indicator("RSI", mild_down_ticks, {"period": 14, "trend_mode": 1})[0] == -1

    flat_ticks = _ticks_from_prices([100.0] * 25)
    assert evaluate_single_indicator("RSI", flat_ticks, {"period": 14, "trend_mode": 1}) == (0, 50.0)


def test_multiple_ema_instances_in_indicator_model() -> None:
    prices = [100.0 + i * 0.25 for i in range(220)]
    for _ in range(12):
        prices.append(prices[-1] - 0.9)
    cfg = [
        {"id": "EMA", "params": {"fast": 50, "slow": 200, "crossover_only": 0}},
        {"id": "EMA", "params": {"fast": 9, "slow": 21, "crossover_only": 1}},
    ]
    found_buy = False
    for _ in range(30):
        prices.append(prices[-1] + 1.1)
        res = evaluate_indicator_model(_ticks_from_prices(prices), cfg, combine_mode="ALL")
        assert res["total"] == 2
        assert len(res["details"]) == 2
        if res["signal"] == "BUY":
            found_buy = True
            assert res["buy_votes"] == 2
            break
    assert found_buy is True


def test_required_bars_and_fetch_cache_and_test_summary(tmp_path: Path) -> None:
    from prado_linux.indicators import required_bars_for_indicators

    assert required_bars_for_indicators([]) == 200
    bars_200 = required_bars_for_indicators([{"id": "EMA", "params": {"fast": 50, "slow": 200}}])
    assert 240 <= bars_200 <= 1000
    assert required_bars_for_indicators([{"id": "SMA", "params": {"period": 50, "slow": 600}}]) == 640
    assert required_bars_for_indicators([{"id": "SMA", "params": {"period": 1200}}]) == 1000

    svc = _sim_service(tmp_path)
    res = svc.test_custom_template(
        {
            "custom_mode": "INDICATORS",
            "combine_mode": "MAJORITY",
            "indicators": [{"id": "EMA", "params": {"fast": 50, "slow": 200, "crossover_only": 0}}],
            "symbol": "EURUSD",
            "timeframe": "M5",
        }
    )
    assert res["ok"] is True
    assert res["data_source"] == "SIMULATION"
    assert res["ticks_count"] >= 240
    assert res["bars_scanned"] >= 1
    assert isinstance(res["buy_signals_count"], int)
    assert isinstance(res["sell_signals_count"], int)
    assert res["last_signal"] in ("BUY", "SELL", "WAIT")
    assert "last_signal_bars_ago" in res

    class _FakeClient:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def get_ticks_history(self, symbol: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
            self.calls.append(count)
            return _ticks_from_prices([1.1000 + i * 0.0001 for i in range(180)])

    fake_client = _FakeClient()
    svc.cfg.connection_mode = "CTRADER_CLOUD"
    svc.connector._client = fake_client  # type: ignore[assignment]
    svc.connector._tick_cache.clear()

    t1 = svc.connector.fetch_ticks("EURUSD", count=200, granularity=300)
    assert len(t1) == 180
    assert fake_client.calls == [200]

    t2 = svc.connector.fetch_ticks("EURUSD", count=260, granularity=300)
    assert len(t2) == 180
    assert fake_client.calls == [200, 260]

    t3 = svc.connector.fetch_ticks("EURUSD", count=260, granularity=300)
    assert len(t3) == 180
    assert fake_client.calls == [200, 260]


def test_catalog_descriptions_and_ready_made_recipes(tmp_path: Path) -> None:
    from prado_linux.indicators import READY_MADE_RECIPES

    assert len(INDICATOR_CATALOG) == 21
    catalog_ids = set()
    for item in INDICATOR_CATALOG:
        catalog_ids.add(item["id"])
        assert str(item.get("description") or "").strip()

    assert len(READY_MADE_RECIPES) == 9
    assert any(r["id"] == "RECIPE_GOLDEN_CROSS_SMA_ADX" for r in READY_MADE_RECIPES)
    for r in READY_MADE_RECIPES:
        for key in ("id", "name", "style", "markets", "recommended_timeframe", "description", "combine_mode", "indicators"):
            assert r.get(key)
        assert r["combine_mode"] in ("MAJORITY", "ALL")
        for ind in r["indicators"]:
            assert ind["id"] in catalog_ids

    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=SupabaseStore(SupabaseConfig()))
    auth = _login_headers(app)
    code, body, _ = app.handle_request("GET", "/api/bot-templates", auth)
    assert code == 200
    payload = json.loads(body)
    assert len(payload["recipes"]) == 9


def test_sma_wma_dema_dual_average_crossover() -> None:
    # slow=0 preserves classic price vs moving average
    up = _ticks_from_prices([100.0 + i * 0.5 for i in range(40)])
    for ind in ("SMA", "WMA", "DEMA"):
        assert evaluate_single_indicator(ind, up, {"period": 10, "slow": 0, "crossover_only": 0})[0] == 1

    # Explicit differentiation: price bounces above MA(5) (slow=0 -> +1) while MA(5) is still below MA(20) (slow=20 -> -1)
    bounce = _ticks_from_prices([150.0 - i * 1.0 for i in range(25)] + [128.0])
    for ind in ("SMA", "WMA", "DEMA"):
        assert evaluate_single_indicator(ind, bounce, {"period": 5, "slow": 0, "crossover_only": 0})[0] == 1
        assert evaluate_single_indicator(ind, bounce, {"period": 5, "slow": 20, "crossover_only": 0})[0] == -1

    # Dual average crossover (period=5, slow=15)
    for ind in ("SMA", "WMA", "DEMA"):
        prices = [130.0 - i * 0.6 for i in range(25)]
        crossed_up = False
        for _ in range(30):
            prices.append(prices[-1] + 0.9)
            t = _ticks_from_prices(prices)
            v_cross, _ = evaluate_single_indicator(ind, t, {"period": 5, "slow": 15, "crossover_only": 1})
            v_pos, _ = evaluate_single_indicator(ind, t, {"period": 5, "slow": 15, "crossover_only": 0})
            if v_cross == 1:
                crossed_up = True
                assert v_pos == 1
                break
        assert crossed_up, f"{ind} failed Golden Cross detection"

        # Next bar continues up: crossover_only=1 returns 0 while crossover_only=0 remains +1
        prices.append(prices[-1] + 0.9)
        t_after = _ticks_from_prices(prices)
        assert evaluate_single_indicator(ind, t_after, {"period": 5, "slow": 15, "crossover_only": 1})[0] == 0
        assert evaluate_single_indicator(ind, t_after, {"period": 5, "slow": 15, "crossover_only": 0})[0] == 1

        # Reverse down -> Death Cross (-1) then 0 on continuation
        crossed_down = False
        for _ in range(35):
            prices.append(prices[-1] - 1.4)
            t = _ticks_from_prices(prices)
            v_cross, _ = evaluate_single_indicator(ind, t, {"period": 5, "slow": 15, "crossover_only": 1})
            if v_cross == -1:
                crossed_down = True
                break
        assert crossed_down, f"{ind} failed Death Cross detection"
        prices.append(prices[-1] - 1.4)
        t_after_d = _ticks_from_prices(prices)
        assert evaluate_single_indicator(ind, t_after_d, {"period": 5, "slow": 15, "crossover_only": 1})[0] == 0
        assert evaluate_single_indicator(ind, t_after_d, {"period": 5, "slow": 15, "crossover_only": 0})[0] == -1


def test_adx_stochastic_psar_and_rsi_crossover_modes() -> None:
    # 1) ADX crossover_only=1 (+DI crosses -DI with DX >= min_adx)
    adx_prices = [140.0 - i * 0.8 for i in range(25)]
    adx_cross_idx: int | None = None
    for _ in range(30):
        adx_prices.append(adx_prices[-1] + 1.5)
        vote, dx_val = evaluate_single_indicator(
            "ADX", _ticks_from_prices(adx_prices), {"period": 10, "min_adx": 10.0, "crossover_only": 1}
        )
        if vote == 1:
            assert dx_val >= 10.0
            adx_cross_idx = len(adx_prices)
            break
    assert adx_cross_idx is not None
    adx_prices.append(adx_prices[-1] + 1.5)
    assert (
        evaluate_single_indicator(
            "ADX", _ticks_from_prices(adx_prices), {"period": 10, "min_adx": 10.0, "crossover_only": 1}
        )[0]
        == 0
    )

    # 2) STOCHASTIC crossover_only=1 (%K crosses %D in oversold / overbought zone)
    stoch_prices = [120.0 - i * 1.2 for i in range(18)]
    stoch_cross_up = False
    for _ in range(10):
        stoch_prices.append(stoch_prices[-1] + 1.6)
        vote, _ = evaluate_single_indicator(
            "STOCHASTIC",
            _ticks_from_prices(stoch_prices),
            {"period": 14, "d_period": 3, "oversold": 35.0, "overbought": 65.0, "crossover_only": 1},
        )
        if vote == 1:
            stoch_cross_up = True
            break
    assert stoch_cross_up is True
    # Push strongly to high zone where %K stays near 100 and is no longer crossing %D upward
    for _ in range(6):
        stoch_prices.append(stoch_prices[-1] + 3.0)
    assert (
        evaluate_single_indicator(
            "STOCHASTIC",
            _ticks_from_prices(stoch_prices),
            {"period": 14, "d_period": 3, "oversold": 35.0, "overbought": 65.0, "crossover_only": 1},
        )[0]
        == 0
    )
    # Reverse down in overbought zone -> SELL crossover (-1)
    stoch_cross_down = False
    for _ in range(12):
        stoch_prices.append(stoch_prices[-1] - 2.0)
        vote, _ = evaluate_single_indicator(
            "STOCHASTIC",
            _ticks_from_prices(stoch_prices),
            {"period": 14, "d_period": 3, "oversold": 35.0, "overbought": 65.0, "crossover_only": 1},
        )
        if vote == -1:
            stoch_cross_down = True
            break
    assert stoch_cross_down is True

    # 3) PARABOLIC_SAR crossover_only=1 (flip only)
    sar_prices = [130.0 - i * 1.0 for i in range(18)]
    sar_flipped_up = False
    for _ in range(15):
        sar_prices.append(sar_prices[-1] + 2.5)
        vote, _ = evaluate_single_indicator(
            "PARABOLIC_SAR", _ticks_from_prices(sar_prices), {"step": 0.02, "max_step": 0.2, "crossover_only": 1}
        )
        if vote == 1:
            sar_flipped_up = True
            break
    assert sar_flipped_up is True
    sar_prices.append(sar_prices[-1] + 2.5)
    assert (
        evaluate_single_indicator(
            "PARABOLIC_SAR", _ticks_from_prices(sar_prices), {"step": 0.02, "max_step": 0.2, "crossover_only": 1}
        )[0]
        == 0
    )

    # 4) RSI trend_mode=2 (crossing back above oversold / back below overbought)
    rsi_prices = [120.0 - i * 1.0 for i in range(20)]
    rsi_cross_up = False
    for _ in range(20):
        rsi_prices.append(rsi_prices[-1] + 1.4)
        vote, rsi_v = evaluate_single_indicator(
            "RSI", _ticks_from_prices(rsi_prices), {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 2}
        )
        if vote == 1:
            assert rsi_v > 30.0
            rsi_cross_up = True
            break
    assert rsi_cross_up is True
    rsi_prices.append(rsi_prices[-1] + 0.5)
    assert (
        evaluate_single_indicator(
            "RSI", _ticks_from_prices(rsi_prices), {"period": 14, "oversold": 30.0, "overbought": 70.0, "trend_mode": 2}
        )[0]
        == 0
    )


def test_custom_template_data_source_label(tmp_path: Path) -> None:
    svc = _sim_service(tmp_path)
    payload = {
        "custom_mode": "INDICATORS",
        "combine_mode": "MAJORITY",
        "indicators": [{"id": "EMA", "params": {"fast": 9, "slow": 21, "crossover_only": 0}}],
        "symbol": "EURUSD",
        "timeframe": "M5",
    }
    res_sim = svc.test_custom_template(payload)
    assert res_sim["data_source"] == "SIMULATION"

    class _EmptyClient:
        def get_ticks_history(self, symbol: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
            return []

    svc.cfg.connection_mode = "CTRADER_CLOUD"
    svc.connector._tick_cache.clear()
    svc.connector._client = _EmptyClient()  # type: ignore[assignment]
    res_fb = svc.test_custom_template(payload)
    assert res_fb["data_source"] == "SIMULATION_FALLBACK"

    class _LiveClient:
        def get_ticks_history(self, symbol: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
            return _ticks_from_prices([1.1000 + i * 0.0002 for i in range(60)])

    svc.connector._tick_cache.clear()
    svc.connector._client = _LiveClient()  # type: ignore[assignment]
    res_live = svc.test_custom_template(payload)
    assert res_live["data_source"] == "CTRADER_LIVE"


def test_template_persistence_and_delete_guard_when_bot_uses_it(tmp_path: Path) -> None:
    app = PradoWebApp(config_path=tmp_path / "config.json", supabase_store=SupabaseStore(SupabaseConfig()))
    app.cfg.connection_mode = "SIMULATION"
    auth = _login_headers(app)

    saved = app.service.save_custom_template(
        {
            "name": "Macro Micro EMA",
            "custom_mode": "INDICATORS",
            "combine_mode": "ALL",
            "recommended_timeframe": "M5",
            "indicators": [
                {"id": "EMA", "params": {"fast": 50, "slow": 200, "crossover_only": 0}},
                {"id": "EMA", "params": {"fast": 9, "slow": 21, "crossover_only": 1}},
            ],
        }
    )
    assert "Todos Concordam" in saved["formula"]
    assert saved["recommended_timeframe"] == "M5"
    assert len(saved["indicators"]) == 2

    bot = app.service.create_bot(
        {
            "name": "Bot Teste EMA",
            "symbol": "US100",
            "template_id": saved["template_id"],
            "timeframe": "M5",
            "lot_size": 0.01,
        }
    )

    with pytest.raises(ValueError, match="Bot Teste EMA"):
        app.service.delete_custom_template(saved["template_id"])

    code, body, _ = app.handle_request(
        "POST",
        "/api/bot-templates",
        auth,
        json.dumps({"action": "DELETE", "template_id": saved["template_id"]}).encode("utf-8"),
    )
    assert code == 400
    err = json.loads(body)
    assert err["ok"] is False
    assert "Bot Teste EMA" in err["error"]

    app.service.control_bot(bot["bot_id"], "DELETE")
    assert app.service.delete_custom_template(saved["template_id"]) is True
