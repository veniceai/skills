---
name: venice-api-keys
description: Manage Venice API keys. Covers GET/POST/PATCH/DELETE /api_keys, GET /api_keys/{id}, GET /api_keys/rate_limits, GET /api_keys/rate_limits/log, the two-step /api_keys/generate_web3_key wallet flow, INFERENCE vs ADMIN key types, per-key consumption limits (USD / DIEM), and rate_limits balances (USD / DIEM / BUNDLED_CREDITS).
---

# Venice API Keys

Admin endpoints for managing Bearer API keys. You need an **ADMIN** key (or parent session) to call these. For wallet-only auth, use [`venice-auth`](../venice-auth/SKILL.md) / [`venice-x402`](../venice-x402/SKILL.md) instead.

| Endpoint | Purpose |
|---|---|
| `GET /api_keys` | List your keys (masked). |
| `POST /api_keys` | Create a new key. Response contains the **only copy of the secret**. |
| `PATCH /api_keys` | Update `description`, `expiresAt`, `consumptionLimit`. |
| `DELETE /api_keys?id=...` | Revoke a key. |
| `GET /api_keys/{id}` | Full details for one key (usage, limits, expiration). |
| `GET /api_keys/rate_limits` | Balances (`USD` / `DIEM` / `BUNDLED_CREDITS`) + per-model rate-limit tiers for the current key. |
| `GET /api_keys/rate_limits/log` | Last 50 rate-limit breaches. |
| `GET /api_keys/generate_web3_key` | Get a SIWE-style token to sign with a wallet. |
| `POST /api_keys/generate_web3_key` | Authenticate a wallet (holds sVVV) and mint a classic API key. |

Limits: key creation is capped at **20 requests/minute** and **500 active keys per user**.

## Key types

| Type | Can call |
|---|---|
| `INFERENCE` | Inference endpoints plus any route that only requires authentication — e.g. `/chat/*`, `/image/*`, `/audio/*`, `/video/*`, `/embeddings`, `/augment/*`, `/crypto/rpc`, `/characters`, `/api_keys/rate_limits*`, `/support-bot`. Rejected from admin routes listed below with `401`. |
| `ADMIN` | Everything an `INFERENCE` key can do, plus admin-only routes: `POST/PATCH/DELETE /api_keys`, `GET /api_keys` (list), `GET /api_keys/{id}`, `GET /billing/balance`, `GET /billing/usage`. |

A leaf app should almost always use **`INFERENCE`** keys — per-app, per-user, with consumption caps.

## `GET /api_keys`

```bash
curl https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $ADMIN_KEY"
```

Returns:

```json
{
  "object": "list",
  "data": [
    {
      "id": "uuid",
      "apiKeyType": "INFERENCE",
      "description": "backend prod",
      "createdAt": "2025-10-01T12:00:00Z",
      "expiresAt": null,
      "lastUsedAt": "2026-04-20T10:05:00Z",
      "last6Chars": "2V2jNW",
      "consumptionLimits": { "usd": 50, "diem": 10 },
      "usage": { "trailingSevenDays": { "usd": "4.20", "diem": "0.00" } }
    }
  ]
}
```

The full secret is **never** returned on list — only `last6Chars`.

## `POST /api_keys` — create

```bash
curl https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "apiKeyType": "INFERENCE",
    "description": "backend prod",
    "expiresAt": "2026-12-31T23:59:59Z",
    "consumptionLimit": { "usd": 50, "diem": 10 }
  }'
```

Response includes the **one-time** `apiKey` secret:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "apiKey": "VENICE_INFERENCE_KEY_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "apiKeyType": "INFERENCE",
    "description": "backend prod",
    "expiresAt": "2026-12-31T23:59:59Z",
    "consumptionLimit": { "usd": 50, "diem": 10 }
  }
}
```

**Save it immediately** — Venice won't show the secret again. If you lose it, delete and re-create.

### Required

- `apiKeyType`
- `description`

### Optional

- `expiresAt` — empty string or ISO 8601 date/datetime. Omit for non-expiring.
- `consumptionLimit.usd` / `.diem` — per-epoch caps. Null means no cap on that currency.
- `consumptionLimit.vcu` — **deprecated** (legacy Diem). Use `diem` instead.

## `PATCH /api_keys` — update

```bash
curl -X PATCH https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "id": "uuid", "description": "renamed", "consumptionLimit": { "usd": 100 } }'
```

Only `description`, `expiresAt`, and `consumptionLimit` are mutable. Pass `"expiresAt": ""` or `null` to remove an expiration.

## `DELETE /api_keys?id=<uuid>` — revoke

```bash
curl -X DELETE "https://api.venice.ai/api/v1/api_keys?id=uuid" \
  -H "Authorization: Bearer $ADMIN_KEY"
