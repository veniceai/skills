---
name: venice-create-video
description: End-to-end video creation workflow with Venice. Use when a user wants a finished clip - "make a 5 second product teaser", "animate this image", "turn this still into a loop". Covers choosing text-to-video vs image-to-video, reading a model's durations, aspect ratios, resolutions and audio support from the live catalog, quoting the price and confirming before spending, queuing, polling at the right interval, download_url results, cleanup with delete_media_on_completion, saving the MP4, and refunds. Uses the Venice MCP tools (venice_video_quote, venice_video_generate, venice_video_status, venice_list_models, venice_model_details) when available, or the /video/quote, /video/queue and /video/retrieve endpoints otherwise.
---

# Create videos with Venice

A workflow for going from an idea to a finished MP4. Video generation is asynchronous and priced per clip, so this workflow always quotes before it queues. Every field is documented in [`venice-video`](../venice-video/SKILL.md).

| Step | Venice MCP tool | REST endpoint |
|---|---|---|
| Find models and their limits | `venice_list_models` (`type: "video"`), `venice_model_details` | `GET /api/v1/models?type=video` |
| Price the clip | `venice_video_quote` | `POST /api/v1/video/quote` |
| Queue the job | `venice_video_generate` | `POST /api/v1/video/queue` |
| Poll, then collect the result | `venice_video_status` | `POST /api/v1/video/retrieve` |

## Use when

- The user wants a video clip generated from a text idea or from an image.
- You need to compare a couple of models or lengths on price before committing.
- A still image (generated with [`venice-create-image`](../venice-create-image/SKILL.md) or supplied) should become the first frame of a clip.

## Workflow

### 1. Pin down the brief

Ask for: what happens in the shot, how long, where it will be shown (which sets the aspect ratio: `16:9` for web, `9:16` for vertical social), whether it needs sound, and whether there is a starting image. One clear action per clip works better than a sequence of events; plan longer stories as several clips.

### 2. Pick a model

Call `venice_list_models` with `type: "video"`. Text-to-video and image-to-video are separate model ids (for example `...-text-to-video` and `...-image-to-video`). Then call `venice_model_details` with `type: "video"` and read:

- `durations`: the exact strings `duration` accepts, such as `"5s"`. It is required.
- `aspect_ratios`: required when the list is non-empty, rejected when it is empty.
- `resolutions`, and whether `audio` is configurable.
- the prompt character limit.

Each model rejects fields it does not support with a `400`, so build the request from these lists, not from memory.

### 3. Quote and confirm

Call `venice_video_quote` with `model` and `duration`. It returns the price in USD and costs nothing. Tell the user the price and get a yes before queuing, especially for long clips, high resolutions or several takes.

The MCP quote tool prices by model and duration. If resolution or audio changes the price for that model, quote through `POST /api/v1/video/quote` with those fields too.

### 4. Queue

Call `venice_video_generate` with `model`, `prompt`, `duration`, and `aspect_ratio` when the model requires it. Optional: `resolution`, `audio`, `negative_prompt`, `seed`.

- **Image-to-video:** pass the first frame as `image_url` (a public URL or a `data:` URL). Some models also take `end_image_url` for a transition between two frames.
- The response contains a `queue_id`. Keep it with the `model`; you need both to poll.
- Some models also return a `download_url` here. Keep it: those models deliver the finished video through that link instead of in the status response.

### 5. Poll

Call `venice_video_status` with `queue_id` and `model`.

- While it says `PROCESSING`, it reports `average_execution_time` and `execution_duration` in milliseconds. Use them to tell the user roughly how long is left, and to space your polls: every 10-20 seconds is plenty.
- When it completes, the result is either an embedded MP4 or a `download_url` link. A link is valid for up to 24 hours.
- A failure is final for that `queue_id`; polling again returns the same error. Most failures are refunded automatically.

### 6. Clean up and deliver

On the final status call for an embedded result, pass `delete_media_on_completion: true` so Venice deletes its stored copy once the video is returned. For a `download_url` result, download the file first, then clean up. Do not rely on a separate complete call for cleanup: `/video/complete` currently rejects ids issued by `/video/queue`.

Tell the user the model, prompt, duration and seed so the clip can be reproduced.

## Save files

The MCP tools return the video inline. To save it to disk, poll from a shell with the user's key in `VENICE_API_KEY`; the completed response body is the MP4:

```bash
curl -s https://api.venice.ai/api/v1/video/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"wan-2.6-text-to-video","queue_id":"<queue_id>","delete_media_on_completion":true}' \
  --output clip.mp4

file clip.mp4   # "ISO Media" means the video; JSON text means it is still processing
```

For models that returned a `download_url`, `GET` that URL without an auth header once the status is `COMPLETED`.

## Cost

Video is the most expensive thing Venice generates, and the charge happens when the job is queued. Quote first, confirm, and avoid "just try another take" loops without telling the user each take is billed. Failed jobs are normally refunded; content-policy rejections on some providers are not (see [`venice-video`](../venice-video/SKILL.md)).

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | A field the model doesn't support, a `duration` or `aspect_ratio` not in its lists, an unreachable image URL, or an unknown or expired `queue_id` | Re-read `venice_model_details`; ids expire after 24 hours. |
| `402` | Insufficient balance | Tell the user; don't retry. |
| `422` | Content policy rejection, before or after queuing | Rephrase; don't resubmit the same prompt. |
| `429` | Rate limit while queuing or polling | Back off, then poll again. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- `duration` is a string from the model's list (`"5s"`), not a number of seconds.
- A successful quote does not validate the queue request: the quote ignores fields the model doesn't use, while the queue rejects them.
- Content screening runs after queuing, so a policy rejection can show up on the first status poll rather than on the queue call.
- Text-to-video models reject `image_url`; use the image-to-video variant of the model.
- Polling doesn't start a new job, but status calls are rate limited (120 a minute per user). Space them out.

## Related skills

- [`venice-video`](../venice-video/SKILL.md): every queue field, reference media, upscale and video-to-video.
- [`venice-create-image`](../venice-create-image/SKILL.md): make the first frame for image-to-video.
- [`venice-models`](../venice-models/SKILL.md): reading model constraints.
- [`venice-errors`](../venice-errors/SKILL.md): error shapes and retries.
