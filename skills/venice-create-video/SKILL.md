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
- When it completes, the result is either an embedded MP4 or a `download_url` link.
- A failure is final for that `queue_id`; polling again returns the same error. Most failures are refunded automatically.

### 6. Clean up and deliver

Cleanup works through `POST /video/retrieve` only. With `delete_media_on_completion: true` on that call, Venice deletes its stored copy once the video has been returned, so send it on every REST poll ([Save files](#save-files) does), not only the last one; it is safe while the job is still processing.

The MCP tool doesn't honor the flag. `venice_video_status` always retrieves without it, then tries to delete through `/video/complete`, which currently rejects ids issued by `/video/queue`. Ignore its suggestion to call `venice_video_complete`, which fails the same way. To remove a video you fetched through the MCP tool, retrieve it once more over REST with the flag.

A `download_url` result has nothing to clean up and nothing else to call. Download the file right away, because the link expires within 24 hours.

Tell the user the model, prompt, duration and seed so the clip can be reproduced.

## Save files

The MCP tools return the video inline. To save it to disk, poll from a shell with the user's key in `VENICE_API_KEY`. Only a `200` with a `video/` content type is the MP4. A job that is still processing, a finished `download_url` model and a failed job all return JSON, so check both before keeping the file:

```bash
result=$(curl -sS https://api.venice.ai/api/v1/video/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"wan-2.6-text-to-video","queue_id":"<queue_id>","delete_media_on_completion":true}' \
  --output clip.mp4 -w '%{http_code} %{content_type}')

case "$result" in
  "200 video/"*)  echo "saved clip.mp4" ;;
  "200 "*)        cat clip.mp4; rm -f clip.mp4 ;;  # PROCESSING, or COMPLETED for a download_url model
  429*|502*|503*) rm -f clip.mp4; echo "busy, poll again later" ;;
  *)              cat clip.mp4; rm -f clip.mp4 ;;  # failed: stop polling, every poll returns this error
esac
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
