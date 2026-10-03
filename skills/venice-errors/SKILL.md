---
name: venice-errors
description: Handle Venice API errors correctly. Covers the error body shapes (StandardError, DetailedError with validation details/issues, OpenAI-style context_length_exceeded, upstream provider rejections with request_id including TypeSafe/FastAPI validation errors, ContentViolationError, ProviderContentPolicyError, PayloadTooLargeError, the two x402 402 bodies), every meaningful status code (400-504, including 410 for retired endpoints), the three families of rate-limit headers, the per-key error budget (FAILED_REQUESTS / UNSUPPORTED_FEATURE_REQUESTS), Retry-After on overloaded models, SSE stream errors, and a backoff strategy that won't trip the error budget.
---

# Venice errors & retries

Most Venice errors are `{ "error": "<message>" }`, but several paths add structure. Knowing which shape you got tells you how to react.

## Error body shapes

### 1. `StandardError` - simple message

The default for 4xx/5xx.

```json
{ "error": "Authentication failed" }
```

### 2. `DetailedError` - schema validation failure (`400`)

When a request fails Venice's own schema, `details` is a nested tree (`_errors` recursively keyed by field) and `issues` is the flat issue list. Some image, video and upstream failures instead return `details` as a plain string, so check its type before walking it.

```json
{
  "error": "Invalid request parameters",
  "details": {
    "_errors": [],
    "type": { "_errors": ["Invalid enum value. Expected 'asr' | 'decision' | … , received 'bogus'", "Invalid enum value. Expected 'all' | 'code', received 'bogus'"] }
  },
  "issues": [
    { "code": "invalid_union", "unionErrors": [ … ], "path": ["type"], "message": "Invalid input" }
  ]
}
```

(That is the live response to `GET /models?type=bogus`.)

Many `400`s are plain `StandardError` - handle both. Render `details` / `issues`; don't retry.

### 3. OpenAI-style context overflow (`400`, chat)

```json
{
  "error": {
    "message": "Your request exceeds the model's maximum context. Please reduce your prompt or completion length.",
    "type": "invalid_request_error",
    "param": "messages",
    "code": "context_length_exceeded"
  }
}
```

Note `error` is an **object** here, so OpenAI SDKs can detect it. `message` is the provider's wording when Venice can extract it, otherwise the text above - match on `code`, not `message`. Trim the prompt or lower `max_completion_tokens`.

### 4. Upstream provider rejection (`400`)

When the request passed Venice's schema but the model provider rejected it, Venice returns the provider's message, plus a `request_id` on routes that track one (chat, for example; `/decisions` omits it):

```json
{ "error": "<provider's validation message>", "request_id": "…" }
```

FastAPI-style validation errors (e.g. from the TypeSafe provider behind `POST /decisions`, which answers `422`) are surfaced as `400` with up to five `field.path: message` items joined by `; `. If Venice can't extract a message you get `"Invalid request parameters. For assistance, please reach out to support@venice.ai"`, followed by `" and reference request ID: <id>"` when there is one. These count against the lenient unsupported-feature budget on chat / responses (see [Error budget](#error-budget)). Fix the input; quote `request_id` to support.

### 5. `ContentViolationError` - `422` content policy

```json
{
  "error": "Your prompt violates the content policy of Venice.ai or the model provider",
  "suggested_prompt": "A cinematic instrumental track inspired by stormy weather and dramatic tension."
}
```

Returned by chat, responses, image edit and multi-edit, and audio generation. `/image/generate` does not use it (a blocked image comes back as a `200` with `x-venice-is-content-violation: true`), and video content-policy rejections arrive on `/video/retrieve` rather than on queue. `suggested_prompt` is only emitted by `/audio/queue` and `/audio/retrieve`; when present, retry once with it if the user consents. Other `422`s include `"Your input was blocked by content moderation."` and media-validation failures (image too large, bad aspect ratio, audio/video duration out of range, ASR unable to process the audio).

### 6. `ProviderContentPolicyError` - `422` on `/video/retrieve`

