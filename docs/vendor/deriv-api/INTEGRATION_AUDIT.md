# Auditoria Completa da Integração Deriv API — Prado Ubuntu HFT

Data da auditoria: 2026-11-22  
Referência oficial: `docs/vendor/deriv-api/llms.txt` (186 arquivos sincronizados: 67 Markdown + 118 schemas JSON + `llms.txt`, SHA-256 verificado via `python scripts/sync_deriv_docs.py --verify`).

## Matriz de Auditoria Atualizada

| Funcionalidade | Implementação atual | Estado | Observação / Próxima Ação |
|---|---|---|---|
| Token PAT | `deriv_client.py` valida `pat_...` via REST `https://api.derivws.com` com `Authorization: Bearer` + `Deriv-App-ID` e conecta WS via OTP | TESTADO COM MOCK / AGUARDANDO CREDENCIAL | Requer token `pat_...` + App ID próprio de `developers.deriv.com` para teste real em Demo |
| App ID | Bloqueio explícito de `pat_...` com App ID legado `1089` (`APP_ID_MISMATCH`); suporte a `DERIV_APP_ID` via env/config | IMPLEMENTADO / TESTADO COM MOCK | Configurar App ID criado em `developers.deriv.com` |
| Autenticação REST | `DerivClient._rest_call` centralizado com `Authorization: Bearer`, `Deriv-App-ID` apenas para PAT (omitido em OAuth 2.0), tratamento 401/403/429 | TESTADO COM MOCK | Aguardando credencial Demo válida para validação live |
| Escopos | HTTP 403 / `InsufficientScope` mapeado para `auth_state = INSUFFICIENT_SCOPE` e exibido no diagnóstico | TESTADO COM MOCK | Garantir escopos `trade` e `account_manage` no token PAT |
| Contas Demo | `_pick_account()` seleciona `account_type == "demo"` por padrão; `allow_real_trading=False` bloqueia Real | TESTADO COM MOCK | Aguardando credencial Demo válida |
| OTP | `POST /trading/v1/options/accounts/{accountId}/otp` obtém `data.url`; WS conecta direto sem reenviar `authorize`; renova OTP na reconexão | TESTADO COM MOCK | Aguardando credencial Demo válida |
| WebSocket público | `wss://api.derivws.com/trading/v1/options/ws/public` (sem OTP, sem token) com fallback `websocket-client` / `websockets.sync` | TESTADO LIVE (PÚBLICO) | Validado com recebimento real de ticks `R_100` e 95 símbolos ativos |
| WebSocket Demo | Conecta via `data.url` do endpoint OTP (`/ws/demo?otp=...`) com `ping()` e `reconnect()` controlados | TESTADO COM MOCK / AGUARDANDO CREDENCIAL | Requer credencial PAT + App ID para teste real em Demo |
| WebSocket Real | Bloqueado por padrão (`allow_real_trading=False`) em `place_order()` e `_compute_trading_state()` | IMPLEMENTADO / TESTADO COM MOCK | Manter bloqueado por padrão |
| Catálogo de símbolos | `{"active_symbols": "brief"}` com mapeamento `underlying_symbol` / `underlying_symbol_name` e cache de 60s | TESTADO LIVE (PÚBLICO) | 95 ativos recebidos do WS público |
| Ticks | `get_ticks_history` com `req_id`, cache compartilhado de 3s por símbolo e controle de orçamento | TESTADO LIVE (PÚBLICO) | Ticks reais de `R_100` validados |
| Histórico | `get_ticks_history` sob `DerivRateLimiter` (orçamento `other`: 220/min, 14400/h) | TESTADO LIVE (PÚBLICO) | Respeita fila e cache compartilhado |
| Proposal | `place_multiplier_order()` envia `underlying_symbol`, `proposal: 1`, `basis: stake`, `limit_order` | TESTADO COM MOCK | Aguardando credencial Demo para execução real |
| Buy | `buy` com `req_id`, ciclo de vida distinto (`ORDER_REQUESTED` -> `PROPOSAL_VALIDATED` -> `CONTRACT_OPEN`), nunca reenvia em timeout | TESTADO COM MOCK | Aguardando credencial Demo para execução real |
| Contratos abertos | `get_open_contracts()` com cache de 5s respeitando orçamento `portfolio` (30/min) | TESTADO COM MOCK | Aguardando credencial Demo |
| Sell | `close_contract()` via `DerivRateLimiter`, registra resultado em `deals_history` | TESTADO COM MOCK | Aguardando credencial Demo |
| Portfolio | Cache de 5s em `get_open_positions()` respeitando 30 req/min | TESTADO COM MOCK | Evita loop de polling |
| Balance | `get_balance()` leve com cache de 10s (100/min) sem re-chamar `authorize()` no loop | TESTADO COM MOCK | Elimina causa raiz de RateLimit |
| RateLimit | `DerivRateLimiter` centralizado com janelas WS/REST oficiais, backoff exponencial + jitter e bloqueio em `place_order()` | IMPLEMENTADO / TESTADO COM MOCK | Recuperação após cooldown validada em testes |
| Reconexão | `ping()` periódico (30s) + `reconnect()` com transição `RECONNECTING` -> `CONNECTED` / `DISCONNECTED` e renovação de OTP | IMPLEMENTADO / TESTADO COM MOCK | Estados separados refletidos no painel |
