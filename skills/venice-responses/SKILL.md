---
name: venice-responses
description: Use Venice's Alpha POST /responses endpoint - an OpenAI-compatible Responses API with typed output blocks (reasoning, message, function_call, web_search_call). Covers request shape, streaming, differences from /chat/completions, supported venice_parameters subset, and E2EE behavior.
---

# Venice Responses API (Alpha)

`POST /api/v1/responses` is Venice's OpenAI-compatible Responses endpoint. It returns a **structured, typed output array** instead of a single `message.content` string — ideal for agents that need to separate reasoning, messages, tool calls, and built-in tool events.

> **Alpha.** Access is gated behind the `responsesApiEnabled` flag on Bearer API keys (staff-only during beta). x402 wallet auth bypasses this flag — you can pay per request without the flag. Schemas may change.

## Use when

- You need the OpenAI Responses-style response shape (`output[]` with typed `type: "reasoning" | "message" | "function_call" | "web_search_call"` blocks) for a client library that expects it.
- You want clean separation of reasoning vs message vs tool-call output.
- You want streaming via SSE with typed events.

Otherwise use [`venice-chat`](../venice-chat/SKILL.md) — it has more features, more models, and full Venice parameters.

## Limitations vs `/chat/completions`

| Limitation | Detail |
|---|---|
| **Stateless** | No conversation persistence across requests. Send the full history each call. |
| **E2EE models default to rejection** | E2EE-capable models return `400` unless you pass `venice_parameters.enable_e2ee: false` (TEE-only mode). For end-to-end encrypted inference with E2EE headers, use `/chat/completions`. |
| **Subset of `venice_parameters`** | `character_slug`, `enable_e2ee`, `enable_web_search`, `enable_web_scraping`, `enable_web_citations`, `include_venice_system_prompt`, `include_search_results_in_stream` are supported. `strip_thinking_response`, `disable_thinking`, `enable_x_search` are **not** wired through in Alpha. Disable reasoning with `reasoning.enabled: false` instead. |
| **Access gated by feature flag** | Bearer keys without `responsesApiEnabled` get `401`. x402 requests are allowed (pay-per-call). |

## Authentication

Same as the rest of the API — either `Authorization: Bearer <key>` or `SIGN-IN-WITH-X: <SIWX>`. See [`venice-auth`](../venice-auth/SKILL.md).

## Minimal request

```bash
curl https://api.venice.ai/api/v1/responses \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "zai-org-glm-5-1",
    "input": "Explain why the sky is blue in one paragraph."
  }'
```

`input` accepts:
- a plain string, or
- an array of typed input items (similar to `chat/completions` message parts) for multi-turn or multimodal history. `input_image.image_url` accepts a URL string or `{url, detail}` (`auto` \| `low` \| `high`).

## Response shape

```json
{
  "id": "resp_abc123",
  "object": "response",
  "created_at": 1735689600,
  "model": "zai-org-glm-5-1",
  "status": "completed",
  "output": [
    {
      "type": "reasoning",
      "id": "rs_1",
      "summary": ["I considered Rayleigh scattering..."],
      "encrypted_content": "..."
    },
    {
      "type": "message",
      "id": "msg_1",
      "status": "completed",
      "role": "assistant",
      "content": [{
        "type": "output_text",
        "text": "The sky is blue because...",
        "annotations": [{
          "type": "url_citation",
          "url": "https://example.com/rayleigh",
          "title": "Rayleigh scattering",
          "start_index": 42,
          "end_index": 99
        }]
      }]
    },
    {
      "type": "function_call",
      "id": "fc_1",
      "call_id": "call_abc",
      "name": "get_weather",
      "arguments": "{\"city\":\"Paris\"}",
      "status": "completed"
    },
    {
      "type": "web_search_call",
      "id": "ws_1",
      "status": "completed"
    }
  ],
  "usage": {
    "input_tokens": 20,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens": 80,
    "output_tokens_details": {"reasoning_tokens": 40},
    "total_tokens": 100
  }
}
```

Top-level `status` ∈ `completed` \| `failed` \| `in_progress` \| `cancelled` \| `incomplete`. On `failed`, `error.code` and `error.message` are populated. On `incomplete`, `incomplete_details.reason` is `max_output_tokens` or `content_filter`; partial `output[]` and `usage` are retained — do not discard them.

## Output block types

| `type` | Purpose |
|---|---|
| `reasoning` | Thought process from reasoning models. `summary[]` holds human-readable text; `encrypted_content` holds opaque signatures — round-trip verbatim for multi-turn tool calls. |
| `message` | Main text output. `content[].type === "output_text"`, plus `annotations[]` for `url_citation` entries from web search. |
| `function_call` | Tool call: `name`, stringified-JSON `arguments`, `call_id`. |
| `web_search_call` | Sentinel showing the built-in web_search tool fired; use alongside `url_citation` annotations on messages. |

