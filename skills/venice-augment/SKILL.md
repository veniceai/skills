---
name: venice-augment
description: Venice augmentation endpoints for agent pipelines. Covers POST /augment/text-parser (extract text from PDF/EPUB/DOCX/PPTX/XLSX/XLS, plain text and source code; multipart, up to 25MB; JSON or plain-text response), POST /augment/scrape (fetch a URL and return markdown; blocks X/Reddit and private/internal URLs), and POST /augment/search (Brave ZDR or anonymized Google; structured title/url/content/date results, limit up to 20 but effectively capped at 10 Brave / 5 Google). $0.01 per successful call, 20 req/min on scrape and search, privacy, and error shapes.
---

# Venice Augment (text parse / scrape / search)

Three lightweight helpers for agent pipelines that need document text, web pages, or search results without running your own parser, crawler, or search account. All three are marked **experimental** in the docs — request/response shapes may change.

| Endpoint | Input | Output | Price |
|---|---|---|---|
| `POST /augment/text-parser` | `multipart/form-data` `file` (≤ 25 MB) | `{ text, tokens }` JSON, or `text/plain` | $0.01 / successful call |
| `POST /augment/scrape` | `{ url }` | `{ url, content, format: "markdown" }` | $0.01 / successful call |
| `POST /augment/search` | `{ query, limit?, search_provider? }` | `{ query, results: [{ title, url, content, date }] }` | $0.01 / successful call |

All three accept a **Bearer API key** or an **x402 wallet** (`SIGN-IN-WITH-X` header) — see [`venice-auth`](../venice-auth/SKILL.md). The balance is checked before the work runs; the charge is applied only after a `200` response. (The OpenAPI `x-payment-info` advertises a generic dynamic range of `$0.001–$10.00`; the actual price sheet charge is $0.01.)

## `POST /augment/text-parser` — extract text from documents

### Request

Always `multipart/form-data`:

| Field | Notes |
|---|---|
| `file` | Required. Max **25 MB** (larger → `413`). |
| `response_format` | `json` (default) or `text`. |

Accepted file types (matched by MIME type, or by filename extension when the MIME type isn't recognized, e.g. `application/octet-stream`):

- **Structured documents:** PDF, EPUB, DOCX, PPTX, XLSX, XLS. Legacy `.doc` and `.ppt` are **not** accepted.
- **Text / data:** any `text/*` MIME, plus Markdown, CSV/TSV, JSON/JSONL, YAML, TOML, XML, HTML, RTF, LaTeX, logs, etc.
- **Source code:** `.py`, `.ts`, `.js`, `.go`, `.rs`, `.c`, `.cpp`, `.java`, `.sh`, `.ps1`, `.sql`, … plus extensionless `Dockerfile` / `Makefile` (~140 text/data/code extensions are recognized in total).

Anything else → `400 Unsupported file type`.

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
  "text": "…extracted text…",
  "tokens": 3821
}
```

`response_format=text` — the raw extracted text as the body (`Content-Type: text/plain`).

### Tips

- DOCX, PPTX, XLSX/XLS and EPUB come back as **markdown** (spreadsheets as markdown tables). PDFs and text files come back as plain text.
- `tokens` is a character-based estimate (`ceil(chars / 3.2)`), not a model tokenizer count — use it for rough budgeting of a downstream chat request.
- Scanned/image-only PDFs are not OCR'd; if nothing can be extracted you get `400 "No text content could be extracted from the file."` Run page images through a vision model via `/chat/completions` instead.
- Password-protected PDFs → `400 "The PDF file is password-protected…"`; empty/corrupt PDFs → `400 "The PDF file is empty or invalid."`
- Documents are processed **in memory** and content is not retained after the response. (Operational metadata such as request IDs and error traces may still be logged — this is a no-content-retention guarantee, not a zero-log guarantee.)

## `POST /augment/scrape` — URL → markdown

### Request

```json
{ "url": "https://example.com/article" }
```

`url` must be a valid absolute `http://` or `https://` URL.

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

### How it fetches

Sites that serve markdown directly are returned as-is; otherwise the page is fetched and converted to markdown. Redirects are followed, but a redirect to a private/internal target fails the request (see below). The X/Reddit blocklist is checked against the URL you send, not against redirect targets.

### Tips

