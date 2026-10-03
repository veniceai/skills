---
name: venice-image-generate
description: Generate images with Venice. Covers POST /image/generate (Venice-native), POST /images/generations (OpenAI-compatible), GET /image/styles (style presets), request fields (prompt, width/height, aspect_ratio, resolution, quality, cfg_scale, steps, seed, variants, style_preset, style_references, enhance_prompt, safe_mode, hide_watermark, format, return_binary), per-model constraints from GET /models, response formats and headers.
---

# Venice Image Generation

Two text-to-image endpoints:

1. **`POST /api/v1/image/generate`** — Venice-native, full control (negative prompts, CFG, seed, style presets/references, quality, up to 4 variants).
2. **`POST /api/v1/images/generations`** — OpenAI-compatible, fewer knobs but drop-in for the OpenAI SDK.

Plus:

- **`GET /api/v1/image/styles`** — list of style preset names for `style_preset`. No auth required.

For editing / upscaling / multi-image / background removal, see [`venice-image-edit`](../venice-image-edit/SKILL.md).

## Use when

- You need to generate images from text prompts.
- You need multiple variants in one call.
- You're porting from OpenAI's `images.generate` and want a zero-change SDK swap.
- You want to browse style presets before committing to one.
- You want generated images to match the look of existing images (`style_references`).

## `/image/generate` — Venice-native

### Request

```bash
curl https://api.venice.ai/api/v1/image/generate \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "z-image-turbo",
    "prompt": "A beautiful sunset over a mountain range",
    "width": 1024,
    "height": 1024,
    "cfg_scale": 7.5,
    "seed": 123456789,
    "variants": 1,
    "format": "webp",
    "style_preset": "3D Model",
    "safe_mode": true
  }'
```

The request schema is **strict**: unknown fields are rejected with `400`.

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `model` | string | — | **Required.** Image model ID from `GET /models?type=image`. Unknown IDs return `404` (with a suggestion); retired IDs return `404` naming the replacement when one exists. |
| `prompt` | string | — | **Required.** Non-blank. Max `constraints.promptCharacterLimit` for the model (1,500 – 32,768 today). |
| `negative_prompt` | string | — | What *not* to show. Same character cap as `prompt`. Only used by some models today (e.g. `venice-sd35`, `lustify-*`, `wai-Illustrious`, `qwen-image-2`, `qwen-image-2-pro`, `qwen-image-3`, `qwen-image-3-pro`, `wan-2-7-*`). Silently dropped everywhere else, including `z-image-turbo` and `chroma`. |
| `width`, `height` | int | 1024, 1024 | ≤ 1280 each. Only used by pixel-sized models (no `constraints.aspectRatios`). Aspect-ratio models ignore them, and `qwen-image`, `qwen-image-3`, `qwen-image-3-pro` **reject** them with `400` — use `aspect_ratio`. |
| `aspect_ratio` | string | model default | E.g. `"1:1"`, `"16:9"`, `"4:3"`. Send only values from the model's `constraints.aspectRatios`. `/image/generate` doesn't validate this field: most models fall back to `defaultAspectRatio`, but some pass it upstream and fail. |
| `resolution` | string | model default | `"1K"`, `"2K"`, `"4K"`. Must be in the model's `constraints.resolutions` (otherwise `400`). Silently dropped for models with no `resolutions`. |
| `quality` | `"low"`/`"medium"`/`"high"` | model default | Only for models with `constraints.qualities` (GPT Image 2 / 2.5, Ideogram V4.5, Grok Imagine 2.0). A value outside that list is `400`; ignored on other models. Changes the price — see `pricing.quality`. |
| `cfg_scale` | number | model default | `0 < x ≤ 20`. Higher = more prompt adherence. |
| `steps` | int | `min(steps.max, 20)` | Only used by models that take steps (today `venice-sd35`, `lustify-*`, `wai-Illustrious`); on those it is `1..constraints.steps.max` and above max is `400`. Every other model, including `z-image-turbo` and `chroma`, accepts any integer and ignores it. |
| `seed` | int | random | `-999999999..999999999`. Omit for a random seed (`0` is a literal seed, not "random"). Some models ignore it (e.g. GPT Image, Muse, Luma, Recraft, ImagineArt, Seedream V5 Pro, Nano Banana Pro, Grok Imagine). |
| `variants` | int | 1 | 1–4. Only with `return_binary: false`. Only the **first** image uses your `seed`; the others get random seeds. Each variant is billed and rate-limited as one image. |
| `style_preset` | string | — | Exact value from `GET /image/styles`; anything else is `400`. |
| `style_references` | array | — | Reference images that guide the aesthetic. Each item: `{ "image": <raw base64, data URI, or http(s) URL; < 8 MB; not SVG>, "strength": 0.1–1 (default 0.5) }`. Only on models with `supportsStyleReferences: true`, max `constraints.maxStyleReferences` entries; otherwise `400`. `strength` is ignored when `constraints.supportsStyleReferenceStrength` is `false`. |
| `lora_strength` | int | — | 0–100. Only applies to models that use LoRAs. |
| `enhance_prompt` | bool | `false` | Rewrites the prompt to add visual detail before generating. Adds up to ~30 s and a $0.04 charge when a rewrite is produced (fails open to your original prompt). The final prompt comes back URL-encoded in the `x-venice-enhanced-prompt` response header. |
| `disable_prompt_optimization_thinking` | bool | model default | Skip the model's prompt-optimization thinking step for speed. Only honored by models with `supportsOptimizePromptThinking: true` (e.g. `seedream-v5-pro`, `qwen-image-3`). |
| `enable_web_search` | bool | `false` | Only for models with `supportsWebSearch: true` (currently `nano-banana-2`, `nano-banana-pro`); ignored elsewhere. The spec warns that search can cost extra, but today the per-image charge is the same with or without it. |
| `format` | `"webp"`/`"png"`/`"jpeg"` | `webp` | Output image format. |
| `return_binary` | bool | `false` | `true` → raw image bytes; `false` → JSON with base64. |
| `embed_exif_metadata` | bool | `false` | Embed prompt info in EXIF. |
| `hide_watermark` | bool | `false` | Only matters on Venice's flat-priced models (`z-image-turbo`, `venice-sd35`, `chroma`, `lustify-*`, `wai-Illustrious`). All other models are never watermarked. Images classified as adult content and very small images are never watermarked either. |
| `safe_mode` | bool | `true` | Blurs images classified as adult content. |
| `anon_user_id` | string | — | Optional end-user identifier (printable ASCII, ≤ 128 chars, no `\|\|`) forwarded for upstream attribution. |
| `inpaint` | — | — | **Removed** (disabled May 19 2025). Sending it is a `400`. Use [`/image/edit`](../venice-image-edit/SKILL.md). |

