---
name: venice-models
description: Discover Venice models, their capabilities, constraints, and pricing. Covers GET /models (with the ?type filter - text, image, video, music, tts, asr, embedding, upscale, inpaint, decision, all, code), /models/traits, /models/compatibility_mapping, every ModelResponse field (capabilities, constraints, per-type pricing with promotional rates, uncensored, deprecation, voice-changer and voice-cloning specs), and how to use this to pick the right model programmatically.
---

# Venice Models

Three read-only endpoints for model discovery - all `GET`, all public:

| Endpoint | Returns |
|---|---|
| `/models` | Model catalog with `model_spec` (capabilities, constraints, pricing). |
| `/models/traits` | Trait → model ID map (e.g. `default`, `default_reasoning`, `highest_quality`). |
| `/models/compatibility_mapping` | Legacy / third-party model ID → Venice model ID aliases. |

**Auth is optional.** These routes need no API key, so a plain `curl` works. If you send `Authorization: Bearer $VENICE_API_KEY` the result is tailored to that caller: a key's `modelPrivacy` setting filters the list, beta-flagged accounts also see beta models, and partner accounts see their negotiated rates. An invalid key is not rejected - you just get the public view.

**`?type=` values** (default `text` when omitted):

| Value | `/models` | `/models/traits` | `/models/compatibility_mapping` |
|---|---|---|---|
| `text`, `image`, `video`, `music`, `tts`, `asr`, `embedding`, `upscale`, `inpaint`, `decision` | yes | yes | yes |
| `all` (every type) | yes | yes | `400` |
| `code` (text models with `capabilities.optimizedForCode: true`) | yes | yes | `400` |

Anything else returns `400 { "error": "Invalid request parameters", "details": …, "issues": … }`.

`music` includes long-form audio (songs, sound effects, ElevenLabs narration models) and any voice-changer models. `decision` lists the typed-judgment models used by `POST /decisions` (today: `jev-latest`, flagged `betaModel: true`) - see [`venice-decisions`](../venice-decisions/SKILL.md).

## Use when

- You need to pick a model at runtime based on capabilities (vision, reasoning, function calling, E2EE, X search, multi-image, …).
- You need to validate a request against a model's `constraints` (prompt length, aspect ratio, resolution, steps, durations).
- You need the current **price per million tokens / per image / per second / per million characters** to build a cost estimate.
- You want to resolve a trait (`default`, `default_reasoning`, `highest_quality`) or a legacy alias (`gpt-4o`) to a concrete Venice model ID.

## `GET /models`

```bash
curl "https://api.venice.ai/api/v1/models?type=text"
```

```json
{
  "object": "list",
  "type": "text",
  "data": [
    {
      "id": "zai-org-glm-5-2",
      "object": "model",
      "owned_by": "venice.ai",
      "type": "text",
      "created": 1781568000,
      "context_length": 1000000,
      "model_spec": {
        "name": "GLM 5.2",
        "description": "GLM-5.2 is the next-generation large language model…",
        "availableContextTokens": 1000000,
        "maxCompletionTokens": 131072,
        "privacy": "private",
        "modelSource": "https://huggingface.co/zai-org/GLM-5.2",
        "offline": false,
        "traits": ["default", "function_calling_default"],
        "capabilities": { "supportsReasoning": true, "reasoningEffortOptions": ["none", "high", "max"], "…": "…" },
        "pricing": {
          "input":       { "usd": 1.4,  "diem": 1.4 },
          "cache_input": { "usd": 0.26, "diem": 0.26 },
          "output":      { "usd": 4.4,  "diem": 4.4 }
        }
      }
    }
  ]
}
```

### Top-level `ModelResponse` fields

| Field | Notes |
|---|---|
| `id` | The model ID to send as `model`. |
| `object` / `owned_by` | Always `"model"` / `"venice.ai"`. |
| `type` | One of the 10 model types above. |
| `created` | Unix seconds - release date on the Venice API. |
| `context_length` | Text models only. OpenAI-compatible mirror of `model_spec.availableContextTokens`. |
| `discount_to_user` | Reseller-only (0 < x < 1). Returned only to the reselling partner whose agreement it belongs to and omitted for other callers - treat absent as no discount. |
| `model_spec` | Everything below. |

### `model_spec` - common fields

