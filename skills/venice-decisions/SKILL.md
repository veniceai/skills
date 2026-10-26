---
name: venice-decisions
description: Call Venice's Beta POST /decisions (and its TypeSafe-compatible alias POST /systemone) to get typed judgments instead of generated text. Covers the state + questions request shape, optional images (PNG/JPEG data URI or {content_type, base64}, 1–4), the three question/answer types (noul yes/no probability, choice with probability distribution + confidence, score on an ordered rubric), model discovery via GET /models?type=decision (privacy, maxStateTokens / maxTotalTokens, pricing), rate limits, and how upstream 422 validation errors surface as 400.
---

# Venice Decisions (Beta)

`POST /api/v1/decisions` evaluates a `state` (text or JSON) against a map of typed `questions` and returns one structured `answer` per question — probabilities, picks, and scores your code can branch on directly. It does **not** generate text. Models are **System One** decision models from `GET /models?type=decision` (the catalog is not Jev-only). Examples below use `jev-latest`.

> **Beta.** The spec labels both routes Beta: "Request/response schemas and behavior may change without notice."

## Use when

- Routing / classifying (support tickets, intents, moderation buckets) into a closed set of options.
- Yes/no gates where the probability itself is useful (`is_urgent`, `requests_refund`).
- Rating something on an ordered rubric (severity, frustration, quality).
- You want several independent judgments about the **same** state in one call.

Use [`venice-chat`](../venice-chat/SKILL.md) instead when you need prose, explanations, multi-turn conversation, tool calling, or open-ended answers.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/decisions` | Main route (`operationId: createDecision`). API key or x402. |
| `POST` | `/api/v1/systemone` | Same behavior as `/decisions` (`createDecisionSystemOne`). Mirrors TypeSafe's upstream path so TypeSafe SDKs work with a base-URL swap: `TYPESAFE_BASE_URL=https://api.venice.ai/api`. |
| `GET` | `/api/v1/models?type=decision` | Lists decision models with pricing and token limits. |

Both POST routes accept `Accept-Encoding: gzip, br`.

## Quick start

```bash
curl https://api.venice.ai/api/v1/decisions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "jev-latest",
    "state": "My payouts have failed for three days and nobody has replied. Please help ASAP.",
    "questions": {
      "is_urgent": {
        "type": "noul",
        "instructions": "Does this message require urgent attention?"
      },
      "department": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "criteria": {
          "billing": "Payments, invoices, or refunds",
          "technical": "Bugs, outages, or integrations",
          "sales": "Pricing, upgrades, or new accounts"
        }
      },
      "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": ["Calm", "Frustrated", "Very angry"]
      }
    }
  }'
```

Illustrative response (values vary per request):

```json
{
  "model": "jev-latest",
  "answers": {
    "is_urgent": { "type": "noul", "noul": 0.95 },
    "department": {
      "type": "choice",
      "choice": "billing",
      "probabilities": { "billing": 0.95, "technical": 0.05, "sales": 0 },
      "confidence": 0.93
    },
    "frustration": {
      "type": "score",
      "score": 1.27,
      "legend": { "0": "Calm", "1": "Frustrated", "2": "Very angry" },
      "probabilities": { "0": 0, "1": 0.73, "2": 0.27 },
      "confidence": 0.6
    }
  },
  "usage": { "input_tokens": 429, "output_tokens": 73 }
}
```

## Request schema

