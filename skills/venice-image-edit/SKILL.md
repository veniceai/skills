---
name: venice-image-edit
description: Transform existing images with Venice. Covers POST /image/edit (prompt-driven single-image edit), /image/multi-edit (compose multiple images), /image/upscale (2x or 4x upscale), and /image/background-remove. Accepts base64, file upload, or HTTPS URL.
---

# Venice Image Editing

Four endpoints, all operating on existing images:

| Endpoint | Purpose |
|---|---|
| `POST /image/edit` | Transform one image with a text prompt. |
| `POST /image/multi-edit` | Composite / layer several images with a single prompt. Also has a `multipart/form-data` variant. |
| `POST /image/upscale` | Upscale 2× or 4×. |
| `POST /image/background-remove` | Produce a transparent cutout. |

For text-to-image generation, see [`venice-image-generate`](../venice-image-generate/SKILL.md).

## Shared rules

- Input image accepts **base64 string**, **file upload**, or **HTTPS URL**, but not every combination on every content type. `/image/edit` and `/image/multi-edit` accept base64 or HTTPS URL in JSON (multi-edit also has a `multipart/form-data` file variant). `/image/background-remove` JSON is **either** base64 `image` **or** `image_url`; its multipart variant is a required binary `image` file and does **not** accept `image_url`.
- File size < **25 MB**. Image dimensions must be between **65,536** (256×256 equivalent) and **33,177,600** pixels (~5,761×5,761). Upscale caps at **16,777,216** pixels after scaling.
- HTTPS URLs must be publicly reachable from Venice's network.
- All four endpoints return the image as **binary**, never JSON. There is no `return_binary` field on edit / multi-edit / upscale / background-remove (that flag only exists on `/image/generate`). `/image/edit` and `/image/multi-edit` return `image/png`, `image/jpeg`, or `image/webp` depending on `output_format`; `/image/upscale` and `/image/background-remove` always return `image/png`.

## `/image/edit`

Edit one image with a short, descriptive prompt.

```bash
curl https://api.venice.ai/api/v1/image/edit \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "firered-image-edit",
    "prompt": "Change the color of the sky to a sunrise",
    "image": "iVBORw0KGgoAAAANSUhEUg...",
    "aspect_ratio": "16:9",
    "safe_mode": true
  }'
```

| Field | Notes |
|---|---|
| `model` | Default `firered-image-edit`. See `GET /models?type=inpaint` for edit-capable models. `modelId` is accepted for backwards compatibility but deprecated on `/image/edit` — prefer `model`. |
| `prompt` | Required, ≤ 32 768 chars (usually 1500 is plenty). Short & specific works best. |
| `image` | Required. Base64 string, file upload, or `https://` URL. |
| `aspect_ratio` | Optional: `auto`, `1:1`, `3:2`, `16:9`, `21:9`, `9:16`, `2:3`, `3:4`, `4:3`, `4:5`. Supported values vary per model — check `constraints` on `GET /models`. |
| `resolution` | Optional tier, e.g. `"1K"`, `"2K"`, `"4K"`. Defaults to `"1K"`. Supported values vary per model. |
| `output_format` | Optional `jpeg` \| `png` \| `webp`. When omitted, inferred from `resolution`: PNG for 1K, JPEG for 2K/4K. |
| `enhance_prompt` | Optional bool, default `false`. Rewrites your prompt against the input image before editing. Costs extra credits and adds up to ~30 s. The rewritten prompt comes back URL-encoded in the `x-venice-enhanced-prompt` response header. |
| `disable_prompt_optimization_thinking` | Optional bool. Skips the model's prompt-optimization thinking step for speed. Only honored by models with `supportsOptimizePromptThinking`; ignored elsewhere. |
| `safe_mode` | Default `true`; blurs adult content. |

Good prompts: *"remove the tree"*, *"add sunglasses to the cat"*, *"make the sky a vivid orange sunrise"*.

Edit-capable model IDs change often. Read them from `GET /models?type=inpaint`
rather than pinning a literal, and note that older IDs like `qwen-edit` have
been retired in favor of `qwen-image-2-edit` and friends.

## `/image/multi-edit`

Combine several images into one with a prompt. The **first image is the base**; the rest are layers / masks / references. The minimum is 1 image and the maximum is model-specific — read `capabilities.maxInputImages` from `GET /models`.

> **Field name:** `/image/multi-edit` takes **`modelId`**, not `model`. This is the only image endpoint that uses `modelId` as the primary field name.

### JSON (base64 or URLs)

```json
{
  "modelId": "firered-image-edit",
  "prompt": "Place the person from image 2 onto the beach in image 1",
  "images": [
    "https://example.com/beach.jpg",
    "data:image/png;base64,iVBOR..."
  ],
  "safe_mode": true
}
```

### Multipart (file upload)

