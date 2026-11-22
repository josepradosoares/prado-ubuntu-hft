# Custom Math Models (21 Indicators + Python Editor/Upload) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `Modelos Matemáticos` menu allowing users to create, edit, test, and delete custom trading models via either a 21-indicator visual builder or a custom Python editor/upload, and integrate them into bot execution and backtesting.

**Architecture:** Implement 21 pure-Python technical/institutional indicators and safe Python-strategy execution in `prado_linux/indicators.py`, persist `custom_templates` in `PradoServerConfig`, wire CRUD/test/execution into `engine.py` and `web_app.py`, and build a dedicated `ModelBuilderPanel.tsx` + `Sidebar.tsx` tab in React.

**Tech Stack:** Python 3.14 (stdlib `math`, `statistics`, `ast`, `io`, `contextlib`), React + TypeScript + Tailwind CSS + Vite.

**Spec:** `docs/superpowers/specs/2026-11-22-custom-math-models-design.md`

## Global Constraints
- Pure Python only for indicators (no `TA-Lib` or `pandas-ta`).
- Native `MATH_BOT_TEMPLATES` (1–6) cannot be deleted or broken.
- Errors in custom Python strategies must never crash `step_once()` or the web server.
- Windows PowerShell build uses `npm.cmd run build`; tests use `py -3.14 -m pytest`.

## Review Focus
- Short tick/candle series (`len < period`): indicators must return `0` (NEUTRAL) safely without `ZeroDivisionError` or `IndexError`.
- Custom Python syntax error or runtime exception (e.g., `1/0`, missing `evaluate`): `/api/bot-templates/test` returns `{ ok: False, error: ... }` and `step_once()` logs/falls back to `WAIT`.
- Custom Python returning lowercase/whitespace (`" buy "`) or invalid value: normalized cleanly (`BUY`/`SELL`/`WAIT`).
- Deleting a custom template that is not native works; attempting to delete a native template returns an error.
- Custom templates saved in `config.json` persist across `load_config()` and appear in `/api/bot-templates`, `Configurar robô matemático`, and `Backtest`.

---

### Task 1: Pure-Python 21 Indicators & Safe Python Evaluator (`prado_linux/indicators.py`)

**Files:**
- Create: `prado_linux/indicators.py`
- Test: `tests/test_deriv_integration.py`

- [ ] **Step 1:** Create `prado_linux/indicators.py` with `INDICATOR_CATALOG` (all 21 indicators across Tendência, Momento, Volatilidade, Institucional), `evaluate_indicator(name, ticks, params)`, `evaluate_indicator_model(ticks, indicators_cfg, combine_mode)`, and `evaluate_python_model(code, prices, ticks, params)` (using `ast.parse` + restricted globals + `redirect_stdout` + timing).
- [ ] **Step 2:** Write unit test `test_21_indicators_and_custom_python_evaluator` in `tests/test_deriv_integration.py` verifying all 21 indicator IDs compute cleanly, `evaluate_indicator_model` returns `BUY`/`SELL`/`WAIT`, and `evaluate_python_model` handles valid scripts, syntax errors, and runtime exceptions.
- [ ] **Step 3:** Run `py -3.14 -m pytest tests/test_deriv_integration.py -k test_21_indicators -v` and confirm PASS.

---

### Task 2: Persistence, Engine Execution, Backtest & API Routes (`config.py`, `engine.py`, `web_app.py`)

**Files:**
- Modify: `prado_linux/config.py`
- Modify: `prado_linux/engine.py`
- Modify: `prado_linux/web_app.py`
- Test: `tests/test_deriv_integration.py`

- [ ] **Step 1:** Add `custom_templates: list[dict[str, Any]]` to `PradoServerConfig` in `config.py` (serialized/deserialized in `load_config` / `save_config`).
- [ ] **Step 2:** In `engine.py`, add `get_all_templates()`, `save_custom_template(payload)`, `delete_custom_template(template_id)`, `test_custom_template(payload)`, and update `create_bot`, `step_once()`, and `run_backtest()` to evaluate `CUSTOM_INDICATORS` and `CUSTOM_PYTHON` templates.
- [ ] **Step 3:** In `web_app.py`, update `GET /api/bot-templates` (include `templates` + `indicators` catalog), add `POST /api/bot-templates` (`SAVE` / `DELETE`), and add `POST /api/bot-templates/test`.
- [ ] **Step 4:** Add `test_custom_templates_crud_test_and_execution` in `tests/test_deriv_integration.py` and run pytest to confirm PASS.

---

### Task 3: Frontend Menu & Builder UI (`types.ts`, `Sidebar.tsx`, `ModelBuilderPanel.tsx`, `App.tsx`)

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/ModelBuilderPanel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1:** Update `BotTemplate` and add `IndicatorMeta` / `CustomIndicatorSelection` types in `frontend/src/types.ts`.
- [ ] **Step 2:** Add `'templates'` (`Modelos Matemáticos`) tab to `Sidebar.tsx` and `PAGE_META` in `App.tsx`.
- [ ] **Step 3:** Create `frontend/src/components/ModelBuilderPanel.tsx` with:
  - List of native (read-only badge) + custom models (Edit / Delete).
  - Mode switcher: **Indicadores (21)** vs **Código Python (Editor + Upload `.py`)**.
  - 21-indicator selector grouped by category with per-indicator parameter inputs and `ALL`/`MAJORITY` rule.
  - Python code editor + `<input type="file" accept=".py">` upload button + asset selector + **Testar Código** button showing signal, elapsed ms, stdout, and errors.
- [ ] **Step 4:** Wire `ModelBuilderPanel` into `App.tsx` and refresh `templates` after save/delete.

---

### Task 4: Build, Full Test Verification & Push

- [ ] **Step 1:** Run `cd C:\Projeto\Prado\prado-ubuntu-hft\frontend; npm.cmd run build` (`tsc -b && vite build`).
- [ ] **Step 2:** Run full `pytest` suite (`tests/`) and confirm 0 failures.
- [ ] **Step 3:** Commit all changes and push to `origin/main`.
