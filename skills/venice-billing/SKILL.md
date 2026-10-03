---
name: venice-billing
description: Venice billing and usage analytics - GET /billing/balance, GET /billing/usage-history (keyset-paginated per-request ledger, JSON or CSV), and GET /billing/usage-analytics (aggregated by date/model/key). All require an ADMIN key. GET /billing/usage was sunset on 2026-09-16 and now always returns 410. Covers the DIEM/EARNED_CREDITS/BUNDLED_CREDITS/USD consumption priority and building dashboards. (Beta)
---

# Venice Billing

Read-only endpoints for account-level billing and analytics. `usage-analytics` is tagged **Beta** in the spec — its schema/behavior may change.

| Endpoint | Purpose |
|---|---|
| `GET /billing/balance` | Current `canConsume` flag, remaining DIEM, earned credits, bundled credits and USD, epoch allocation. |
| `GET /billing/usage-history` | Per-request ledger with keyset (cursor) pagination. JSON or CSV. |
| `GET /billing/usage-analytics` | Aggregated breakdowns: by date, model, API key. |
| `GET /billing/usage` | **Retired.** Sunset 2026-09-16; every request returns `410`. |

All three live endpoints require Bearer auth with an **ADMIN** key — an `INFERENCE` key gets `401` (`"Admin API key required"`). They do not accept x402 wallet auth; for wallet balances use [`venice-x402`](../venice-x402/SKILL.md). A request with no `Authorization` header at all gets a `402` x402 discovery body rather than a `401` — ignore its payment options and send an ADMIN Bearer key; a bad key gets `401`.

> **`GET /billing/usage` is gone.** Since 2026-09-16 it returns `410 Gone` to every
> request, authenticated or not, with no usage data. The body's `error` string names
> the replacement and the parameter renames, and the response carries
> `Deprecation: @1783555200`, `Sunset: Wed, 16 Sep 2026 00:00:00 GMT`, and
> `Link: </api/v1/billing/usage-history>; rel="successor-version", <https://docs.venice.ai/api-reference/endpoint/billing/usage-history>; rel="deprecation"; type="text/html"`.
> The route is rate limited to 60 requests/minute per IP (then `429`, whose message
> repeats the migration pointer). Migrate to `GET /billing/usage-history`:
> `page` + `limit` → `pageSize` + `nextCursor`, `startDate` / `endDate` → `startTimestamp` / `endTimestamp`.

## Currency / priority

Each request is charged to a single currency, picked in this order:

1. **`DIEM`** — from staked DIEM; the allocation resets every epoch (UTC day).
2. **`EARNED_CREDITS`** — USD-denominated earned credits.
3. **`BUNDLED_CREDITS`** — USD-denominated credits included with paid Venice subscription plans.
4. **`USD`** — prepaid fiat balance.

Prepaid (quoted) charges such as queued jobs and images use the first currency that covers the whole cost. Token-priced requests are billed after they run, to the first currency with a positive balance, which can leave it slightly negative.

Legacy `VCU` (the old name for DIEM) is no longer a consumable currency; it is rejected by `/billing/usage-history`'s `currency` filter.

A per-key USD consumption limit covers `USD`, `BUNDLED_CREDITS` and `EARNED_CREDITS` together; a DIEM limit covers `DIEM` (see [`venice-api-keys`](../venice-api-keys/SKILL.md)).

## `GET /billing/balance`

