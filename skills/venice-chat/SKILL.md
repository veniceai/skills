---
name: venice-chat
description: Call POST /chat/completions on Venice. Covers the OpenAI-compatible request shape, Venice-only venice_parameters (web search, scraping, citations, E2EE, characters, thinking control, X search), anon_user_id, multimodal inputs (images/audio/video/files), tool calls, reasoning controls (reasoning_effort, reasoning.enabled), streaming, prompt caching, structured output, per-model caps, and model feature suffixes.
---

# Venice Chat Completions

`POST /api/v1/chat/completions` is Venice's main text endpoint. It's OpenAI-compatible, plus a `venice_parameters` object for Venice-only features. Auth is a Bearer API key or an x402 wallet (`SIGN-IN-WITH-X`); see [`venice-auth`](../venice-auth/SKILL.md).

## Use when

- You need LLM text generation, with or without tools, with or without streaming.
- You want multimodal inputs (images, audio, video, documents) to a capable model.
- You want Venice-specific features: web search, web scraping, citations, E2EE, characters, xAI X/Twitter search, thinking control.
- You need prompt caching for large system prompts or long documents.
- You need structured (`json_schema`) output.

For the OpenAI Responses-style shape (typed `output[]` blocks), see [`venice-responses`](../venice-responses/SKILL.md). To pick a model, see [`venice-text-routing`](../venice-text-routing/SKILL.md).

## Minimal request

```bash
curl https://api.venice.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "zai-org-glm-5-1",
    "messages": [{"role": "user", "content": "Why is the sky blue?"}]
  }'
```

OpenAI SDK (Python) — Venice-only fields go in `extra_body`:

```python
import os
from openai import OpenAI
client = OpenAI(api_key=os.environ["VENICE_API_KEY"], base_url="https://api.venice.ai/api/v1")
resp = client.chat.completions.create(
    model="zai-org-glm-5-1",
    messages=[{"role": "user", "content": "Summarize today's AI news."}],
    extra_body={"venice_parameters": {"enable_web_search": "auto", "include_venice_system_prompt": False}},
)
```

Response shape is the standard OpenAI `chat.completion` object (`id`, `object: "chat.completion"`, `created`, `model`, `choices[].message`, `choices[].finish_reason`, `usage`) plus:

- `cost: {usd, diem}` — the request's cost split by the currency it was charged in (bundled credits count as USD). `0` when the response has no output tokens (those responses are not billed). Omitted if the cost can't be computed, and currently also when the request was charged to earned credits.
- `venice_parameters` — the effective Venice settings, plus `web_search_citations[]` (an empty array when no search ran).
- `usage.prompt_tokens_details.{cached_tokens, cache_creation_input_tokens}` and `usage.completion_tokens_details.reasoning_tokens` when the provider reports them.

`choices[].finish_reason` is one of `stop`, `length`, `tool_calls`, or `content_filter`. `content_filter` is a `200` in which the model refused or the output was cut (e.g. a Claude refusal); it is not a `422`, so check for it before trusting `message.content`. Some providers block mid-stream instead; the stream then ends with an in-band error chunk (`type: "content_filter_error"`, `code: "content_blocked_by_provider"`) followed by `[DONE]`.

`system_fingerprint` is always stripped. With `stream: true`, responses come as SSE `data:` lines in `chat.completion.chunk` format.

## The request body

The top-level schema is **strict**: unknown top-level fields return `400`. (A few compatibility aliases are rewritten before validation: `input` → `messages`, `max_output_tokens` → `max_tokens`, `web_search: true|false` → `enable_web_search`, `promptCacheKey` → `prompt_cache_key`.)

### Core fields (OpenAI-compatible)