Match tool outputs back by `call_id` when continuing the turn.

## Common request fields

| Field | Notes |
|---|---|
| `model` | Required. Model ID, trait, or compatibility mapping. Feature suffixes allowed (see [`venice-chat`](../venice-chat/SKILL.md#model-feature-suffixes)). |
| `input` | Required. String or input-items array. To set system/developer context, include a leading message with `role: "system"`/`"developer"` in the input array. |
| `tools` | Array of `{type:"function",function:{...}}` or built-in `{type:"web_search"}` — availability depends on the model. |
| `tool_choice` | `"auto"` / `"required"` / `"none"` / `{type:"function",function:{"name":"..."}}`. |
| `reasoning.effort` | Reasoning effort hint for thinking models (`none` \| `minimal` \| `low` \| `medium` \| `high` \| `xhigh` \| `max`). Mapped to `reasoning_effort`. |
| `reasoning.enabled` | bool. Set `false` to disable reasoning on supported models. Ignored when an effort level is provided. This is the Alpha disable path; `venice_parameters.disable_thinking` is still not wired through. |
| `temperature`, `top_p`, `max_output_tokens` | Standard generation controls. `max_output_tokens` maps to `max_tokens`. |
| `web_search` | Boolean shortcut for enabling web search, equivalent to adding `{"type":"web_search"}` to `tools` or setting `venice_parameters.enable_web_search`. |
| `include` | Array of additional response fields to include (OpenAI compat). |
| `fallbacks` | Up to 10 entries. Anthropic beta parameter for Claude Fable 5 server-side refusal fallback; forwarded only on direct Anthropic routes. |
| `stream` | Boolean. SSE response with typed events (`response.created`, `response.output_item.added`, `response.output_text.delta`, `response.completed`, …). |
| `venice_parameters` | Subset listed above. Example: `{"character_slug":"alan-watts","enable_web_search":"on"}`. |

**Silently dropped generation controls.** `n`, `stop`, `seed`, and
`prompt_cache_key` are not in the Alpha schema and are not translated to
`/chat/completions`. The request body is permissive, so sending them does not
error — they just never reach inference. If you need reproducible sampling
(`seed`), stop sequences, or explicit cache routing, stay on
`/chat/completions`.

Fields commonly found in OpenAI's Responses API that are **not** in Venice's Alpha schema (and silently ignored or rejected by Zod): `instructions`, `metadata`, `parallel_tool_calls`, `response_format`, `store`, `previous_response_id`, `background`. For `response_format` / JSON-schema structured output, use `/chat/completions`.

## Streaming

With `stream: true`, the response is an SSE stream of typed events. Typical flow:

```
event: response.created
event: response.output_item.added        # type=reasoning
event: response.reasoning.delta
event: response.output_item.added        # type=message
event: response.content_part.added
event: response.output_text.delta
event: response.output_text.delta
event: response.output_item.done
event: response.completed
```

Consume events in order and reconstruct `output[]` client-side; the shape on `response.completed` matches the non-streamed response exactly.

## Authentication & error responses

- `400` — bad request; also returned when an E2EE-capable model is used without `venice_parameters.enable_e2ee: false`.
- `401` — auth failed, or Bearer key lacks `responsesApiEnabled`, or the model is Pro-only and you're on an INFERENCE key / x402 wallet.
- `402` — insufficient balance. Bearer → `{ error: "INSUFFICIENT_BALANCE" }`. x402 → `PAYMENT_REQUIRED` with `topUpInstructions` and `siwxChallenge` (see [`venice-x402`](../venice-x402/SKILL.md)).
- `429` — rate-limited.
- `500` — inference failed.

`X-Balance-Remaining` is on 200 responses when using x402 auth; `PAYMENT-REQUIRED` header on 402.

## Migration notes

- Port `messages` → pass as `input` (string, or typed array with leading `{role:"system"|"developer", content:"..."}`).
- `venice_parameters.character_slug` → **supported**; pass inside `venice_parameters` or as a model feature suffix (`:character_slug=alan-watts`).
- `venice_parameters.enable_web_search` → pass inside `venice_parameters`, or append `:enable_web_search=on` to the model ID, or add `{"type":"web_search"}` to `tools`.
- `venice_parameters.strip_thinking_response` / `disable_thinking` → **not supported on `/responses`** in Alpha. Use `reasoning.enabled: false` here, or stay on `/chat/completions` for the older `venice_parameters` path.
- Full E2EE flow (E2EE request headers + encrypted response) → stay on `/chat/completions`. For TEE-only inference on an E2EE-capable model, pass `venice_parameters.enable_e2ee: false` here.
- `response_format` / JSON-schema structured output → stay on `/chat/completions`.
