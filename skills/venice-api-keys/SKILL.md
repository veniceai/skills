---
name: venice-api-keys
description: Manage Venice API keys. Covers GET/POST/PATCH/DELETE /api_keys, GET /api_keys/{id}, GET /api_keys/rate_limits, GET /api_keys/rate_limits/log, the two-step /api_keys/generate_web3_key wallet flow, INFERENCE vs ADMIN key types, per-key consumption limits (USD / DIEM) with EPOCH / MONTH / LIFETIME reset windows, and per-key modelPrivacy (ALL / PRIVATE_TEXT / PRIVATE_ONLY).
---

# Venice API Keys

Admin endpoints for managing Bearer API keys. Management routes need an **ADMIN** key. For wallet-only auth, use [`venice-auth`](../venice-auth/SKILL.md) / [`venice-x402`](../venice-x402/SKILL.md) instead.

| Endpoint | Key type | Purpose |
|---|---|---|
| `GET /api_keys` | ADMIN | List your active keys (masked). |
| `POST /api_keys` | ADMIN | Create a key. Response contains the **only copy of the secret**. |
| `PATCH /api_keys` | ADMIN | Update `description`, `expiresAt`, `consumptionLimit`, `limitPeriod`, `modelPrivacy`. |
| `DELETE /api_keys?id=...` | ADMIN | Revoke a key. |
| `GET /api_keys/{id}` | ADMIN | Full details for one key (usage, limits, expiration). |
| `GET /api_keys/rate_limits` | any | Balances + per-model rate limits for the calling key. |
| `GET /api_keys/rate_limits/log` | ADMIN | Last 50 rate-limit breaches on the account. |
| `GET /api_keys/generate_web3_key` | none | Get a short-lived token to sign with a wallet. |
| `POST /api_keys/generate_web3_key` | none | Prove a wallet holds staked VVV and mint an API key. |

Limits: key creation (`POST /api_keys`) is capped at **20 requests/minute per user** and **500 active keys per user** (expired keys don't count).

A request with no `Authorization` header gets a `402` x402 auth challenge rather than `401`; a bad key gets `401`.

## Key types

| Type | Can call |
|---|---|
| `INFERENCE` | Inference and utility routes — `/chat/completions`, `/responses`, `/decisions`, `/systemone`, `/image/*`, `/images/generations`, `/audio/*`, `/video/*`, `/embeddings`, `/augment/*`, `/crypto/rpc/*`, `/characters*`, `/models*` — plus `GET /api_keys/rate_limits`. Admin-only routes return `401` `"Admin API key required"`. |
| `ADMIN` | Everything above, plus `GET/POST/PATCH/DELETE /api_keys`, `GET /api_keys/{id}`, `GET /api_keys/rate_limits/log`, and all billing routes (`/billing/balance`, `/billing/usage-history`, `/billing/usage-analytics`). |

Secrets are prefixed `VENICE_INFERENCE_KEY_` or `VENICE_ADMIN_KEY_`. A leaf app should almost always use **`INFERENCE`** keys — per-app, per-user, with consumption caps.

## `GET /api_keys`

```bash
curl https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

```json
{
  "object": "list",
  "data": [
    {
      "id": "e28e82dc-9df2-4b47-b726-d0a222ef2ab5",
      "apiKeyType": "INFERENCE",
      "description": "backend prod",
      "createdAt": "2025-10-01T12:00:00.000Z",
      "expiresAt": null,
      "lastUsedAt": "2026-04-20T10:05:00.000Z",
      "last6Chars": "2V2jNW",
      "consumptionLimits": { "usd": 50, "diem": 10, "vcu": null },
      "limitPeriod": "MONTH",
      "modelPrivacy": "ALL",
      "usage": { "trailingSevenDays": { "usd": "4.2000", "vcu": "0.0000", "diem": "0.0000" } },
      "currentPeriodUsage": { "usd": "12.5000", "diem": "0.0000" }
    }
  ]
}
```

- Only non-expired keys are listed, newest first. The full secret is **never** returned — only `last6Chars`.
- `usage.trailingSevenDays` and `currentPeriodUsage` values are **strings** with 4 decimals. The `usd` figures include bundled-credit spend but not earned-credit spend, even though the USD limit counts both.
- `currentPeriodUsage` is spend inside the current `limitPeriod` window and is present **only** when the key has a USD or DIEM limit set.
- `consumptionLimits.vcu` is deprecated and always shown; ignore it.

## `POST /api_keys` — create

```bash
curl https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "apiKeyType": "INFERENCE",
    "description": "backend prod",
    "expiresAt": "2026-12-31T23:59:59Z",
    "consumptionLimit": { "usd": 50, "diem": 10 },
    "limitPeriod": "MONTH",
    "modelPrivacy": "PRIVATE_ONLY"
  }'