| Field | Notes |
|---|---|
| `model` | string — model ID, trait (e.g. `default`, `default_code`), or compatibility mapping. Required. Feature suffixes allowed (see below). Lookups also tolerate dots/underscores/spaces (`kimi k2.6` → `kimi-k2-6`) and a `venice-` prefix (for IDEs that hijack `claude-*` names). |
| `messages` | array of `system` / `developer` / `user` / `assistant` / `tool` messages. Required, min 1. Assistant messages with neither `content` nor `tool_calls` are silently dropped. |
| `temperature` (0–2), `top_p` (0–1), `top_k` (int ≥ 0), `min_p` (0–1), `min_temp`, `max_temp` (0–2) | sampling controls. Some models publish defaults in `model_spec.constraints` |
| `repetition_penalty` (≥ 0), `frequency_penalty`, `presence_penalty` (−2..2) | repetition controls |
| `max_completion_tokens` / `max_tokens` *(deprecated)* | integers. Output cap including reasoning tokens. Above the model's `model_spec.maxCompletionTokens` → `400` on models with an enforced API cap. `max_tokens ≤ 0` is ignored; `max_tokens` is ignored when `max_completion_tokens` is set |
| `n` | number of choices (default `1`; you pay for all choices) |
| `seed` | positive integer |
| `stop` / `stop_token_ids` | string or 1–4 strings / array of token IDs |
| `stream`, `stream_options.include_usage` | SSE streaming (Venice sends the usage chunk even without `include_usage` — see Streaming) |
| `response_format` | `{type:"json_schema", json_schema:{name, schema, strict}}` (preferred), `{type:"json_object"}`, or `{type:"text"}` |
| `tools`, `tool_choice`, `parallel_tool_calls` | function calling |
| `logprobs`, `top_logprobs` (int ≥ 0) | log-probabilities |
| `reasoning_effort` / `reasoning.effort` | `none` \| `minimal` \| `low` \| `medium` \| `high` \| `xhigh` \| `max`. `reasoning_effort` wins if both are set |
| `reasoning.enabled` | `false` disables reasoning on supported models. Ignored when an effort is set |
| `reasoning.summary` | `auto` \| `concise` \| `detailed` |
| `prompt_cache_key` | cache-routing hint. If omitted, Venice derives a stable key per API user |
| `prompt_cache_retention` | `default` \| `extended` \| `24h`. `extended` and `24h` extend retention to 24 hours on supported models |
| `verbosity` / `text.verbosity` | `low` \| `medium` \| `high` \| `auto` (both placements accepted). Non-reasoning OpenAI models accept only `medium` / `auto` (`400` otherwise) |
| `anon_user_id` | optional end-user identifier (see below) |
| `fallbacks` | up to 10 `{model}` entries. Anthropic beta parameter for Claude Fable 5 server-side refusal fallback. Forwarded only on direct Anthropic routes, ignored elsewhere |
| `include`, `metadata` | accepted for OpenAI compatibility, removed before validation and not forwarded |
| `user`, `store` | accepted and discarded (OpenAI compat). `user` is **not** an alias of `anon_user_id` |

**`anon_user_id`** — identifies *your* end user; Venice combines it with your Venice user id when attributing the request upstream. Trimmed (a blank value is treated as absent); 1–128 characters; printable ASCII only (`0x20`–`0x7E`); must not contain `||`. Violations → `400`. Also accepted on `/responses`.

### Capability gates (400 before inference)

| You send | Model must have (`model_spec.capabilities`) |
|---|---|
| `image_url` parts | `supportsVision` |
| `input_audio` parts | `supportsAudioInput` |
| `video_url` parts | `supportsVideoInput` |
| `tools`, `tool_choice`, `parallel_tool_calls: true` | `supportsFunctionCalling` |
| `response_format` other than `text` | `supportsResponseSchema` |
| `logprobs: true` or any `top_logprobs` | `supportsLogProbs` |

Each rejection is a `400` whose `issues[]` entry for that field gives the reason; read `issues`, not just the top-level `error`.

OpenAI reasoning models (e.g. `openai-gpt-52`) also reject `seed`, `stop`, `n ≠ 1`, and non-zero `presence_penalty` / `frequency_penalty` with `400` (the `issues[]` entry for that field reads `"<field> is not supported by this model"`).

### `venice_parameters` (Venice-only)

All optional. Unknown keys inside `venice_parameters` are dropped.

| Field | Type | Default | Effect |
|---|---|---|---|
| `character_slug` | string | — | Apply a published Venice character (the "Public ID" on its page). Unknown slug → `404`. See [`venice-characters`](../venice-characters/SKILL.md). |
| `strip_thinking_response` | bool | `false` | Strip reasoning from the response (`<think>` blocks and `reasoning_content`) on reasoning models. |
| `disable_thinking` | bool | `false` | Disable thinking on supported reasoning models and strip reasoning. On models that can't turn reasoning off, reasoning still runs (some drop to their lowest effort) but is stripped from the response; those reasoning tokens may still be billed. |
| `enable_e2ee` | bool | `true` | On E2EE-capable models, use E2EE when E2EE headers are present. `false` forces TEE-only mode. |
| `enable_web_search` | `"off"` / `"auto"` / `"on"` | `"off"` | Venice web search. `on` always searches; `auto` lets a classifier decide. |
| `enable_web_scraping` | bool | `false` | Scrape URLs found in the latest user message. When URLs are found, scraping replaces web search for that request. |
| `enable_web_citations` | bool | `false` | Ask the model to cite sources as `^1^` / `^1,3^`. |
| `include_search_results_in_stream` | bool | `false` | Experimental. Streaming only: emit a `choices: []` chunk carrying `venice_parameters.web_search_citations` at the end of the stream, before `data: [DONE]`. |
| `return_search_results_as_documents` | bool | — | Also surface search results as a synthetic tool call (see Web search). |
| `include_venice_system_prompt` | bool | `true` | Prepend Venice's system prompt to yours. Set `false` for full control. |
| `enable_x_search` | bool | `false` | xAI native web + X search on models with `supportsXSearch` (Grok). Ignored on other models. Billed per search (~$0.01). |

