# Prado Institutional HFT — Deriv Multipliers Native Integration Design

**Date:** 2026-11-22
**Target Repository:** `C:\Projeto\Prado\prado-ubuntu-hft`
**Runtime Target:** Ubuntu Server (`152.67.44.54:8080`, Python 3 + systemd)

---

## 1. Intent and Why
Replace all legacy MetaTrader 5 / MetaApi Cloud / XM Global configuration and bridge code with a **100% free, zero-terminal, pure-Python Deriv WebSocket API integration** (`wss://ws.derivws.com/websockets/v3?app_id=1089`).

The user wants to run their quantitative VWAP + Standard Deviation ($\pm 2\sigma$) + Aggression Z-Score trading bots 24/7 on their Ubuntu VPS **without** running MetaTrader anywhere and **without** paying third-party MetaApi hosting fees.

---

## 2. Goals, Non-Goals, and Anti-Goals
- **Goals:**
  1. **Remove legacy MT5/MetaApi/XM code:** Delete `metaapi_client.py`, remove `mt5_login`/`mt5_server`/`metaapi_token` fields, remove XM Global pre-seeded accounts and broker server autocomplete.
  2. **Pure-Python Deriv Client (`prado_linux/deriv_client.py`):** Connect to `wss://ws.derivws.com/websockets/v3` (using `websocket-client` or lightweight RFC-6455 client, injectable transport for 100% deterministic unit tests) and support:
     - `authorize` (validates token, reads `loginid` e.g. `VRTC...` Demo or `CR...` Real, `currency`, `balance`, `is_virtual`);
     - `active_symbols` (discovers **Principais** vs **Todos** Deriv symbols across Synthetic Volatility 24/7, Forex, Gold, and Crypto);
     - `ticks_history` + `ticks` stream (feeds real-time ticks into `flow_math.py` for VWAP, $\pm 2\sigma$, and Z-Score);
     - `proposal` + `buy` (`MULTUP` / `MULTDOWN` Multipliers with `amount` stake, `multiplier`, `limit_order` Stop Loss & Take Profit);
     - `portfolio` / `proposal_open_contract` (live open positions and real-time P&L);
     - `sell` (immediate single-position close and *Zerar todas as posições*).
  3. **Updated Web UI — Área Dedicada para Salvar & Usar Tokens Deriv (`prado_linux/templates.py`):**
     - Replace "Contas Demo e Real (MT5)" with **"Tokens & Contas Deriv (Demo e Real)"**:
       - Formulário limpo para salvar o **Deriv API Token** (`pat_...`), **Nome da conta**, **Ambiente (Demo / Real)**, **App ID** (padrão `1089`), **Stake padrão (USD)** e **Multiplicador (ex: 100x)**;
       - Ao salvar o token, o backend chama `authorize` na Deriv, valida na hora se o token funciona, exibe o **Login ID (`VRTC...` ou `CR...`)**, **Saldo Real/Demo** e **Moeda (`USD`)**, e salva o token no `data/prado_server_config.json` para todas as negociações dos robôs;
       - Tabela de tokens/contas salvas com botões **Ativar para negociações**, **Editar** e **Apagar** (com seletor rápido no topo do painel para trocar entre Token Demo e Token Real com 1 clique).
     - Keep all existing quantitative features intact: Login screen, **Mesa de execução e robôs** (click-to-edit, Comprar/Vender, Pausar/Iniciar, Apagar, Posições Abertas, Histórico), **Configurar robô matemático** (5 Wall Street math templates + Principais/Todos + Categorias), **Backtest tick a tick**, **Categorias de ativos**, and **Matriz VWAP e Z-Score**.
- **Non-Goals:**
  - Operating MetaTrader 5 accounts (including Deriv MT5 sub-accounts).
  - Fixed-duration binary Rise/Fall (`CALL`/`PUT`) contracts in this phase.
- **Anti-Goals:**
  - Never commit user personal Deriv tokens (`pat_...`) into the public GitHub repository.
  - Never break the existing Quant Simulation fallback when no Deriv token is configured.

---

## 3. Constraints
- **OS & Memory:** Must run on Ubuntu 20.04–26.04 `x86_64` with ~80–120 MB RAM (no Docker, no Wine, no GUI).
- **Security:** Tokens stored only in local `data/prado_server_config.json` (gitignored) and masked as `********` in `/api/config` and `/api/accounts` responses.
- **Design System:** Preserve the institutional quant desk UI (`Plus Jakarta Sans` + `IBM Plex Mono`, hairline grid, single-line segmented `.action-strip`, sentence case).

---

## 4. Approaches Considered
1. **Approach A — Deriv Multipliers via WebSocket (`MULTUP` / `MULTDOWN`) *(Selected)*:**
   - Trades leveraged Multipliers with native Stop Loss, Take Profit, live P&L, and instant `sell` close. Maps 1:1 to our $\pm 2\sigma$ SL/TP engine and risk guard.
2. **Approach B — Deriv Rise/Fall Fixed-Time Contracts (`CALL` / `PUT`):**
   - Fixed expiry contracts without Stop Loss, Take Profit, or mid-trade panic flatten. Rejected because it breaks our risk guard and $\sigma$-based SL/TP model.

---

## 5. Architecture & Builder Calls (My Calls)
- **WebSocket library:** Use `websocket-client` (lightweight pure-Python, 1 small package in `requirements.txt`) with an injectable `ws_factory` / `rpc_transport` so all tests run fast and offline without hitting live Deriv servers.
- **Account discovery:** When saving a Deriv API token, call `authorize` once to auto-detect whether the token belongs to a **Demo (`is_virtual=1`, `VRTC...`)** or **Real (`is_virtual=0`, `CR...`)** account, its currency, and balance.
- **Default Deriv Symbols & Categories:**
  - *Sintéticos Volatility 24/7:* `R_10`, `R_25`, `R_50`, `R_75`, `R_100`, `1HZ10V`, `1HZ50V`, `1HZ100V`
  - *Forex & Ouro:* `frxEURUSD`, `frxGBPUSD`, `frxUSDJPY`, `frxXAUUSD`
  - *Cripto 24/7:* `cryBTCUSD`, `cryETHUSD`
- **Stake & Multiplier mapping:** Each bot can configure `lot_size` as **Stake (USD)** (default `10.0`) and `multiplier` (default `100`), with `stop_loss` / `take_profit` computed from $\sigma$ and capped safely at the stake amount.