- **Blocked sites** — `x.com`, `twitter.com` (incl. `www.` / `mobile.`) and `reddit.com` (incl. `www.` / `old.` / `new.`) are rejected immediately with `400`. Use `enable_x_search` or `enable_web_search` on `/chat/completions` for those — see [`venice-chat`](../venice-chat/SKILL.md).
- **Blocked URLs** — non-HTTP(S) schemes, URLs with embedded credentials, `localhost` / private / reserved IPs and cloud-metadata hosts return `400`. A public hostname that resolves or redirects to such a target fails with `500`.
- Unreachable hosts, timeouts and pages with no extractable content return `500` with a message (e.g. `"URL unreachable: …"`). You are not charged.
- Some sites return a partial body. Check `content` length before piping it into a model.
- Rate limit: **20 requests/minute per user** (`429` beyond that). The counter runs before URL validation, so rejected URLs also count.

## `POST /augment/search` — web search

### Request

| Field | Notes |
|---|---|
| `query` | Required. 1–400 chars. Longer is **rejected** (`400`), not truncated. |
| `limit` | Integer 1–20. Default `10`. See the cap below. |
| `search_provider` | `"brave"` (default) or `"google"`. |

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

- `date` is whatever the provider reports and may be an **empty string**; don't assume a fixed format.
- Results without a snippet are dropped, so you can get fewer than `limit`. A search with no hits returns `200` with `results: []` (still charged).

### Providers

| Provider | Retention | Results | `content` |
|---|---|---|---|
| `brave` (default) | Zero Data Retention — queries are not stored or logged by the provider. | **At most 10** | Snippet plus any extra snippets. |
| `google` | Anonymized — proxied through Venice so your identity isn't attached to the query; Venice doesn't store or log queries. | **At most 5** | Extracted page summary/markdown (longer), truncated to a budget. |

`limit` accepts up to 20, but the upstream request is fixed at 10 results for `brave` and 5 for `google`, so values above those caps have no effect.

### Tips

- For cited answers inside a chat completion, use `/chat/completions` with `venice_parameters.enable_web_search` + `enable_web_citations` instead. See [`venice-chat`](../venice-chat/SKILL.md).
- For "search + read" pipelines, feed `results[*].url` into `/augment/scrape` — mind the 20/min scrape limit.
- Rate limit: **20 requests/minute per user** (`429` beyond that). Requests that fail body validation still count.

## Errors

| Status | Cause |
|---|---|
| `400` | Missing file, unsupported file type, no extractable text, password-protected/invalid PDF; invalid/blocked URL (X, Reddit, private/internal); empty or > 400-char query; `limit` out of range; non-JSON `Content-Type` on scrape/search (`"'Content-Type' must be 'application/json'"`). Body: `{ error }`, or `{ error: "Invalid request parameters", details, issues }` on schema failures. |
| `401` | Invalid API key or SIWX signature. |
| `402` | Insufficient balance or the key's USD/DIEM spend limit reached. Bearer → `"Insufficient USD or Diem balance…"`; x402 → payment-required body + `PAYMENT-REQUIRED` header. Requests with no credentials at all also get `402` (x402 discovery challenge). |
| `403` | API access disabled for the account (`"API access has been disabled for this account…"`). |
| `413` | Text-parser file over 25 MB (`PAYLOAD_TOO_LARGE`). |
| `429` | Per-endpoint rate limit (scrape/search: 20/min) or the failed-request limiter. Back off with jitter. |
| `500` | Scrape fetch failure, search provider failure (`"Search provider failed to return results…"`), or parse failure (`"Failed to parse document"`). Not charged; safe to retry. |

See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Response headers

- `X-Balance-Remaining` — listed in the spec for x402 callers but not currently set by the server; poll `GET /x402/balance/{walletAddress}` instead.
- `x-ratelimit-limit-requests` / `x-ratelimit-remaining-requests` / `x-ratelimit-reset-requests` — scrape and search.
- `Content-Encoding` — when you send `Accept-Encoding: gzip, br`.

## Patterns

- **Document QA** — upload a PDF to `/augment/text-parser`, put `text` into a `/chat/completions` message, ask questions.
- **Research agent** — `/augment/search` → `/augment/scrape` on the top URLs → `/chat/completions` with the markdown bodies.
- **Data extraction** — XLSX via text-parser yields markdown tables you can pipe to a model with `response_format: { type: "json_schema", ... }`.
- **Code review** — send source files directly to text-parser (no need to convert to PDF) and feed the text to a coding model.

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
