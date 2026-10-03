---
name: venice-image-edit
description: Transform existing images with Venice. Covers POST /image/edit (prompt-driven single-image edit), /image/multi-edit (compose several images, per-model input cap, quality tiers), /image/upscale (2x–4x upscale with creativity), and /image/background-remove (transparent PNG cutout). Input formats (base64, data URI, URL, multipart), per-model constraints from GET /models?type=inpaint, response headers, and errors.
---

# Venice Image Editing

Four endpoints, all operating on existing images:

| Endpoint | Purpose |
|---|---|
| `POST /image/edit` | Transform one image with a text prompt. JSON or `multipart/form-data`. |
| `POST /image/multi-edit` | Composite / layer several images with a single prompt. JSON or `multipart/form-data`. |
| `POST /image/upscale` | Upscale 2×–4×. JSON or `multipart/form-data`. |
| `POST /image/background-remove` | Produce a transparent PNG cutout. JSON or `multipart/form-data`. |

For text-to-image generation, see [`venice-image-generate`](../venice-image-generate/SKILL.md).

## Shared rules

| | `/image/edit` | `/image/multi-edit` | `/image/upscale` | `/image/background-remove` |
|---|---|---|---|---|
| JSON input | `image`: raw base64, data URI, or `http(s)://` URL | `images[]`: raw base64, data URI, or `http(s)://` URLs | `image`: raw base64 only | `image` (base64 / data URI) **or** `image_url` |
| Multipart input | one file in `image` | files in repeated `images` parts | one file in `image` | one file in `image` |
| Min size | ≥ 65,536 px total and ≥ 64 px per side | same | same | not checked by Venice |
| Max size | ≤ 33,177,600 px (7680×4320) | same | output ≤ 16,777,216 px (4096×4096) | not checked by Venice |
| Response | edited image bytes (PNG/JPEG/WebP) | edited image bytes | `image/png` | `image/png` with alpha |
| Model | `model` (default `firered-image-edit`) | `modelId` (default `firered-image-edit`) | fixed: `upscaler` | fixed: `bria-bg-remover` |

- Accepted input formats: JPEG, PNG, WebP, HEIF/HEIC, AVIF. SVG is rejected. Background-remove doesn't pre-validate the format; it passes the image straight to the model.
- Files must be < **25 MB** (multipart files over 25 MB return `413`). URLs fetched for edit and multi-edit are capped at 25 MB too. JSON bodies over 35 MB (for example a large base64 image) return `413`.
- URLs are fetched server-side and must be publicly reachable. Private, internal, and metadata hosts are blocked (`400`).
- All four endpoints return the image as **binary**, never JSON. There is no `return_binary` field (that flag only exists on `/image/generate`).
- JSON bodies on edit, multi-edit, and background-remove are **strict**: unknown fields are a `400`. `/image/upscale` ignores unknown fields.
- Edit, multi-edit, and background-remove accept an optional `anon_user_id` (printable ASCII, ≤ 128 chars, no `||`) for upstream end-user attribution.

## Choosing an edit model

```bash
curl "https://api.venice.ai/api/v1/models?type=inpaint"
```

Per model, read `model_spec.constraints`:

- `aspectRatios[]` — allowed `aspect_ratio` values. Not every model lists `auto` (e.g. `gpt-image-2-edit`, `qwen-image-2-edit`); `wan-2-7-pro-edit` only accepts `auto`.
- `resolutions[]` + `defaultResolution` — present when the model accepts `resolution`.
- `qualities[]` + `defaultQuality` — present when the model accepts `quality` (multi-edit only).
- `promptCharacterLimit` — enforced per model (1,500 for `firered-image-edit`, up to 32,768 for Nano Banana edits).
- `combineImages` — `false` means the model takes exactly one input image.
- `maxInputImages` — input-image cap for multi-edit. When it's absent and `combineImages` is `true`, the cap is **3**.
- `supportsOptimizePromptThinking` — whether `disable_prompt_optimization_thinking` does anything.

Pricing: `pricing.inpaint.usd` per edit, `pricing.resolutions[tier]` / `pricing.quality[tier][level]` on tiered models, and `pricing.inputImages` (`included` + `additional.usd` per extra image) on models that charge per additional input image. When `included` is `0` (e.g. `qwen-image-3-edit`, the Grok Imagine edits), every input image is surcharged, including the single image on `/image/edit`.

