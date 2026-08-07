---
name: venice-augment
description: Venice augmentation endpoints for agent pipelines. Covers POST /augment/text-parser (extract text from PDF/DOCX/XLSX/plain text, multipart, up to 25MB, JSON or plain text response), POST /augment/scrape (fetch a URL and return markdown; blocks X/Reddit), and POST /augment/search (Brave ZDR or anonymized Google; structured title/url/content/date results, up to 20 per query). Privacy (zero data retention), rate limits, and error shapes.
---

# Venice Augment (text parse / scrape / search)

Three lightweight helpers for agent pipelines that need document text, web pages, or search results without spinning up your own crawler.

| Endpoint | Input | Output | Privacy |
|---|---|---|---|
| `POST /augment/text-parser` | `multipart/form-data` file (PDF / DOCX / XLSX / plain text, ≤ 25 MB) | `{ text, tokens }` JSON or plain text | In-memory only, zero retention |
| `POST /augment/scrape` | `{ url }` | `{ url, content (markdown), format: "markdown" }` | Zero retention |
| `POST /augment/search` | `{ query, limit?, search_provider? }` | `{ query, results: [{ title, url, content, date }] }` | Brave ZDR / Google anonymized; zero retention |

All three accept **Bearer API key** or **SIWE** (x402 wallet). All three are priced dynamically (`$0.001–$10.00`).

## `POST /augment/text-parser` — extract text from documents

### Request

Always `multipart/form-data`:

| Field | Notes |
|---|---|
| `file` | Required. PDF, DOCX, XLSX, or plain text. Max **25 MB**. |
| `response_format` | `json` (default) or `text`. |

```bash
curl -X POST https://api.venice.ai/api/v1/augment/text-parser \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "file=@./contract.pdf" \
  -F "response_format=json"
```

### Response

`response_format=json`:

```json
{
  "text": "…extracted plaintext…",
  "tokens": 3821
}
```

`response_format=text` — raw plaintext body (`Content-Type: text/plain`).

### Tips

- `tokens` is the count of the extracted text — use it to pre-budget a downstream chat request.
- Scanned image PDFs are not OCR'd. Run images through a vision model via `/chat/completions` instead.
- Documents are processed **in memory only** and **content is not retained** after the response. (Operational metadata like request IDs and error traces may still be logged for debugging — this is a no-content-retention guarantee, not a zero-log guarantee.)

## `POST /augment/scrape` — URL → markdown

### Request

```json
{ "url": "https://example.com/article" }
```

```bash
curl -X POST https://api.venice.ai/api/v1/augment/scrape \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

### Response

```json
{
  "url": "https://example.com",
  "content": "# Example Domain\n\nThis domain is for use in …",
  "format": "markdown"
}
```

### Tips

- **Blocked sites** — X/Twitter and Reddit reject automated access and return `400` immediately. Use `enable_x_search` or `enable_web_search` on `/chat/completions` for those.
- Some sites may return a partial body. Verify with the returned `content` length before piping into a model.
- Use together with `/chat/completions`: scrape → feed markdown into messages → summarize.
- For bulk scraping, issue requests in parallel; each is billed independently.

## `POST /augment/search` — web search

### Request

| Field | Notes |
|---|---|
| `query` | 1–400 chars. Required. |
| `limit` | 1–20. Default `10`. |
| `search_provider` | `"brave"` (default, ZDR) or `"google"` (anonymized). |

```bash
curl -X POST https://api.venice.ai/api/v1/augment/search \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "venice ai api pricing",
    "limit": 5,
    "search_provider": "brave"
  }'
