# API Overview

**This documents the Deriv API.** If a field or endpoint is not documented here, it does not exist in the API.

## Base URLs

- REST base: `https://api.derivws.com`
- OAuth authorization: `https://auth.deriv.com/oauth2/auth`
- OAuth token: `https://auth.deriv.com/oauth2/token`

## Gateways

- **WebSocket (public market data):** `wss://api.derivws.com/trading/v1/options/ws/public` — no authentication, no request body. Use for `ticks`, `active_symbols`, `proposal`, `time`, `trading_times`.
- **WebSocket (authenticated trading):** obtained from `POST /trading/v1/options/accounts/{accountId}/otp`, which returns a one-time-password WebSocket URL (`wss://api.derivws.com/trading/v1/options/ws/real` or `/ws/demo`). Connect to that URL and send messages directly.
- **REST:** `https://api.derivws.com` — authenticated calls require `Authorization: Bearer <token>` (plus `Deriv-App-ID` when using PAT authentication). Base paths: `/trading/v1/options/` (accounts, OTP, contracts), `/wallet/v1/` (Wallet balances, transactions, transfers), `/payment-agents/v1/`, `/partners/` (partner analytics, client tags), `/account/v1/`, `/applications/v1/`.

## Auth model summary

- OAuth2 Authorization Code + PKCE → Bearer access token.
- REST trading calls: `Authorization: Bearer` (plus `Deriv-App-ID` for PAT auth).
- WebSocket trading: exchange the Bearer token for an OTP URL via `POST .../otp`, then connect.
- Bulk-purchase: `Deriv-App-ID` + per-account PATs (no Bearer).
- Wallet and payment-agent calls: `Authorization: Bearer` carrying the `payment` scope (plus `Deriv-App-ID` for PAT auth). A token without `payment` scope is rejected with `403`.
- Partners calls: `Authorization: Bearer` carrying the `application_read` scope (plus `Deriv-App-ID` for PAT auth). A token without `application_read` scope is rejected with `403`.

See [authentication](https://developers.deriv.com/llms/authentication.md) for the full flow.

## Rate limits

These are the limits on the [Limits page](https://developers.deriv.com/docs/limits). We provide them for reference and reserve the right to change them at any time.

**WebSocket API.** Each line below is one budget, shared by the calls in it: requests to any of those calls draw on the same counter. The per-minute and per-hour limits apply at the same time.

- `proposal`, `proposal_open_contract`, `buy`, `sell`: 360 per minute and 14,400 per hour
- `balance`, `statement`: 100 per minute and 2,000 per hour
- `portfolio`, `profit_table`: 30 per minute and 1,500 per hour
- All other calls, which includes `contracts_for`: 220 per minute and 14,400 per hour

`ping` sits outside these budgets. Each connection can send 10 pings per second.

**REST API.** Each request counts against the IP address it comes from and, once you are logged in, against your account as well.

- IP address: 300 requests per 1 minute, and 1,000 requests per 10 minutes
- Logged-in user: 80 requests per minute. Once you are logged in, you reach this limit first.

## Resources

- **Documentation:** https://developers.deriv.com/docs/
- **Interactive Playground:** https://developers.deriv.com/playground
- **Support:** api-support@deriv.com

_Source: [api-overview](https://developers.deriv.com/llms/api-overview.md)._