```bash
curl https://api.venice.ai/api/v1/billing/balance \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

```json
{
  "canConsume": true,
  "consumptionCurrency": "DIEM",
  "balances": { "diem": 90.5, "usd": 25, "bundledCredits": 10, "earnedCredits": null },
  "diemEpochAllocation": 100
}
```

- `canConsume` is `true` when the account's spendable DIEM, earned credits, bundled credits and USD total at least $0.10. It does **not** account for per-key limits or the account's API tier — the real admission check runs on each inference request. Use `GET /api_keys/rate_limits` → `accessPermitted` for a check that includes those.
- `consumptionCurrency` is the first currency with a positive balance, in the order `DIEM`, `EARNED_CREDITS`, `BUNDLED_CREDITS`, `USD`, or `null`. The spec enum also lists `VCU`, but it is never returned.
- `balances.diem` is `null` when the account isn't staking DIEM; otherwise the remaining DIEM this epoch.
- `balances.usd`, `balances.bundledCredits` and `balances.earnedCredits` are `null` when not positive.
- `diemEpochAllocation` is the total DIEM for the current epoch — `balances.diem / diemEpochAllocation` = remaining fraction.

## `GET /billing/usage-history`

Per-request ledger with keyset (cursor) pagination, in **ascending** timestamp order.

```bash
curl "https://api.venice.ai/api/v1/billing/usage-history?startTimestamp=2026-06-01T00:00:00Z&endTimestamp=2026-07-01T00:00:00Z&pageSize=1000&currency=USD" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Accept: application/json"
```

### Query parameters

A request is **either** a filtered first page **or** a bare continuation. Sending
`cursor` alongside any filter is a `400`, and so is any unknown parameter — the
validator is strict.

| Param | Notes |
|---|---|
| `startTimestamp` | Optional. Inclusive lower bound, ISO 8601 UTC with a `Z` suffix (max 40 chars). First page only. |
| `endTimestamp` | Optional. Exclusive upper bound, same format. Must be later than `startTimestamp`. Consecutive windows that share a boundary walk the history with no gaps and no overlaps. |
| `currency` | Optional. `USD` / `DIEM` / `BUNDLED_CREDITS` / `EARNED_CREDITS`. |
| `pageSize` | Integer 10–1000. Default **1000**. |
| `cursor` | Opaque continuation token (`[A-Za-z0-9_-]`, ≤ 512 chars) from a previous `nextCursor`. Carries the filters and page size of the walk it continues, so send it **alone**. |

A cursor that is expired, tampered with, or was issued to another user returns
`400` (`"Invalid or expired cursor; restart from the first page"`). Page contents
stay stable while new usage is recorded; no result totals are reported.

### Response (JSON)

```json
{
  "data": [
    {
      "timestamp": "2026-06-15T19:05:10.504Z",
      "sku": "zai-org-glm-5-1-llm-output-mtoken",
      "units": 0.000227,
      "pricePerUnitUsd": 2.8,
      "amount": -0.06356,
      "currency": "DIEM",
      "notes": "API Inference",
      "inferenceDetails": {
        "requestId": "chatcmpl-4007fd29f42b7d3c4107f4345e8d174a",
        "promptTokens": 339,
        "completionTokens": 227,
        "inferenceExecutionTime": 2964
      }
    }
  ],
  "nextCursor": "AZq3fK9tXhIVDm2j4vN8cQwYt1sB6uEoLxRgPzKaJdHfM5nC7yW0K3w"
}
```

`nextCursor` is `null` on the last page.

### Fields

- `sku` — billing line item (model + unit type + format).
- `units` — for LLMs, millions of tokens (e.g. `0.000227` = 227 tokens).
- `pricePerUnitUsd` — rate per unit in USD.
- `amount` — negative for a debit.
- `currency` — `USD`, `DIEM`, `BUNDLED_CREDITS`, or `EARNED_CREDITS`.
- `inferenceDetails` — `null` for non-inference entries. When present, `requestId` is the `id` returned on the original response; `promptTokens`, `completionTokens`, and `inferenceExecutionTime` (ms) are each nullable when not recorded (tokens are `null` for non-LLM usage).

### CSV

Send `Accept: text/csv`. Columns: `timestamp, sku, pricePerUnitUsd, units, amount, currency, notes, inferenceDetails.requestId, inferenceDetails.inferenceExecutionTime, inferenceDetails.promptTokens, inferenceDetails.completionTokens`.
`Content-Disposition` is `attachment; filename=billing-usage-history-<UTC export stamp>.csv`, so each page of a walk downloads under a unique, sort-ordered name. Because CSV has no envelope, the continuation token moves to the **`x-next-cursor`** response header, which is absent on the last page.

### Walking the full history

```ts
let url = `${base}/billing/usage-history?startTimestamp=${start}&endTimestamp=${end}`
for (;;) {
  const page = await fetch(url, { headers }).then(r => r.json())
  handle(page.data)
  if (page.nextCursor === null) break
  url = `${base}/billing/usage-history?cursor=${encodeURIComponent(page.nextCursor)}`
}
```

## `GET /billing/usage-analytics`

Aggregated summary for dashboards. **Cached 10 minutes** per user + period.

```bash
curl "https://api.venice.ai/api/v1/billing/usage-analytics?lookback=7d" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY"
```

### Query parameters (choose one approach)

- `lookback=Nd` — must match `^[1-9]\d*d$`. Default `7d`. Values above `90d` are **clamped** to 90 days (the response `lookback` then reads `"90d"`).
- **OR** `startDate=YYYY-MM-DD` **and** `endDate=YYYY-MM-DD` (inclusive, UTC days). The range may span at most 90 days and `endDate` must not be before `startDate`. Send both: if only one is given it is ignored and `lookback` applies.

### Response (selected keys)

```json
{
  "lookback": "7d",
  "byDate": [{ "date": "2026-04-20", "USD": 0.5, "DIEM": 10.25 }],
  "byModel": [
    {
      "modelName": "GLM 5.1",
      "unitType": "tokens",
      "modelType": "LLM",
      "totalUsd": 0.4,
      "totalDiem": 12.5,
      "totalUnits": 50000,
      "breakdown": [
        { "type": "Output", "usd": 0.3, "diem": 10, "units": 35000 },
        { "type": "Input",  "usd": 0.1, "diem": 2.5, "units": 15000 }
      ]
    }
  ],
  "byModelDaily": [{ "date": 1705276800000, "GLM 5.1": 5.5, "Kimi K2.6": 3.2 }],
  "byModelDailyUsd": [{ "date": 1705276800000, "GLM 5.1": 0.4, "Kimi K2.6": 0 }],
  "topModels": ["GLM 5.1", "Kimi K2.6"],
  "byKey": [
    { "apiKeyId": "key_abc123", "description": "Production Key",
      "totalUsd": 0.8, "totalDiem": 15, "totalUnits": 75000 },
    { "apiKeyId": null, "description": "Web App",
      "totalUsd": 0, "totalDiem": 4, "totalUnits": 25000 }
  ],
  "byKeyDaily": [{ "date": 1705276800000, "Production Key": 8.5, "Web App": 2 }],
  "byKeyDailyUsd": [{ "date": 1705276800000, "Production Key": 0.8, "Web App": 0 }],
  "topKeyNames": ["Production Key", "Web App"]
}
```

- `byDate` has one entry per day in the window (ascending, zero-filled). `USD` totals include `BUNDLED_CREDITS` but not `EARNED_CREDITS`: spend paid from earned credits is left out of every analytics total.
- `byModel` / `byKey` list **every** model and key, sorted by total spend (USD + DIEM). `breakdown` (Input / Output / Cache Read / Cache Write …) is present only when a model has more than one token type.
- `byModelDaily` / `byKeyDaily` are chart rows: `date` (Unix ms) plus one field per series with USD + DIEM combined. `byModelDailyUsd` / `byKeyDailyUsd` are the same rows with only the USD (incl. bundled credits) portion. These two `*Usd` arrays are returned but not yet in the published schema.
- `topModels` / `topKeyNames` are the charted series: the top **50** by spend, plus a trailing `"Other"` series that sums everything past 50 (only when there are more than 50). The spec text still says "top 8"; the API returns 50.
- `apiKeyId: null` / `description: "Web App"` is usage from the Venice web app. Keys without a description show as `Key ...<last 6 of id>`; duplicate descriptions get a ` (...<last 6 of id>)` suffix so series don't collide.
- Credit purchases are excluded; only debits are aggregated.

## Recipes

### Abort before calling inference if the account is empty

`/billing/balance`'s `canConsume` ignores per-key limits and the account's API tier, so gate on `accessPermitted` from `GET /api_keys/rate_limits` instead (works with the key you are about to use, including `INFERENCE` keys):

```ts
const { data } = await fetch(`${base}/api_keys/rate_limits`, { headers }).then(r => r.json())
if (!data.accessPermitted) throw new Error('Venice balance exhausted — top up before continuing')
```

### Monthly CSV export

```bash
curl -D headers.txt "https://api.venice.ai/api/v1/billing/usage-history?startTimestamp=2026-04-01T00:00:00Z&endTimestamp=2026-05-01T00:00:00Z&pageSize=1000" \
  -H "Authorization: Bearer $VENICE_ADMIN_KEY" \
  -H "Accept: text/csv" \
  -o billing-april-001.csv
