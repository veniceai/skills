---
name: venice-embeddings
description: Call POST /embeddings on Venice. Covers request shape (input, model, encoding_format, dimensions, user), text-only input (token arrays rejected), per-input and batch limits, per-model dimensions/privacy, the text-embedding-ada-002 alias, API-key privacy gating, OpenAI/LangChain compatibility, response compression (gzip/br), and practical usage for retrieval, clustering, and RAG.
---

# Venice Embeddings

`POST /api/v1/embeddings` returns vector embeddings for strings. It's OpenAI-compatible: request and response match `https://api.openai.com/v1/embeddings` closely enough that the OpenAI SDK works with `baseURL: "https://api.venice.ai/api/v1"`, with one exception: **token-ID arrays are not accepted** (see below).

Auth: Bearer API key or x402 wallet (`SIGN-IN-WITH-X`) — see [`venice-auth`](../venice-auth/SKILL.md).

## Use when

- You're building retrieval / RAG / similarity search.
- You need text clustering, classification, deduplication, or reranking features.
- You want embeddings from a model Venice runs as **Private** (most of the catalog) rather than an anonymized third-party one — check `model_spec.privacy` on each model.

Text-only: `input` must be a string or an array of strings. For images, run them through a vision chat model and embed the description.

## Minimal request

```bash
curl https://api.venice.ai/api/v1/embeddings \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  --compressed \
  -d '{
    "model": "text-embedding-bge-m3",
    "input": "Why is the sky blue?"
  }'
```

```json
{
  "object": "list",
  "model": "text-embedding-bge-m3",
  "data": [
    { "object": "embedding", "index": 0, "embedding": [0.0023, -0.0093, 0.0158, ...] }
  ],
  "usage": { "prompt_tokens": 8, "total_tokens": 8 }
}
```

## Request schema

The body is **strict** — unknown top-level fields (e.g. `input_type`, `task`, `truncate`) are rejected with `400`.