```json
{
  "error": {
    "message": "The selected model provider rejected this request due to its content policies. Credits have been refunded. Try using <model> instead.",
    "type": "provider_content_policy",
    "credits_refunded": true,
    "recommended_model": "<model id>"
  }
}
```

Check `credits_refunded`; optionally re-queue on `recommended_model`.

### 7. `PayloadTooLargeError` - `413`

```json
{ "code": "PAYLOAD_TOO_LARGE", "error": "File exceeds the maximum allowed size of 25 MB." }
```

### 8. x402 `402` bodies

A `402` comes in two forms. Both also set the `PAYMENT-REQUIRED` header. The no-credentials form is returned on every route that needs credentials, including Bearer-only routes (`/api_keys*`, `/billing/*`, `/characters*`), where its payment options don't apply.

**No credentials at all** - x402 v2 discovery (not `401`):

```json
{
  "x402Version": 2,
  "error": "Authentication required",
  "resource": { "url": "https://api.venice.ai/api/v1/chat/completions", "description": "Venice API", "mimeType": "application/json" },
  "accepts": [ { "scheme": "exact", "network": "eip155:8453", "…": "…" }, { "scheme": "exact", "network": "solana", "…": "…" } ],
  "extensions": { "sign-in-with-x": { "info": { "domain": "api.venice.ai", "statement": "Sign in to Venice AI", "…": "…" }, "supportedChains": [ … ] } },
  "authOptions": {
    "apiKey": { "header": "Authorization: Bearer YOUR_API_KEY", "getKey": "https://venice.ai/settings/api", "docs": "…" },
    "x402Wallet": { "header": "SIGN-IN-WITH-X", "legacyHeader": "X-Sign-In-With-X", "topUp": "POST /api/v1/x402/top-up", "docs": "…" }
  }
}
```

**Signed-in wallet below the $0.10 minimum balance** - discriminate on `code: "PAYMENT_REQUIRED"`:

```json
{
  "error": "Payment required",
  "code": "PAYMENT_REQUIRED",
  "reason": "insufficient_balance",
  "currentBalanceUsd": 0.01,
  "minimumBalanceUsd": 0.1,
  "description": "Venice API",
  "suggestedTopUpUsd": 10,
  "minimumTopUpUsd": 5,
  "supportedTokens": ["USDC"],
  "supportedChains": ["base", "solana"],
  "topUpInstructions": {
    "step1": "POST /api/v1/x402/top-up with no payment header to get payment requirements",
    "step2": "Choose a payment option from accepts and sign a USDC transfer authorization using the x402 SDK (createPaymentHeader)",
    "step3": "POST /api/v1/x402/top-up with the signed X-402-Payment header",
    "receiverWallet": "0x…",
    "tokenAddress": "0x…",
    "tokenDecimals": 6,
    "network": "eip155:8453",
    "minimumAmountUsd": 5
  },
  "siwxChallenge": { "info": { … }, "supportedChains": [ … ] }
}
```

`topUpInstructions` describes the Base rail only; read `accepts[]` from `POST /x402/top-up` to pay on Solana (and send `PAYMENT-SIGNATURE`, the canonical header - `X-402-Payment` / `X-PAYMENT` still work). The `PAYMENT-REQUIRED` header is the base64 x402 `paymentRequired` object (`x402Version`, `error`, `resource`, `accepts[]`, `extensions`), not the body. See [`venice-x402`](../venice-x402/SKILL.md).

API-key `402`s are plain: `{ "error": "Insufficient USD or Diem balance to complete request. Visit https://venice.ai/settings/api to add credits." }`, or the per-key spend-limit variants ("API key DIEM spend limit exceeded…" / "API key USD spend limit exceeded…"). A wallet can get the same plain "Insufficient USD or Diem balance…" body when its credit clears the $0.10 floor but not the quoted price of this request (e.g. `/video/queue`, `/audio/queue`) - top up and retry.

### 9. x402 sign-in failures (`401`)

