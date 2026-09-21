---
name: venice-decisions
description: Typed decisions via POST /decisions (beta) and its TypeSafe alias POST /systemone. Evaluate a state against noul/choice/score questions and get structured answers, probabilities, and confidence — not generated prose. Discover models with GET /models?type=decision.
---

# Venice Decisions (Jev) — Beta

`POST /api/v1/decisions` evaluates a `state` against a map of typed `questions` and returns machine-ready `answers` under the same ids. It does **not** generate prose, call tools, or keep a conversation.

Also available as `POST /api/v1/systemone` (same request/response schema) for TypeSafe SDK drop-in.

> **Beta.** Spec: schemas and behavior may change without notice. Live `GET /models?type=decision` currently lists `jev-latest` with `model_spec.betaModel: true`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/decisions` | Canonical path. Bearer or SIWX. Dynamic USD (`x-payment-info` min `0.001`, max `10.00`). |
| `POST` | `/systemone` | Alias of `/decisions`. Same body. Public URL is `/api/v1/systemone`. |

## Use when

- You need a yes/no probability, a closed classification, or a scored rubric — values your code can branch on.
- Several independent questions should share one `state` (they run in parallel, in isolation).

Use [`venice-chat`](../venice-chat/SKILL.md) instead for generated text, multi-turn chat, tool calling, or open-ended reasoning.

## Discover a model

```bash
curl "https://api.venice.ai/api/v1/models?type=decision" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Read `model_spec.maxStateTokens`, `model_spec.maxTotalTokens`, and `model_spec.pricing` from that row. Do not hard-code limits or prices. `GET /models/traits?type=decision` and `GET /models/compatibility_mapping?type=decision` currently return empty `data` objects.

The spec example / enum includes `jev-latest`. Confirm it is still present and not `offline` before calling.

## `POST /decisions`

Required: `state`, `model`, `questions` (object, **at least one** key). Additional properties rejected.

`state` is a non-empty string, a JSON object, or a non-empty array (chat logs, records, application state).

`questions` is a map keyed by **your** ids. Ids are **not** sent to the model. Answers come back under the same keys. Every question is evaluated in parallel against the same `state`; one answer is not hidden context for another.

### Question types

| `type` | Required fields | Answer |
|---|---|---|
| `noul` | `instructions`. Optional `criteria.true` / `criteria.false` (strings). | `{ type, noul }` where `noul` is 0 (no) … 1 (yes). **No** `confidence` field. |
| `choice` | `instructions` + `criteria` (map of option name → rubric string or `null`). | `{ type, choice, probabilities, confidence }` |
| `score` | `instructions` + `criteria` (ordered string array, **min 2** levels, low → high). | `{ type, score, legend, probabilities, confidence }` |

`instructions` may be a non-empty string, an object, or a non-empty array.

- **Noul** — probability of yes. Near `1` is strong yes, near `0` strong no, near `0.5` uncertain.
- **Choice** — `choice` is the highest-probability option; `probabilities` maps every option to a float (they sum to 1); `confidence` is 0–1 derived from that distribution.
- **Score** — `score` is probability-weighted and can land **between** levels. Level indexes start at `0`. `legend` maps level number → description.

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

Example `200` (probabilities vary between requests):

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

```ts
const res = await fetch('https://api.venice.ai/api/v1/decisions', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'jev-latest',
    state: 'My payouts have failed for three days.',
    questions: {
      is_urgent: {
        type: 'noul',
        instructions: 'Does this message require urgent attention?',
      },
    },
  }),
})
if (!res.ok) throw new Error(await res.text())
const { answers, usage } = await res.json()
```

Gate automated actions on `choice` / `score` `confidence`. Noul uses the `noul` value itself as the certainty signal.

## `POST /systemone`

Same JSON body and response as `/decisions`. Call the public v1 path:

```bash
curl https://api.venice.ai/api/v1/systemone \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "jev-latest",
    "state": "Help! My payouts have been failing for 3 days.",
    "questions": {
      "is_urgent": {
        "type": "noul",
        "instructions": "Does this message convey urgency?"
      }
    }
  }'
```

```ts
const res = await fetch('https://api.venice.ai/api/v1/systemone', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'jev-latest',
    state: { ticket: { message: 'I was charged twice.' } },
    questions: {
      refund_requested: {
        type: 'noul',
        instructions: 'Does ticket.message explicitly request a refund?',
      },
    },
  }),
})
```

The spec text says TypeSafe clients may set `TYPESAFE_BASE_URL=https://api.venice.ai/api`. That base plus `/systemone` is `https://api.venice.ai/api/systemone`, which currently **404s**. The live path is `/api/v1/systemone`. Prefer that unless you have confirmed TypeSafe routing.

## Errors

| Status | Cause | Fix |
|---|---|---|
| `400` | Zod validation (`DetailedError`) — missing `state`/`model`/`questions`, empty questions map, `choice`/`score` missing `criteria`, `score.criteria` shorter than 2. | Fix the body. Don't retry. |
| `401` | Auth failed, or Pro-only / beta-gated model. | Check the key and `betaModel` on `/models`. |
| `402` | Insufficient balance / x402 payment required. | See [`venice-errors`](../venice-errors/SKILL.md). Unauthenticated calls to these paths return x402 discovery (`402`), not `401`. |
| `415` | Wrong `Content-Type`. JSON only. | Send `application/json`. |
| `429` | Rate limited. | Back off. |
| `500` / `503` | Inference / capacity. | Retry with jitter. |

Accepts `Accept-Encoding: gzip, br` (`Content-Encoding` on `200`).

## Gotchas

- Empty `questions` is invalid (`minProperties: 1`).
- Question ids are yours for bookkeeping; they are not model-visible. Put everything the model needs in `state` + `instructions` / `criteria`.
- Batch independent questions in one request. Make a second call only when the next `state` or choice set depends on an earlier answer.
- Include an `other` / `none` option on `choice` when the closed set may not cover every state (`criteria` values may be `null` when an option needs no extra rubric).
- `usage.input_tokens` / `usage.output_tokens` are on every `200`. Pricing is on `GET /models?type=decision` → `model_spec.pricing` (input/output USD and DIEM) — do not assume chat-model rates.
- Privacy for `jev-latest` is currently `anonymized` on `/models` (not private / zero-retention). Re-read the catalog; do not treat this like a private chat model.

Related: [`venice-models`](../venice-models/SKILL.md), [`venice-chat`](../venice-chat/SKILL.md), [`venice-errors`](../venice-errors/SKILL.md).