Top level is **strict** — unknown fields are rejected with `400`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `model` | string | Yes | A decision-model id from `GET /models?type=decision`. `jev-latest` also accepts aliases `jev-1-13-0` / `typesafe-jev`. Missing/empty → `400 "model is required"`; non-string → `400`; unknown → `404` with a suggestion. |
| `state` | string \| object \| array | Yes | What to evaluate. String must be non-empty; array must have ≥ 1 item; object is free-form JSON (not checked by Venice for emptiness). Use structured JSON for chat logs, records, or app state. |
| `images` | array | No | 1–4 PNG or JPEG images the model should look at, shared by every question. Each entry is a `data:` URI or `{ content_type, base64 }`. Remote URLs are **not** fetched. See [Images](#images). |
| `questions` | object (map) | Yes | Map of `question_id → question`. At least one entry (`"At least one question is required"`). Answers come back under the same ids. Each question is evaluated in parallel and in isolation against the same state; question ids are not sent to the model, so put all meaning in `instructions`. |

### Question objects

Each question is **strict** (no extra keys) and discriminated by `type`. `instructions` on every type accepts a non-empty string, a JSON object, or a non-empty array.

| `type` | `instructions` | `criteria` | Venice-side limits |
|---|---|---|---|
| `noul` | Required. The yes/no question. | Optional object `{ "true"?: string, "false"?: string }` — what a yes (≈1) / no (≈0) means. | Any other key inside `criteria` is silently stripped (not rejected). |
| `choice` | Required. What to decide. | **Required** map `option_name → description \| null` (`null` = no extra detail). | No minimum option count enforced by Venice; upstream may reject degenerate sets. |
| `score` | Required. What to rate. | **Required** array of level descriptions, ordered lowest → highest. | `minItems: 2`. |

Any other `type` value is rejected with `400`.

### Images

Optional. Use when the judgment depends on something visual (screenshot, receipt, product photo). Every question in the request sees the same images alongside `state`.

Each entry is one of:

- a `data:` URI string matching `data:image/(png|jpeg|jpg);base64,…`
- an object `{ "content_type": "image/png" | "image/jpeg" | "image/jpg", "base64": "<raw base64, no data: prefix>" }`

Spec limits (live `CreateDecisionRequestSchema.images`): `minItems` 1, `maxItems` 4; each encoded string `maxLength` 13631488; PNG/JPEG only. Venice does not fetch `http(s)` URLs — embed the bytes. Sending `images: []` fails schema validation (`minItems: 1`); omit the field when you have no images.

```bash
curl https://api.venice.ai/api/v1/decisions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "jev-latest",
    "state": "Customer reports that the checkout page shows an error after entering card details.",
    "images": [
      "data:image/png;base64,iVBORw0KGgo="
    ],
    "questions": {
      "shows_error": {
        "type": "noul",
        "instructions": "Does the screenshot show a visible error message?"
      }
    }
  }'
```

The placeholders above are schema-shaped, not a real screenshot. Public `GET /models?type=decision` does not currently advertise a vision/image capability flag — the field is on the deployed request schema.

### Token limits

From `GET /models?type=decision` (`model_spec`) — **do not hard-code Jev's numbers**:

- `maxStateTokens` — `state` plus the single longest question.
- `maxTotalTokens` — `state` plus all questions combined.

On 2026-10-26 the public catalog reported `jev-latest` at 32000 / 64000 and `clef-api` at 32768 / 32768. Re-read the catalog.

Venice does **not** count tokens before forwarding; these budgets are enforced upstream. An oversized request therefore passes Venice validation and fails upstream — as a `400` carrying TypeSafe's message if TypeSafe answers 400/422, otherwise as a `500` (see Errors). The generic JSON body cap is 35 MB.

## Answer types

Every answer has `type`. The response schema passes unknown extra fields through, and an answer whose `type` is not `noul`/`choice`/`score` is forwarded as-is (forward-compat) — branch on `type` and ignore what you don't recognise.

### `noul` — yes/no probability

```json
{
  "refund_requested": {
    "type": "noul",
    "instructions": "Does the customer explicitly request a refund?",
    "criteria": {
      "true": "The customer asks for money to be returned",
      "false": "The customer does not ask for money to be returned"
    }
  }
}
```

```json
{ "refund_requested": { "type": "noul", "noul": 0.88 } }
```

- `noul`: number in `[0, 1]`; ≈1 strong yes, ≈0 strong no, ≈0.5 uncertain. There is **no** `confidence` field on noul answers.

### `choice` — pick one option

```json
{
  "request_type": {
    "type": "choice",
    "instructions": "What is the customer's primary request?",
    "criteria": {
      "refund": "Return money already paid",
      "troubleshooting": "Help resolve a product problem",
      "information": "Answer a question without taking action",
      "other": null
    }
  }
}
```

```json
{
  "request_type": {
    "type": "choice",
    "choice": "refund",
    "probabilities": { "refund": 0.9, "troubleshooting": 0.06, "information": 0.03, "other": 0.01 },
    "confidence": 0.85
  }
}
```

- `choice`: the highest-probability option name.
- `probabilities`: every option → probability in `[0, 1]` (sum to 1).
- `confidence`: `[0, 1]`, derived from the distribution.
- Include an `other` / `none` option when your options may not cover every state.

### `score` — position on an ordered rubric

```json
{
  "severity": {
    "type": "score",
    "instructions": "How severe is the reported issue?",
    "criteria": [
      "Cosmetic or no material impact",
      "Workflow is impaired but a workaround exists",
      "Critical workflow is blocked with no workaround"
    ]
  }
}
```

```json
{
  "severity": {
    "type": "score",
    "score": 1.4,
    "legend": {
      "0": "Cosmetic or no material impact",
      "1": "Workflow is impaired but a workaround exists",
      "2": "Critical workflow is blocked with no workaround"
    },
    "probabilities": { "0": 0.05, "1": 0.5, "2": 0.45 },
    "confidence": 0.55
  }
}
```

- Levels are indexed from `0` in the order you gave them; `legend` and `probabilities` are keyed by the index **as a string**.
- `score`: probability-weighted (≥ 0), so it can land between levels.
- `confidence`: `[0, 1]`, derived from the distribution.

## Response

| Field | Type | Notes |
|---|---|---|
| `model` | string | Canonical catalog id of the model that ran (e.g. `jev-latest` even if you sent an alias). |
| `answers` | object | One answer per question id (shapes above). |
| `usage.input_tokens` | integer ≥ 0 | Tokens for state + questions. Billed. |
| `usage.output_tokens` | integer ≥ 0 | Tokens produced evaluating the questions. Currently priced at $0. |

Headers: `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`; `Content-Encoding` when compressed. The spec also lists `X-Balance-Remaining` for x402 callers, but the server does not currently set it — poll `GET /x402/balance/{walletAddress}` instead.

## JavaScript / Python

No OpenAI SDK method exists for this route — use plain HTTP.

```ts
const res = await fetch('https://api.venice.ai/api/v1/decisions', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'jev-latest',
    state: { ticket: { subject: 'Duplicate charge', message: 'I was charged twice. Please refund the duplicate.' }, account: { plan: 'pro' } },
    questions: {
      covered: { type: 'noul', instructions: 'Does ticket.message request a refund for a duplicate charge?' },
      priority: { type: 'score', instructions: 'How urgent is this ticket?', criteria: ['Low', 'Medium', 'High'] },
    },
  }),
})
if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
const { answers } = await res.json()

if (answers.covered.type === 'noul' && answers.covered.noul >= 0.9) {
  // auto-approve
}
```

```python
import os, requests

r = requests.post(
    "https://api.venice.ai/api/v1/decisions",
    headers={"Authorization": f"Bearer {os.environ['VENICE_API_KEY']}"},
    json={
        "model": "jev-latest",
        "state": "Help! My payouts have been failing for 3 days.",
        "questions": {
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {"billing": "Payments, invoicing, refunds", "technical": "Bugs, outages, integrations"},
            }
        },
    },
    timeout=60,
)
r.raise_for_status()
team = r.json()["answers"]["team"]
route = team["choice"] if team["confidence"] >= 0.8 else "human_review"
```

## Authentication

Both routes accept either (see [`venice-auth`](../venice-auth/SKILL.md)):

- `Authorization: Bearer $VENICE_API_KEY`, or
- `SIGN-IN-WITH-X` wallet auth for x402 (legacy `X-Sign-In-With-X` also accepted). Payment headers (`X-PAYMENT` etc.) are only accepted on `/x402/top-up`; sending one here → `400 PAYMENT_HEADER_NOT_ACCEPTED`. See [`venice-x402`](../venice-x402/SKILL.md).

With no credentials at all you get a `402` x402 discovery response. The spec's `x-payment-info` is `mode: dynamic`, USD, `min 0.001` / `max 10.00`.

API keys whose `modelPrivacy` forbids the selected model's `model_spec.privacy` are refused (`403`). Decision models are **not** all anonymized — read the catalog (`jev-latest` is `anonymized`; `clef-api` is `private` on 2026-10-26). `PRIVATE_TEXT` still gates this route as well as text and embeddings.

## Pricing & limits

- **Price** — read `model_spec.pricing` on `GET /models?type=decision`. On 2026-10-26 `jev-latest` was **$0.042 / 1M input** and **$0 output**; `clef-api` was **$0.05 / 1M** input and output. Do not assume Jev's numbers.
- Charged from `usage` **after** a successful response. If the upstream answer is malformed or missing `usage`, you get `500` and are not charged.
- Balance is checked before the call; insufficient balance → `402`.
- **Rate limits** (per account, shared by all its keys; Jev-specific override): Paid tier **100 RPM / 1,000,000 TPM**; Partner Tier 1 **300 RPM / 10,000,000 TPM**. One request is counted before the model runs; tokens (`input + output`) are metered afterwards. Check yours with `GET /api_keys/rate_limits` ([`venice-api-keys`](../venice-api-keys/SKILL.md)).

## Errors

| Status | Cause | Fix |
|---|---|---|
| `400` | `model` missing / empty or not a string → plain `{ "error": "model is required" }` / `"model must be a string"` (checked before the schema, no `issues`). | Send `"model": "jev-latest"`. |
| `400` | Venice schema validation failed (missing `state`/`questions`, empty `questions`, bad `type`, extra field, `score` with < 2 levels, missing `choice` criteria). Body: `{ error: "Invalid request parameters", details, issues }`. | Fix the field named in `issues[].path`. |
| `400` | **Upstream TypeSafe 400/422** — a request that passed Venice's schema but TypeSafe rejected. Venice flattens FastAPI `detail` into `{ "error": "<loc>: <msg>; …" }` (up to 5 items, `body.` prefix stripped, echoed input never returned). If nothing is extractable: `"Invalid request parameters. For assistance, please reach out to support@venice.ai"`. | Read `error` — it names the field path and TypeSafe's message. |
| `400` | `PAYMENT_HEADER_NOT_ACCEPTED` | Use `SIGN-IN-WITH-X`, not a payment header. |
| `401` | Auth failed. | Check the key / SIWX header. |
| `402` | No credentials (x402 discovery); insufficient balance (`"Insufficient USD or Diem balance…"` for keys, structured `PAYMENT_REQUIRED` for x402); per-key USD/DIEM spend limit reached. | API key: add credits at https://venice.ai/settings/api, or raise the key's limit (ADMIN key, `PATCH /api_keys`). Wallet: `POST /x402/top-up` ([`venice-x402`](../venice-x402/SKILL.md)). |
| `403` | Key privacy setting forbids anonymized models; region or provider restriction; API access disabled for the account. | Use a key with `modelPrivacy: ALL`. |
| `404` | Unknown `model`. | Send an id from `GET /models?type=decision`. |
| `400` | Non-JSON `Content-Type` → `"'Content-Type' must be 'application/json'"` (the spec lists `415`, but the server returns `400`). | `Content-Type: application/json`. |
| `429` | Venice rate limit for your account on this model; **or** TypeSafe capacity (upstream 429/529 → "The model is currently overloaded", with `Retry-After`, upstream value or 30 s); **or** the error-budget lockout (50 non-429 4xx responses within a 30 s window, per key + `model`; this route rejects a `user` field, so all of a key's decisions requests share one bucket). | Honour `Retry-After`; back off with jitter. |
| `500` | Any other upstream failure (non-400/422/429/529 status), the 30 s upstream timeout, or a malformed upstream answer. Not charged. | Retry with backoff. |
| `503` | Model marked offline. | Retry later. |

General retry strategy and body shapes: [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- **Beta, catalog models.** `GET /models?type=decision` lists the public System One models (on 2026-10-26: `jev-latest` and `clef-api`). Don't assume Jev-only privacy, pricing, or token limits — read `model_spec`.
- **Images are embed-only.** The spec rejects remote URLs; send `data:` URIs or `{ content_type, base64 }`, 1–4 PNG/JPEG. Omit `images` rather than sending an empty array.
- **Not chat.** There is no `messages`, `temperature`, `max_tokens`, streaming, or tools. Adding any unknown field is a `400` (strict schema).
- **Questions are isolated.** One answer never becomes context for another. If question B depends on A's result, make a second request.
- **Question ids carry no meaning to the model.** `{"urgent": {...}}` with vague `instructions` won't help — write complete instructions and name the fields in structured state (e.g. "Does `ticket.message` request a refund covered by `refund_policy`?").
- **Token budgets are enforced upstream**, so Venice validation passes and the failure arrives from TypeSafe. Pre-trim long states yourself.
- **Every 4xx except 429 counts toward the failed-requests error budget** on this route (the separate unsupported-feature budget applies only to `/chat/completions` and `/responses`), so a client looping on bad requests locks itself out for the rest of the 30 s window.
- **Probabilities vary between requests.** Calibrate thresholds on your own data; `confidence` is not a correctness guarantee. Noul has no `confidence` — use distance from 0.5.
- **`score` keys are strings** (`"0"`, `"1"`, …) in both `legend` and `probabilities`.
- **Branch on `answer.type`** — unknown future answer types are passed through untouched.
- **Anonymized, not private.** State is sent to TypeSafe; don't route data that requires Venice-private inference.
- Model discovery and pricing fields: [`venice-models`](../venice-models/SKILL.md).