### Response (JSON, `return_binary: false`)

```json
{
  "id": "...",
  "images": ["<base64>", "<base64>"],
  "timing": { "inferenceDuration": 0, "inferencePreprocessingTime": 0, "inferenceQueueTime": 0, "total": 0 },
  "request": { "success": true, "data": { "...": "the parsed request with defaults filled in (style_references omitted)" } }
}
```

Send `Accept-Encoding: gzip, br` to get the JSON compressed.

With `return_binary: true`, the body is the raw image; `Content-Type` is detected from the bytes (`image/webp`, `image/png`, or `image/jpeg`).

### Response headers

| Header | Meaning |
|---|---|
| `x-venice-is-content-violation` | `"true"` if the image was blocked. The call still returns `200`: JSON images are blacked out; binary returns a PNG placeholder. You are not charged. |
| `x-venice-is-blurred` | `"true"` if `safe_mode` blurred the output. |
| `x-venice-enhanced-prompt` | URL-encoded rewritten prompt (only when `enhance_prompt` produced one). |
| `x-venice-model-deprecation-warning`, `x-venice-model-deprecation-date`, `x-venice-deprecated`, `x-venice-deprecated-replacement` | Present when the model is scheduled for or already in deprecation. |
| `x-ratelimit-{limit,remaining,reset}-*`, `x-venice-balance-usd`, `x-venice-balance-diem` | Rate-limit and balance state, set before the image is generated. |
| `X-Balance-Remaining` | Listed in the spec for x402 callers but not currently set by the server — poll `GET /x402/balance/{walletAddress}` instead. |

## `/images/generations` — OpenAI-compatible

Use this if you're already on the OpenAI SDK. Field names match `openai.images.generate()`.

```ts
import OpenAI from 'openai'

const client = new OpenAI({
  apiKey: process.env.VENICE_API_KEY,
  baseURL: 'https://api.venice.ai/api/v1',
})

const res = await client.images.generate({
  model: 'z-image-turbo',
  prompt: 'A beautiful sunset over mountain ranges',
  size: '1024x1024',
  response_format: 'b64_json',
})

const b64 = res.data[0].b64_json
```

### Mapped fields