### Model feature suffixes

Some `venice_parameters` can be set on the `model` string — useful when the client (OpenAI SDK, LangChain, an IDE) can't send `venice_parameters`:

```
<model-id>:<key>=<value>[&<key>=<value>…]
```

Values are URL-decoded; booleans are `true` / `false`. Suffixes override the same keys in `venice_parameters`. Supported keys (exact match):

| Key | Values | Maps to |
|---|---|---|
| `enable_web_search` | `on` / `off` / `auto` | `venice_parameters.enable_web_search` |
| `enable_web_citations` | `true` / `false` | `venice_parameters.enable_web_citations` |
| `enable_web_scraping` | `true` / `false` | `venice_parameters.enable_web_scraping` |
| `include_venice_system_prompt` | `true` / `false` | `venice_parameters.include_venice_system_prompt` |
| `include_search_results_in_stream` | `true` / `false` | `venice_parameters.include_search_results_in_stream` |
| `return_search_results_as_documents` | `true` / `false` | `venice_parameters.return_search_results_as_documents` |
| `character_slug` | string | `venice_parameters.character_slug` |
| `strip_thinking_response` | `true` / `false` | `venice_parameters.strip_thinking_response` |
| `disable_thinking` | `true` / `false` | `venice_parameters.disable_thinking` |

Unknown keys are silently ignored. `enable_e2ee` and `enable_x_search` are **not** suffix keys. Suffixes only apply on `/chat/completions` — `/responses` resolves the model but ignores the suffix.

```
zai-org-glm-5-1:enable_web_search=on
kimi-k2-6:strip_thinking_response=true&enable_web_search=auto
zai-org-glm-5-1:character_slug=alan-watts
```

## Messages and modalities

`messages[].content` is a string or an array of typed parts. Roles: `user`, `assistant`, `tool`, `system`, `developer`. Only `user` messages may carry image / audio / video / file parts; `system` / `developer` / `assistant` array content is text-only. Anthropic-style `tool_use` / `tool_result` blocks and Cursor-style `{type:"image"}` parts are converted automatically.

Per-**message** caps: 10 `image_url`, 5 `input_audio`, 3 `video_url`, 5 `file` parts. Per-**request** cap: 3 `video_url` parts total.

### Images (`image_url`)

```json
{
  "model": "kimi-k2-6",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "What's in this image?"},
      {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}}
    ]
  }]
}
```