Representative edit IDs today (the list changes often, so read it from `/models`): `firered-image-edit` (default), `qwen-image-3-edit`, `qwen-image-3-pro-edit`, `nano-banana-2-edit`, `nano-banana-pro-edit`, `gpt-image-2-5-flare-edit`, `gpt-image-2-5-sunburst-edit`, `gpt-image-2-edit`, `seedream-v5-pro-edit`, `seedream-v5-lite-edit`, `muse-image-edit`, `flux-2-max-edit`, `grok-imagine-image-2-0-edit`, `luma-uni-1-edit` (single image only). The old `qwen-edit` ID still works as an alias and runs `qwen-edit-uncensored`.

## `/image/edit`

Edit one image with a short, descriptive prompt.

```bash
curl https://api.venice.ai/api/v1/image/edit \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-image-3-edit",
    "prompt": "Change the color of the sky to a sunrise",
    "image": "https://example.com/photo.jpg",
    "aspect_ratio": "16:9",
    "resolution": "2K",
    "safe_mode": true
  }'
```

Multipart equivalent: send `image` as a file part and the other fields as text parts (`-F image=@photo.jpg -F prompt=... -F model=...`). Only one file is allowed.

| Field | Notes |
|---|---|
| `model` | Default `firered-image-edit`. Must be an ID from `GET /models?type=inpaint` (otherwise `400 Invalid model id`). `modelId` is still accepted as a deprecated alias; `model` wins if both are sent. |
| `prompt` | Required. ≤ the model's `promptCharacterLimit` (hard ceiling 32,768). Short and specific works best. |
| `image` | Required. See the shared rules for accepted input formats. |
| `aspect_ratio` | Optional: `auto`, `1:1`, `3:2`, `16:9`, `21:9`, `9:16`, `2:3`, `3:4`, `4:3`, `4:5`. Must be in the model's `constraints.aspectRatios`, or you get `400`. Omit it (or send `auto` where listed) to infer from the input image. |
| `resolution` | Optional, e.g. `"1K"`, `"2K"`, `"4K"`. Must be in the model's `constraints.resolutions`. **Sending any `resolution` to a model without resolutions is a `400` on this endpoint.** Defaults to the model's `defaultResolution`. |
| `output_format` | Optional `jpeg` (or `jpg`) \| `png` \| `webp`. When omitted: PNG for 1K (or no resolution), JPEG for 2K/4K. |
| `enhance_prompt` | Optional bool, default `false`. Rewrites your prompt against the input image before editing. Adds up to ~30 s and a $0.04 charge when a rewrite is produced. The rewritten prompt comes back URL-encoded in the `x-venice-enhanced-prompt` response header. |
| `disable_prompt_optimization_thinking` | Optional bool. Only honored by models with `supportsOptimizePromptThinking: true`; ignored elsewhere. |
| `safe_mode` | Default `true`; blurs adult content. |

There is **no `quality` field** on `/image/edit`; sending it is a `400`, and quality-tier models are billed at their `defaultQuality`. To pick a quality tier (GPT Image models, `ideogram-v4-5-edit`), use `/image/multi-edit` with a single image.

Good prompts: *"remove the tree"*, *"add sunglasses to the cat"*, *"make the sky a vivid orange sunrise"*.

## `/image/multi-edit`

Combine several images into one with a prompt. The **first image is the base**; the rest are layers or references. Minimum 1 image. The maximum is per model: `constraints.maxInputImages` (6 on most current models), 3 if that field is absent, and 1 when `combineImages` is `false`.

> **Field name:** `/image/multi-edit` takes **`modelId`**, not `model`. Sending `model` is a `400` (unknown field).

### JSON (base64, data URIs, or URLs)

```json
{
  "modelId": "nano-banana-2-edit",
  "prompt": "Place the person from image 2 onto the beach in image 1",
  "images": [
    "https://example.com/beach.jpg",
    "data:image/png;base64,iVBOR..."
  ],
  "resolution": "2K",
  "safe_mode": true
}
```

