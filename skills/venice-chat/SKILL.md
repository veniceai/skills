---
name: venice-chat
description: Call POST /chat/completions on Venice. Covers the OpenAI-compatible request shape, Venice-only venice_parameters (web search, E2EE, characters, thinking control, X search), multimodal inputs (images/audio/video), tool calls, reasoning controls, streaming, prompt caching, structured output, and model feature suffixes.
---

# Venice Chat Completions

`POST /api/v1/chat/completions` is Venice's main text endpoint. It's OpenAI-compatible, plus a `venice_parameters` object for Venice-only features.

## Use when

- You need LLM text generation, with or without tools, with or without streaming.
- You want multimodal inputs (images, audio, video) to a vision/audio-capable model.
- You want Venice-specific features: web search, E2EE, characters, xAI X/Twitter search, strip-thinking, web scraping.
- You need prompt caching for large system prompts or long documents.
- You need structured (`json_schema`) output.

For the newer Alpha **Responses API**, see [`venice-responses`](../venice-responses/SKILL.md).

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

Response shape is the standard OpenAI `chat.completion` object (`id`, `object: "chat.completion"`, `choices[].message`, `usage`). With `stream: true`, responses come as SSE `data:` lines in `chat.completion.chunk` format.

## The request body

### Core fields (OpenAI-compatible)

| Field | Notes |
|---|---|
| `model` | string — model ID, trait name, or compatibility mapping. Suffixes allowed (see below). Required. |
| `messages` | array of `system` / `developer` / `user` / `assistant` / `tool` messages. Required, min 1. |
| `temperature`, `top_p`, `top_k`, `min_p`, `min_temp`, `max_temp` | sampling controls |
| `repetition_penalty`, `frequency_penalty`, `presence_penalty` | repetition controls |
| `max_tokens` *(deprecated)* / `max_completion_tokens` | upper bound on output tokens |
| `n` | number of choices (keep `1` to minimize cost) |
| `seed` | integer for reproducibility |
| `stop` / `stop_token_ids` | up to 4 strings, or raw token IDs |
| `stream`, `stream_options.include_usage` | SSE streaming + include usage in the final chunk |
| `response_format` | `{type:"json_schema", json_schema:{...}}` (preferred), `{type:"json_object"}`, or `{type:"text"}` |
| `tools`, `tool_choice`, `parallel_tool_calls` | function calling / built-in tools |
| `logprobs`, `top_logprobs` | return token log-probabilities |
| `reasoning.effort` / `reasoning_effort` | `none` \| `minimal` \| `low` \| `medium` \| `high` \| `xhigh` \| `max` |
| `reasoning.summary` | `auto` \| `concise` \| `detailed` |
| `prompt_cache_key`, `prompt_cache_retention` (`default`/`extended`/`24h`) | prompt caching hints. `extended` and `24h` both extend retention to 24 hours on supported models |
| `verbosity`, `text.verbosity` | `low`/`medium`/`high`/`auto`. Also accepted as a root-level field, not only nested under `text` |
| `include` | array of extra fields to include in the response (OpenAI compat) |
| `fallbacks` | up to 10 entries. Anthropic beta parameter for Claude Fable 5 server-side refusal fallback. Forwarded only on direct Anthropic routes and ignored by every other provider |
| `metadata` | key/value strings for tracking |
| `user`, `store` | accepted but ignored (OpenAI compat) |

### `venice_parameters` (Venice-only)

All optional. Combined with model feature suffixes, these are how you enable Venice features.