| Field | Values | Notes |
|---|---|---|
| `model` | string | Required in practice: omitting it (or sending `""`) returns `400 "model is required"`, even though the spec lists a `"default"` default. Unknown IDs (e.g. `dall-e-3`) silently fall back to Venice's default image model (`z-image-turbo`). |
| `prompt` | string, 1–1500 chars | Required. 1500 is the cap here regardless of model. |
| `size` | `auto` (default → 1024×1024), `256x256`, `512x512`, `1024x1024`, `1536x1024`, `1024x1536`, `1792x1024`, `1024x1792` | Mapped to width/height, so it only affects pixel-sized models; aspect-ratio models use their default aspect ratio. |
| `output_format` | `jpeg` / `png` / `webp` | Defaults to `png`. |
| `response_format` | `b64_json` (default) / `url` | `url` returns a `data:` URL (not a hosted URL). |
| `moderation` | `auto` (default, safe mode on) / `low` (safe mode off) | — |
| `n` | `1` | Only one image per call. |
| `anon_user_id` | string | Same as on `/image/generate`. |
| `quality`, `style`, `background`, `output_compression`, `user` | — | Accepted for OpenAI compatibility and ignored, but values must still be valid (`quality`: `auto`/`high`/`medium`/`low`/`hd`/`standard`; `style`: `vivid`/`natural`; `background`: `transparent`/`opaque`/`auto`; `output_compression`: 0–100). `user` is not used for inference and is not an alias of `anon_user_id`, but it does split the error budget per value (see [`venice-errors`](../venice-errors/SKILL.md#error-budget)). |

Response: `{ "created": <unix>, "data": [{ "b64_json": "..." }] }` (or `[{ "url": "data:image/png;base64,..." }]`). Images from this endpoint are never watermarked. Unknown fields are rejected with `400`.

If you need `variants`, `seed`, `negative_prompt`, `cfg_scale`, `aspect_ratio`, `resolution`, `quality`, `style_preset`, or `style_references`, switch to `/image/generate`.

## `/image/styles` — list presets

```bash
curl https://api.venice.ai/api/v1/image/styles
```

No API key needed. Returns a list of strings:

```json
{ "object": "list", "data": ["3D Model", "Analog Film", "Anime", "Cinematic", "Comic Book", "..."] }
```

Pass any `data[]` entry verbatim as `style_preset` (it is case-sensitive). Cache it; the list rarely changes.

## Choosing a model

```bash
curl "https://api.venice.ai/api/v1/models?type=image"
```

Inspect each model's `model_spec`:

- `constraints.promptCharacterLimit` — max prompt length (also applies to `negative_prompt`).
- `constraints.aspectRatios[]` + `defaultAspectRatio` — present on aspect-ratio-driven models; use `aspect_ratio` instead of `width`/`height`.
- `constraints.resolutions[]` + `defaultResolution` — present when the model accepts `resolution`.
- `constraints.qualities[]` + `defaultQuality` — present when the model accepts `quality`.
- `constraints.steps.{default,max}` — step bounds. Every model lists them, but only a few use `steps` (see the field table).
- `constraints.widthHeightDivisor` — pixel-sized models work best with `width`/`height` as multiples of this (8 or 16). The API does not validate it.
- `supportsStyleReferences`, `constraints.maxStyleReferences`, `constraints.supportsStyleReferenceStrength` — style-reference support.
- `supportsWebSearch`, `supportsOptimizePromptThinking` — whether those request flags do anything.
- `privacy` (`private` / `anonymized`) and `uncensored` — privacy tier and content posture.
- Pricing: `pricing.generation.usd` (flat per image), or `pricing.resolutions[tier].usd` for resolution-tiered models, plus `pricing.quality[tier][level].usd` for quality-tiered models.

Representative IDs (verify with `GET /models?type=image` — the list changes often):

| Sizing idiom | Examples |
|---|---|
| `width`/`height` | `z-image-turbo` (default model), `venice-sd35`, `chroma`, `lustify-v8` |
| `aspect_ratio` only | `flux-2-pro`, `seedream-v5-lite`, `muse-image`, `qwen-image-2`, `krea-v2-large` |
| `aspect_ratio` + `resolution` | `nano-banana-2`, `nano-banana-pro`, `seedream-v5-pro`, `qwen-image-3` |
| `aspect_ratio` + `resolution` + `quality` | `gpt-image-2`, `gpt-image-2-5-flare`, `gpt-image-2-5-sunburst`, `ideogram-v4-5` (1K / 2K), `grok-imagine-image-2-0` (low/medium only) |

`bria-bg-remover` also appears under `type=image`, but it is the background-removal model. Use it through [`/image/background-remove`](../venice-image-edit/SKILL.md), not `/image/generate`.

## Common patterns

### Fixed-seed reproducibility

```json
{"model": "z-image-turbo", "prompt": "...", "seed": 42}
```

On models that honor `seed` (e.g. `z-image-turbo`, `seedream-v4`, `nano-banana-2`), the same model + prompt + seed + settings should reproduce the same image, though third-party models don't guarantee bit-identical output. With `variants > 1`, only the first image uses `seed`; the rest are random, so run separate calls with different seeds if you need each one reproducible.

### Aspect-ratio + resolution model (Nano Banana, Seedream V5 Pro)

```json
{"model": "nano-banana-2", "prompt": "...", "aspect_ratio": "16:9", "resolution": "2K"}
```

```json
{"model": "seedream-v5-pro", "prompt": "...", "aspect_ratio": "4:3", "resolution": "2K"}
```

### Quality tier (GPT Image 2 / 2.5, Ideogram V4.5)

```json
{"model": "gpt-image-2-5-flare", "prompt": "...", "aspect_ratio": "3:2", "resolution": "2K", "quality": "medium"}
```

Omitting `quality` uses `defaultQuality` (`high` for the GPT Image and Ideogram V4.5 models). The price depends on both resolution and quality.

### Style preset + negative

Use a model that honors `negative_prompt` (see the field table); `z-image-turbo` silently drops it.

```json
{
  "model": "venice-sd35",
  "prompt": "a red sports car in a parking lot",
  "negative_prompt": "blurry, people, clouds",
  "style_preset": "3D Model"
}
```

### Style references (match the look of existing images)

```json
{
  "model": "krea-v2-large",
  "prompt": "a lighthouse on a rocky coast at dusk",
  "style_references": [
    { "image": "https://example.com/ref-1.png", "strength": 0.8 },
    { "image": "data:image/png;base64,....", "strength": 0.4 }
  ]
}
```

Describe the **subject** in the prompt; the references carry the **style**. Today the supporting models are `krea-v2-large` / `krea-v2-medium` (up to 3 refs, strength honored) and `luma-uni-1` / `luma-uni-1-max` (up to 3 refs, strength ignored). All four are `anonymized` models. Re-check `supportsStyleReferences` via `GET /models?type=image`. The Krea V2 models add a small per-request surcharge when references are used; it isn't itemized in the `/models` pricing.

### Stream binary to disk (Node)

```ts
const res = await fetch('https://api.venice.ai/api/v1/image/generate', {
  method: 'POST',
  headers: { Authorization: `Bearer ${process.env.VENICE_API_KEY}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ model: 'z-image-turbo', prompt: '...', return_binary: true }),
})
if (!res.ok) throw new Error(await res.text())
if (res.headers.get('x-venice-is-content-violation') === 'true') throw new Error('Content violation')
const ext = (res.headers.get('content-type') ?? 'image/webp').split('/')[1]
const buf = Buffer.from(await res.arrayBuffer())
await fs.writeFile(`out.${ext}`, buf)
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad params: missing `model`, schema violation, unknown field, prompt too long, `steps` above max (on models that use steps), invalid `style_preset`, unsupported `resolution`/`quality` for the model, `width`/`height` sent to `qwen-image`/`qwen-image-3`/`qwen-image-3-pro`, `variants` with `return_binary: true`, `style_references` on an unsupported model or over the cap, unreachable/corrupt reference image. |
| `401` | Auth failed. |
| `402` | No credentials at all (x402 payment-requirements body + `PAYMENT-REQUIRED` header), insufficient balance (Bearer: `"Insufficient USD or Diem balance…"`; x402 wallet: `PAYMENT_REQUIRED` body + header), or the API key's USD/DIEM spend limit is reached. |
| `403` | The API key's `modelPrivacy` setting blocks this model (e.g. a `PRIVATE_ONLY` key calling an `anonymized` model), or the model is unavailable in your region or restricted for your account. |
| `404` | Model not found or retired (message names the replacement when there is one). On `/images/generations`, unknown IDs fall back to the default model instead. |
| `422` | Reference image too large in pixels (over 7680×4320). |
| `429` | Rate limited, or the upstream provider is overloaded (`Retry-After` is set). |
| `500` | Inference failed. |
| `503` | Model at capacity or offline. Retry with jitter. |

