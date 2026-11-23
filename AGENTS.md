# AGENTS.md — Prado Ubuntu HFT

## Arquitetura do Projeto
- **Backend**: Python (`prado_linux/web_app.py`, `prado_linux/engine.py`, `prado_linux/ctrader_client.py`, `prado_linux/config.py`, `prado_linux/flow_math.py`, `prado_linux/auth.py`, `prado_linux/indicators.py`, `prado_linux/news_scout.py`, `prado_linux/supabase_store.py`).
- **Frontend**: React + TypeScript + Tailwind CSS + Lightweight Charts (`frontend/src/`), compilado para `prado_linux/static/` e servido na porta `8080` sem necessidade de Node.js em produção.
- **Testes**: `tests/` (`PYTHONPATH=. python -m pytest tests -v`).

## Regra Permanente da cTrader Open API (OBRIGATÓRIO)
Antes de qualquer alteração envolvendo integração com a cTrader (autenticação OAuth 2.0, Client ID/Secret, WebSocket porta 5036, símbolos, spots, trendbars, tickdata, ordens, posições, saldo, limites ou robôs), leia e siga estritamente:

- [Regra Permanente cTrader Open API](.agent/rules/ctrader-api.md)

## Fluxo Oficial de Autenticação & Negociação cTrader (Open API Porta 5036)
1. **Hosts WebSocket JSON (porta 5036)**:
   - Demo: `wss://demo.ctraderapi.com:5036`
   - Live: `wss://live.ctraderapi.com:5036`
2. **OAuth 2.0**:
   - Cadastro de App: `https://openapi.ctrader.com/apps` (`Client ID` e `Client Secret`).
   - Autorização: `https://id.ctrader.com/my/settings/openapi/grantingaccess/`
   - Troca/Refresh de Token (`GET`): `https://openapi.ctrader.com/apps/token`
3. **Handshake WebSocket**: `2100` (`ProtoOAApplicationAuthReq`) → `2149` (`ProtoOAGetAccountListByAccessTokenReq`) → `2102` (`ProtoOAAccountAuthReq`) no host (`demo` ou `live`) correspondente ao `isLive` da conta.
4. **Ordens a Mercado (`2106`)**: Usar `orderType = 1` (MARKET), `volume` em centicents conforme `lotSize` do símbolo, e proteção via `relativeStopLoss` / `relativeTakeProfit`.