| Field | Type | Default | Effect |
|---|---|---|---|
| `character_slug` | string | — | Apply a published Venice character. Slug is the "Public ID" on the character page. See [`venice-characters`](../venice-characters/SKILL.md). |
| `strip_thinking_response` | bool | `false` | Strip `<think>...</think>` from the assistant output on reasoning models. |
| `disable_thinking` | bool | `false` | Disable thinking entirely on supported reasoning models and strip tags. |
| `enable_e2ee` | bool | `true` | End-to-end encryption on E2EE-capable models when E2EE headers are present. Set to `false` to force TEE-only. |
| `enable_web_search` | `"off"`/`"auto"`/`"on"` | `"off"` | Venice server-side web search. Citations arrive in the first streamed chunk or the response. |
| `enable_web_scraping` | bool | `false` | Scrape any URLs found in the last user message (Firecrawl). |
| `enable_web_citations` | bool | `false` | Ask the LLM to cite sources with `^1^` / `^1,3^` superscripts. |
| `include_search_results_in_stream` | bool | `false` | Experimental — emit search results as the first stream chunk. |
| `return_search_results_as_documents` | bool | — | Also surface search results as a synthetic tool call `venice_web_search_documents` (LangChain-friendly). |
| `include_venice_system_prompt` | bool | `true` | Prepend Venice's curated system prompt. Turn off for full control. |
| `enable_x_search` | bool | `false` | xAI native web + X/Twitter search (Grok models with `supportsXSearch`). Adds ~$0.01/search. |

### Model feature suffixes

Some `venice_parameters` can also be expressed as **model feature suffixes** on the `model` string — useful when the caller/library (OpenAI SDK, LangChain) can't set `venice_parameters`. Syntax:

```
<model-id>:<key>=<value>[&<key>=<value>…]
```

Values are URL-decoded. Supported keys (exact match):

| Key | Type | Maps to |
|---|---|---|
| `enable_web_search` | `on` / `off` / `auto` | `venice_parameters.enable_web_search` |
| `enable_web_citations` | `"true"` / `"false"` | `venice_parameters.enable_web_citations` |
| `enable_web_scraping` | `"true"` / `"false"` | `venice_parameters.enable_web_scraping` |
| `include_venice_system_prompt` | `"true"` / `"false"` | `venice_parameters.include_venice_system_prompt` |
| `include_search_results_in_stream` | `"true"` / `"false"` | `venice_parameters.include_search_results_in_stream` |
| `return_search_results_as_documents` | `"true"` / `"false"` | `venice_parameters.return_search_results_as_documents` |
| `character_slug` | string | `venice_parameters.character_slug` |
| `strip_thinking_response` | `"true"` / `"false"` | `venice_parameters.strip_thinking_response` |
| `disable_thinking` | `"true"` / `"false"` | `venice_parameters.disable_thinking` |

Unknown keys are silently ignored. Examples:

```
zai-org-glm-5-1:enable_web_search=on
kimi-k2-6:strip_thinking_response=true&enable_web_search=auto
zai-org-glm-5-1:character_slug=alan-watts
```

Note: `enable_e2ee` and `enable_x_search` can **only** be set via `venice_parameters`, not as suffixes.

## Messages and modalities

`messages[].content` is either a string or an array of typed parts. Roles: `user`, `assistant`, `tool`, `system`, `developer` (reasoning models like o-series / codex).

### Text + image (`image_url`)

```json
{
  "model": "zai-org-glm-5-1",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "What's in this image?"},
      {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}}
    ]
  }]
}
```

- `url` accepts a public URL **or** `data:image/png;base64,...`.
- Models with `model_spec.capabilities.supportsMultipleImages: true` preserve images across the whole conversation; single-image vision models only keep images from the **last** user message. Check `model_spec.capabilities.maxImages` for the per-request cap.

### Audio input (`input_audio`)

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Transcribe this clip."},
    {"type": "input_audio", "input_audio": {"data": "<base64>", "format": "wav"}}
  ]
}
```

Formats: `wav`, `mp3`, `aiff`, `aac`, `ogg`, `flac`, `m4a`, `pcm16`, `pcm24`. Audio URLs are **not** supported — always inline base64.

### Video input (`video_url`)

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Summarize this."},
    {"type": "video_url", "video_url": {"url": "https://www.youtube.com/watch?v=..."}}
  ]
}
```

Accepts public URLs (including YouTube for some providers) or `data:video/mp4;base64,...`. Supported formats: `mp4`, `mpeg`, `mov`, `webm`. This is the replacement for sunset `POST /video/transcriptions` (always `410`) — pick a model where `GET /models` reports `model_spec.capabilities.supportsVideoInput: true`. See [`venice-video`](../venice-video/SKILL.md).

### Prompt caching (`cache_control`)

Any text / image_url / input_audio / video_url part can carry:

```json
{"cache_control": {"type": "ephemeral", "ttl": "1h"}}
```

