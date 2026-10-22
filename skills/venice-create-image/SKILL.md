---
name: venice-create-image
description: End-to-end image creation workflow with Venice. Use when a user wants finished images, not API docs - "make me a logo", "generate a hero image", "create 4 variations". Covers turning a brief into a prompt, picking a model and its aspect ratios from the live catalog, style presets and style references, variants and seeds, iterating with edit and multi-edit, upscaling, background removal, saving files to disk, and cost. Uses the Venice MCP tools (venice_image_generate, venice_image_edit, venice_image_multi_edit, venice_image_upscale, venice_image_remove_bg, venice_image_styles, venice_list_models, venice_model_details) when available, or POST /image/generate and the /image/* edit endpoints otherwise.
---

# Create images with Venice

A workflow for going from a brief to finished image files. It sits on top of the reference skills: [`venice-image-generate`](../venice-image-generate/SKILL.md) and [`venice-image-edit`](../venice-image-edit/SKILL.md) document every field.

| Step | Venice MCP tool | REST endpoint |
|---|---|---|
| Find models and their limits | `venice_list_models` (`type: "image"`), `venice_model_details` | `GET /api/v1/models?type=image` |
| List style presets | `venice_image_styles` | `GET /api/v1/image/styles` |
| Generate | `venice_image_generate` | `POST /api/v1/image/generate` |
| Edit one image | `venice_image_edit` | `POST /api/v1/image/edit` |
| Combine several images | `venice_image_multi_edit` | `POST /api/v1/image/multi-edit` |
| Upscale 2x-4x | `venice_image_upscale` | `POST /api/v1/image/upscale` |
| Cut out the background | `venice_image_remove_bg` | `POST /api/v1/image/background-remove` |

Prefer the MCP tools when they are connected: they return images inline so you and the user can review them. Use the REST endpoints when you need the files on disk (see [Save files](#save-files)).

## Use when

- The user wants images produced, reviewed and refined in the conversation.
- You need several on-brand variations to choose from.
- A generated or supplied image needs edits, a transparent cutout, or a higher resolution.

## Workflow

### 1. Pin down the brief

Ask only for what changes the result: subject, style or mood, where it will be used (which sets the aspect ratio), how many options, and any text that must appear in the image. Turn the answers into one concrete prompt: subject first, then setting, lighting, composition and style. Put things to avoid in `negative_prompt`, not in the prompt.

### 2. Pick a model

Call `venice_list_models` with `type: "image"`. Each entry includes capabilities, traits and pricing. Then call `venice_model_details` with the chosen `model_id` and `type: "image"` to read its constraints: supported aspect ratios and resolutions, whether it takes `negative_prompt`, steps, and its style-reference limit.

- Without a `model`, the MCP tool uses its default (`flux-2-pro`).
- Text rendering, photorealism and stylized art vary a lot between models. Pick by the brief, and say which model you used.
- Do not guess `aspect_ratio` or `resolution` values; use the ones `venice_model_details` lists.

### 3. Choose a look

- **Style preset:** `venice_image_styles` lists names for `style_preset`. Offer two or three that fit the brief.
- **Style references:** to match existing artwork, pass image URLs in `style_references` on models that support them (check the model's style-reference limit).

### 4. Generate

Call `venice_image_generate` with `prompt`, `model`, `aspect_ratio` (or `width`/`height`), and optionally `style_preset`, `negative_prompt`, `seed` and `variants`.

- `variants` (1-4) returns several options in one call. Each variant is billed as one image.
- Only the first variant uses your `seed`. To reproduce a result exactly, regenerate with the same `seed` and `variants: 1`.
- Keep `safe_mode` on unless the user explicitly wants otherwise and the model allows it.

### 5. Review and refine

Show the results and ask what to change. Then pick the smallest operation that gets there:

| Request | Tool | Notes |
|---|---|---|
| Change one thing ("make the sky orange", "remove the cup") | `venice_image_edit` | Pass `image_url` and an instruction-style `prompt`. |
| Put elements from several images together | `venice_image_multi_edit` | Pass `image_urls` and a `prompt` describing the composition. |
| Transparent PNG for a logo, sticker or product | `venice_image_remove_bg` | |
| Print or large-display size | `venice_image_upscale` | `scale` 2-4. Keep `creativity` low to stay faithful. |
| Start over with a different idea | `venice_image_generate` | Change the prompt, not just the seed. |

Edit and multi-edit use their own models, listed by `venice_list_models` with `type: "inpaint"` (default `firered-image-edit`).

Image inputs must be reachable by Venice: a public `https://` URL, or for edit and multi-edit, a `data:` URL. Through the MCP tools, upscale and background removal need a public `http(s)://` URL. Local file paths are not accepted.

### 6. Deliver

Tell the user which model, prompt, seed and style you used so they can reproduce the image, and save the final files where they asked.

## Save files

The MCP tools return images inline, which is right for review but does not write files. To save to disk, call the REST endpoint from a shell with the user's key in `VENICE_API_KEY`:

```bash
curl -s https://api.venice.ai/api/v1/image/generate \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flux-2-pro",
    "prompt": "Minimal flat logo of a lighthouse, navy and coral, white background",
    "aspect_ratio": "1:1",
    "format": "png",
    "variants": 2
  }' | jq -r '.images | to_entries[] | "\(.key + 1) \(.value)"' \
  | while read -r n b64; do printf '%s' "$b64" | base64 -d > "logo-$n.png"; done
```

The edit, multi-edit, upscale and background-removal endpoints return the image bytes directly, so `--output result.png` is enough. See [`venice-image-edit`](../venice-image-edit/SKILL.md) for their request bodies.

## Cost

Every generated image and every variant is billed, and so is every edit, upscale and cutout. The pricing for each model is in `venice_list_models`. Before a large batch, tell the user how many images you are about to create and on which model.

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | Unsupported `aspect_ratio`, `resolution` or field for this model, or an unreachable image URL | Re-read `venice_model_details`; make sure input URLs are public. |
| `402` | Insufficient balance | Tell the user; don't retry. |
| `422` | Content policy rejection | Rephrase the prompt; don't retry it unchanged. |
| `429` | Rate limit | Wait and retry with backoff. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- `variants` only works with JSON responses, not `return_binary: true`.
- Aspect ratios and resolutions are model-specific. A value one model accepts can be a `400` on another.
- Edits work best with instructions ("replace X with Y") rather than a full description of the new image.
- Upscaled output is capped at 4096x4096; large inputs are scaled down first.
- A transparent cutout is a PNG. Converting it to JPEG drops the transparency.

## Related skills

- [`venice-image-generate`](../venice-image-generate/SKILL.md): every `/image/generate` field and response header.
- [`venice-image-edit`](../venice-image-edit/SKILL.md): edit, multi-edit, upscale and background removal in detail.
- [`venice-models`](../venice-models/SKILL.md): reading the model catalog.
- [`venice-errors`](../venice-errors/SKILL.md): error shapes and retries.
