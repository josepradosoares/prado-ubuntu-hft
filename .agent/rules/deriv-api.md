# Regra Permanente — Integração Oficial Deriv API

## Consulta Obrigatória
Antes de qualquer alteração envolvendo **Tokens, Autenticação, App ID, REST, WebSocket, OTP, Ativos, Ticks, Histórico, Propostas, Compra, Venda, Contratos, Portfolio, Saldo, Limites, Erros ou Robôs**, todo agente de programação DEVE consultar a documentação oficial sincronizada localmente em:

- `docs/vendor/deriv-api/llms.txt`
- `docs/vendor/deriv-api/llms/`
- `docs/vendor/deriv-api/schemas/`
- `docs/vendor/deriv-api/manifest.json`
- `docs/vendor/deriv-api/INTEGRATION_AUDIT.md`

Para atualizar ou verificar a integridade da documentação local, execute:
```bash
python scripts/sync_deriv_docs.py
python scripts/sync_deriv_docs.py --verify
```

## Proibições Estritas
1. **NUNCA inventar endpoints** REST ou WebSocket. Utilizar apenas os documentados em `docs/vendor/deriv-api/llms.txt` e `docs/vendor/deriv-api/llms/`.
2. **NUNCA inventar parâmetros**. Sempre conferir os nomes exatos dos campos (ex.: `underlying_symbol` na nova API `/trading/v1/options/...`, `proposal`, `buy`, `sell`, `contract_id`, `req_id`).
3. **NUNCA misturar API antiga (`ws.derivws.com/websockets/v3` + App ID legado 1089) com a API moderna (`api.derivws.com/trading/v1/options/...` + PAT `pat_...` + OTP)**.
4. **NUNCA utilizar App IDs incompatíveis** com o tipo de token (tokens `pat_...` exigem App ID registrado em `developers.deriv.com` e cabeçalho `Deriv-App-ID` no REST; o App ID legado `1089` não aceita `pat_...`).
5. **NUNCA expor tokens** no frontend, HTML, logs, Git ou respostas públicas da API. Sempre mascarar (ex.: `pat_****1234`).
6. **NUNCA ignorar schemas** ou respostas de erro da Deriv (`error.code`, `error.message`).
7. **NUNCA repetir ordens (`buy`) automaticamente** após timeout sem antes consultar `proposal_open_contract` / `portfolio` e reconciliar o contrato para evitar compras duplicadas.
8. **NUNCA fazer polling desnecessário** (`authorize`, `ticks_history`, `portfolio`) quando uma assinatura WebSocket (`subscribe: 1`) ou cache compartilhado for suficiente. Respeitar os orçamentos de `docs/vendor/deriv-api/llms/api-overview.md`.
9. **NUNCA executar operações financeiras reais** durante testes automatizados. Priorizar conta Demo (`demo`) e manter conta Real bloqueada por padrão.