```

### Response

```json
{
  "query": "venice ai api pricing",
  "results": [
    {
      "title": "Pricing — Venice.ai",
      "url": "https://venice.ai/pricing",
      "content": "Venice offers per-token pricing …",
      "date": "2026-04-10"
    }
  ]
}
```

### Providers

| Provider | Retention | Bias / filter |
|---|---|---|
| `brave` (default) | Zero Data Retention — Brave never stores queries. | Safesearch defaults, Brave Index. |
| `google` | Anonymized — proxied through Venice so Google doesn't see you; Venice doesn't log queries. | Google ranking. |

### Tips

- Pair with `/chat/completions` + `venice_parameters.enable_web_citations` to generate cited answers. See [`venice-chat`](../venice-chat/SKILL.md).
- For "search + read" pipelines, feed `results[*].url` into `/augment/scrape` in parallel.
- `query` is validated as 1–400 chars. Anything longer is **rejected** (400 `INVALID_REQUEST`), not truncated.

## Errors

| Status | Cause |
|---|---|
| `400` | Missing/oversized file, unsupported format, URL on a blocklist (X, Reddit), empty query, query > 400 chars. |
| `401` | Missing/invalid Bearer or SIWE. |
| `402` | Insufficient balance. x402 wallets receive the `PAYMENT-REQUIRED` header with base64 top-up instructions; Bearer users get `INSUFFICIENT_BALANCE`. |
| `403` | Unauthorized access. |
| `429` | Rate limit tripped. Back off with jitter. |
| `500` | Upstream fetch / parse failure. Safe to retry. |

## Response headers

- `X-Balance-Remaining` — remaining x402 credit (x402 auth only).
- `Content-Encoding` — present when `Accept-Encoding: gzip, br` is sent (text-parser + scrape outputs compress well).

## Patterns

- **Document QA** — Upload PDF via `/augment/text-parser`, pass `text` into a `/chat/completions` system message, ask questions.
- **Research agent** — `/augment/search` → parallel `/augment/scrape` → `/chat/completions` with all markdown bodies.
- **Data extraction** — XLSX via text-parser surfaces tab-delimited cell data you can then pipe to a model with `response_format: { type: "json_schema", ... }`.
- **Citation pipeline** — Use `/augment/search` to pick sources, then give the chat model `venice_parameters.enable_web_citations: true` for inline `[n]` marks.

## Evidence-first research agent pattern

Use `/augment/search` + `/augment/scrape` when an agent needs to choose, inspect, and filter sources before synthesis. Use `venice_parameters.enable_web_search` when you want the model to manage retrieval itself. This pattern keeps evidence gathering separate from reasoning so the agent can preserve source URLs, discard weak pages, and return structured output.

| Need | Prefer |
|---|---|
| Agent chooses and filters sources | `/augment/search` + `/augment/scrape` |
| Model manages retrieval automatically | `venice_parameters.enable_web_search` |
| Inline cited prose | `enable_web_citations` on `/chat/completions` |
| Reliable downstream fields | `response_format: { type: "json_schema" }` |
| Wallet-funded agent | SIWE / x402 auth |

### Minimal loop

```ts
const base = 'https://api.venice.ai/api/v1'
const headers = {
  Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
  'Content-Type': 'application/json',
}

async function post(path: string, body: unknown) {
  const res = await fetch(`${base}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`)
  return res.json()
}

const search = await post('/augment/search', {
  query: 'is Venice x402 suitable for wallet-funded AI agents?',
  limit: 5,
  search_provider: 'brave',
})

const selected = search.results.slice(0, 3)
const scraped = await Promise.all(selected.map(async (result) => {
  try {
    const page = await post('/augment/scrape', { url: result.url })
    return { url: result.url, title: result.title, content: page.content }
  } catch (error) {
    return { url: result.url, title: result.title, error: 'scrape_failed' }
  }
}))

const sources = scraped
  .filter((source) => source.content)
  .map((source, index) =>
    `SOURCE ${index + 1}: ${source.title}\n${source.url}\n${source.content.slice(0, 4000)}`,
  )
  .join('\n\n---\n\n')

const brief = await post('/chat/completions', {
  model: 'zai-org-glm-5-1',
  response_format: {
    type: 'json_schema',
    json_schema: {
      name: 'evidence_brief',
      schema: {
        type: 'object',
        properties: {
          brief: { type: 'string' },
          evidence: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                claim: { type: 'string' },
                source_url: { type: 'string' },
                confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
              },
              required: ['claim', 'source_url', 'confidence'],
            },
          },
          open_questions: { type: 'array', items: { type: 'string' } },
          next_searches: { type: 'array', items: { type: 'string' } },
        },
        required: ['brief', 'evidence', 'open_questions', 'next_searches'],
      },
    },
  },
  messages: [
    {
      role: 'system',
      content: 'Answer only from the supplied sources. Mark uncertainty clearly.',
    },
    {
      role: 'user',
      content: `Create an evidence-backed brief from these sources:\n\n${sources}`,
    },
  ],
})
```

### Agent gotchas

- Search snippets are leads, not evidence. Scrape the page before making a factual claim.
- Keep `limit` small on the first search, then run follow-up searches from `open_questions` or `next_searches`.
- Do not scrape every result blindly; select by title, URL, snippet, source quality, and user intent.
- Failed scrapes are missing evidence, not negative evidence. Preserve failed URLs if the agent may need to retry.
- Trim or chunk long pages before synthesis to control context and cost.
- Use Brave for ZDR search by default; use Google when ranking quality matters more than provider diversity.
- For cited prose managed by the model, use `/chat/completions` with `venice_parameters.enable_web_search` and `enable_web_citations`. See [`venice-chat`](../venice-chat/SKILL.md).
- Wallet-funded agents can use SIWE / x402 auth instead of Bearer. See [`venice-x402`](../venice-x402/SKILL.md).