```

Read `x-next-cursor` from `headers.txt` and re-request with `?cursor=<token>` (and
no other parameters) until the header is absent.

### Top-models chart

```ts
const a = await fetch(`${base}/billing/usage-analytics?lookback=30d`, { headers }).then(r => r.json())
// chart(a.byModelDaily, { series: a.topModels, xField: 'date' })
```

## Errors

| Code | Meaning |
|---|---|
| `400` | `/billing/usage-history`: a `cursor` sent with any filter, an unknown parameter, a malformed timestamp, `pageSize` outside 10–1000, `endTimestamp` not later than `startTimestamp`, or an invalid/expired cursor. `/billing/usage-analytics`: malformed `lookback` / date, `endDate` before `startDate`, or a calendar range over 90 days (`lookback` over 90d is clamped, not rejected). |
| `401` | Invalid key, or a non-ADMIN key on any billing endpoint. |
| `402` | No `Authorization` header at all — the x402 auth challenge. |
| `410` | `/billing/usage` — always. Sunset 2026-09-16. |
| `429` | `/billing/usage` over 60 requests/min per IP; or the generic API error budget. |
| `500` | Internal error. |
| `504` | `/billing/usage-analytics` query timed out — shorten `lookback` or the date range. |

## Gotchas

- Every billing endpoint needs an **ADMIN** key, including `usage-analytics` (older docs said any key worked — that changed on 2026-07-21).
- Don't call `/billing/usage` at all. It returns no data; treat any `410` from it as "migrate now".
- `/billing/usage-history` takes `startTimestamp` / `endTimestamp` (full ISO datetimes with `Z`) and `pageSize`; `/billing/usage-analytics` takes `lookback` or `startDate` / `endDate` as plain `YYYY-MM-DD` dates. Don't mix the formats.
- `VCU` is not accepted by `/billing/usage-history`'s `currency` filter; use `DIEM`.
- `inferenceDetails` is `null` for non-inference entries (e.g. subscription charges).
- One inference request can appear as several ledger rows (e.g. separate input and output token SKUs) that repeat the same `inferenceDetails`. Sum `amount` across rows, but dedupe by `requestId` before summing token counts.
- The analytics endpoint is **cached 10 min** — sudden spikes lag in the dashboard by that window.
- `byModelDaily.date` is a **Unix milliseconds integer**; `byDate.date` is a **`YYYY-MM-DD` string**.
- Usage from the Venice web app has `apiKeyId: null` — don't drop it when reconciling.
- For x402 (wallet) balance, don't use these endpoints — use `GET /x402/balance/{walletAddress}`.
