# Deriv Multipliers Native Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all legacy MetaTrader 5 / MetaApi Cloud / XM Global code and replace it with a pure-Python Deriv WebSocket API (`wss://ws.derivws.com/websockets/v3`) connector for Multipliers (`MULTUP` / `MULTDOWN`) plus a dedicated Token Vault UI in the web panel.

**Architecture:** `prado_linux/deriv_client.py` handles WebSocket RPC calls (`authorize`, `active_symbols`, `ticks_history`, `proposal`, `buy`, `portfolio`, `sell`) with an injectable transport for deterministic offline testing. `prado_linux/engine.py` wires `DerivClient` into `PradoTradingService` (alongside the Quant Simulation fallback), while `prado_linux/templates.py` provides a dedicated **Tokens e Contas Deriv (Demo e Real)** panel area to save, validate, switch, edit, and delete Deriv API tokens used in live trades.

**Tech Stack:** Python 3.10+, `websocket-client`, `pytest`, `systemd`, `Plus Jakarta Sans` + `IBM Plex Mono` institutional UI.

**Spec:** `docs/superpowers/specs/2026-11-22-deriv-multipliers-design.md`

## Global Constraints
- Zero MetaTrader 5, MetaApi Cloud, Wine, or Docker dependencies.
- Never commit personal user tokens (`pat_...`) into Git; store only in gitignored `data/prado_server_config.json`.
- Mask saved `deriv_token` as `********` in `/api/config` and `/api/accounts` HTTP responses.
- Keep `flow_math.py` universal VWAP + $\pm 2\sigma$ + Z-Score engine intact and all 8+ tests passing.

## Review Focus
- Invalid or expired Deriv token on `authorize` must return a clear Portuguese error and fall back safely to `SIMULATION_FEED` without crashing the background loop.
- Switching between a saved Demo token and Real token in the header or Tokens tab must immediately re-authorize and refresh `account` balance/loginid.
- Editing a saved account without retyping the token must preserve the existing `deriv_token`.
- Stop Loss / Take Profit on Deriv Multipliers must never exceed the stake or send invalid negative values.
- `close_all_positions` (*Zerar todas as posições*) must call `sell` on every open contract ID returned by `portfolio`.

---

### Task 1: Create `prado_linux/deriv_client.py` & Remove `metaapi_client.py`

**Files:**
- Delete: `prado_linux/metaapi_client.py`
- Create: `prado_linux/deriv_client.py`
- Modify: `requirements.txt`
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: `DerivClient(token: str, app_id: str = "1089", rpc_transport: Callable | None = None)` with methods `authorize()`, `get_active_symbols()`, `get_ticks_history(symbol, count)`, `place_multiplier_order(symbol, is_buy, stake, multiplier, sl_amount, tp_amount)`, `get_open_contracts()`, `close_contract(contract_id)`.

- [ ] **Step 1: Write failing test for `DerivClient` (authorize, symbols, ticks, buy multiplier, portfolio, sell)**
- [ ] **Step 2: Run pytest to confirm failure (`ModuleNotFoundError: No module named 'prado_linux.deriv_client'`)**
- [ ] **Step 3: Implement `DerivClient` in `prado_linux/deriv_client.py`, add `websocket-client>=1.6.0` to `requirements.txt`, delete `prado_linux/metaapi_client.py`**
- [ ] **Step 4: Run pytest to verify `DerivClient` tests pass**

---

### Task 2: Clean `prado_linux/config.py` & `prado_linux/engine.py` for Deriv-Only + Simulation

**Files:**
- Modify: `prado_linux/config.py`
- Modify: `prado_linux/engine.py`
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: `PradoServerConfig` with `deriv_token`, `deriv_app_id = "1089"`, `default_stake_usd = 10.0`, `default_multiplier = 100`, `accounts` (Deriv tokens list), `DEFAULT_CATEGORIES` with Deriv 24/7 symbols (`R_10`, `R_25`, `R_50`, `R_75`, `R_100`, `1HZ10V`, `1HZ100V`, `frxEURUSD`, `frxXAUUSD`, `cryBTCUSD`).
- Produces: `DerivUniversalConnector` and `PradoTradingService` without any `mt5_*` or `metaapi_*` fields.

- [ ] **Step 1: Update tests in `tests/test_web_server.py` to test Deriv token saving, Demo/Real switching, and symbol discovery**
- [ ] **Step 2: Run pytest to verify RED on legacy fields**
- [ ] **Step 3: Rewrite `prado_linux/config.py` and `prado_linux/engine.py` cleanly**
- [ ] **Step 4: Run pytest to verify GREEN**

---

### Task 3: Update `prado_linux/web_app.py` & `prado_linux/templates.py` (Token Vault Area)

**Files:**
- Modify: `prado_linux/web_app.py`
- Modify: `prado_linux/templates.py`
- Modify: `README.md`
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: `/api/accounts` (saves/validates Deriv Token via `authorize`, masks `deriv_token` in responses), `/api/accounts/select`, `/api/symbols`, `/api/bots`, `/api/backtest`, `/api/flatten`, `/api/risk/reset`.
- UI: Dedicated **"Tokens e Contas Deriv (Demo e Real)"** tab where user saves/tests/edits/deletes Deriv API tokens used for live trading.

- [ ] **Step 1: Update `web_app.py` routes and mask `deriv_token` in `_safe_config_dict()` and `/api/accounts`**
- [ ] **Step 2: Update `templates.py` with Deriv Token Vault form, Deriv Multiplier stake/multiplier inputs on bots, and clean institutional labels**
- [ ] **Step 3: Run full `pytest` suite (`8/8` passing, zero warnings), commit, and push to GitHub**
