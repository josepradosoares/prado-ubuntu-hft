# AGENTS.md — Prado Ubuntu HFT

## Arquitetura do Projeto
- **Backend**: Python (`prado_linux/web_app.py`, `prado_linux/engine.py`, `prado_linux/deriv_client.py`, `prado_linux/config.py`, `prado_linux/flow_math.py`, `prado_linux/auth.py`).
- **Frontend**: React + TypeScript + Tailwind CSS + Lightweight Charts (`frontend/src/`), compilado para `prado_linux/static/` e servido na porta `8080` sem necessidade de Node.js em produção.
- **Testes**: `tests/` (`PYTHONPATH=. python -m pytest tests -v`).

## Regra Permanente da Deriv API (OBRIGATÓRIO)
Antes de qualquer alteração envolvendo integração com a Deriv (autenticação, tokens, App ID, REST, WebSocket, OTP, símbolos, ticks, propostas, compra, venda, contratos, saldo, limites ou robôs), leia e siga estritamente:

- [Regra Permanente Deriv API](.agent/rules/deriv-api.md)
- Índice oficial offline: `docs/vendor/deriv-api/llms.txt`
- Guias e endpoints: `docs/vendor/deriv-api/llms/`
- Schemas: `docs/vendor/deriv-api/schemas/`
- Manifesto de integridade: `docs/vendor/deriv-api/manifest.json`
- Auditoria da integração: `docs/vendor/deriv-api/INTEGRATION_AUDIT.md`

## Fluxo Oficial de Autenticação & Negociação Deriv (API Moderna)
1. **Dados públicos de mercado**: `wss://api.derivws.com/trading/v1/options/ws/public` (sem OTP, sem token).
2. **REST autenticado (PAT `pat_...`)**: `https://api.derivws.com` com cabeçalhos `Authorization: Bearer <token>` e `Deriv-App-ID: <app_id>`.
3. **WebSocket autenticado (Negociação)**: `POST /trading/v1/options/accounts/{accountId}/otp` retorna `data.url`. Conectar diretamente à URL retornada sem reenviar `authorize`.
4. **Campo de símbolo**: Utilizar `underlying_symbol` conforme documentação oficial da nova API.
