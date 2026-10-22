---
name: venice-youtube-thumbnail
description: Thumbnail and cover workflow with Venice. Use when a user needs a YouTube thumbnail, a podcast or video cover, or a vertical cover for Shorts, Reels or TikTok. Covers a truthful concept from the video's actual topic, 16:9 and 9:16 framing, leaving room for a headline, in-image text vs adding text afterwards, using a real person's face only from their own photo, generating and comparing variants, focused edits, and saving at the right size. Uses venice_image_generate, venice_image_edit and venice_image_multi_edit from the Venice MCP server, or POST /image/generate and /image/edit.
---

# Thumbnails and covers with Venice

A thumbnail has one job: show, honestly and at a glance, what the video is about. This workflow produces a few strong options, then refines the winner. Built on [`venice-create-image`](../venice-create-image/SKILL.md).

| Step | Venice MCP tool | REST endpoint |
|---|---|---|
| Generate concepts | `venice_image_generate` | `POST /api/v1/image/generate` |
| Refine one concept | `venice_image_edit` | `POST /api/v1/image/edit` |
| Put the creator's own photo into a scene | `venice_image_multi_edit` | `POST /api/v1/image/multi-edit` |
| Find models that handle text and faces well | `venice_list_models`, `venice_model_details` | `GET /api/v1/models` |

## Use when

- A video needs a thumbnail, or a channel needs a consistent thumbnail style.
- A podcast, course or Shorts series needs covers.
- A user wants several options to A/B test.

## Workflow

### 1. Start from the video, not the clickbait

Ask what the video actually shows and what the viewer gets. The thumbnail should promise only that. Pick one idea: a result, a contrast (before and after), a question, or an emotion. Avoid images of things that never happen in the video.

### 2. Decide the format

| Placement | Aspect ratio |
|---|---|
| YouTube video thumbnail | `16:9` (commonly 1280x720) |
| Shorts, Reels, TikTok cover | `9:16` |
| Podcast or course cover | `1:1` |

Check the platform's current upload limits, such as maximum file size and minimum width, before delivering.

### 3. Decide how to handle text

Keep any headline to three to five words.

- **In the image:** pick a model that renders text well (compare candidates with `venice_list_models` and `venice_model_details`), put the exact words in quotes in the prompt, and check the spelling in every result.
- **Added afterwards:** ask the model to leave clean space for the headline ("empty area on the left third for a title"), then add the text in a design tool. This is the safer choice for exact fonts and spelling.

### 4. Faces

Only show a real person if the user provides their own photo or has that person's permission. Put them into the scene with `venice_image_multi_edit` (their photo plus a scene description) or `venice_image_edit` on their photo, and keep their likeness faithful. Do not generate look-alikes of public figures.

### 5. Generate options

Call `venice_image_generate` with the concept, the aspect ratio and `variants: 3` or `4` to compare directions in one call. Thumbnails are viewed small, so ask for a bold subject, strong contrast, a clean background and no clutter.

### 6. Refine and check

Use `venice_image_edit` for focused changes ("make the background darker", "increase contrast on the face", "remove the extra object on the right"). Then view the image at a small size: if the idea is not clear at a glance, simplify it.

## Save files

The MCP tools return images inline. To save a thumbnail to disk, call the REST endpoint with `VENICE_API_KEY` set:

```bash
curl -s https://api.venice.ai/api/v1/image/generate \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "flux-2-pro",
    "prompt": "Bold YouTube thumbnail: a cracked smartphone on the left, the same phone repaired and glowing on the right, high contrast, clean dark background, empty space at the top for a title",
    "aspect_ratio": "16:9",
    "format": "jpeg",
    "return_binary": true
  }' --output thumbnail.jpg
```

With `return_binary: true` the response body is the image, so `--output` writes it directly. Variants need `return_binary: false`; see [`venice-create-image`](../venice-create-image/SKILL.md#save-files).

## Cost

Each variant and each edit is billed as one image. Three to four concepts and one or two edits is usually enough.

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | An aspect ratio the model doesn't list, or `variants` with `return_binary: true` | Check `venice_model_details`; use JSON responses for variants. |
| `422` | Content policy rejection | Rework the concept. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- Misspelled text is the most common failure; always proofread in-image text.
- Small details disappear at thumbnail size. One subject and one idea.
- Keep a channel's thumbnails consistent by reusing the same style words, palette and, where it helps, a `seed`.
- Do not imply the video contains something it doesn't.

## Related skills

- [`venice-create-image`](../venice-create-image/SKILL.md): the general image workflow.
- [`venice-image-generate`](../venice-image-generate/SKILL.md): every generation field.
- [`venice-image-edit`](../venice-image-edit/SKILL.md): edit and multi-edit fields.