```

```json
{
  "success": true,
  "data": {
    "id": "e28e82dc-9df2-4b47-b726-d0a222ef2ab5",
    "apiKey": "VENICE_INFERENCE_KEY_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "apiKeyType": "INFERENCE",
    "description": "backend prod",
    "expiresAt": "2026-12-31T23:59:59.000Z",
    "consumptionLimit": { "usd": 50, "diem": 10, "vcu": null },
    "limitPeriod": "MONTH",
    "modelPrivacy": "PRIVATE_ONLY"
  }
}
```

**Save `apiKey` immediately** — Venice won't show the secret again. If you lose it, delete and re-create. The body is strict: unknown fields are a `400`.

### Required

- `apiKeyType` — `INFERENCE` or `ADMIN`.
- `description` — string, max **64** characters.

### Optional

- `expiresAt` — `""`, a date `YYYY-MM-DD`, or a UTC datetime `YYYY-MM-DDTHH:mm:ss[.sss]Z`. Omit (or `""`) for non-expiring.
- `consumptionLimit.usd` / `.diem` — number `0`–`9999999999`, or `null` for no cap. The **USD** limit caps `USD`, `BUNDLED_CREDITS` and `EARNED_CREDITS` spend combined; the **DIEM** limit caps DIEM spend.
- `consumptionLimit.vcu` — **deprecated** (legacy DIEM). Use `diem`.
- `limitPeriod` — window the limits are measured over. Default `EPOCH`.
- `modelPrivacy` — which models the key may call. Default `ALL`.

### `limitPeriod`

| Value | Window |
|---|---|
| `EPOCH` | Resets every UTC day (default, legacy behaviour). |
| `MONTH` | Resets at 00:00 UTC on the 1st of each calendar month. |
| `LIFETIME` | Never resets — a permanent cap on the key. |

When a key hits its limit while the account still has funds, inference returns `402` with only an `error` string: `"API key USD spend limit exceeded. Your account may still have USD balance, but this API key has reached its configured USD spending limit."` (or the same with DIEM). There is no `code` field.

### `modelPrivacy`

Enforced on every inference route. A disallowed model returns **`403`** (`"This API key is set to '…', but `<model>` is an Anonymous model. Choose a Private, TEE, or E2EE model, or change the model privacy setting of this API key."`). `GET /models`, `/models/traits`, and `/models/compatibility_mapping` called with the key are filtered to models it may use.

| Value | Effect |
|---|---|
| `ALL` | Any model (default). |
| `PRIVATE_TEXT` | Text, embedding, and decision models must be Private, TEE, or E2EE. Image / audio / video models may be Anonymous. |
| `PRIVATE_ONLY` | Every model must be Private, TEE, or E2EE. Anonymous models are rejected. |

With a restricted key, `GET /models` returns only the models that key may call — the simplest way to pick an allowed model (see [`venice-models`](../venice-models/SKILL.md)).

## `PATCH /api_keys` — update

```bash
curl -X PATCH https://api.venice.ai/api/v1/api_keys \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "id": "e28e82dc-9df2-4b47-b726-d0a222ef2ab5", "description": "renamed", "consumptionLimit": { "usd": 100 }, "limitPeriod": "LIFETIME" }'
```

- `id` is required; everything else is optional and only the fields you send change. `apiKeyType` cannot be changed.
- Mutable: `description` (≤ 64 chars), `expiresAt`, `consumptionLimit` (`usd` / `diem` / `vcu`, each may be `null` to remove that cap), `limitPeriod`, `modelPrivacy`.
- Pass `"expiresAt": ""` or `null` to remove an expiration.
- Returns `{ success: true, data: { id, apiKeyType, description, createdAt, expiresAt, lastUsedAt, last6Chars, consumptionLimits, limitPeriod, modelPrivacy } }`.
- An unknown or already-expired `id` → `400` `"API key not found or expired"`.

## `DELETE /api_keys?id=<uuid>` — revoke

```bash
curl -X DELETE "https://api.venice.ai/api/v1/api_keys?id=e28e82dc-9df2-4b47-b726-d0a222ef2ab5" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

