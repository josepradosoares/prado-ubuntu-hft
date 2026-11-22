# Auditoria Completa da Integração Deriv API — Prado Ubuntu HFT

Data da auditoria: 2026-11-22  
Referência oficial: `docs/vendor/deriv-api/llms.txt` (186 arquivos sincronizados, SHA-256 verificado).

## Matriz de Auditoria

| Funcionalidade | Implementação atual | Estado | Correção |
|---|---|---|---|
| Token PAT | `deriv_client.py` aceita `pat_` apenas em REST quando `app_id != "1089"` e depois tenta `{"authorize": token}` no WebSocket v3 | Incompatível | Usar REST `https://api.derivws.com` com `Authorization: Bearer <token>` + `Deriv-App-ID` e fluxo OTP para WebSocket |
| App ID | `1089` como padrão em `config.py` e `deriv_client.py` | Legado / Incompatível com PAT | Bloquear `pat_` com `1089` com diagnóstico claro (`APP_ID_MISMATCH`), exigir App ID de `developers.deriv.com` para PAT |
| Autenticação REST | `GET /trading/v1/options/accounts` parcial em `authorize()` | Parcial | Centralizar cliente REST com `Authorization: Bearer`, `Deriv-App-ID` (somente PAT), tratamento 401/403/429 |
| Escopos | Não validados na resposta nem sinalizados no painel | Pendente | Tratar `403` / `InsufficientScope` como `INSUFFICIENT_SCOPE` (ex.: `trade`, `account_manage`) |
| Contas Demo | Seleciona `accounts[0]` sem filtrar `account_type == "demo"` | Parcial | Filtrar conta Demo (`account_type == "demo"`) por padrão e manter Real bloqueada salvo liberação explícita |
| OTP | Inexistente (`_send_rpc` enviava `{"authorize": token}` no WS) | Ausente | Implementar `POST /trading/v1/options/accounts/{accountId}/otp` e conectar direto em `data.url` sem `authorize` |
| WebSocket público | Conectava em `wss://red.derivws.com/websockets/v3?app_id=...` | Legado | Migrar para `wss://api.derivws.com/trading/v1/options/ws/public` (sem OTP, sem auth) |
| WebSocket Demo | Conectava em `websockets/v3` com `authorize` | Incompatível com API moderna | Conectar via `data.url` retornado pelo endpoint OTP (`/ws/demo?otp=...`) |
| WebSocket Real | Sem trava dedicada na camada de execução | Risco | Manter negociação Real bloqueada por padrão (`allow_real_trading=False`) |
| Catálogo de símbolos | Usava `{"active_symbols": "brief", "product_type": "basic"}` e lia `symbol`/`display_name` | Legado | Usar `{"active_symbols": "brief"}` e mapear `underlying_symbol` / `underlying_symbol_name` (com fallback compatível) |
| Ticks | Polling via `ticks_history` a cada ciclo sem `req_id` | Polling excessivo | Cache compartilhado de 3s + throttling/fila + suporte a `ticks` subscription no WS público |
| Histórico | `get_ticks_history` sem `req_id` nem controle de orçamento | Parcial | Adicionar `req_id`, fila centralizada e respeitar orçamento de 220 req/min |
| Proposal | Enviava `"symbol"` em vez de `"underlying_symbol"` | Incompatível com nova API | Enviar `"underlying_symbol"` conforme `proposal.md` |
| Buy | Sem `req_id`, sem reconciliação em timeout | Risco de duplicidade | Adicionar `req_id`, nunca repetir `buy` em timeout sem checar `portfolio`/`proposal_open_contract` |
| Contratos abertos | Chamava `portfolio` + `proposal_open_contract` em loop a cada 1s em `get_account_summary()` | Causador de RateLimit | Respeitar orçamento de `portfolio` (30/min) com cache/throttle e evitar chamar `authorize()` no loop |
| Sell | `sell` sem `req_id` nem verificação de orçamento | Parcial | Passar pelo gerenciador de fila/rate-limit com `req_id` |
| Portfolio | Chamado em todo `get_account_summary()` | Polling excessivo | Cache/intervalo controlado respeitando 30 req/min |
| Balance | Chamado via `authorize()` a cada 1s em `get_account_summary()` | Causador principal de RateLimit | Substituir por `balance` com cache/throttle (100/min) sem re-autenticar a cada ciclo |
| RateLimit | Nenhum controle; `step_once()` disparava RPCs a cada 1s | Crítico | Implementar `DerivRateLimiter` com orçamentos oficiais, fila, concorrência, backoff exponencial + jitter |
| Reconexão | Sem ping, sem detecção de queda, sem renovação de OTP | Incompleto | Implementar `ping`, detecção de desconexão, renovação de OTP e atualização imediata dos 5 estados |
