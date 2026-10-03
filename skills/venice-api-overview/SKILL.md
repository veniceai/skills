---
name: venice-api-overview
description: High-level map of the Venice.ai API - base URL, which auth mode each endpoint accepts (API key, x402 wallet, or none), endpoint categories (including decisions, voice changer, and retired routes), response headers (rate limit, balance, deprecation, x402), pricing model, error shape, and versioning. Load this first when starting any Venice integration.
---

# Venice API Overview

Venice.ai is an OpenAI-compatible inference platform for text, image, audio, video, embeddings, and typed decisions. One API - two ways to pay: a traditional **API key** (Venice account), or a **wallet** (x402, USDC on Base or Solana, no account required).

## Use when

- You're writing code against `api.venice.ai` for the first time.
- You need to decide between API-key and x402/wallet authentication.
- You want a quick map of which endpoint to call for which task.
- You need to understand the common response headers (`x-ratelimit-*`, `PAYMENT-REQUIRED`, deprecation headers, etc.).

## Base URL

All endpoints live under:

```
https://api.venice.ai/api/v1
```

The OpenAPI spec is served at `https://api.venice.ai/api/v1/swagger.yaml` (`info.version` is a `YYYYMMDD.HHMMSS` timestamp; read it from the live spec).

## Authentication

| Scheme | Header | Best for |
|---|---|---|
| `BearerAuth` | `Authorization: Bearer $VENICE_API_KEY` | Server-side apps, account management, usage analytics, DIEM / bundled credits |
| `siwx` (x402) | `SIGN-IN-WITH-X: <base64 SIWX JSON>` (legacy `X-Sign-In-With-X` also accepted) | No account, pay-as-you-go with USDC on Base or Solana, serverless / agents |

Not every endpoint accepts both:

| Endpoints | Accepts |
|---|---|
| All inference: chat, responses, embeddings, decisions, image, audio (speech, transcriptions, voices, queue/retrieve/complete, voice-changer queue/retrieve/complete), video queue/retrieve/complete, augment, `POST /crypto/rpc/{network}` | Bearer **or** SIWX |
| `/api_keys/*` (except `generate_web3_key`), `/billing/*` (except the retired `/billing/usage`), `/characters/*` | Bearer only (a `SIGN-IN-WITH-X` header alone gets `401 Authentication failed`) |
| `/x402/balance/{wallet}`, `/x402/transactions/{wallet}` | SIWX only (signer must own the wallet) |
| `/models*`, `/image/styles`, `/video/quote` (except upscale models such as `topaz-video-upscale`: Bearer key required, so wallets can't quote them), `/audio/quote`, `/audio/voice-changer/quote`, `/crypto/rpc/networks`, `/tee/attestation`, `/tee/signature`, `/api_keys/generate_web3_key`, `POST /x402/top-up` | No auth needed |

On any route that needs credentials - Bearer-only ones included - a request with **no** `Authorization` and no `SIGN-IN-WITH-X` header gets `402` with an x402 discovery body (payment options + SIWX challenge + `authOptions`), not `401`. See [`venice-auth`](../venice-auth/SKILL.md).

```bash
# Bearer
curl https://api.venice.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"zai-org-glm-5-2","messages":[{"role":"user","content":"hi"}]}'
```

```ts
// x402 wallet via the SDK (EVM / Base wallets)
import { VeniceClient } from 'venice-x402-client'
const v = new VeniceClient(process.env.WALLET_KEY!)
await v.models()
```

## Endpoint map

### Inference

| Category | Endpoints | Skill |
|---|---|---|
| Chat | `POST /chat/completions` | [`venice-chat`](../venice-chat/SKILL.md) |
| Responses (Alpha) | `POST /responses` | [`venice-responses`](../venice-responses/SKILL.md) |
| Embeddings | `POST /embeddings` | [`venice-embeddings`](../venice-embeddings/SKILL.md) |
| Decisions (Beta) | `POST /decisions` (alias `POST /systemone`) | [`venice-decisions`](../venice-decisions/SKILL.md) |
| Image gen | `POST /image/generate`, `POST /images/generations`, `GET /image/styles` | [`venice-image-generate`](../venice-image-generate/SKILL.md) |
| Image edit | `POST /image/edit`, `POST /image/multi-edit`, `POST /image/upscale`, `POST /image/background-remove` | [`venice-image-edit`](../venice-image-edit/SKILL.md) |
| TTS | `POST /audio/speech`, `POST /audio/voices` (voice cloning) | [`venice-audio-speech`](../venice-audio-speech/SKILL.md) |
| STT | `POST /audio/transcriptions` | [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md) |
| Music / audio (async) | `POST /audio/quote`, `/audio/queue`, `/audio/retrieve`, `/audio/complete` | [`venice-audio-music`](../venice-audio-music/SKILL.md) |
| Voice changer (async) | `POST /audio/voice-changer/quote`, `/queue`, `/retrieve`, `/complete` | [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md) |
| Video (async) | `POST /video/quote`, `/video/queue`, `/video/retrieve`, `/video/complete` | [`venice-video`](../venice-video/SKILL.md) |

Voice changer: the endpoints are in the spec, but no voice-changer model is publicly listed today - check `GET /models?type=music` for a model with `voice_changer: true` first.

### Catalog

| Category | Endpoints | Skill |
|---|---|---|
| Models | `GET /models`, `/models/traits`, `/models/compatibility_mapping` | [`venice-models`](../venice-models/SKILL.md) |
| Characters | `GET /characters`, `/characters/{slug}`, `/characters/{slug}/reviews` | [`venice-characters`](../venice-characters/SKILL.md) |

`GET /models?type=` accepts `text` (default), `image`, `video`, `music`, `tts`, `asr`, `embedding`, `upscale`, `inpaint`, `decision`, plus the filters `all` and `code`.

### Account, billing, wallet

| Category | Endpoints | Skill |
|---|---|---|
| API keys | `GET`/`POST`/`PATCH`/`DELETE /api_keys`, `GET /api_keys/{id}`, `/api_keys/rate_limits`, `/api_keys/rate_limits/log`, `/api_keys/generate_web3_key` | [`venice-api-keys`](../venice-api-keys/SKILL.md) |
| Billing (Beta) | `GET /billing/balance`, `/billing/usage-history`, `/billing/usage-analytics` | [`venice-billing`](../venice-billing/SKILL.md) |
| x402 wallet | `POST /x402/top-up`, `GET /x402/balance/{wallet}`, `GET /x402/transactions/{wallet}` | [`venice-x402`](../venice-x402/SKILL.md) |

### Utility

| Category | Endpoints | Skill |
|---|---|---|
| Crypto RPC proxy | `GET /crypto/rpc/networks`, `POST /crypto/rpc/{network}` | [`venice-crypto-rpc`](../venice-crypto-rpc/SKILL.md) |
| Augment | `POST /augment/text-parser`, `/augment/scrape`, `/augment/search` | [`venice-augment`](../venice-augment/SKILL.md) |
| TEE verification | `GET /tee/attestation`, `GET /tee/signature` (public, 10 req/min per IP) | [`venice-text-routing`](../venice-text-routing/SKILL.md#verifying-a-tee-claim) |

### Retired (return `410 Gone`)

| Endpoint | Replacement |
|---|---|
| `GET /billing/usage` - sunset 2026-09-16 | `GET /billing/usage-history` (cursor pagination: `pageSize` + `nextCursor`, `startTimestamp` / `endTimestamp`) |
| `POST /video/transcriptions` | `POST /chat/completions` with a `video_url` part on a model whose `capabilities.supportsVideoInput` is `true` |

Both answer with `410` plus `Deprecation` and `Link: <…>; rel="successor-version"` headers (`/billing/usage` also sends `Sunset`). They need no auth; a per-IP limit of 60 requests/minute returns `429` to clients that keep polling.

## Response headers to watch

| Header | When | Meaning |
|---|---|---|
| `x-ratelimit-limit-requests` / `-remaining-requests` / `-reset-requests` | Most inference responses | Request window for your account - per model (the tighter of per-minute and per-day), or per endpoint on video / audio-generation routes and `/augment/scrape` / `/augment/search`. Reset is a Unix timestamp in **milliseconds**. |
| `x-ratelimit-limit-tokens` / `-remaining-tokens` / `-reset-tokens` | Token-limited text models | Tokens-per-minute window (reset in ms). |
| `x-ratelimit-remaining` / `x-ratelimit-resets` | Most responses on routes that need credentials | The **error budget** (failed requests allowed in the 30 s window), not your request quota. Read before the current response is counted, so a failed response showing `1` means none are left. Reset in ms. |
| `x-venice-balance-usd` / `x-venice-balance-diem` | Inference responses | Spendable balance when the request started (x402 callers see their wallet credit here). Omitted when that balance is zero; the USD figure excludes bundled and earned credits. |
| `x-venice-version` | Inference responses | Server revision - handy in bug reports. |
| `x-venice-deprecated`, `x-venice-model-deprecation-date`, `x-venice-model-deprecation-warning`, `x-venice-deprecated-replacement` | Requests to a model scheduled for retirement (chat, image, video queue) | Retirement date and suggested replacement. |
| `PAYMENT-REQUIRED` | Every x402 `402`: no credentials, wallet below the minimum balance, `/x402/top-up` discovery, `/x402/balance` / `/x402/transactions` without SIWX | Base64 JSON of the x402 v2 payment-required object (`accepts[]`, plus the `sign-in-with-x` challenge except on `/x402/top-up`). |
| `Retry-After` | `429` "model overloaded" | Seconds to wait (default 30). |
| `Deprecation` / `Sunset` / `Link` | Retired endpoints | See table above. |
| `Content-Encoding` | When you send `Accept-Encoding` (`gzip`, `br`, `deflate`) | Compressed responses on any route, once the body is large enough to be worth compressing. The spec documents it on chat, embeddings, decisions and image generation. |

The spec also documents an `X-Balance-Remaining` header on x402 responses, but current server code does not set it - read `x-venice-balance-usd` or call `GET /x402/balance/{wallet}` instead.

## Pricing model at a glance

- Pricing is **dynamic per request**, metered in USD. Paid endpoints in the spec carry an `x-payment-info` block (`price.mode: dynamic`, `min: "0.001"`, `max: "10.00"` USD); `POST /x402/top-up` is `5`-`10000`. Read-only routes (`/models`, quotes) have none.
- API-key accounts charge each request to a single currency, picked in the order **DIEM** → **earned credits** → **bundled credits** → **USD** (see [`venice-billing`](../venice-billing/SKILL.md#currency--priority)). Per-key `consumptionLimits` can cap USD / DIEM spend.
- x402 wallets spend a prepaid **USDC credit balance** topped up on Base or Solana (minimum top-up $5; a request needs at least $0.10 of balance to start). An EVM wallet linked to a Venice account with staked DIEM spends DIEM first.
- The per-model price is on `GET /models` → `model_spec.pricing`, already including any promotion active for your account. Video has no price there - use `POST /video/quote`; music / voice changer have exact quotes via `/audio/quote` and `/audio/voice-changer/quote`. See [`venice-models`](../venice-models/SKILL.md).

## Standard error shape

Most errors are:

```json
{ "error": "Human-readable message" }
```

Schema validation failures (`400`) add a `details` tree and an `issues` array:

```json
{ "error": "Invalid request parameters", "details": { "_errors": [], "type": { "_errors": ["Invalid enum value…"] } }, "issues": [ … ] }
```

Exceptions worth knowing: context-length overflows on chat return an OpenAI-style object (`{ "error": { "message", "type": "invalid_request_error", "param": "messages", "code": "context_length_exceeded" } }`), upstream provider rejections return the provider's message (plus `request_id` on routes that track one, such as chat), and `402` on x402 returns structured top-up data. A `POST` whose `Content-Type` is neither `application/json` nor `multipart/form-data` gets `400` `"'Content-Type' must be 'application/json'"` before auth runs. See [`venice-errors`](../venice-errors/SKILL.md) for the full table and retry strategy.

## OpenAI compatibility - what works and what doesn't

- Drop-in: `/chat/completions`, `/responses`, `/embeddings`, `/images/generations`, `/audio/speech`, `/audio/transcriptions`, `/models`.
- Accepted but ignored for compat: `user`, `store` (on chat). `user` is **not** an alias of Venice's `anon_user_id` (it does partition the error budget - see [`venice-errors`](../venice-errors/SKILL.md#error-budget)).
- Venice-only extensions live under `venice_parameters` - the full set on `/chat/completions`, a seven-field subset (`character_slug`, `enable_e2ee`, `enable_web_search`, `enable_web_scraping`, `enable_web_citations`, `include_venice_system_prompt`, `include_search_results_in_stream`) on `/responses`.
- Model feature suffixes (e.g. `zai-org-glm-5-1:enable_web_search=on`, `kimi-k2-6:strip_thinking_response=true&disable_thinking=true`) flip `venice_parameters` via the model ID - see [`venice-chat`](../venice-chat/SKILL.md#model-feature-suffixes).
- A trait name (`default_reasoning`) or a legacy alias (`gpt-4o`) can be sent as `model`; Venice resolves it. See [`venice-models`](../venice-models/SKILL.md).

## Versioning

- `info.version` in `swagger.yaml` is a timestamp (`YYYYMMDD.HHMMSS`). There is **no** `/v2`; features roll forward on the single `/api/v1` surface and are guarded by:
  - **Alpha/Beta** labels in endpoint descriptions (Responses is Alpha; Decisions and Billing are Beta).
  - `betaModel` / `deprecation` metadata and capability flags on `/models`.
- Retired endpoints answer `410` with `Deprecation` / `Link` headers rather than disappearing silently.
- Always check the model's `model_spec.capabilities` (`supportsWebSearch`, `supportsReasoning`, `supportsE2EE`, `supportsXSearch`, `supportsMultipleImages`, `supportsFunctionCalling`, `supportsAudioInput`, `supportsVideoInput`, …) before relying on a feature.

## Fast start checklist

1. Read [`venice-auth`](../venice-auth/SKILL.md) and choose Bearer vs x402.
2. `GET /models?type=…` - pick a model and note its `model_spec.constraints` and `model_spec.pricing`.
3. Wire up one happy-path call from the matching skill.
4. Add error handling using [`venice-errors`](../venice-errors/SKILL.md) (402, 422, 429).
5. Hook up observability via `x-ratelimit-*` / `x-venice-balance-*` headers, `/billing/usage-history` (ADMIN key only), or `/x402/transactions/{wallet}` (wallet callers).