The id may also be sent as a JSON body `{ "id": "..." }`. Returns `{"success": true}`. An unknown key → `400` `"API key could not be found"`. Revocation is immediate.

## `GET /api_keys/{id}` — details

Returns `{ data: <key> }` with the same fields as a list entry (`usage.trailingSevenDays`, `currentPeriodUsage` when limited, `limitPeriod`, `modelPrivacy`, …). Unknown or expired id → `400` `"API key not found"`.

## `GET /api_keys/rate_limits`

Callable with any key type; reports on the **calling** key.

```bash
curl https://api.venice.ai/api/v1/api_keys/rate_limits \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

```json
{
  "data": {
    "accessPermitted": true,
    "apiTier": { "id": "paid", "isCharged": true },
    "balances": { "USD": 50.23, "DIEM": 100.023, "BUNDLED_CREDITS": 25 },
    "keyExpiration": null,
    "nextEpochBegins": "2026-04-21T00:00:00.000Z",
    "rateLimits": [
      {
        "apiModelId": "zai-org-glm-5-1",
        "rateLimits": [
          { "type": "RPM", "amount": 100 },
          { "type": "TPM", "amount": 2000000 }
        ]
      }
    ]
  }
}
```

- `accessPermitted` is the real admission check (balance, per-key limits, account status) — prefer it over `/billing/balance`'s `canConsume`.
- `balances` are what **this key** can spend right now: each account balance clamped to the key's remaining limit. `BUNDLED_CREDITS` is USD-denominated and `0` when the plan has none. Earned credits are not listed. Any of the three may be omitted when unknown.
- `apiTier.id` is the account's API tier (e.g. `paid`); `isCharged` is always `true`.
- `rateLimits[].rateLimits[].type` is `RPM` (requests/min), `RPD` (requests/day), or `TPM` (tokens/min); the amounts shown above are illustrative — read them from the response. Video and music models return an empty array (they are not throughput-limited).
- `nextEpochBegins` is when DIEM allocations and `EPOCH`-period key limits reset.

## `GET /api_keys/rate_limits/log`

Requires an **ADMIN** key. Returns the account's last 50 rate-limit breaches, newest first:

```json
{
  "object": "list",
  "data": [
    { "apiKeyId": "e28e82dc-...", "modelId": "zai-org-glm-5-1", "rateLimitType": "RPM",
      "rateLimitTier": "paid", "timestamp": "2026-04-20T12:34:56.000Z" }
  ]
}
```

`rateLimitType` is one of:

| Value | Meaning |
|---|---|
| `RPM` / `TPM` / `RPD` | Per-model throughput caps. |
| `FAILED_REQUESTS` | The generic error budget: more than 50 client-error responses (4xx other than `429`) within 30 seconds. |
| `UNSUPPORTED_FEATURE_REQUESTS` | More than 200 "model doesn't support this feature" rejections within 30 seconds on `/chat/completions` or `/responses`. |

`modelId` is usually a model id, but endpoint-level limits log `endpoint:api/v1/...` (e.g. `endpoint:api/v1/crypto/rpc`) and unresolvable model names log `model:unknown`.

## Web3 API keys — two-step wallet flow

Lets a wallet with **staked VVV on Base** mint a Bearer API key. No Venice account required; one is created and linked to the wallet on first use.

### 1. `GET /api_keys/generate_web3_key`

```bash
curl https://api.venice.ai/api/v1/api_keys/generate_web3_key
```

Returns `{ "success": true, "data": { "token": "<JWT>" } }`. The token is valid for **15 minutes**.

### 2. Sign the token, then `POST /api_keys/generate_web3_key`

```ts
import { Wallet } from 'ethers'