| Field | Type | Notes |
|---|---|---|
| `model` | string | **Required.** Model ID from `GET /models?type=embedding`. `text-embedding-ada-002` is accepted as an alias for `text-embedding-bge-m3` (the response `model` then reads `text-embedding-bge-m3`). |
| `input` | string \| string[] | **Required.** A non-empty string, or an array of 1–2048 strings. Token-ID arrays (`number[]` / `number[][]`) are rejected with `400` — see Gotchas. |
| `encoding_format` | `"float"` \| `"base64"` | Default `"float"`. `"base64"` returns each vector as a base64-encoded string — a much smaller payload; decode client-side. |
| `dimensions` | integer ≥ 1 | Optional. Requested output size. Only honoured by models whose `model_spec.supportsCustomDimensions` is `true`; it is forwarded as-is otherwise, and the provider may ignore or reject it. |
| `user` | string | Accepted for OpenAI compatibility; not used for inference, but it does split the error budget per value (see [`venice-errors`](../venice-errors/SKILL.md#error-budget)). |

### Input limits

- **Per item:** Venice estimates tokens as `ceil(chars / 3.2 × 0.95)` and rejects any string over **8192** estimated tokens (≈ 27,500 characters) with `400 "Input text exceeds the maximum token limit of 8192 tokens"`. This cap is the same for every model, including those whose `maxInputTokens` is 32768.
- **Model limit:** models with a smaller `model_spec.maxInputTokens` (e.g. 512 for `text-embedding-multilingual-e5-large-instruct`, 2048 for `gemini-embedding-2-preview`) enforce that limit themselves; Venice's pre-check does not. Chunk to the model's `maxInputTokens`.
- **Batch:** at most **2048** strings per request. Venice returns one embedding per element, in order, with matching `index`.

## Response headers & compression

Send `Accept-Encoding: gzip, br` (curl: `--compressed`; most HTTP clients decode automatically); the response comes back with `Content-Encoding` set. For large batches this matters — float vectors in JSON are big.

Also returned:

- `x-ratelimit-limit-*` / `x-ratelimit-remaining-*` / `x-ratelimit-reset-*` (`requests`, `tokens`) — see [`venice-errors`](../venice-errors/SKILL.md).
- `x-venice-balance-usd` / `x-venice-balance-diem` — current balance, when non-zero.
- `X-Balance-Remaining` — listed in the spec for x402 callers but not currently set by the server; poll `GET /x402/balance/{walletAddress}` instead.

## Using the OpenAI SDK

```ts
import OpenAI from 'openai'

const client = new OpenAI({
  apiKey: process.env.VENICE_API_KEY,
  baseURL: 'https://api.venice.ai/api/v1',
})

const res = await client.embeddings.create({
  model: 'text-embedding-bge-m3',
  input: ['first doc', 'second doc'],
})

const vec0 = res.data[0].embedding
```

The OpenAI Node SDK asks for `base64` when you omit `encoding_format` and decodes it client-side. Venice forwards `encoding_format` to the model; if the decoded vectors look wrong, pass `encoding_format: 'float'` explicitly.

### LangChain

LangChain's `OpenAIEmbeddings` tokenizes input and sends **token arrays** by default, which Venice rejects. Turn that off:

```python
import os
from langchain_openai import OpenAIEmbeddings

emb = OpenAIEmbeddings(
    model="text-embedding-bge-m3",
    base_url="https://api.venice.ai/api/v1",
    api_key=os.environ["VENICE_API_KEY"],
    check_embedding_ctx_length=False,
)
```

Wrappers that build `OpenAIEmbeddings` internally without that flag (e.g. gpt-researcher's `openai` provider) hit the same `400`.

## Batch-embedding pattern

```ts
async function embedBatch(texts: string[], batchSize = 64) {
  const out: number[][] = []
  for (let i = 0; i < texts.length; i += batchSize) {
    const slice = texts.slice(i, i + batchSize)
    const res = await client.embeddings.create({
      model: 'text-embedding-bge-m3',
      input: slice,
      encoding_format: 'float',
    })
    for (const row of res.data) out[i + row.index] = row.embedding
  }
  return out
}
```

- Keep each string under the per-item limits above; batch size is capped at 2048.
- On `429`, back off exponentially and halve the batch — see [`venice-errors`](../venice-errors/SKILL.md).

## Choosing a model

Query `GET /models?type=embedding` for the current catalog. Each entry's `model_spec` exposes:

- `embeddingDimensions` — native output dimension (e.g. 1024 for `text-embedding-bge-m3`, 4096 for `text-embedding-qwen3-8b`).
- `maxInputTokens` — the model's per-input token limit.
- `supportsCustomDimensions` — present and `true` only on models that honour `dimensions` (absent otherwise).
- `privacy` — `"private"` (no retention) or `"anonymized"` (a third-party model; the request is sent without your identity).
- `pricing.input` / `pricing.output` — `{ usd, diem }` per **million** tokens.

Representative IDs: `text-embedding-bge-m3` (private, 1024-d), `text-embedding-qwen3-8b` (private, 4096-d, custom dimensions), `text-embedding-multilingual-e5-large-instruct` (private, 512-token inputs), `text-embedding-3-small` / `text-embedding-3-large` (anonymized, OpenAI, custom dimensions), `gemini-embedding-2-preview` (anonymized, custom dimensions). The list changes — always read it from `/models`.

Always pin the model ID — cosine distances are **not** comparable across different embedding models.

## Error handling

| Code | Meaning |
|---|---|
| `400` | Missing `model`, or a validation error (`details` names the field): token-array input, empty string/array, > 2048 items, item over the 8192-token estimate, unknown field. Non-JSON `Content-Type` → `"'Content-Type' must be 'application/json'"`. Also model-side rejections (e.g. input over the model's own limit), returned with the model's message when one can be extracted, otherwise a generic `"Invalid request parameters…"`. |
| `401` | Invalid API key or SIWX signature. |
| `402` | Insufficient balance or the key's USD/DIEM spend limit reached. Bearer → `"Insufficient USD or Diem balance…"`; x402 → payment-required body + `PAYMENT-REQUIRED` header. A request with **no** credentials at all also gets `402` (x402 discovery challenge), not `401`. |
| `403` | The API key's `modelPrivacy` is `PRIVATE_TEXT` or `PRIVATE_ONLY` and the model is `anonymized`. Also region / provider restrictions, or API access disabled for the account. |
| `404` | Unknown model (the message may suggest a close match). |
| `429` | Rate limited. |
| `500` | Inference failed; retry with jitter. |
| `503` | Model temporarily offline; retry later. |

## Gotchas

- **Token arrays are rejected.** `input: [101, 2023, ...]` or `[[101, ...]]` returns `400 "Token array inputs are not supported. Pass a string or an array of strings."` Send text.
- **API-key privacy applies to embeddings.** A key with `modelPrivacy: PRIVATE_TEXT` (or `PRIVATE_ONLY`) can only call `private` embedding models; `text-embedding-3-*` and `gemini-embedding-2-preview` return `403`. See [`venice-api-keys`](../venice-api-keys/SKILL.md).
- A top-level empty string is rejected with `400`, but empty strings *inside* an array are not pre-checked — filter them out yourself.
- The request must be `Content-Type: application/json`; anything else is rejected with `400 "'Content-Type' must be 'application/json'"` before auth or validation runs.
- Whether returned vectors are L2-normalized depends on the model — verify with `Math.hypot(...v) ≈ 1` before assuming.
- For RAG, store `model` (and `dimensions`, if set) alongside each vector so you can re-embed on upgrade.
