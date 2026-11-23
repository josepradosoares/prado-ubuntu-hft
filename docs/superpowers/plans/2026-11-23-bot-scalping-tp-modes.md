# Bot Scalping Take Profit Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow each bot to configure its Take Profit target as `"AUTO"` (legacy 90% of stake), `"USD"` (fixed dollar amount), `"PCT"` (% of stake), or `"TICKS"` (tick-distance scalping monitored in the engine loop).

**Architecture:** `USD` and `PCT` compute `tp_usd` and pass it directly into Deriv's native `limit_order.take_profit` in `place_order` for zero-latency broker-side execution. `TICKS` keeps the default safety `take_profit` on Deriv and monitors open bot positions every engine cycle using the minimum non-zero recent tick delta, closing via `close_single_position` once `>= tp_value` ticks in profit are reached. `supabase_store.py` and `frontend/src/App.tsx` persist and expose `tp_mode` and `tp_value`.

**Tech Stack:** Python 3.14, pytest, TypeScript/React (Vite), Supabase REST.

**Spec:** `docs/superpowers/specs/2026-11-23-bot-scalping-tp-modes-design.md`

## Global Constraints
- Preserve backward compatibility: existing bots without `tp_mode` or `tp_value` must default to `"AUTO"` (`max(1.5, stake * tp_usd_mult)`).
- Never send `take_profit <= 0` to Deriv (`place_multiplier_order` requires positive `tp_amount`; clamp `USD`/`PCT` to `>= 0.05`).
- `TICKS` mode must only close a position when `profit > 0` so spread/commission never causes a premature losing exit.
- Grid Linear (`GRID_LINEAR_HFT`) keeps its own `grid_tp_points` logic unchanged.

## Review Focus
- `tp_mode` missing, `None`, lowercase, or unknown value -> normalize to `"AUTO"`.
- `tp_value` `<= 0`, `None`, or non-numeric when `tp_mode` is `"USD"`, `"PCT"`, or `"TICKS"` -> fallback safely (`0.50` USD, `10.0` %, `2.0` ticks, or clamp positive) without crashing.
- `TICKS` mode when recent ticks are all identical (zero delta) -> do not divide by zero or close prematurely.
- `TICKS` mode when price moved `>= tp_value` ticks in favor *but* `profit <= 0` (spread) -> hold position until `profit > 0`.
- `FIRE_BUY` / `FIRE_SELL`, `news_assisted`, and `duplicateBot` -> forward `tp_mode` and `tp_value` consistently.

---

### Task 1: Backend Take Profit Modes (`engine.py` & `supabase_store.py`)

**Files:**
- Modify: `prado_linux/engine.py` (`place_order`, `create_bot`, `control_bot`, `_run_cycle`, helper `_estimate_tick_step` & `_normalize_tp_config`)
- Modify: `prado_linux/supabase_store.py` (`load_user_config`)
- Test: `tests/test_deriv_integration.py`

**Interfaces:**
- Produces:
  - `normalize_tp_config(tp_mode: Any, tp_value: Any) -> tuple[str, float]`
  - `place_order(..., tp_mode: str = "AUTO", tp_value: float = 0.0) -> tuple[bool, str]`
  - Bot dict fields: `tp_mode: str`, `tp_value: float`

- [ ] **Step 1: Write failing tests in `tests/test_deriv_integration.py`**
  - Test `place_order` with `self.connector._deriv` mocked:
    - `tp_mode="USD", tp_value=0.35, stake=10.0` -> `tp_amount == 0.35`
    - `tp_mode="PCT", tp_value=15.0, stake=10.0` -> `tp_amount == 1.5`
    - `tp_mode="AUTO"` -> `tp_amount == 9.0` (legacy `stake * 0.9`)
    - `tp_mode="TICKS", tp_value=3.0` -> `tp_amount == 9.0` (safety TP)
    - `tp_mode="INVALID"` -> normalized to `"AUTO"`
  - Test `create_bot` persists `tp_mode` and `tp_value` (and defaults to `"AUTO"`, `0.0`).
  - Test `_check_bot_tick_take_profit` closes open position when price moves `>= tp_value * tick_step` in favor AND `profit > 0`, and does NOT close when `profit <= 0` or when ticks are flat.
  - Test `SupabaseStore.load_user_config` preserves `tp_mode`/`tp_value` from `config_json` and defaults to `"AUTO"` / `0.0` when absent.

- [ ] **Step 2: Run pytest on the new tests to verify they fail**
  - Run: `$env:PYTHONPATH="C:\Projeto\Prado\prado-ubuntu-hft"; py -3.14 -m pytest tests/test_deriv_integration.py -k "tp_mode" -v`

- [ ] **Step 3: Implement backend changes in `prado_linux/engine.py` and `prado_linux/supabase_store.py`**
  - Add `normalize_tp_config(tp_mode, tp_value)` in `engine.py`.
  - Update `place_order` to compute `tp_usd` using `tp_mode` and `tp_value` when `self._deriv is not None`.
  - Update `create_bot`, `control_bot` (`FIRE_BUY`/`FIRE_SELL`), and `_run_cycle` (both `news_assisted` and standard bot execution) to pass `tp_mode` and `tp_value`.
  - Add `_estimate_tick_step(ticks)` and `_check_bot_tick_take_profit(bot, ticks, positions)` in `engine.py` and call it in `_run_cycle` for non-Grid bots with `tp_mode == "TICKS"`.
  - Update `supabase_store.py` `load_user_config` to default `tp_mode` (`"AUTO"`) and `tp_value` (`0.0`) on loaded `prado_bots` when missing.

- [ ] **Step 4: Run full pytest suite to verify all tests pass**
  - Run: `$env:PYTHONPATH="C:\Projeto\Prado\prado-ubuntu-hft"; py -3.14 -m pytest tests -v`

---

### Task 2: Frontend UI & Production Build (`frontend/` -> `prado_linux/static`)

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.tsx`
- Rebuild: `prado_linux/static/` via `npm run build`

- [ ] **Step 1: Update `frontend/src/types.ts`**
  - Add `tp_mode?: 'AUTO' | 'USD' | 'PCT' | 'TICKS' | string;` and `tp_value?: number;` to `BotItem`.

- [ ] **Step 2: Update `frontend/src/App.tsx`**
  - Add `botTpMode` (`'AUTO' | 'USD' | 'PCT' | 'TICKS'`) and `botTpValue` (`number`) state.
  - Reset/populate them in `editBot`, `duplicateBot`, `saveBot`, and template reset.
  - Render **Alvo de Ganho (Take Profit)** `<select>` and **Valor do alvo** `<input>` in the `Configurar robô matemático` form (disabled/hidden hint when `AUTO`).

- [ ] **Step 3: Build frontend and verify**
  - Run: `cd C:\Projeto\Prado\prado-ubuntu-hft\frontend && npm run build`
  - Verify `prado_linux/static/index.html` and assets updated cleanly and re-run `pytest tests -v`.