### Multipart (file upload)

```
POST /image/multi-edit
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="modelId"

nano-banana-2-edit
--boundary
Content-Disposition: form-data; name="prompt"

Place the person from image 2 onto the beach in image 1
--boundary
Content-Disposition: form-data; name="images"; filename="base.jpg"
Content-Type: image/jpeg

<bytes>
--boundary
Content-Disposition: form-data; name="images"; filename="subject.png"
Content-Type: image/png

<bytes>
--boundary--
```

Multipart accepts only file parts for `images` (no URLs or base64), and at most 10 files at the transport layer.

| Field | Notes |
|---|---|
| `modelId` | Default `firered-image-edit`. Must be an inpaint model ID. |
| `prompt` | Required. ≤ the model's `promptCharacterLimit`. |
| `images` | Required, 1..per-model max. More than one image on a `combineImages: false` model (e.g. `luma-uni-1-edit`) is a `400`. |
| `aspect_ratio` | Optional, same enum as `/image/edit`. Must be in the model's `aspectRatios`. `auto` or omitted infers it from the **first** image. |
| `resolution` | Optional. Must be in the model's `resolutions` if it has any. Silently dropped for models without resolutions (unlike `/image/edit`). Defaults to `defaultResolution`. |
| `quality` | Optional `low` \| `medium` \| `high`, for models with `constraints.qualities` (GPT Image 2 / 2.5 edits, `ideogram-v4-5-edit`; Grok Imagine 2.0 edit takes `low`/`medium`). A value outside the list is `400`; ignored on other models. Omitted → `defaultQuality`. Changes the price. |
| `output_format` | Optional `jpeg`/`jpg` \| `png` \| `webp`. Omitted → PNG for 1K, JPEG for 2K/4K. |
| `enhance_prompt` | Optional bool, default `false`. Same behavior, $0.04 charge, and `x-venice-enhanced-prompt` header as `/image/edit`. |
| `disable_prompt_optimization_thinking` | Optional bool. |
| `safe_mode` | Default `true`. |

### Edit / multi-edit response headers

| Header | Meaning |
|---|---|
| `Content-Type` | Detected from the output bytes (`image/png`, `image/jpeg`, or `image/webp`). |
| `x-venice-model-id`, `x-venice-model-name` | The model that ran. |
| `x-venice-is-blurred` | `"true"` if `safe_mode` blurred the output. |
| `x-venice-is-content-violation` | Always `"false"` on a `200`. Flagged edits return `422` instead (see errors). |
| `x-venice-enhanced-prompt` | URL-encoded rewritten prompt (only when `enhance_prompt` produced one). |
| `x-venice-model-deprecation-warning`, `x-venice-model-deprecation-date`, `x-venice-deprecated`, `x-venice-deprecated-replacement` | Deprecation signals for the model. |

## `/image/upscale`

Upscale 2×–4× with Venice's private upscaler (model ID `upscaler`). It takes three fields.

```bash
curl https://api.venice.ai/api/v1/image/upscale \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "iVBORw0KGgo...",
    "scale": 4,
    "creativity": 0.01
  }'
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `image` | raw base64 string (JSON) or file (multipart field `image`) | — | Required. URLs are not accepted. ≥ 65,536 px and < 25 MB. |
| `scale` | number, 2–4 | 2 | Documented as `2` or `4`. Anything below 2 (including the old `scale: 1`) is a `400`. If `width × height × scale²` would exceed 16,777,216 px, the scale is reduced automatically. If no real upscale fits, you get a `400`. |
| `creativity` | number | 0.01 | How much detail and texture the upscaler adds. Clamped to **0–0.02**, so `0.5` behaves as `0.02`. `null` is coerced to `0`. |

Response: `image/png` bytes. Every successful upscale is charged.

Billing (from `/models` `pricing.upscale`): **$0.02** when the effective scale is ≤ 2, **$0.08** when it is above 2. For example, `scale: 3` bills at the 4× rate.

> **Breaking change (upscaler rewrite):** the old `enhance`, `enhanceCreativity`, `enhancePrompt`, and `replication` fields no longer do anything. They are silently ignored, not rejected, so remove them to avoid confusion. `creativity` is **not** `enhanceCreativity` renamed: its range is only 0–0.02, so an old `enhanceCreativity: 0.5` sent as `creativity: 0.5` just behaves as `0.02` (the max).

## `/image/background-remove`

Produce a transparent PNG cutout with `bria-bg-remover` (an `anonymized` model, $0.03 per call per `/models`).

```bash
# With base64 (raw or data URI)
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image": "iVBOR..."}'