Content-policy violations are **not** an error on these endpoints. You get `200` with `x-venice-is-content-violation: true` and a blocked image, and no charge. See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Gotchas

- Each model uses one sizing idiom: `width`/`height`, or `aspect_ratio` (+ `resolution`). Read `constraints` first. Sending `width`/`height` to an aspect-ratio model is silently ignored, except on `qwen-image`, `qwen-image-3`, and `qwen-image-3-pro`, where it is a `400`.
- `aspect_ratio` isn't validated on `/image/generate`, so a value the model doesn't list usually falls back to its default without an error. A `resolution` or `quality` the model doesn't list is a `400`.
- `variants > 1` requires `return_binary: false`.
- Grok Imagine models return the provider's bytes unchanged when nothing is blurred, so the output format may not match `format` and EXIF isn't embedded. Trust `Content-Type`, or sniff the bytes.
- Always check `x-venice-is-content-violation`. A blocked image still arrives as a `200`.
- `style_references` on a model without `supportsStyleReferences: true` is a `400`, not a silent no-op.
- `enhance_prompt` bills $0.04 each time it produces a rewrite. Leave it off for cost- or latency-sensitive calls.
- For OpenAI-compat, `response_format: "url"` returns a **data URL**, not a hosted URL. Plan for that if you're saving to storage.