Combine with `prompt_cache_key` and `prompt_cache_retention: "24h"` on the root request for predictable cache routing. Cache read / write pricing is model-specific — check `model_spec.pricing` on `/models`.

## Tools & function calling

### Function tools

```json
{
  "tools": [{
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "Get current weather for a city",
      "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
      },
      "strict": true
    }
  }],
  "tool_choice": "auto"
}
```

- `tool_choice` can also be `"required"`, `"none"`, or `{"type":"function","function":{"name":"get_weather"}}`.
- `parallel_tool_calls: true` (default) lets the model emit multiple calls at once.
- Respond by appending `{"role":"tool","tool_call_id":"...","content":"..."}` before the next call.

### Built-in tools

```json
"tools": [{"type": "web_search"}, {"type": "x_search"}]
```

Equivalent to toggling `venice_parameters.enable_web_search` / `enable_x_search`. `x_search` requires a model with `supportsXSearch`.

## Reasoning models

On thinking models (GLM 5.1, Kimi K2.6, Claude Opus 4.7, GPT-5.4 Pro, …):

```json
{
  "model": "zai-org-glm-5-1",
  "reasoning": {"effort": "medium", "summary": "auto"},
  "venice_parameters": {"strip_thinking_response": false},
  "messages": [...]
}
```

- `reasoning_effort` is the OpenAI-compatible flat variant (takes precedence over `reasoning.effort`).
- Reasoning models may return `reasoning_content` or structured `reasoning_details[]` on the assistant message. **Pass `reasoning_details` back verbatim** in the next turn — it encodes thought signatures for providers like Claude Opus 4.7 and GPT-5.4 Pro.
- Use `venice_parameters.disable_thinking: true` to skip thinking entirely on supported models.

## Structured output (`response_format`)

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "type": "object",
      "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
      "required": ["name", "age"]
    }
  }
}
```

Prefer `json_schema` over the legacy `json_object`. Plain text is the default (`{"type": "text"}`).

## E2EE (end-to-end encryption)

For models advertising `supportsE2EE`:

1. Perform an HPKE / Noise handshake with Venice (see docs.venice.ai/e2ee).
2. Send encrypted payload with the required E2EE request headers.
3. Leave `venice_parameters.enable_e2ee` at default `true`, or set `false` to fall back to TEE-only.

E2EE is **not** supported on `/responses` — use `/chat/completions` for encrypted inference.

## Streaming

```json
{"stream": true, "stream_options": {"include_usage": true}}
```

- Response is `text/event-stream`. Each event is `data: {...chunk...}\n\n`, terminated by `data: [DONE]`.
- `include_usage: true` adds a final chunk with token counts.
- With `venice_parameters.include_search_results_in_stream: true`, the **first** chunk carries `venice_search_results`.

## Web-search answers

When `enable_web_search` is `"auto"` or `"on"`, the response includes `venice_parameters.web_search_citations[]` where each entry has `url`, `title`, `content` (snippet), and `date`. Turn on `enable_web_citations` to have the model insert `^1^` superscripts inline.

## Error handling specifics

- `402` — insufficient balance. Bearer: `INSUFFICIENT_BALANCE`. x402: `PAYMENT_REQUIRED` with structured `topUpInstructions` and `siwxChallenge`.
- `422` — prompt violates Venice or provider content policy. May include `suggested_prompt`.
- `413` — payload too large (mostly vision/audio).
- `429` — rate limit. See `/api_keys/rate_limits` and [`venice-errors`](../venice-errors/SKILL.md).

## Common gotchas

- `max_tokens` is deprecated — prefer `max_completion_tokens`.
- Image URLs must be **publicly reachable** from Venice's network. Localhost / signed S3 URLs without public access fail.
- Audio inputs cannot be URLs — always base64.
- Single-image vision models drop older images on each turn; chain them into the **last** user message.
- For multi-turn with tools on Claude Opus 4.7, GPT-5.4 Pro, and similar, always round-trip `reasoning_details` unchanged.
- `parallel_tool_calls: true` means you MUST be prepared to execute several tools in parallel before sending a single `tool`-role reply chain.
- `character_slug` **replaces** the default Venice system prompt. Combine with `include_venice_system_prompt: false` for total control.