```
POST /image/multi-edit
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="modelId"

firered-image-edit
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

| Field | Notes |
|---|---|
| `modelId` | **Required field name** (multi-edit does not accept `model`). Default `firered-image-edit`. |
| `prompt` | Required, ≤ 32 768 chars. |
| `images` | Required. Minimum 1; maximum is model-specific (`capabilities.maxInputImages`). JSON variant accepts base64 or HTTPS URLs; multipart variant accepts raw file parts. |
| `aspect_ratio` | Optional; inferred from the **first** image when set to `auto` or omitted. |
| `resolution` | Optional tier, e.g. `"1K"`, `"2K"`, `"4K"`. Defaults to `"1K"`. |
| `output_format` | Optional `jpeg` \| `png` \| `webp`. Inferred from `resolution` when omitted. |
| `quality` | Optional `low` \| `medium` \| `high` for models that support it (e.g. GPT Image 2). Higher values can raise the charge. |
| `enhance_prompt` | Optional bool, default `false`. Same behavior and `x-venice-enhanced-prompt` header as `/image/edit`. |
| `disable_prompt_optimization_thinking` | Optional bool. |
| `safe_mode` | Default `true`. |

## `/image/upscale`

Upscale 2× or 4×. This endpoint has **three fields**.

> **Breaking change:** `/image/upscale` no longer accepts `enhance`,
> `enhanceCreativity`, `enhancePrompt`, or `replication`, and no longer accepts
> `scale: 1`. The enhancer knobs were replaced by a single `creativity` field
> with a much narrower range. If you are sending the old fields, drop them.

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
| `image` | base64, file upload | — | Required. Must be ≥ 65 536 px² to start, < 25 MB, and ≤ 16 777 216 px after scaling. |
| `scale` | number, 2 or 4 | 2 | Must be either `2` or `4`. `4` on large images is dynamically reduced to stay within the 16 MP output cap. |
| `creativity` | number, 0–0.02 | 0.01 | How much detail and texture the upscaler adds. Higher adds more; lower stays closer to the source. Values outside the range are clamped, so `0.5` behaves as `0.02`, not as "half creative". Nullable. |

Also available as `multipart/form-data`. Response is the upscaled image as
binary `image/png`.

## `/image/background-remove`

Produce a transparent PNG cutout. JSON and multipart are **different schemas**.

### JSON (`application/json`)

Send **exactly one** of `image` (non-empty base64) or `image_url` (URI). Not both — the spec is an `anyOf` of two closed objects.

```bash
# With base64
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image": "iVBOR..."}'

# With a URL
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/photo.jpg"}'
```

```ts
await fetch('https://api.venice.ai/api/v1/image/background-remove', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ image_url: 'https://example.com/photo.jpg' }),
})
```

### Multipart (`multipart/form-data`)

Required field `image` is a **binary file** (< 25 MB). There is no `image_url` field on this schema — do not mix a URL into the form.

```bash
curl https://api.venice.ai/api/v1/image/background-remove \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "image=@./photo.jpg"
```

Response is `image/png` with alpha channel.

## Error behavior (all four endpoints)

| Code | Cause |
|---|---|
| `400` | Bad params — image dims out of range, file too large, unknown model, unsupported aspect ratio for the model, content-policy refusal. |
| `401` | Auth failed. (Pro-gating on these paths surfaces as `400` / `402` depending on condition.) |
| `402` | Insufficient balance. Bearer: plain `{ "error": "Insufficient balance" }`. x402: `PAYMENT_REQUIRED` body + `PAYMENT-REQUIRED` header. |
| `415` | Wrong `Content-Type` (e.g. JSON sent to a multipart endpoint, or vice versa). |
| `429` | Rate limited. |
| `500` / `503` | Inference / capacity issue — retry with jitter. |

(`413` and `422` are **not** documented for these image paths in the OpenAPI spec — a `413` from the platform may still appear if you exceed ingress limits, but treat `400` / `415` as the primary failure surface.)

## Gotchas

- `/image/multi-edit` `images[]` explicitly accepts `data:image/...;base64,...` URLs or plain base64. For `/image/edit` and `/image/upscale`, send base64 as a plain string unless the docs say otherwise — if your client adds a `data:` prefix and you get a `400`, strip it.
- For multipart `/image/multi-edit`, the field name is `images` and you send **multiple parts with the same field name** — order matters (base first).
- Field-name asymmetry: `/image/edit` prefers **`model`** (`modelId` is a deprecated alias). `/image/multi-edit` accepts **only `modelId`**. Get the name right per endpoint — sending the wrong one is a `400`.
- `/image/upscale` with `scale=4` on a large input is silently clamped to stay under 16 MP.
- `creativity` on `/image/upscale` is **not** the old `enhanceCreativity` under a new name. Its usable range is 0 to 0.02, so port `enhanceCreativity: 0.5` as `creativity: 0.02` (the maximum), not as `0.5`.
- `enhance_prompt` on edit / multi-edit bills extra credits whenever a rewrite is produced. Leave it off for latency-sensitive or cost-sensitive calls.
- `safe_mode: true` can blur otherwise valid inputs if the source image trips content classifiers; switch to `false` (and handle the legal/ToS consequences yourself) when you control the input.
- `/image/background-remove` JSON is **either** `image` (base64) **or** `image_url`, not both. Multipart is a required `image` file only — `image_url` is JSON-only.
