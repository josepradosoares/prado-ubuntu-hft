# Regra Permanente da cTrader Open API — Prado Ubuntu HFT

## 1. Protocolo e Transporte Oficial
- Utilizar exclusivamente **JSON sobre WebSocket na porta `5036`** com `websocket-client` (sem `ctrader-open-api`/Twisted para não conflitar com `ThreadingHTTPServer`).
- **Ambiente Demo:** `wss://demo.ctraderapi.com:5036` (`isLive = false`)
- **Ambiente Live (Real):** `wss://live.ctraderapi.com:5036` (`isLive = true`)
- Sempre rotear para o host correspondente ao `isLive` da conta selecionada.
- Envelope JSON obrigatório:
  ```json
  { "clientMsgId": "req_1", "payloadType": 2100, "payload": { ... } }
  ```

## 2. Autenticação OAuth 2.0 & Handshake
1. **Portal de Apps:** `https://openapi.ctrader.com/apps` (onde se cria o App para obter `client_id` e `client_secret`).
2. **Autorização do Usuário (OAuth2):** `https://id.ctrader.com/my/settings/openapi/grantingaccess/?client_id=...&redirect_uri=...&scope=trading&product=web`
3. **Troca / Renovação de Token (HTTP GET):** `https://openapi.ctrader.com/apps/token` (`grant_type=authorization_code` ou `refresh_token`).
4. **Sequência no WebSocket:**
   - `2100` (`ProtoOAApplicationAuthReq`: `clientId`, `clientSecret`) -> `2101`
   - `2149` (`ProtoOAGetAccountListByAccessTokenReq`: `accessToken`) -> `2150`
   - `2102` (`ProtoOAAccountAuthReq`: `ctidTraderAccountId`, `accessToken`) -> `2103`
   - `2121` (`ProtoOATraderReq`) e `2112` (`ProtoOAAssetListReq`) para saldo, moeda e alavancagem.

## 3. Escalas Numéricas Críticas
- **Preços** (`ProtoOASpotEvent`, `ProtoOATrendbar`, `ProtoOATickData`, `relativeStopLoss`, `relativeTakeProfit`): escala `100_000` (`1 / 100000` da unidade de preço).
- **Valores monetários** (`balance`, `grossProfit`, `swap`, `commission`, `netUnrealizedPnL`): dividir por `10 ** moneyDigits` (padrão `2` se omitido).
- **Volumes** (`lotSize`, `minVolume`, `maxVolume`, `stepVolume`, `volume` em ordens/fechamento): em centicents (`0.01` unidade). Sempre converter lotes usando `lotSize` do símbolo (`ProtoOASymbol`) e fazer clamp/snap por `minVolume`/`maxVolume`/`stepVolume`.
- **Histórico de Ticks (`2145`/`2146`):** `tickData` retorna mais recente primeiro com delta-encoding cumulativo em `timestamp` e `tick`. Decodificar cumulativamente e inverter para ordem cronológica.

## 4. Execução de Ordens e Segurança
- Ordens `MARKET` (`orderType = 1`) usam `relativeStopLoss` e `relativeTakeProfit` (nunca `stopLoss`/`takeProfit` absolutos).
- Stop Loss obrigatório na abertura de posição CFD para proteção de margem.
- **Nunca** fazer fallback silencioso de `DEMO` para `REAL` (lançar `NO_DEMO_ACCOUNT`).
- Negociação em conta `REAL` permanece bloqueada por padrão até `allow_real_trading = True`.
- **Nunca** reenviar `ProtoOANewOrderReq` automaticamente após timeout sem reconciliar (`2124`).

## 5. Rate Limits e Heartbeat
- Tempo real / ordens / conta: **50 req/s**.
- Histórico (`GetTrendbars`, `GetTickData`, `DealList`): **5 req/s**.
- Enviar `HeartbeatEvent` (`payloadType = 51`) periodicamente (<= 25s).