const { data: { token } } = await fetch(`${base}/api_keys/generate_web3_key`).then(r => r.json())
const wallet = new Wallet(process.env.WALLET_KEY!)
const signature = await wallet.signMessage(token) // EIP-191 personal_sign of the exact JWT string

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

- Body: `address`, `signature`, `token`, and `apiKeyType` are required; `description` defaults to `"Web3 API Key"`; `expiresAt`, `consumptionLimit`, `limitPeriod`, `modelPrivacy` work as in `POST /api_keys`.
- The signature is verified on Base (chain 8453). Verification failures are `400` with a specific message: bad address, expired/modified token, signature mismatch, or `"Wallet … has no staked VVV on Base"`.
- The response has the same shape as `POST /api_keys`. The returned `apiKey` behaves exactly like a normal Bearer key. Staked VVV only gates minting: the key still spends DIEM, earned credits, bundled credits, or USD from the linked account.

## Recipes

### Per-customer keys with a $5 monthly USD cap, private models only

```ts
await fetch(`${base}/api_keys`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${ADMIN_KEY}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    apiKeyType: 'INFERENCE',
    description: `cust:${customerId}`,
    consumptionLimit: { usd: 5 },
    limitPeriod: 'MONTH',
    modelPrivacy: 'PRIVATE_ONLY',
  }),
})
```

Revoke on churn.

### Health-check for a key

```ts
const { data } = await fetch(`${base}/api_keys/rate_limits`, {
  headers: { Authorization: `Bearer ${key}` },
}).then(r => r.json())

if (!data.accessPermitted) alert('Key blocked — top up or raise its limit')
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad body (missing `apiKeyType`, `description` > 64 chars, malformed `expiresAt`, unknown field), 500 active keys reached, unknown/expired key id, or any Web3 verification failure. |
| `401` | Invalid key, or a non-ADMIN key on an admin-only route (`"Admin API key required"`). |
| `402` | No `Authorization` header (x402 auth challenge). On inference, `"API key USD spend limit exceeded…"` / `"API key DIEM spend limit exceeded…"` when the key's limit is used up. |
| `403` | On inference: the model is not permitted by the key's `modelPrivacy`. |
| `429` | Exceeded 20 key creations/min, or the generic API error budget. |
| `500` | Transient; retry. |

## Gotchas

- The secret is returned **exactly once**, in the create response. Losing it = delete + recreate.
- `consumptionLimit` is measured over `limitPeriod` — `EPOCH` (UTC day) unless you choose `MONTH` or `LIFETIME`. It is not per call.
- The USD limit covers USD, bundled credits and earned credits together.
- `GET /api_keys/rate_limits` works with an `INFERENCE` key; `GET /api_keys/rate_limits/log` does **not** (ADMIN only).
- `modelPrivacy` is enforced: a `PRIVATE_ONLY` key gets `403` for Anonymous models, and `/models` hides them from that key.
- `vcu` is legacy — use `diem`.
- `expiresAt: ""` means "no expiration" on create; on update `""` or `null` **removes** an existing one.
- Rate-limit log is capped at 50 entries — pull it frequently if debugging bursts.
- The Web3 flow's token expires after 15 minutes, and the wallet must hold **staked** VVV on Base. On that path, read limits back with `GET /api_keys/{id}` rather than trusting the create response's `consumptionLimit` echo — its `diem` is derived from `vcu` (so it reads `null` if you only sent `diem`) and a `usd` of `0` echoes as `null`. The stored limits are correct.
