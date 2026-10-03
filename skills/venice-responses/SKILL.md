---
name: venice-responses
description: Use Venice's Alpha POST /responses endpoint - an OpenAI-compatible, stateless Responses API with typed output blocks (reasoning, message, function_call, web_search_call). Covers request shape, input items, tools (function, web_search, x_search), reasoning controls, incomplete responses, streaming events, differences from /chat/completions, the supported venice_parameters subset, and E2EE behavior.
---

# Venice Responses API (Alpha)

`POST /api/v1/responses` is Venice's OpenAI-compatible Responses endpoint. It returns a **typed output array** instead of a single `message.content` string — useful for agents that need to separate reasoning, messages, tool calls, and web-search events. Internally the request is translated to a chat completion, so model support matches [`venice-chat`](../venice-chat/SKILL.md).

> **Alpha.** The spec labels it Alpha (and its description still says "Alpha testers only"), but access is no longer restricted: any Bearer API key or x402 wallet can call it. Schemas may still change.

## Use when

- A client library expects the OpenAI Responses shape (`output[]` with `type: "reasoning" | "message" | "function_call" | "web_search_call"`).
- You want reasoning, message, and tool-call output cleanly separated.
- You want SSE streaming with typed events.

Otherwise use [`venice-chat`](../venice-chat/SKILL.md) — it has structured output, audio/video/file inputs, E2EE, sampling controls, and every `venice_parameters` field.

## Limitations vs `/chat/completions`

| Limitation | Detail |
|---|---|
| **Stateless** | Nothing is stored. Send the full history each call. `previous_response_id`, `store`, `background` are ignored. |
| **No E2EE** | E2EE-capable models return `400` unless `venice_parameters.enable_e2ee: false` (TEE-only mode). For encrypted inference use `/chat/completions`. |
| **Text + image input only** | `input_text` / `input_image` (and `text` / `image_url` parts). No audio, video, or file parts. |
| **No structured output** | `text.format` / `response_format` are dropped. Use `/chat/completions`. |
| **Subset of `venice_parameters`** | `character_slug`, `enable_e2ee`, `enable_web_search`, `enable_web_scraping`, `enable_web_citations`, `include_venice_system_prompt`, `include_search_results_in_stream`. Other keys (`strip_thinking_response`, `disable_thinking`, `enable_x_search`, `return_search_results_as_documents`) are silently dropped. |
| **No model feature suffixes** | `model: "zai-org-glm-5-1:enable_web_search=on"` resolves the model but ignores the suffix. |
| **Few generation controls** | Only `temperature`, `top_p`, `max_output_tokens`. |

## Authentication

Same as the rest of the API — `Authorization: Bearer <key>` or `SIGN-IN-WITH-X: <SIWX>` for x402 wallets. See [`venice-auth`](../venice-auth/SKILL.md).

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

OpenAI SDK (Python):

```python
import os
from openai import OpenAI
client = OpenAI(api_key=os.environ["VENICE_API_KEY"], base_url="https://api.venice.ai/api/v1")
resp = client.responses.create(model="zai-org-glm-5-1", input="Explain why the sky is blue.")
print(resp.output_text)
```

## Request fields

| Field | Notes |
|---|---|
| `model` | Required. Model ID, trait, or compatibility mapping. |
| `input` | Required. A string, or an array of input items (below). |
| `max_output_tokens` | Positive integer. Mapped to `max_tokens`; above the model's `model_spec.maxCompletionTokens` → `400` on models with an enforced cap. |
| `temperature` (0–2), `top_p` (0–1) | Sampling. |
| `reasoning.effort` | `none` \| `minimal` \| `low` \| `medium` \| `high` \| `xhigh` \| `max` (per-model support: `model_spec.capabilities.reasoningEffortOptions`). `reasoning` may be `null`. |
| `reasoning.enabled` | `false` disables reasoning on supported models and suppresses reasoning blocks. Ignored when an effort is set. |
| `reasoning.summary` | `auto` \| `concise` \| `detailed`. Accepted but not forwarded. |
| `tools` | See Tools. |
| `tool_choice` | `"auto"` \| `"none"` \| `"required"` \| `{"type":"function","function":{"name":"..."}}`. Dropped when no function tools remain. |
| `web_search` | Boolean. `true` forces web search on (same as a `{"type":"web_search"}` tool). |
| `include` | Only `"reasoning.encrypted_content"` has an effect (adds `encrypted_content` to reasoning blocks when the provider returns it). |
| `stream` | Boolean. SSE with typed events. |
| `anon_user_id` | Optional end-user id: 1–128 printable ASCII characters, no `||`. Distinct from `user`. |
| `fallbacks` | Up to 10 `{model}` entries. Anthropic beta refusal fallback for Claude Fable 5; forwarded only on direct Anthropic routes. |
| `venice_parameters` | Subset listed above. Example: `{"character_slug":"alan-watts","enable_web_search":"auto"}`. |

