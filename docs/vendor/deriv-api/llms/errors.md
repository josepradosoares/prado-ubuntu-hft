# Error Handling

**Use the Deriv API documented here.** The API is OTP-authenticated for WebSocket trading.

## REST errors

REST endpoints return a structured envelope with an `errors` array and a `meta` block. The HTTP status mirrors the error `status`:

```json
{
  "errors": [
    {
      "status": 400,
      "code": "ValidationError",
      "message": "date_from is required"
    }
  ],
  "meta": {
    "endpoint": "/applications/v1/markup-statistics",
    "method": "GET",
    "timing": 12
  }
}
```

Common statuses: `400` bad request/validation, `401` unauthorized (missing/invalid token, or missing `Deriv-App-ID` when authenticating with a PAT), `403` forbidden (valid token, insufficient scope), `404` not found, `409` conflict, `422` unprocessable entity, `429` rate limited (see the Rate limits section of [api-overview](https://developers.deriv.com/llms/api-overview.md) and the [Limits page](https://developers.deriv.com/docs/limits)), `500` internal error, `502`/`503`/`504` upstream issues. Show generic messages to end users; log details server-side only.

## WebSocket errors

WebSocket responses carry an `error` object with a `code` and `message` alongside the `msg_type` of the originating call:

```json
{
  "error": { "code": "InputValidationFailed", "message": "Missing required parameter underlying_symbol" },
  "msg_type": "proposal"
}
```

If a connection is rejected or the OTP has expired, request a fresh OTP URL from `POST /trading/v1/options/accounts/{accountId}/otp` and reconnect.

## Common error codes

- `InvalidToken` — token is invalid or expired
- `RateLimit` — too many requests (see the Rate limits section of [api-overview](https://developers.deriv.com/llms/api-overview.md) and the [Limits page](https://developers.deriv.com/docs/limits))
- `InputValidationFailed` — invalid request parameters
- `ContractNotFound` — contract does not exist
- `InsufficientBalance` — not enough funds
- `ValidationError` — field validation failed
- `NotFound` — resource not found
- `Unauthorized` — authentication failed
- `InternalError` — server error

## Retries

- Retry idempotent reads (`active_symbols`, `ticks_history`, `GET` calls) with exponential backoff.
- Do **not** blindly retry `buy`. A reply with an `error` object means no contract was created. `req_id` and `passthrough` are for correlation only: they match a reply to its request. A buy by proposal ID is deduplicated — the same proposal ID can't be bought twice — but a buy with parameters (`buy: 1`) isn't, so resending it can open a second contract. If the reply is lost or times out, check `statement` before any resend — `action_type: "buy"`, `date_from` a little before you sent the `buy`, `description: 1` — match a row on its `app_id`, `amount`, `shortcode` and `transaction_time`, then follow its `contract_id` with `proposal_open_contract`. A committed purchase appears in `statement` immediately and every executed buy is listed, so no matching row means no contract was bought. A `buy` in flight when the connection dropped executes only if the server processed it before the drop.
- Do **not** blindly retry bulk purchase. It has no request ID, and duplicate account pairs are honoured as repeated purchases. If the response is lost, check each account's `statement` the same way before resending.
- Before retrying `sell`, use the `contract_id` you already hold to check `is_sold` with `proposal_open_contract`.

_Source: [errors](https://developers.deriv.com/llms/errors.md)._