# With a URL
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/photo.jpg"}'

# With a file
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F image=@photo.jpg
```

- JSON: send **exactly one** of `image` (non-empty base64; raw base64 is treated as PNG) or `image_url`. Sending both, neither, or an empty/whitespace `image` is a `400`.
- Multipart: one non-empty file in `image`. `image_url` is not accepted in multipart.
- Response: `image/png` with alpha, plus `x-venice-model-id` / `x-venice-model-name` headers.

## Error behavior (all four endpoints)

| Code | Cause |
|---|---|
| `400` | Bad params: schema violation or unknown field, invalid or corrupt image, image too small, multi-edit image over 8K, unknown/non-edit model (`Invalid model id`), prompt over the model limit, `aspect_ratio`/`resolution`/`quality` not supported by the model, too many input images, blocked URL, unsupported `Content-Type` (edit, upscale, background-remove). |
| `401` | Auth failed. |
| `402` | No credentials at all (x402 payment-requirements body + `PAYMENT-REQUIRED` header), insufficient balance (Bearer: `"Insufficient USD or Diem balance…"`; x402 wallet: `PAYMENT_REQUIRED` body + header), or the API key's USD/DIEM spend limit is reached. |
| `403` | The API key's `modelPrivacy` setting blocks the model. A `PRIVATE_ONLY` key can't use anonymized models, which includes most edit models and `bria-bg-remover`. |
| `404` | Edit / multi-edit: the provider couldn't find or fetch the input media (the body carries the provider's message). |
| `413` | Multipart file over 25 MB, or request body too large. |
| `415` | `/image/multi-edit` only, when the body is empty. A wrong `Content-Type` on any route is a `400` (`"'Content-Type' must be 'application/json'"`) — send JSON or multipart. |
| `422` | Content-policy violation on edit / multi-edit (`{"error":"Your prompt violates the content policy of Venice.ai or the model provider"}`, no `code` field), or an image exceeds a pixel limit during processing (e.g. an `/image/edit` input over 8K). |
| `429` | Rate limited, or the upstream provider is overloaded. |
| `500` | Edit / upscale / background removal failed. |
| `503` | Model at capacity — retry with jitter. |

A `422` content-policy rejection is normally not charged. If Venice's own moderation blocks an image after the provider already generated it, the edit **is** charged. See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Gotchas

- Field-name asymmetry: `/image/edit` uses **`model`** (`modelId` is a deprecated alias). `/image/multi-edit` accepts **only `modelId`**.
- `resolution` behaves differently per endpoint. On `/image/edit`, sending it to a model without resolutions is a `400`. On `/image/multi-edit`, it is silently dropped.
- `quality` exists on `/image/multi-edit` but not on `/image/edit`.
- Don't send `aspect_ratio: "auto"` to a model whose `aspectRatios` don't include it (e.g. `gpt-image-2-edit`). Omit the field instead.
- For multipart `/image/multi-edit`, send **multiple parts with the same field name `images`**. Order matters: the base image goes first.
- `/image/upscale` needs **raw** base64 in JSON. Strip any `data:image/...;base64,` prefix. Edit, multi-edit, and background-remove accept data URIs.
- `/image/upscale` with `scale: 4` on a large input is silently reduced to stay under 16 MP, and it still bills at the 4× rate if the effective scale is above 2.
- `enhance_prompt` on edit / multi-edit bills $0.04 whenever a rewrite is produced. Leave it off for latency- or cost-sensitive calls.
- `safe_mode: true` can blur otherwise valid outputs; check `x-venice-is-blurred`. Switch to `false` only when you control the input and accept the ToS consequences.
- Some models charge extra for each input image beyond the included count (`pricing.inputImages`). Where `included` is `0`, even a single-image `/image/edit` pays the surcharge.