The body is permissive: other fields (`instructions`, `metadata`, `parallel_tool_calls`, `n`, `stop`, `seed`, `prompt_cache_key`, `store`, `previous_response_id`, `background`, `text`, `user`) are accepted without error but **never reach inference** (`user` still splits the error budget per value). Put system instructions in the `input` array instead of `instructions`.

### Input items

| Item | Shape | Handling |
|---|---|---|
| Message | `{role, content}` or `{type:"message", role, content}` | `role`: `user` / `assistant` / `system` / `developer` (`developer` becomes `system`). `content` is a string or an array of parts. |
| Function call | `{type:"function_call", call_id, name, arguments}` | Replayed as an assistant tool call. |
| Function output | `{type:"function_call_output", call_id, output}` | `output` may be a string, array, object, number, boolean, or null. `input_image` parts inside an array output are forwarded to the model as images. |
| Reasoning | `{type:"reasoning", ...}` | Accepted but **discarded** — reasoning is not carried between turns. |
| Item reference | `{type:"item_reference", id}` | Accepted but discarded (nothing is stored to reference). |

Content parts: `input_text`, `output_text` (to replay assistant output), and `input_image`. `input_image.image_url` may be a URL **string** (OpenAI Responses style) or `{url, detail}`; `detail` (`auto` / `low` / `high`) may also sit on the part. Messages without `type` additionally accept Chat-style `text` and `image_url` parts. Image URLs get the same validation as on `/chat/completions` (public, no redirects, ≥ 64 px); failures → `400`. Use a vision model: message images are not capability-checked on this endpoint (images inside a `function_call_output` on a non-vision model do return `400`).

### Tools

| Tool | Effect |
|---|---|
| `{"type":"function","function":{name, description, parameters, strict}}` | Function calling. The flat OpenAI form `{"type":"function","name":...,"parameters":...}` is also accepted. Use a model with `supportsFunctionCalling` (not pre-checked on this endpoint, unlike chat). |
| `{"type":"web_search"}` | Forces Venice web search **on** (not `auto`). `search_context_size` / `user_location` are accepted but ignored. |
| `{"type":"x_search", ...}` | xAI native web + X search on models with `supportsXSearch` (Grok); ignored on other models. Optional filters: `allowed_x_handles` / `excluded_x_handles` (≤ 10 each), `from_date`, `to_date`, `enable_image_understanding`, `enable_video_understanding`. |
| `code_interpreter`, `file_search`, `computer_use_preview`, others | Accepted and dropped. Unknown tool types that carry a `name` are treated as function tools. |

## Response shape

```json
{
  "id": "resp_chatcmpl-abc123",
  "object": "response",
  "created_at": 1735689600,
  "model": "zai-org-glm-5-1",
  "status": "completed",
  "output": [
    {"type": "reasoning", "id": "rs_1", "summary": ["I considered Rayleigh scattering..."]},
    {"type": "web_search_call", "id": "ws_1", "status": "completed"},
    {"type": "function_call", "id": "fc_1", "call_id": "call_abc", "name": "get_weather",
     "arguments": "{\"city\":\"Paris\"}", "status": "completed"},
    {"type": "message", "id": "msg_1", "status": "completed", "role": "assistant",
     "content": [{"type": "output_text", "text": "The sky is blue because... ^1^",
       "annotations": [{"type": "url_citation", "url": "https://example.com/rayleigh",
         "title": "Rayleigh scattering", "start_index": 27, "end_index": 30}]}]}
  ],
  "usage": {
    "input_tokens": 20,
    "input_tokens_details": {"cached_tokens": 8},
    "output_tokens": 80,
    "output_tokens_details": {"reasoning_tokens": 40},
    "total_tokens": 100
  }
}
```

- Non-streamed `output` order: `reasoning` → `web_search_call` → `function_call`(s) → `message`. The `message` block is omitted when the model returned only tool calls with no text.
- `status` is `completed` or `incomplete`. Errors before or during inference come back as HTTP errors (streaming uses `response.failed`).
- **Incomplete responses keep their output and usage.** When generation stops on `max_output_tokens` or a content filter, `status: "incomplete"`, `incomplete_details: {"reason": "max_output_tokens" | "content_filter"}`, and message / function_call blocks carry `status: "incomplete"`.
- `input_tokens_details` appears only when cached tokens are non-zero; `output_tokens_details` only when the provider reports reasoning tokens. There is no `cost` field (unlike `/chat/completions`).

## Output block types

