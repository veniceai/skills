---
name: venice-video
description: Generate and transcribe videos via Venice. Covers the async /video/quote + /video/queue + /video/retrieve + /video/complete loop, text-to-video, image-to-video, video-to-video (upscale), audio input, reference images, reference video and reference audio (R2V), scene and element support, H3 Max Multi-Angle camera_trajectory, plus /video/transcriptions for YouTube URLs.
---

# Venice Video

Video is **asynchronous** — like audio music. Five endpoints:

| Endpoint | Purpose |
|---|---|
| `POST /video/quote` | Price in USD (no charge, no job). |
| `POST /video/queue` | Enqueue generation. Returns `queue_id`, charges (reserves) funds. |
| `POST /video/retrieve` | Poll status or download `video/mp4`. |
| `POST /video/complete` | Finalize & delete media from Venice storage. |
| `POST /video/transcriptions` | Sync: transcribe a YouTube URL's audio. |

## Use when

- You need text-to-video, image-to-video, video upscale, video-with-audio, or video transcription.
- You can tolerate async execution (single-digit seconds to several minutes depending on model, duration, and queue depth — inspect `average_execution_time` and `execution_duration` on `/video/retrieve` for your job's live estimate).
- You want to price a job precisely before committing (`/video/quote`).

## Lifecycle — generation

### 1. Price with `/video/quote`

```bash
curl https://api.venice.ai/api/v1/video/quote \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan-2-7-text-to-video",
    "duration": "5s",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "audio": true
  }'
```

Response: `{"quote": 0.35}` USD.

`/video/quote` requires `model` and `duration`. It also takes `resolution`
(required for models priced by duration × resolution × rate), `upscale_factor`
and `video_url` for upscale models (`video_url` lets Venice auto-detect the
source duration), and `reference_video_total_duration` for reference-to-video
models — the aggregate seconds of every reference video you intend to send, up
to 45. Quote a reference-video job without it and you get the no-reference
baseline price. For upscale models, `upscale_factor` is `1`, `2`, or `4` and
the quote bills the output tier of source height × factor. It defaults to the
model's default factor when omitted.

### 2. Submit with `/video/queue`

```bash
curl https://api.venice.ai/api/v1/video/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan-2-7-text-to-video",
    "prompt": "Commerce being conducted in the city of Venice, Italy.",
    "negative_prompt": "low resolution, worst quality, defects",
    "duration": "5s",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "audio": true
  }'
```

Response: `{ "model": "...", "queue_id": "uuid", "download_url": "https://..." }`.

- `download_url` only appears for **VPS-backed** models. When present, the retrieve endpoint returns JSON status only — fetch this URL to download. Valid 24 h.

### 3. Poll with `/video/retrieve`

```bash
curl https://api.venice.ai/api/v1/video/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"...","queue_id":"..."}' \
  --output out.mp4
```

- Processing: JSON `{"status":"PROCESSING","average_execution_time":145000,"execution_duration":53200}` (ms).
- Completed (non-VPS): binary `video/mp4` body.
- Completed (VPS-backed): `{"status":"COMPLETED", ...}` — fetch the `download_url` from the queue response.
- `delete_media_on_completion: true` auto-deletes after successful retrieve.

### 4. Finalize with `/video/complete`

```bash
curl https://api.venice.ai/api/v1/video/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"...","queue_id":"..."}'
```

## `QueueVideoRequest` fields

Availability depends on the model — check `GET /models?type=video`.

| Field | Type | Notes |
|---|---|---|
| `model` | string | Required. |
| `prompt` | string, min 1, ≤ 20000 | Required for most models; **optional for H3 Max Multi-Angle**. Schema max is 20000; most models cap near 2500 (`prompt_character_limit` on `GET /models?type=video`). |
| `negative_prompt` | string, ≤ 2500–3500 | — |
| `duration` | enum `1s..16s` in 1s steps, plus `18s`, `20s`, `25s`, `30s`, `1 gen`, `Auto` | Required. Model-specific subset. `1 gen` means one generation unit for models priced per generation rather than per second. |
| `aspect_ratio` | `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9`, `21:9` | Some models ignore. |
| `resolution` | `256p..4k`, or upscale hints `2x` / `4x` / `true_1080p` | Use `upscale_factor` for upscale models. |
| `upscale_factor` | `1` / `2` / `4` | Only for upscale models. `1` = quality enhancement. |
| `audio` | bool | Default `true`. Audio-capable models. |
| `image_url` | URL or `data:` URL | Image-to-video reference frame. Required for `camera_trajectory`. |
| `camera_trajectory` | array, 2–12 objects | H3 Max Multi-Angle only. Each item requires `time` (0–1, strictly increasing), `azimuth` (degrees, signed; total absolute travel at most 32 turns), `elevation` (−90 to 90), `distance` (positive; `1` = unchanged). Requires `image_url`; aspect ratio follows that image. Omit to leave the camera path to the model. Resolve the current Multi-Angle model ID via `GET /models?type=video`. |
| `end_image_url` | URL or data URL | End frame / transition reference. |
| `audio_url` | URL or data URL | Background music input. WAV/MP3, ≤ 30 s, ≤ 15 MB. |
| `video_url` | URL or data URL | Video-to-video / upscale input. MP4/MOV/WebM. |
| `reference_image_urls[]` | array of URLs, ≤ 9 | Character / style consistency images. |
| `reference_video_urls[]` | array of URLs, ≤ 3 | Reference-to-video models (e.g. Seedance 2.0 R2V). Inherits subject motion, camera movement, and style. Per clip 2–15 s, `.mp4` or `.mov`, ≤ 50 MB; aggregate ≤ 15 s. |
| `reference_audio_urls[]` | array of URLs, ≤ 3 | Donor audio for vocal timbre, narration, or sound effects. Per clip 2–15 s, `.wav` or `.mp3`; aggregate ≤ 15 s. **Must be paired with at least one reference image or reference video** — audio-only Reference workflows are rejected at validation. |
| `consents` | object | Provider-specific consent attestations. Seedance requires consent only when the submitted media contains faces. |
| `elements[]` | array, ≤ 4 | Advanced models (e.g. Kling O3 R2V): each has `frontal_image_url`, up to 3 `reference_image_urls`, `video_url`. Reference in prompt as `@Element1`, `@Element2`. |
| `scene_image_urls[]` | array of URLs, ≤ 4 | Advanced scene refs; reference in prompt as `@Image1`, `@Image2`. |

## Common recipes

### Text → video with audio

```json
{
  "model": "wan-2-7-text-to-video",
  "prompt": "A golden retriever chasing a frisbee in slow motion at sunset.",
  "duration": "6s",
  "aspect_ratio": "16:9",
  "resolution": "720p",
  "audio": true
}
```

### Image → video

```json
{
  "model": "<image-to-video model>",
  "prompt": "Camera slowly zooms out, revealing the cityscape.",
  "image_url": "https://example.com/cityscape.jpg",
  "duration": "5s",
  "aspect_ratio": "16:9"
}
```

### H3 Max Multi-Angle camera path

```bash
curl https://api.venice.ai/api/v1/video/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<H3 Max Multi-Angle id from GET /models?type=video>",
    "image_url": "https://example.com/subject.jpg",
    "duration": "6s",
    "camera_trajectory": [
      {"time": 0, "azimuth": 0, "elevation": 0, "distance": 1},
      {"time": 1, "azimuth": 45, "elevation": 10, "distance": 1}
    ]
  }'
```

```ts
await fetch('https://api.venice.ai/api/v1/video/queue', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: multiAngleModelId, // from GET /models?type=video
    image_url: 'https://example.com/subject.jpg',
    duration: '6s',
    camera_trajectory: [
      { time: 0, azimuth: 0, elevation: 0, distance: 1 },
      { time: 1, azimuth: 45, elevation: 10, distance: 1 },
    ],
  }),
})
```

`prompt` may be omitted on this model. `camera_trajectory` without `image_url` is rejected. Do not send `aspect_ratio` — it follows the image.

### Video upscale

```json
{
  "model": "<upscale model>",
  "video_url": "data:video/mp4;base64,...",
  "upscale_factor": 2,
  "duration": "Auto"
}
```

### Multi-element consistency (Kling O3 R2V-style)

```json
{
  "model": "<advanced-model>",
  "prompt": "@Element1 walks toward @Element2 against @Image1.",
  "elements": [
    { "frontal_image_url": "<char1.png>", "reference_image_urls": ["<alt1.png>"] },
    { "frontal_image_url": "<char2.png>" }
  ],
  "scene_image_urls": ["<street-scene.jpg>"]
}
```

## `/video/transcriptions` (sync)

Transcribe a YouTube video URL directly — no queue.

```bash
curl https://api.venice.ai/api/v1/video/transcriptions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=...","response_format":"json"}'
```

Response: `{"transcript":"...","lang":"en"}` (JSON) or plain `text/plain` body when `response_format: text`.

For arbitrary audio files, use [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md) instead.

## Full polling loop

```ts
async function waitForVideo(model: string, queueId: string, downloadUrl?: string) {
  while (true) {
    const res = await fetch(`${base}/video/retrieve`, {
      method: 'POST', headers,
      body: JSON.stringify({ model, queue_id: queueId }),
    })
    const ct = res.headers.get('content-type') ?? ''
    if (ct.startsWith('video/')) {
      return Buffer.from(await res.arrayBuffer())
    }
    const body = await res.json()
    if (body.status === 'COMPLETED' && downloadUrl) {
      const v = await fetch(downloadUrl)
      return Buffer.from(await v.arrayBuffer())
    }
    if (body.status !== 'PROCESSING') throw new Error(`unexpected ${body.status}`)
    await new Promise(r => setTimeout(r, 5000))
  }
}
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad params (duration/resolution not supported by model, missing required `image_url` for i2v or `camera_trajectory`, missing `prompt` on models that still require it, malformed trajectory, etc.). |
| `401` | Auth / Pro-only. |
| `402` | Insufficient balance. |
| `403` | Model unavailable in your region. |
| `413` | Request payload too large — shrink images / audio. (Returned from `/video/queue`.) |
| `422` | Content policy violation. (Returned from `/video/queue`.) |
| `500` | Inference failed. |
| `503` | Model at capacity — retry later. **On `/video/retrieve`**, returned when the queue is backed up. |

`/video/queue` does not document `503` in the spec — upstream capacity issues surface there as `500`. Watch for `503` specifically on `/video/retrieve`.

## Gotchas

- **`duration` is required on `/video/queue`.** Even `Auto` is a valid explicit value.
- `prompt` is optional only for H3 Max Multi-Angle. Every other `/video/queue` model still requires a non-empty prompt.
- `camera_trajectory` requires `image_url`. Aspect ratio is taken from that image. Keyframe `time` values must be strictly increasing in `[0, 1]`.
- `download_url` is **only sometimes** returned at queue time. Always handle both paths: binary from `/retrieve` OR fetching `download_url` after status `COMPLETED`.
- `download_url` expires in 24 h — download promptly.
- Upscale models use `upscale_factor` *instead of* `resolution`.
- `reference_image_urls[]` is capped at 9 entries, `reference_video_urls[]` and `reference_audio_urls[]` at 3 each, `elements[]` at 4, `scene_image_urls[]` at 4. Over-limit is `400`.
- Quote reference-video jobs with `reference_video_total_duration` (aggregate seconds of all reference videos). It switches the quote to the provider's "input with video" rate tier and the `(input + output) × pixels` token formula. Omit it and you get the no-reference baseline, which will under-quote the job.
- `data:` URLs count toward payload size; large base64 videos may trip `413` — prefer hosted URLs.
- `/video/transcriptions` is YouTube-URL-only; it does not accept arbitrary video uploads (use ffmpeg to strip audio, then `/audio/transcriptions`).