| Field | Use |
|---|---|
| `name`, `description`, `modelSource` | Display name, blurb, upstream URL (`description` / `modelSource` may be absent). |
| `privacy` | `private` (zero data retention) or `anonymized` (third-party provider; not tied to your identity). |
| `offline` | `true` ⇒ requests return `503` "The model is temporarily offline". Skip it. |
| `traits` | Trait names this model currently holds (may be `[]`). |
| `uncensored` | Present and `true` only for models Venice classifies as uncensored (all modalities). Absent otherwise - never `false`. Upstream providers may still filter. |
| `betaModel` | Model is in beta status (still callable). |
| `beta` | Model is restricted to beta-access accounts. Only appears in lists returned to such accounts. |
| `regionRestrictions` | Country codes where the model is **blocked** (the OpenAPI description reads "intended to be available", but requests are rejected *from* the listed countries). Those requests get `403` "The specified model is unavailable in <country>…". Absent on unrestricted models. |
| `deprecation` | `{ autoRemap, date, removesAt, replacementModelId?, startsAt? }` - present only when retirement is scheduled. The model drops out of `/models` at `removesAt`; `autoRemap: true` means Venice may remap requests for this ID to `replacementModelId` instead of returning an error. |
| `model_sets` | Text, image and video only. Curation tags such as `venice_recommendations`, `featured`, and for video `audio`, `uncensored`, `high_resolution`, `fast`, … (served live but not declared in the OpenAPI schema). |

### `model_spec.capabilities` - text models

