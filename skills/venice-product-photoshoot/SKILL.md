---
name: venice-product-photoshoot
description: Product photography workflow with Venice. Use when a user has a product (a photo of it, or a clear description) and wants brand-quality shots - studio packshots on white, lifestyle scenes, flat lays, hero banners, seasonal campaigns, transparent cutouts, and sizes for marketplaces, social and web. Covers keeping the product faithful while changing the scene, edit vs multi-edit vs generate, aspect ratios per channel, upscaling final picks, and saving files. Uses venice_image_edit, venice_image_multi_edit, venice_image_remove_bg, venice_image_upscale and venice_image_generate from the Venice MCP server, or POST /image/edit, /image/multi-edit, /image/background-remove and /image/upscale.
---

# Product photoshoot with Venice

Turns one product photo into a set of on-brand shots. The product itself should stay exactly as it is; only the scene, light and framing change. Built on [`venice-create-image`](../venice-create-image/SKILL.md); request fields are in [`venice-image-edit`](../venice-image-edit/SKILL.md).

| Shot | Venice MCP tool | REST endpoint |
|---|---|---|
| Same product, new scene or background | `venice_image_edit` | `POST /api/v1/image/edit` |
| Product combined with a scene or style reference | `venice_image_multi_edit` | `POST /api/v1/image/multi-edit` |
| Transparent cutout | `venice_image_remove_bg` | `POST /api/v1/image/background-remove` |
| Final size for print or large screens | `venice_image_upscale` | `POST /api/v1/image/upscale` |
| Concept shots when there is no photo yet | `venice_image_generate` | `POST /api/v1/image/generate` |

## Use when

- A user has a product photo and wants packshots, lifestyle images or ad creatives.
- A store listing needs a clean main image plus supporting shots.
- A campaign needs the same product in several seasonal or themed scenes.

## Workflow

### 1. Collect the inputs

- **The product photo:** a public `https://` URL, or a `data:` URL for edit and multi-edit. A sharp, well-lit photo on a plain background gives the best results. Through the MCP tools, cutouts and upscales need a public URL.
- **Brand cues:** colors, mood, target customer, and any reference images whose look should be matched.
- **Where each shot goes**, which sets the aspect ratio (see below).

### 2. Pick an edit model

Edit models are listed under `venice_list_models` with `type: "inpaint"`; `venice_model_details` shows each one's aspect ratios and resolutions. Without a `model`, the edit tools use `firered-image-edit`.

### 3. Shoot the set

Edit the original photo once per shot, with an instruction that says what changes and what must not:

| Shot | Prompt pattern |
|---|---|
| Studio packshot | "Place the product on a seamless pure white background with soft, even studio lighting and a subtle shadow. Keep the product, its label and colors unchanged." |
| Lifestyle | "Put the product on a sunlit marble kitchen counter with blurred plants behind it, morning light. Keep the product unchanged." |
| Flat lay | "Top-down flat lay of the product on linen with a few matching props around it. Keep the product unchanged." |
| Hero banner | "Wide hero shot, product on the right third, clean empty space on the left for a headline, brand colors navy and coral." |
| Seasonal | "Same product in a cozy winter scene with warm string lights and soft snow outside a window. Keep the product unchanged." |

To match a specific look, use `venice_image_multi_edit` with the product photo and a style or scene reference in `image_urls`, and describe how to combine them.

### 4. Check every shot

Compare each result with the original before showing it: label text, logo, shape, color and proportions must match. Edits can drift on small text. Redo any shot that changed the product, and never present a changed product as the real one.

### 5. Size for each channel

| Channel | Aspect ratio |
|---|---|
| Marketplace main image, social square | `1:1` |
| Social feed portrait | `4:5` |
| Stories, reels, vertical ads | `9:16` |
| Website hero, banner | `16:9` or `21:9` |

Pass `aspect_ratio` on the edit when the model supports it. Check each marketplace's current rules for main images, such as background color, how much of the frame the product fills, and minimum size.

### 6. Cut out and upscale

Run `venice_image_remove_bg` for a transparent PNG to place on any background. Upscale only the final picks with `venice_image_upscale` (`scale` 2-4, low `creativity` so details stay true).

## Save files

The MCP tools return images inline. To work from a local photo and save results, call the REST endpoint from a shell with `VENICE_API_KEY` set. `jq` builds the JSON so the data URL is quoted safely:

```bash
IMG="data:image/jpeg;base64,$(base64 < product.jpg | tr -d '\n')"

jq -n --arg img "$IMG" \
  --arg prompt "Place the product on a seamless pure white background with soft studio lighting. Keep the product, its label and colors unchanged." \
  '{model: "firered-image-edit", image: $img, prompt: $prompt, output_format: "png"}' \
| curl -s https://api.venice.ai/api/v1/image/edit \
    -H "Authorization: Bearer $VENICE_API_KEY" \
    -H "Content-Type: application/json" \
    -d @- --output packshot.png
```

The edit, multi-edit, background-removal and upscale endpoints all return the image bytes, so `--output` writes the file directly.

## Cost

Every edit, cutout and upscale is billed per image. A full set (five shots, a cutout and two upscales) is eight calls; say so before starting, and upscale only the picks.

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | Image under the minimum size, an unsupported format (SVG), an unreachable URL, or an aspect ratio the model doesn't list | Use a JPEG, PNG or WebP of at least 256x256; check `venice_model_details`. |
| `413` | Image or JSON body too large | Resize the photo or host it instead of sending a `data:` URL. |
| `422` | Content policy rejection | Adjust the prompt. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- "Keep the product unchanged" in every prompt noticeably reduces drift.
- Small label text is the first thing to break. Inspect it at full size.
- `/image/edit` has no `quality` field; quality-tier models need `/image/multi-edit` with a single image.
- Cutouts are PNG; saving one as JPEG loses the transparency.
- The REST upscale endpoint takes a raw base64 `image` in JSON or a multipart file, not a URL.

## Related skills

- [`venice-create-image`](../venice-create-image/SKILL.md): the general image workflow.
- [`venice-image-edit`](../venice-image-edit/SKILL.md): edit, multi-edit, upscale and background removal fields.
- [`venice-youtube-thumbnail`](../venice-youtube-thumbnail/SKILL.md): covers and thumbnails.
