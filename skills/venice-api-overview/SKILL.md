---
name: venice-api-overview
description: High-level map of the Venice.ai API - base URL, authentication modes, endpoint categories, response headers, pricing model, error shape, and versioning. Load this first when starting any Venice integration.
---

# Venice API Overview

Venice.ai is an OpenAI-compatible inference platform for text, image, audio, video, and embeddings. One API — two ways to pay: a traditional **API key** (Pro account), or a **wallet** (x402, USDC on Base or Solana, no account required).

## Use when

- You're writing code against `api.venice.ai` for the first time.
- You need to decide between API-key and x402/wallet authentication.
- You want a quick map of which endpoint to call for which task.
- You need to understand the common response headers (`X-Balance-Remaining`, `PAYMENT-REQUIRED`, etc.).

## Base URL

All endpoints live under:

```
https://api.venice.ai/api/v1
```

The OpenAPI spec is distributed at `outerface/swagger.yaml` (current version `20260728.190807`).

## Authentication (pick one per request)

| Scheme | Header | Best for |
|---|---|---|
| `BearerAuth` | `Authorization: Bearer <VENICE_API_KEY>` | Server-side apps, dashboards, usage analytics, bundled credits |
| `siwx` (x402) | `SIGN-IN-WITH-X: <base64 SIWX JSON>` | No account, pay-as-you-go with USDC on Base or Solana, serverless / agents |

Every inference endpoint accepts **either** — see [`venice-auth`](../venice-auth/SKILL.md).

```bash
# Bearer
curl https://api.venice.ai/api/v1/models \
  -H "Authorization: Bearer $VENICE_API_KEY"

# x402 / SIWE (one-liner via the SDK)
import { VeniceClient } from 'venice-x402-client'
const v = new VeniceClient(process.env.WALLET_KEY)
await v.models.list()
```

## Endpoint map

### Inference

| Category | Endpoints | Skill |
|---|---|---|
| Chat | `POST /chat/completions` | [`venice-chat`](../venice-chat/SKILL.md) |
| Responses (Alpha) | `POST /responses` | [`venice-responses`](../venice-responses/SKILL.md) |
| Embeddings | `POST /embeddings` | [`venice-embeddings`](../venice-embeddings/SKILL.md) |
| Image gen | `POST /image/generate`, `POST /images/generations`, `GET /image/styles` | [`venice-image-generate`](../venice-image-generate/SKILL.md) |
| Image edit | `POST /image/edit`, `POST /image/multi-edit`, `POST /image/upscale`, `POST /image/background-remove` | [`venice-image-edit`](../venice-image-edit/SKILL.md) |
| TTS | `POST /audio/speech`, `POST /audio/voices` (voice cloning) | [`venice-audio-speech`](../venice-audio-speech/SKILL.md) |
| STT | `POST /audio/transcriptions` | [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md) |
| Music (async) | `POST /audio/quote`, `/audio/queue`, `/audio/retrieve`, `/audio/complete` | [`venice-audio-music`](../venice-audio-music/SKILL.md) |
| Voice changer (async) | `POST /audio/voice-changer/quote`, `/audio/voice-changer/queue`, `/audio/voice-changer/retrieve`, `/audio/voice-changer/complete` | [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md) |
| Video (async) | `POST /video/quote`, `/video/queue`, `/video/retrieve`, `/video/complete`, `/video/transcriptions` | [`venice-video`](../venice-video/SKILL.md) |

### Catalog

| Category | Endpoints | Skill |
|---|---|---|
| Models | `GET /models`, `/models/traits`, `/models/compatibility_mapping` | [`venice-models`](../venice-models/SKILL.md) |
| Characters | `GET /characters`, `/characters/{slug}`, `/characters/{slug}/reviews` | [`venice-characters`](../venice-characters/SKILL.md) |

### Account, billing, wallet

| Category | Endpoints | Skill |
|---|---|---|
| API keys | `GET|POST|DELETE /api_keys`, `/api_keys/{id}`, `/api_keys/rate_limits`, `/api_keys/rate_limits/log`, `/api_keys/generate_web3_key` | [`venice-api-keys`](../venice-api-keys/SKILL.md) |
| Billing | `GET /billing/balance`, `/billing/usage-history`, `/billing/usage-analytics`, `/billing/usage` (deprecated) | [`venice-billing`](../venice-billing/SKILL.md) |
| x402 wallet | `GET /x402/balance/{wallet}`, `POST /x402/top-up`, `GET /x402/transactions/{wallet}` | [`venice-x402`](../venice-x402/SKILL.md) |