| Flag | Meaning |
|---|---|
| `optimizedForCode` | Tuned for coding tasks (drives `?type=code`). |
| `quantization` | `fp4` / `fp8` / `fp16` / `bf16` / `int8` / `int4` / `not-available`. |
| `supportsFunctionCalling` | `tools` are allowed. |
| `supportsResponseSchema` | Honors `response_format: { type: "json_schema" }`. |
| `supportsReasoning` | Model emits reasoning. |
| `supportsReasoningEffort` | Honors `reasoning_effort` / `reasoning.effort`. When `true`, also `reasoningEffortOptions` (subset of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` - `none` means reasoning can be turned off) and `defaultReasoningEffort`. |
| `supportsVision` | Accepts `image_url` parts. |
| `supportsMultipleImages` + `maxImages` | More than one image per request; `maxImages` is the model's advertised limit. Chat hard-caps every model at 10 images per message. |
| `supportsVideoInput` + `maxVideos` | Accepts `video_url` parts; `maxVideos` present on some models. |
| `supportsAudioInput` | Accepts `input_audio` parts. |
| `supportsWebSearch` | `venice_parameters.enable_web_search` - currently `true` on every text model. |
| `supportsXSearch` | xAI native web + X search via `venice_parameters.enable_x_search`. |
| `supportsLogProbs` | Honors `logprobs` / `top_logprobs`. |
| `supportsTeeAttestation` | Runs in a TEE; verify with `GET /tee/attestation` / `/tee/signature`. |
| `supportsE2EE` | End-to-end encrypted inference (requires TEE). |

### `model_spec.constraints` and type-specific fields

- **Text** - `constraints` is optional (only a handful of models carry it): `temperature.default`, `top_p.default`, optional `{frequency,presence,repetition}_penalty.default`.
- **Image** - `constraints`: `promptCharacterLimit`, `widthHeightDivisor`, `steps.{default,max}`, optional `aspectRatios[]` + `defaultAspectRatio`, optional `resolutions[]` + `defaultResolution`, optional `qualities[]` + `defaultQuality` (models that accept `quality`), optional `maxStyleReferences` + `supportsStyleReferenceStrength`. Alongside: `supportsStyleReferences`, plus `supportsWebSearch` and `supportsOptimizePromptThinking` (served live, not in the OpenAPI schema).
- **Inpaint / edit** - `constraints`: `aspectRatios[]`, `promptCharacterLimit`, `combineImages`, optional `maxInputImages`, `singleImageAspectRatio` (if `false`, single-image edits keep input dimensions and ignore `aspect_ratio`), optional `resolutions[]`/`defaultResolution`, `qualities[]`/`defaultQuality`. Alongside: `supportsOptimizePromptThinking`.
- **Video** - `constraints`: `model_type` (`text-to-video` / `image-to-video` / `video`), `aspect_ratios[]`, `resolutions[]`, `durations[]` (e.g. `"5s"`; most upscale and video-to-video models list `"Auto"`, meaning the source length — omit `duration` for them), `audio`, `audio_configurable`, `audio_input`, `per_reference_audio`, `video_input`, optional `prompt_character_limit` (default 2500), optional `reference_image_min_short_side_pixels`, `reference_image_min_aspect_ratio`, `reference_image_max_aspect_ratio`, and a `topaz` block (`models`, `sliders`, `selects`, `no_upscale_models`, `h264_output`, `prompt`) on enhancement models only. The `audio_input` … `reference_image_*` keys are served live but not declared in the OpenAPI schema.
- **TTS** (top level of `model_spec`) - `voices[]`, `default_format`, `supported_formats[]` (an explicit format outside this list is rejected), `supports_custom_voice_id`, and `voice_cloning` `{ mode: "zero_shot" | "persistent", accepted_formats[], min_sample_seconds, retention_days }` on models whose cloning is open to you (use with `POST /audio/voices`, see [`venice-audio-speech`](../venice-audio-speech/SKILL.md)). Per-model toggles like `prompt` / `temperature` / `top_p` support are **not** exposed here - use the per-model table in [`venice-audio-speech`](../venice-audio-speech/SKILL.md) as the support matrix (the published schema text is incomplete).
- **Music / audio generation** (top level) - `supports_lyrics`, `lyrics_required`, `supports_force_instrumental`, `supports_lyrics_optimizer` (served live, not in the OpenAPI schema), `supports_loop`, `supports_custom_voice_id`, `supports_language_code`, `supports_speed`, `supported_formats[]`, `default_format`, `prompt_character_limit`, `min_prompt_length`, optional `lyrics_character_limit`, `duration_options[]`, `min_duration` / `max_duration` / `default_duration`, `voices[]` / `default_voice`, `default_speed` / `min_speed` / `max_speed`.
- **Voice changer** (music models with `voice_changer: true`) - adds `supports_background_noise_removal`, `supports_seed`, `accepted_audio_formats[]`, `max_source_audio_duration_seconds`. These run on `/audio/voice-changer/*`, not `/audio/queue` - see [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md). No voice-changer model is publicly listed today; check `?type=music` for `voice_changer: true` before relying on it.
- **Embedding** (top level) - `embeddingDimensions`, `maxInputTokens`, `supportsCustomDimensions` (present only when `true`).
- **Decision** (top level) - `maxStateTokens` (state + longest question), `maxTotalTokens` (state + all questions).
- **ASR / upscale** - no extra fields beyond the common ones and `pricing`.

### `model_spec.pricing` - by type

Every price is `{ usd, diem }`; today `diem` always equals `usd`. Prices already include any promotional discount active for the calling account (some promos are tier-gated, so anonymous and Pro callers can see different numbers) - quote from the same credentials you will bill with.

- **Text / embedding / decision** - `input` and `output` per 1 000 000 tokens, optional `cache_input` (cache reads), `cache_write` (cache creation, e.g. Anthropic), and `extended` `{ context_token_threshold, input, output, cache_input?, cache_write? }`. When input tokens exceed the threshold, extended rates apply to the **entire** request.
- **Image** - `generation` (flat per image) **or** `resolutions.<1K|2K|4K>`; optional `quality.<resolution>.<low|medium|high>`; always an `upscale.{2x,4x}` block (the shared upscale price, not a sign that this model upscales, and not promo-discounted).
- **Upscale** (`upscaler`) - same shape as image: `generation` + `upscale.{2x,4x}`.
- **Inpaint / edit** - `inpaint` per edit, optional `resolutions.*`, optional `inputImages { included, additional }` (surcharge per input image beyond `included`), optional `quality.*`.
- **Video** - **no `pricing` on `/models`.** Use `POST /video/quote` (see [`venice-video`](../venice-video/SKILL.md)).
- **Music** - exactly one of `generation` (per job), `durations.<ceiling_seconds>` `{ usd, diem, min_seconds, max_seconds }`, `per_second`, or `per_thousand_characters`. Use `POST /audio/quote` for the exact price.
- **TTS** - `input` per 1 000 000 input **characters**.
- **ASR** - `per_audio_second`.

Crypto RPC pricing is **not** in `/models` - see [`venice-crypto-rpc`](../venice-crypto-rpc/SKILL.md).

## `GET /models/traits`

```bash
curl "https://api.venice.ai/api/v1/models/traits?type=text"
```

```json
{
  "object": "list",
  "type": "text",
  "data": {
    "default": "zai-org-glm-5-2",
    "function_calling_default": "zai-org-glm-5-2",
    "default_reasoning": "kimi-k3",
    "default_code": "deepseek-v4-pro-0813",
    "default_vision": "qwen-3-8-27b",
    "most_intelligent": "grok-4-7",
    "most_uncensored": "venice-uncensored-1-2"
  }
}
```

Possible trait keys: `default`, `fastest`, `most_uncensored`, `eliza-default` (any type), `default_code`, `default_reasoning`, `default_vision`, `function_calling_default`, `most_intelligent` (text), `highest_quality` (image). A key only appears while some model holds it - `fastest` is currently unassigned for text. Today only `text` and `image` (and the `all` / `code` filters built from them) return non-empty maps. `?type=all` merges every type into one map, so keys shared across types collide - e.g. `default` resolves to an image model there. The values above are a snapshot; resolve them at runtime.

A trait name can also be sent directly as `model` (e.g. `"model": "default_reasoning"`) and Venice resolves it per request.

## `GET /models/compatibility_mapping`

```bash
curl "https://api.venice.ai/api/v1/models/compatibility_mapping?type=text"
```

```json
{
  "object": "list",
  "type": "text",
  "data": {
    "gpt-4o": "llama-3.3-70b",
    "gpt-4.1": "qwen3-235b-a22b-instruct-2507",
    "claude-3-5-sonnet-20241022": "llama-3.3-70b",
    "qwen3-235b": "qwen3-235b-a22b-thinking-2507"
  }
}
```

Keys are legacy OpenAI / Anthropic / older Venice IDs; values are the Venice model each one resolves to. `?type=embedding` currently maps `text-embedding-ada-002` → `text-embedding-bge-m3`; other types are empty. Like traits, an alias can be sent directly as `model`. Useful when porting code that hard-codes old OpenAI IDs - but check the target's capabilities, since the mapping is by ID only.

## Common patterns

### Pick a vision + reasoning model at runtime

```ts
const base = 'https://api.venice.ai/api/v1'
const list = await fetch(`${base}/models?type=text`).then(r => r.json())
const match = list.data.find((m: any) =>
  m.model_spec.capabilities.supportsVision &&
  m.model_spec.capabilities.supportsReasoning &&
  !m.model_spec.offline &&
  !m.model_spec.deprecation
)
```

### Validate an image request before submit

```ts
const spec = (await fetch(`${base}/models?type=image`).then(r => r.json()))
  .data.find((m: any) => m.id === myModel)!.model_spec

const { widthHeightDivisor, promptCharacterLimit, aspectRatios } = spec.constraints
if (prompt.length > promptCharacterLimit) throw new Error('prompt too long')
if (width % widthHeightDivisor !== 0) throw new Error('width not divisible')
if (aspectRatios && !aspectRatios.includes(myAspect)) throw new Error('bad aspect')
```

### Estimate LLM cost

```ts
// textSpec = model_spec of a text model from /models?type=text
// inputTokens = total prompt tokens, including cachedTokens
const p = textSpec.pricing
const tier = p.extended && inputTokens > p.extended.context_token_threshold ? p.extended : p
const cacheRate = tier.cache_input?.usd ?? tier.input.usd
const cost =
  ((inputTokens - cachedTokens) / 1_000_000) * tier.input.usd +
  (cachedTokens / 1_000_000) * cacheRate +
  (outputTokens / 1_000_000) * tier.output.usd
```

Cache-write tokens (models with `cache_write`) are billed at that rate instead of `input`.

## Gotchas

- The catalog changes - cache for minutes, not days. Model IDs in this skill are a snapshot; always confirm against `/models`.
- Omitting `?type` returns **text only**. Use `?type=all` for everything.
- `model_spec.pricing` is always absent for video and can be absent for any model without a published price - guard against `undefined`.
- `regionRestrictions` lists blocked countries, not allowed ones.
- `uncensored` is omitted rather than `false` - test with `=== true`.
- Traits and aliases differ by `type` - there is no global default; always pass `?type=...`.
- An API key restricted to private models (`modelPrivacy: PRIVATE_TEXT` / `PRIVATE_ONLY`) sees a filtered list; unauthenticated calls see everything public.
- Some fields are served live but missing from the OpenAPI `ModelResponse` schema (`model_sets`, image `supportsWebSearch`, image and inpaint `supportsOptimizePromptThinking`, music `supports_lyrics_optimizer`, several video constraint keys). Strict generated clients may drop them.