On inference routes a bad `SIGN-IN-WITH-X` returns `{ "error": "<message>", "code": "X402_SIGN_IN_…" }` (e.g. `X402_SIGN_IN_EXPIRED`, `X402_SIGN_IN_NONCE_REUSED`). `/x402/balance` and `/x402/transactions` return a generic `{ "error": "Invalid Sign-in-with-x signature" }`. See [`venice-auth`](../venice-auth/SKILL.md) for every code.

## Status code map

| Status | Typical body | Meaning | What to do |
|---|---|---|---|
| `400` | `DetailedError`, `StandardError`, context-overflow object, or upstream `{ error, request_id }` | Malformed input, missing or non-string `model` (plain `"model is required"` / `"model must be a string"`), unsupported option for this model, provider rejection, invalid JSON (`"Invalid JSON request"`), or a `POST` whose `Content-Type` is neither JSON nor multipart (`"'Content-Type' must be 'application/json'"`). Also `PAYMENT_HEADER_NOT_ACCEPTED` if you send an x402 payment header to an inference route instead of `/x402/top-up`. | Fix and re-send. **Don't retry.** |
| `401` | `StandardError` or `{ error, code }` | Unknown, expired or revoked API key ("Authentication failed"), a non-ADMIN key on an admin-only route ("Admin API key required"), bad SIWX, or "This model is only available to Pro users" (API-key accounts without a paid plan on a Pro-only model). | Fix credentials / plan. **Don't retry.** |
| `402` | See shape 8 | No credentials (discovery), wallet balance too low, or API-key account / key spend limit exhausted. | x402: top up then retry. API key: add credits or raise the key's limit. |
| `403` | `StandardError` | Entitled-but-blocked: model blocked in your country (`regionRestrictions`), key's `modelPrivacy` forbids the model, API access disabled, SIWX wallet ≠ path wallet. | **Don't retry.** |
| `404` | `StandardError` | Unknown model ("Specified model not found: …", sometimes with a suggestion or a "has been deprecated. Please use …" hint), unknown character, expired media. | Fix the ID. |
| `409` | `{ error: { code: "needs_consent", message }, consent_flow, face_media_roles, consent, docs_url }` (video) or `{ error, message, details }` (x402) | `/video/queue` needs consent (only on unlisted model ids; listed models never ask), or an x402 top-up that is already processed or still settling (`error` holds the code, e.g. `"PAYMENT_IN_PROGRESS"` — retry shortly). | See [`venice-video`](../venice-video/SKILL.md) / [`venice-x402`](../venice-x402/SKILL.md). |
| `410` | `StandardError` | Retired endpoint (`GET /billing/usage`, `POST /video/transcriptions`). Message names the replacement. | Migrate. **Never retry.** |
| `413` | `PayloadTooLargeError` | JSON body over 35 MB (`"Request body exceeds the maximum allowed size."`) or a multipart file over 25 MB. | Shrink the upload. |
| `415` | `StandardError` | Rare: `/image/multi-edit` with an empty body, or a body sent with a `Content-Encoding` / charset the server can't decode (`"Request encoding is not supported"`). A wrong `Content-Type` on any route is answered with `400`. | Fix headers. |
| `422` | `ContentViolationError`, `ProviderContentPolicyError`, or `StandardError` | Content policy, or media that can't be processed (dimensions, duration, unreadable audio). | Change the prompt / media. One retry with `suggested_prompt` if offered. |
| `429` | `StandardError` or `{ error, code }` | Request/token rate limit, error budget exhausted, model overloaded, x402 concurrency (`X402_CONCURRENCY_LIMIT`, 5 in-flight per wallet), or a per-route limiter (crypto RPC, `/x402/*`, `/tee/*`, retired endpoints). | See rate limits below. |
| `500` | `StandardError` | Unexpected failure. | Backoff and retry. |
| `502` | `StandardError` | Upstream failure (TTS, ASR, TEE, video fetch). | Backoff and retry. |
| `503` | `StandardError` | Model offline or at capacity. | Backoff; consider a fallback model. |
| `504` | `StandardError` | Request took too long. Mostly non-streaming chat. | Use `stream: true` or a smaller request. |