- `url` is a public `http(s)` URL or a `data:image/...;base64,...` URL (the `example.com` placeholder above fails validation — swap in a real image). Remote URLs are fetched once for validation: redirects are refused, the body must be ≤ 25 MB, the Content-Type must be PNG, JPEG, WebP, HEIF/HEIC, or AVIF, and the image must decode and be ≥ 64 px on each side (data URLs get the same decode + size check). Failures → `400` "Supplied image did not pass validation checks."
- Models with `supportsMultipleImages: true` keep images across the whole conversation (`maxImages` advertises the model's per-request limit; Venice itself enforces the 10-per-message cap). Single-image vision models keep images only from the **last** image-bearing message; earlier images are removed.

### Audio (`input_audio`)

```json
{"type": "input_audio", "input_audio": {"data": "<base64>", "format": "wav"}}
```

`format`: `wav` (default), `mp3`, `aiff`, `aac`, `ogg`, `flac`, `m4a`, `pcm16`, `pcm24`. Audio must be inline base64 — URLs are not supported.

### Video (`video_url`)

```json
{"type": "video_url", "video_url": {"url": "https://www.youtube.com/watch?v=..."}}
```

- YouTube watch/share/embed links are accepted without a pre-fetch (provider support varies).
- `data:video/...;base64,...` URLs must declare `video/mp4`, `video/mpeg`, `video/quicktime`, `video/mov`, or `video/webm`.
- Other remote URLs must return 2xx **without redirects** and one of those Content-Types. Failures → `400` "Supplied video did not pass validation checks."
- More than 3 `video_url` parts in a request → `400` (checked before any URL is fetched).

### Documents (`file`)

```json
{"type": "file", "file": {"file_data": "data:application/pdf;base64,JVBERi0...", "filename": "report.pdf"}}
```

`file_data` is a data URL or a public URL. PDF, EPUB, DOCX, PPTX, XLSX, XLS, plain text, Markdown, CSV, JSON, and most source-code files are extracted to text server-side (so any text model works); image files become `image_url` parts. A file that fails extraction becomes an inline `[Error processing file …]` text part rather than a request error. Not allowed on E2EE requests.

### Prompt caching (`cache_control`)

Any content part can carry `{"cache_control": {"type": "ephemeral"}}` or `{"type": "ephemeral", "ttl": "1h"}`. Explicit markers matter for models that require them (Claude); other models cache automatically on prefix matches. Those models allow at most 4 breakpoints per request; Venice adds its own to the system prompt and conversation history only while your markers leave slots free. Pair with a stable `prompt_cache_key` for consistent routing. Cache read / write prices are per model (`model_spec.pricing.cache_input` / `cache_write`); hits are reported in `usage.prompt_tokens_details`.

## Tools & function calling

```json
{
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Get current weather for a city",
      "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
      "strict": true
    }
  }],
  "tool_choice": "auto"
}
```

- `tool_choice`: `"auto"`, `"required"`, `"none"`, or `{"type":"function","function":{"name":"get_weather"}}`. `{"type":"auto" | "none" | "required"}` is normalized to the string form.
- `parallel_tool_calls` defaults to `true` — be ready to run several calls before replying.
- Reply with one `{"role":"tool","tool_call_id":"...","content":"..."}` message per call, then call again.
- Flat (`{type, name, parameters}`) and Anthropic (`{name, input_schema}`) tool definitions are converted to the nested format.
- When the message carries tool calls, Venice reports `finish_reason: "tool_calls"` rather than `stop` (a `length` cut-off stays `length`).
- The schema also accepts `{"type":"web_search"}` / `{"type":"x_search"}` tool entries, but they do **not** turn on Venice search or xAI X search. Use `venice_parameters.enable_web_search` / `enable_x_search` instead.

## Reasoning models

```json
{
  "model": "zai-org-glm-5-1",
  "reasoning": {"effort": "medium"},
  "messages": [{"role": "user", "content": "Prove there are infinitely many primes."}]
}
```

- Reasoning arrives in `message.reasoning_content` (`delta.reasoning_content` when streaming); `<think>` tags are removed from `content`. Some providers return encrypted or summarized reasoning.
- Supported effort values are per model: check `model_spec.capabilities.supportsReasoningEffort`, `reasoningEffortOptions`, and `defaultReasoningEffort`. On most Claude models and on OpenAI GPT models, a value outside `reasoningEffortOptions` → `400` (`none` is always accepted as a Venice-level off switch; on OpenAI models `minimal` is also accepted and maps to the lowest supported level). Other models are not pre-validated, so stick to `reasoningEffortOptions`.
- To turn thinking off, prefer `reasoning: {"enabled": false}` or `venice_parameters.disable_thinking: true` — both degrade gracefully on mandatory-reasoning models. `reasoning_effort: "none"` also disables thinking where the model allows it, but some mandatory-reasoning models reject it; prefer the two switches above.
- Some models return `reasoning_details[]` (and Gemini via native transport returns `thought_signature`) on the assistant message. **Pass them back verbatim** on the next turn, especially in tool loops, to preserve thought signatures.
- Reasoning tokens count toward `max_completion_tokens` and are billed as output.

## Structured output (`response_format`)

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "person",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
        "required": ["name", "age"],
        "additionalProperties": false
      }
    }
  }
}
```

Put the JSON Schema under `json_schema.schema` (OpenAI shape) — Claude, Gemini, and Grok models only read it from there. `json_object` is deprecated and ignored by Claude models. Requires `supportsResponseSchema`.

## E2EE (end-to-end encryption)

For models with `supportsE2EE: true` (the `e2ee-*` IDs), following the [TEE & E2EE guide](https://docs.venice.ai/guides/features/tee-e2ee-models):

1. `GET /api/v1/tee/attestation?model=<id>&nonce=<64 hex chars>` (no auth needed, 10 req/min/IP). Verify it and take the model's public key.
2. Generate a per-session secp256k1 key pair. Encrypt every `user` and `system` message with ECDH → HKDF-SHA256 → AES-256-GCM.
3. Send the request with `X-Venice-TEE-Client-Pub-Key` and `X-Venice-TEE-Model-Pub-Key` (secp256k1 hex keys), `X-Venice-TEE-Signing-Algo: ecdsa`, and `stream: true` (the guide requires streaming). Malformed headers → `400` with `{"error":{"message":"Invalid E2EE headers: …","type":"invalid_request_error"}}`.
4. Decrypt the streamed content with your private key.

On E2EE requests Venice injects nothing: no Venice system prompt, character, web search, or scraping. `file` parts → `400`. The guide also lists function calling as unsupported. Without E2EE headers (or with `enable_e2ee: false`) the same model runs in TEE-only mode. TEE responses carry `X-Venice-TEE: true` and `X-Venice-TEE-Provider`. E2EE is **not** available on `/responses`.

## Streaming

```json
{"stream": true}
```

- `text/event-stream`, one `data: {chat.completion.chunk}` per event, terminated by `data: [DONE]`.
- Venice requests usage from the model and emits it in a `choices: []` chunk with `usage` (and `cost`) before `[DONE]`, whatever `stream_options.include_usage` says. Usage is not repeated on content chunks.
- If the upstream fails after headers are sent, you get an in-band `data: {"error": {...}}` chunk (e.g. `code: "model_overloaded"` with `retry_after`, `upstream_error`, or `content_blocked_by_provider`) followed by `[DONE]`.
- Web-search citations are **not** in the stream unless `include_search_results_in_stream: true`, in which case a `choices: []` chunk with `venice_parameters.web_search_citations` arrives at the end of the stream, before `[DONE]`.
- With `return_search_results_as_documents: true`, the synthetic `web_search_call` tool call (see Web search) is streamed as a `delta.tool_calls` chunk before the content.

## Web search

- Non-streaming responses include `venice_parameters.web_search_citations[]` with `url`, `title`, `content` (snippet), and `date`. Add `enable_web_citations: true` to get `^n^` markers in the text.
- Search is skipped on E2EE requests, when the last user message contains an image, and when scraping found URLs in that message.
- `return_search_results_as_documents: true` adds a synthetic tool call `{id:"web_search_call", type:"function", function:{name:"web_search", arguments:"{\"documents\":[{id,title,url,snippet,published_at}]}"}}` and sets `finish_reason: "tool_calls"`. Don't try to execute it.
- Billing: $0.01 per search-augmented request, $0.01 per scraped URL, $0.01 per xAI X search.

## Error handling specifics

| Status | When |
|---|---|
| `400` | Invalid body (`error: "Invalid request parameters"`, per-field reasons in `issues[]`), capability rejections, invalid image/video, too many parts, context length exceeded, token cap exceeded, bad E2EE headers |
| `401` | Invalid API key or SIWX sign-in; also a model that requires a paid subscription |
| `402` | No credentials at all (x402 discovery body — not `401`), insufficient balance, or API-key spend limit. x402 insufficient balance: `code: "PAYMENT_REQUIRED"` body with `topUpInstructions` + `siwxChallenge`, and a `PAYMENT-REQUIRED` header ([`venice-x402`](../venice-x402/SKILL.md)) |
| `403` | Model not allowed by the API key's `modelPrivacy`, region-restricted model, or provider restriction |
| `404` | Unknown model (often with a "Did you mean" hint) or `character_slug` |
| `413` | Payload too large |
| `422` | Content-policy violation (Venice or provider) |
| `429` | Rate limit exceeded (`"Rate limit exceeded"` or the error-budget message), or model overloaded (`"The model is currently overloaded…"` with a `Retry-After` header). Both carry `x-ratelimit-*` headers, so tell them apart by `Retry-After` and the message |
| `500` / `503` / `504` | Inference failed / model offline / upstream timeout |

See [`venice-errors`](../venice-errors/SKILL.md) for shapes and retry strategy.

## Common gotchas

- `max_tokens` is deprecated — use `max_completion_tokens`, and stay under `model_spec.maxCompletionTokens`.
- Unknown top-level fields are rejected (`400`); unknown `venice_parameters` keys are silently dropped.
- Image and video URLs must be publicly reachable **without redirects**. Signed S3 URLs that redirect or localhost URLs fail.
- Audio cannot be a URL — always base64.
- Single-image vision models drop older images each turn; put images in the **last** user message.
- Round-trip `reasoning_details` / `thought_signature` unchanged in multi-turn tool loops.
- `character_slug` adds the character's system prompt ahead of yours. Venice's own prompt is still included unless the character uses a custom system prompt or you set `include_venice_system_prompt: false`.
- `web_search` / `x_search` tool entries are not Venice search — use `venice_parameters`.
- OpenAI reasoning models reject `seed`, `stop`, `n > 1`, and non-zero penalties.