| `type` | Purpose |
|---|---|
| `reasoning` | Reasoning from thinking models. `summary[]` holds text; `encrypted_content` appears only if you sent `include: ["reasoning.encrypted_content"]` and the provider returned encrypted reasoning. Sending it back in `input` has no effect. |
| `message` | Main text. `content[].type === "output_text"` with `annotations[]`. |
| `function_call` | Tool call: `name`, JSON-string `arguments`, `call_id`. Answer with a `function_call_output` item with the same `call_id`. |
| `web_search_call` | Marker that Venice web search ran. |

`url_citation` annotations are built only when the text contains single-index `^n^` markers — set `venice_parameters.enable_web_citations: true` to get them. Each annotation spans the marker itself; multi-index markers such as `^1,3^` are not annotated.

## Streaming

With `stream: true`, events are `event: <type>` + `data: {...}` pairs; payloads carry `type` (equal to the event name) and an increasing `sequence_number` — except `response.web_search.done`, whose payload has `type: "web_search_call"`, `id`, `status`, `results` and no `sequence_number`. Typical flow:

```
event: response.created                      # status: in_progress
event: response.web_search.done              # Venice-specific; only when search ran, carries results[{index,url,title,snippet}]
event: response.output_item.added            # item.type = reasoning
event: response.reasoning.delta
event: response.output_item.added            # item.type = message
event: response.content_part.added
event: response.output_text.delta            # repeated
event: response.output_item.added            # item.type = function_call
event: response.function_call_arguments.delta
event: response.output_item.done             # reasoning, then message (after content_part.done), then each function_call
event: response.completed                    # or response.incomplete, with the full response
data: [DONE]
```

- On an upstream failure you get `response.failed` (`response.status: "failed"`, `response.error: {code, message}`) followed by `data: [DONE]`.
- The final `response.completed` / `response.incomplete` payload differs slightly from a non-streamed response: `annotations` are always empty and function calls come after the message.
- `include_search_results_in_stream` has no effect here; search results always arrive in `response.web_search.done`.

## Errors

| Status | When |
|---|---|
| `400` | Invalid body, E2EE-capable model without `enable_e2ee: false`, invalid image, unsupported `reasoning.effort` for the model, context too long, `max_output_tokens` over the cap |
| `401` | Invalid API key or SIWX sign-in; also a model that requires a paid subscription |
| `402` | No credentials at all (x402 discovery body — not `401`), insufficient balance, or API-key spend limit. x402: `PAYMENT_REQUIRED` body with `topUpInstructions` + `siwxChallenge` and a `PAYMENT-REQUIRED` header (see [`venice-x402`](../venice-x402/SKILL.md)) |
| `403` | Model blocked by the key's `modelPrivacy`, region, or provider restriction |
| `404` | Unknown model |
| `422` | Content-policy violation on an input image |
| `429` | Rate limited |
| `500` / `503` | Inference failed (upstream overloads and timeouts also surface as `500` here, not `429` / `504`; retry with backoff) / model offline |

The spec lists an `X-Balance-Remaining` header on x402 `200` responses, but the server does not currently set it — poll `GET /x402/balance/{walletAddress}` instead. See [`venice-errors`](../venice-errors/SKILL.md).

## Migration notes (from `/chat/completions`)

- `messages` → `input` (the same role/content objects work; system prompts go in as `role: "system"` or `"developer"` items).
- `max_tokens` → `max_output_tokens`; `reasoning_effort` → `reasoning.effort`.
- Tool results → `function_call_output` items keyed by `call_id`.
- `venice_parameters.character_slug`, `enable_web_search`, `enable_web_citations`, `enable_web_scraping`, `include_venice_system_prompt` → pass inside `venice_parameters` (not as model suffixes).
- `enable_x_search` → add an `{"type":"x_search"}` tool instead.
- `strip_thinking_response` / `disable_thinking` → use `reasoning.enabled: false`.
- Structured output, audio / video / file inputs, `seed` / `stop` / `n`, logprobs, prompt-cache routing, and full E2EE → stay on `/chat/completions`.

## Gotchas

- Unknown `character_slug` is **not** rejected here (chat returns `404`). The request runs without the character, without your `system` messages, and without the Venice system prompt or web search. Validate slugs first with `GET /characters/{slug}` ([`venice-characters`](../venice-characters/SKILL.md); Bearer key only — wallet callers can't, and should use `/chat/completions`, which returns `404` for unknown slugs).
- Reasoning items in `input` are discarded; there is no cross-turn reasoning carry-over on this endpoint.
- `tool_choice` objects must be `{"type":"function","function":{"name":...}}`; the flat `{"type":"function","name":...}` form fails validation.
- Stateless: `previous_response_id` is silently ignored, so omitting history silently loses context.