## Rate limits and their headers

Three independent header families - they share a prefix but not units, so read them by exact name:

| Headers | Emitted by | Reset unit |
|---|---|---|
| `x-ratelimit-limit-requests`, `x-ratelimit-remaining-requests`, `x-ratelimit-reset-requests` (+ `-tokens` variants) | Model rate limits on inference routes (per account, per model, requests per minute/day and tokens per minute) | Unix **milliseconds** |
| `x-ratelimit-remaining`, `x-ratelimit-resets` | The error budget, on most responses from routes that need credentials (not on the no-credentials `402`) | Unix **milliseconds** |
| `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` | `/crypto/rpc/{network}`, only on the `429` from its per-minute cap | Unix **seconds** |

Model-limit `429`s say `"Rate limit exceeded"`. Pre-fetch your caps with `GET /api_keys/rate_limits` (Bearer keys only). Past hits are in `GET /api_keys/rate_limits/log`, which needs an **ADMIN** key — an INFERENCE key gets `401 "Admin API key required"` ([`venice-api-keys`](../venice-api-keys/SKILL.md)).

Per-route limiters return `429` without these headers: `/x402/top-up` (10/min per IP), `/x402/balance` (30/min per wallet) and `/x402/transactions` (20/min per wallet) say `"Rate limit exceeded. Please try again later."`; `/tee/*` (10/min per IP) says `"Rate limit exceeded."`; the retired endpoints allow 60/min per IP.

**Overloaded upstream**: `429` with `Retry-After` (seconds, default 30) and a message like "The model is currently overloaded. Please try again later." Honor `Retry-After`.

### Error budget

Failed requests are rate-limited harder than successful ones:

| Budget | Threshold | Counts | Logged as |
|---|---|---|---|
| Failed requests | 50 per 30 s | Any `4xx` except `429` (5xx never count) | `FAILED_REQUESTS` |
| Unsupported feature requests | 200 per 30 s, `/chat/completions` and `/responses` only | Requests asking a model for a capability it lacks, or provider-side rejections of otherwise valid requests | `UNSUPPORTED_FEATURE_REQUESTS` |