```

Returns `{"success": true}`. Revocation is immediate.

## `GET /api_keys/{id}` — details

Returns one key's full metadata plus trailing-7-day usage. Useful for an admin dashboard row view.

## `GET /api_keys/rate_limits`

```bash
curl https://api.venice.ai/api/v1/api_keys/rate_limits \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Returns for the calling key:

```json
{
  "data": {
    "accessPermitted": true,
    "apiTier": { "id": "paid", "isCharged": true },
    "balances": { "USD": 50.23, "DIEM": 100.023, "BUNDLED_CREDITS": 25 },
    "keyExpiration": "2025-06-01T00:00:00Z",
    "nextEpochBegins": "2025-05-07T00:00:00.000Z",
    "rateLimits": [
      {
        "apiModelId": "zai-org-glm-5-1",
        "rateLimits": [
          { "type": "RPM", "amount": 100 },
          { "type": "TPM", "amount": 200000 },
          { "type": "RPD", "amount": 10000 }
        ]
      }
    ]
  }
}
```

`balances.BUNDLED_CREDITS` is remaining bundled credit **denominated in USD**. The spec says it returns `0` when the user's plan does not include bundled credits. It is **not** a `consumptionLimit` key — create/patch limits stay `usd` / `diem`. Debit order is documented in [`venice-billing`](../venice-billing/SKILL.md).

Use it to:

- Display current balances in-app (include `BUNDLED_CREDITS`; do not drop an unexpected key).
- Warm-gate calls when the relevant model's RPM cap is near.
- Know when the next epoch resets (DIEM, bundled credits).

## `GET /api_keys/rate_limits/log`

Returns the last 50 rate-limit breaches. Response is wrapped as `{ object: "list", data: [...] }`:

```json
{
  "object": "list",
  "data": [
    { "apiKeyId": "...", "modelId": "zai-org-glm-5-1", "rateLimitType": "RPM",
      "rateLimitTier": "paid", "timestamp": "2026-04-20T12:34:56Z" }
  ]
}
```

Feed these into your monitoring when tuning concurrency.

## Web3 API keys — two-step wallet flow

Lets a wallet that **holds sVVV** mint a classic Bearer API key. No Venice account required.

### 1. `GET /api_keys/generate_web3_key`

```bash
curl https://api.venice.ai/api/v1/api_keys/generate_web3_key
```

Returns `{ success: true, data: { token: "<jwt-ish token>" } }`.

### 2. Sign the token with your wallet, then `POST /api_keys/generate_web3_key`

```ts
import { Wallet } from 'ethers'

const { data: { token } } = await fetch(`${base}/api_keys/generate_web3_key`).then(r => r.json())
const wallet = new Wallet(process.env.WALLET_KEY!)
const signature = await wallet.signMessage(token)

const res = await fetch(`${base}/api_keys/generate_web3_key`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    apiKeyType: 'INFERENCE',
    description: 'Web3 API Key',
    address: wallet.address,
    signature,
    token,
    consumptionLimit: { usd: 50 },
  }),
})

const { data } = await res.json()
console.log(data.apiKey) // save this once
```

The returned `apiKey` behaves exactly like a normal Bearer key.

## Recipes

### Per-customer keys with $5 USD limit

```ts
await fetch(`${base}/api_keys`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${ADMIN_KEY}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    apiKeyType: 'INFERENCE',
    description: `cust:${customerId}`,
    consumptionLimit: { usd: 5 },
  }),
})
```

Rotate monthly; revoke on churn.

### Health-check for a key

```ts
const { data } = await fetch(`${base}/api_keys/rate_limits`, {
  headers: { Authorization: `Bearer ${key}` },
}).then(r => r.json())

if (!data.accessPermitted) alert('Key blocked — top up or change tier')
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad body (e.g. missing `apiKeyType`, malformed `expiresAt`), or attempting to create when you already have 500 active keys. |
| `401` | Missing / bad / non-admin key for admin-only routes. |
| `429` | Exceeded 20 creates/min. |
| `500` | Transient; retry. |

## Gotchas

- The secret is returned **exactly once**, in the `POST` response. Losing it = delete + recreate.
- `consumptionLimit` is per **epoch** (day / reset cycle), not per call.
- `INFERENCE` keys can't call admin-only routes (`POST/PATCH/DELETE /api_keys`, `GET /api_keys`, `GET /api_keys/{id}`, `GET /billing/balance`, `GET /billing/usage`). They **can** call `GET /api_keys/rate_limits` and `/api_keys/rate_limits/log` for themselves. Use a separate `ADMIN` key for management.
- `GET /api_keys/rate_limits` `balances` includes `BUNDLED_CREDITS` (USD-denominated; `0` if the plan has none). Do not treat it as a `consumptionLimit` field.
- `vcu` is legacy — use `diem`.
- `expiresAt` of empty string `""` means "no expiration" in CREATE; on UPDATE it **removes** an existing one.
- Rate-limit log is capped at 50 entries — pull it frequently if debugging bursts.
- The Web3 key flow requires wallet holdings of **sVVV**; otherwise the signing step is rejected.