### Utility

| Category | Endpoints | Skill |
|---|---|---|
| Crypto RPC proxy | `GET /crypto/rpc/networks`, `POST /crypto/rpc/{network}` | [`venice-crypto-rpc`](../venice-crypto-rpc/SKILL.md) |
| Augment | `POST /augment/text-parser`, `/augment/scrape`, `/augment/search` | [`venice-augment`](../venice-augment/SKILL.md) |

## Response headers to watch

| Header | When | Meaning |
|---|---|---|
| `X-Balance-Remaining` | x402 inference success | USDC credits left, e.g. `"4.230000"` |
| `X-RateLimit-Limit-*` / `X-RateLimit-Remaining-*` | all inference | your current per-minute/day caps |
| `PAYMENT-REQUIRED` | `402` on x402 inference | base64 JSON with top-up + SIWX challenge (x402 v2) |
| `Content-Encoding` | `200` when client sent `Accept-Encoding: gzip, br` | compression (embeddings, chat) |

## Pricing model at a glance

- Pricing is **dynamic per request**, metered in USD.
- Paid inference endpoints in the spec carry an `x-payment-info` block with `min` and `max` bounds in USD (typically `min: 0.001`, `max: 10.00`; higher for bulk video/audio). Read-only discovery routes like `GET /models`, `/models/traits`, and `/models/compatibility_mapping` do not.
- Pro (Bearer) accounts draw from **DIEM** (staked credits), **USD** balance, and **bundled credits** in priority order.
- x402 (wallet) users draw from a prepaid **USDC credit balance** on Base.
- The authoritative per-model price is on `GET /models` → `model_spec.pricing` (when present — video models omit it; use `/video/quote` for video pricing) (see [`venice-models`](../venice-models/SKILL.md)).

## Standard error shape

Every error body follows one of:

```json
{ "error": "Human-readable message" }
```

or, for 400 validation errors:

```json
{ "error": "...", "details": { "fieldName": { "_errors": ["Field is required"] } } }
```

`402` on x402 adds structured `topUpInstructions` and `siwxChallenge`. See [`venice-errors`](../venice-errors/SKILL.md) for the full table and retry strategy.

## OpenAI compatibility — what works and what doesn't

- Drop-in: `/chat/completions`, `/embeddings`, `/images/generations`, `/audio/speech`, `/audio/transcriptions`, `/models`.
- Ignored but accepted for compat: `user`, `store`.
- Venice-only extensions live under:
  - `venice_parameters` (chat completions)
  - `venice_parameters` is **rejected** on `/responses` — use headers / native fields instead
- Model feature suffixes (e.g. `zai-org-glm-5-1:enable_web_search=on`, `kimi-k2-6:strip_thinking_response=true&disable_thinking=true`) flip `venice_parameters` via the model ID — see [`venice-chat`](../venice-chat/SKILL.md#model-feature-suffixes).

## Versioning

- `info.version` in `swagger.yaml` is a timestamp (`YYYYMMDD.HHMMSS`). There is **no** `/v2`; features roll forward on the single `/api/v1` surface and are guarded by:
  - **Alpha/Beta** tags in endpoint descriptions (e.g. `/responses`, Billing).
  - `x-guidance` / model capability flags on `/models`.
- Always check the model's `model_spec.capabilities` from `GET /models` for feature flags (`supportsWebSearch`, `supportsReasoning`, `supportsE2EE`, `supportsXSearch`, `supportsMultipleImages`, `supportsFunctionCalling`, `supportsAudioInput`, `supportsVideoInput`, …) before relying on a feature.

## Fast start checklist

1. Read [`venice-auth`](../venice-auth/SKILL.md) and choose Bearer vs x402.
2. `GET /models` — pick a model and note its `model_spec.constraints` and `model_spec.pricing`.
3. Wire up one happy-path call from the matching skill.
4. Add error handling using [`venice-errors`](../venice-errors/SKILL.md) (402, 422, 429).
5. Hook up observability via `X-Balance-Remaining` / `/billing/usage-history` / `/x402/transactions`.