Buckets are per API key (or per IP for x402), per `model`, per OpenAI `user` string; multipart uploads don't expose `model` / `user` in time, so they share the key's (or IP's) bucket. Once a bucket is exhausted **every** request in it gets `429` until reset, with:

```
Too many failed attempts (> 50) resulting in a non-success status code. Please wait 30 seconds and try again. See https://docs.venice.ai/api-reference/rate-limiting for more information.
```

The unsupported-feature bucket uses the same wording with `> 200`. So a client that blindly retries `400`/`401`/`402` locks itself out. Stop on non-retryable errors. (The no-credentials `402`, the `Content-Type` and invalid-JSON `400`s, and the 35 MB JSON-body `413` are rejected before the budget is checked and don't count.)

## Retry strategy

### Never retry

`400`, `401`, `403`, `404`, `410`, `413`, `415` - fix the request, credentials, or endpoint.

### Retry with modification

- `402` with `code: "PAYMENT_REQUIRED"` - top up via `/x402/top-up` within the user's spend cap (see [`venice-x402`](../venice-x402/SKILL.md)), then retry.
- `402` with `x402Version` (no credentials) - add `Authorization: Bearer …`, or `SIGN-IN-WITH-X` on routes that accept wallets. Bearer-only routes (`/api_keys*`, `/billing/*`, `/characters*`) reject SIWX with `401`; send a Bearer key there.
- Any retry with wallet auth needs a **newly signed** `SIGN-IN-WITH-X` header - each nonce is accepted once, so re-sending the original header fails with `X402_SIGN_IN_NONCE_REUSED`.
- `402` on an API key - surface to the user.
- `422` with `suggested_prompt` - one retry with the safer prompt.

### Retry with backoff

- `429` - wait `Retry-After` if present, otherwise until the relevant reset header; add jitter.
- `500` / `502` / `503` / `504` - exponential backoff (0.5 s, 1 s, 2 s, 4 s, 8 s), capped at ~30 s, **3-5 retries max**.
- Async queues (`/video/queue`, `/audio/queue`, `/audio/voice-changer/queue`) can bill before the job finishes (API-key calls are pre-charged at queue time). If a queue response is lost, poll `retrieve` instead of re-queueing. `Idempotency-Key` is supported only on `/crypto/rpc/{network}`.

### Reference retry loop

```ts
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

function waitMs(res: Response, fallback: number): number {
  const retryAfter = Number(res.headers.get('retry-after'))
  if (retryAfter > 0) return retryAfter * 1000
  const msReset = Number(res.headers.get('x-ratelimit-reset-requests') ?? res.headers.get('x-ratelimit-resets'))
  if (msReset > 0) return Math.max(msReset - Date.now(), fallback)
  const secReset = Number(res.headers.get('x-ratelimit-reset')) // crypto RPC
  if (secReset > 0) return Math.max(secReset * 1000 - Date.now(), fallback)
  return fallback
}

// fn must build a fresh SIGN-IN-WITH-X header on every call; nonces are single-use.
async function callVenice<T>(fn: () => Promise<Response>): Promise<T> {
  const maxRetries = 5
  let delay = 500
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const res = await fn()
    if (res.ok) return res.json() as Promise<T>

    const body = await res.clone().json().catch(() => ({}))
    const message = typeof body.error === 'string' ? body.error : body.error?.message ?? 'Venice error'
    const fail = () => Object.assign(new Error(message), { status: res.status, body })

    if ([400, 401, 403, 404, 410, 413, 415, 422].includes(res.status)) throw fail()

    if (res.status === 402) {
      // topUpAllowed must enforce the user's cap and check GET /x402/balance first.
      if (body.code === 'PAYMENT_REQUIRED' && attempt === 0 && (await topUpAllowed())) {
        await topUpX402(Math.min(body.suggestedTopUpUsd, USER_TOP_UP_CAP_USD))
        continue
      }
      throw fail()
    }

    if ((res.status === 429 || res.status >= 500) && attempt < maxRetries) {
      await sleep((res.status === 429 ? waitMs(res, delay) : delay) + Math.random() * 250)
      delay = Math.min(delay * 2, 30_000)
      continue
    }

    throw fail()
  }
  throw new Error('Exceeded max retries')
}
```

## Streaming errors

If a `/chat/completions` stream fails after headers are sent, the HTTP status stays `200` and the error arrives in-band, followed by the terminator:

```
data: {"error":{"message":"…","type":"server_error","code":"model_overloaded","param":null,"retry_after":30}}
data: [DONE]
```

Overload errors use `type: "server_error"`, `code: "model_overloaded"` and may carry `retry_after` (seconds); other upstream failures use `type: "api_error"` with `code: "upstream_error"` or a specific code (e.g. `e2ee_attestation_stale`). Treat the event as terminal.

## Request-ID correlation

Upstream-rejection bodies on chat carry `request_id`, and `/crypto/rpc/{network}` sets an `X-Request-ID` header on proxied responses. Include either (plus `x-venice-version` from the response headers) in support tickets. Other routes don't guarantee a request ID, so keep your own client-side correlation ID too.

## Common gotchas

- A `402` from `/x402/top-up` with no payment header is the **expected discovery** response.
- A `402` (not `401`) on an inference route usually means you sent no auth header at all.
- `x-ratelimit-remaining` without a suffix is the error budget, not your request quota.
- A `429` can come from several different limiters (model limits, error budget, overload, x402 concurrency, per-route caps) - read the message and headers before deciding how long to wait.
- `DetailedError.details` is a nested `_errors` tree, not a flat map, on schema-validation `400`s; some image / video / upstream failures send it as a plain string. Check its type before walking it.
- In SSE streams, `data: [DONE]` is the end of the stream (also after an error chunk), not a keepalive.
