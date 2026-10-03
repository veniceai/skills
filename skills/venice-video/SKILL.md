---
name: venice-video
description: Generate videos via Venice. Covers the async /video/quote + /video/queue + /video/retrieve + /video/complete loop, text-to-video, image-to-video, first/last-frame transitions, video-to-video and upscale, audio input, reference images / videos / audio (R2V) and their per-model caps, Kling elements and scene images, Seedance source-matched edit/extend and omni_reference_task_type, H3 Max Multi-Angle camera_trajectory, and replayed async failures. POST /video/transcriptions is retired (410) — use chat completions with video_url.
---

# Venice Video

Video is **asynchronous** — like audio music. Four live endpoints plus one retired one:

| Endpoint | Purpose |
|---|---|
| `POST /video/quote` | Price in USD (no charge, no job). No API key needed, except for upscale models. |
| `POST /video/queue` | Validate, charge, and enqueue. Returns `queue_id` immediately. |
| `POST /video/retrieve` | Poll status, download `video/mp4`, or receive the job's failure. |
| `POST /video/complete` | Cleanup of the finished media. Currently rejects `queue_id`s from `/video/queue`, so use `delete_media_on_completion` on retrieve instead (see [step 4](#4-clean-up-with-videocomplete)). |
| `POST /video/transcriptions` | **Retired — always returns `410`.** See [below](#videotranscriptions-retired). |

`/video/queue`, `/video/retrieve`, and `/video/complete` accept a Bearer API key or an x402 `SIGN-IN-WITH-X` wallet header (see [`venice-x402`](../venice-x402/SKILL.md)).

## Use when

- You need text-to-video, image-to-video, first/last-frame transitions, reference-to-video (R2V), video-to-video, video upscale, or video-with-audio.
- You can tolerate async execution (seconds to several minutes depending on model, duration, and queue depth — `/video/retrieve` returns `average_execution_time` and `execution_duration` for a live estimate).
- You want to price a job precisely before committing (`/video/quote`).

Not for: understanding or summarizing an existing video — use [`venice-chat`](../venice-chat/SKILL.md) with a `video_url` content part.

## Pick a model first

Every field below is model-specific. Read the model's constraints from `GET /models?type=video` (see [`venice-models`](../venice-models/SKILL.md)) before building a request:

- `constraints.model_type` — `text-to-video`, `image-to-video` (includes R2V and transition models), or `video` (video-to-video, motion control, upscale).
- `constraints.durations`, `aspect_ratios`, `resolutions` — the exact accepted strings (case-sensitive: MiniMax H3 Max uses `480P` / `768P` / `1080P`, MiniMax H3 uses `768P` / `2K`).
- `constraints.audio_configurable` — only then may you send `audio`.
- `constraints.audio_input` — only then may you send `audio_url`.
- `constraints.prompt_character_limit` — present when the model sets its own limit; otherwise the limit is 2500 characters.

The request schema is **strict per model**: a field the model does not support is a `400` (e.g. `"This model does not support aspect_ratio"`), not silently ignored.

## Lifecycle — generation

### 1. Price with `/video/quote`

```bash
curl https://api.venice.ai/api/v1/video/quote \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan-2.6-text-to-video",
    "duration": "5s",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "audio": true
  }'
```

Response: `{"quote": 0.55}` (USD).

- Required: `model`, and `duration` for models with fixed durations.
- `resolution` and `aspect_ratio` fall back to the model default when omitted.
- The quote endpoint **discards** fields a model doesn't use (e.g. `audio` on a model with `audio_configurable: false`, `aspect_ratio` on a model with no `aspect_ratios`, unknown keys) — `/video/queue` rejects them. A successful quote does not prove the queue body is valid.
- **Upscale models** (`topaz-video-upscale`): quote requires a Bearer API key (`403` without one, so x402 wallets can't quote them — queue directly and rely on the `402` balance check) and `video_url` — Venice fetches the file to detect duration, FPS, and height (`400` if it can't read it). `duration` is ignored. Pass `upscale_factor` (`1` / `2` / `4`) to price the factor you will queue; `resolution: "1x"` / `"2x"` / `"4x"` is a deprecated alias.
- **Video-to-video models** (e.g. `wan-2-7-video-to-video`): `video_url` is required; duration is detected from the file.
- **R2V models with reference-video support** (Seedance 2.x, MiniMax H3 / H3 Max, Wan 3.0 R2V, …): pass `reference_video_total_duration` (aggregate seconds of all reference videos, capped at the model's aggregate limit — e.g. 15 for Seedance 2.0 / H3 / Wan 3.0, 30 for Seedance 2.5; over the cap is `400`). Reference video is billed, so omitting it returns the no-reference price, which under-quotes. `reference_image_count` (≤ the model's reference-image cap, else `400`) prices models billed per input image; omitted, one image is billed.

### 2. Submit with `/video/queue`

```bash
curl https://api.venice.ai/api/v1/video/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan-2.6-text-to-video",
    "prompt": "Commerce being conducted in the city of Venice, Italy.",
    "negative_prompt": "low resolution, worst quality, defects",
    "duration": "5s",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "audio": true
  }'
```

Response: `{ "model": "...", "queue_id": "uuid" }`, plus `download_url` for VPS-backed models.

- Validation and the balance check happen before the `200`; API-key callers are also charged then (x402 wallet callers are charged once the job is accepted). Content screening and the provider submit run **after** the response, so those failures are reported on `/video/retrieve`, not here. Failures are normally refunded (`credits_refunded` in the error body reports the outcome where present), with one exception: the Runway models (`runway-gen4-5`, `runway-gen4-5-text`, `runway-gen4-turbo`) keep the charge when the provider rejects the request on content policy (`credits_refunded: false`).
- `download_url` is returned for **VPS-backed** models — currently every Grok Imagine video model, including the `*-private` ids and `grok-imagine-1-5-lite-text-to-video` / `grok-imagine-1-5-lite-image-to-video`. Decide by whether the queue response contains `download_url`, not by the model id. When it does, `/video/retrieve` returns JSON status only; `GET` the `download_url` (no auth header) once status is `COMPLETED`. Valid up to 24 h.

### 3. Poll with `/video/retrieve`

```bash
curl https://api.venice.ai/api/v1/video/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"wan-2.6-text-to-video","queue_id":"...","delete_media_on_completion":false}' \
  --output out.mp4
```

Body: `model` + `queue_id` (both required), optional `delete_media_on_completion` (default `false`). No other keys are accepted.

- Processing: `200` JSON `{"status":"PROCESSING","average_execution_time":145000,"execution_duration":53200}` (ms; `average_execution_time` is a P80 estimate).
- Completed (most models): `200` binary `video/mp4` body.
- Completed (VPS-backed): `200` JSON `{"status":"COMPLETED", ...}` — fetch the `download_url` from the queue response.
- Failed: a non-`200` JSON error (see [Errors](#errors)). Terminal failures (submit failures, content-policy rejections, provider-side failures, expired media) are recorded on the job, so re-polling the same `queue_id` returns the same error. A `429` is transient — back off and poll again.
- `delete_media_on_completion: true` requests deletion of the stored output once it has been returned, replacing the separate `/video/complete` call.
- `queue_id`s are scoped to the key's user and expire after 24 h; unknown or expired ids return `400` `"Request ID is invalid."`.

### 4. Clean up with `/video/complete`

```bash
curl https://api.venice.ai/api/v1/video/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"...","queue_id":"..."}'
```

Body: `model` + `queue_id` only. Response: `200` `{"success": true}`, or `{"success": false}` if the delete did not go through. Currently it returns `400` `"Request ID is invalid."` for `queue_id`s issued by `/video/queue`, so don't rely on it: clean up by polling with `delete_media_on_completion: true`.

## `/video/queue` request fields

| Field | Type | Notes |
|---|---|---|
| `model` | string | Required. |
| `prompt` | string | Required (≥ 1 non-whitespace char) except for upscale models and `minimax-h3-max-multi-angle`. Max length per model: 2500 default; `constraints.prompt_character_limit` otherwise (from 1000 for Runway up to 20000 for Wan 3.0). |
| `negative_prompt` | string | Same max length as `prompt`. Ignored by models without negative-prompt support. |
| `duration` | string | Required, from `constraints.durations` (values span `1s`–`30s`). Upscale and video-to-video models: omit it (server detects the source length) or send seconds as a string such as `"12.5"` (≤ 300) — the literal `"Auto"` is rejected. `seedance-2-5-reference-to-video-basic` also accepts `"-1"` / `"auto"` (match the source clip). |
| `aspect_ratio` | string | **Required** when the model lists `aspect_ratios`; rejected when the list is empty (image-driven models take the ratio from the input). The Seedance 2.0 R2V `-basic` models (standard / fast / mini) and `seedance-2-5-reference-to-video-basic` also accept `adaptive` / `auto` (match the source clip). |
| `resolution` | string | From `constraints.resolutions`; defaults to the model default. Rejected when the model lists no resolutions, and on upscale models — use `upscale_factor`. |
| `upscale_factor` | integer `1` / `2` / `4` | Upscale models only. `1` = enhancement only. Defaults to the model default (`2` for `topaz-video-upscale`). |
| `audio` | bool | Only when `audio_configurable: true`; default `true`. |
| `image_url` | URL or `data:` URL | Start frame for image-to-video. Rejected on text-to-video models. |
| `end_image_url` | URL or `data:` URL | End frame, on models that support one (otherwise `400`). **Required** for transition models (`pixverse-c1-transition`, `pixverse-v5.6-transition`, `flux-3-first-last-frame-to-video`). |
| `audio_url` | URL or `data:` URL | Models with `audio_input: true`. WAV / MP3; generally ≤ 30 s and ≤ 15 MB. On Seedance 2.x R2V and MiniMax H3 R2V it is treated as one more reference audio (same per-clip limits). |
| `video_url` | URL or `data:` URL | Required for upscale and video-to-video models. MP4, MOV, WebM and other common containers. |
| `reference_image_urls[]` | URLs | R2V character / style references. Cap per model (4 if unspecified) — see [limits](#reference-media-limits). |
| `reference_video_urls[]` | URLs | R2V motion / camera / style donors (`.mp4` / `.mov`). Also the source clip for Seedance edit / extend. |
| `reference_audio_urls[]` | URLs | Voice, narration, or SFX donors (`.wav` / `.mp3`). On Seedance, reference them in the prompt as `<Audio 1>`, `<Audio 2>`. **Must be paired with at least one image or video reference** — audio-only is `400`. |
| `reference_document_urls[]` | URLs, ≤ 1 | `wan-3-0-reference-to-video` only: a document (pdf, docx, pptx, xlsx, txt, md, …; ≤ 100 MB) or public webpage. |
| `elements[]` | array, ≤ 4 | Kling O3 R2V models and `kling-v3-4k-reference-to-video` (which also requires `image_url`). Each element needs `frontal_image_url` (plus up to 3 `reference_image_urls`) or a `video_url`. Reference in the prompt as `@Element1`, `@Element2`. |
| `scene_image_urls[]` | URLs, ≤ 4 | Same models as `elements`: scene / style refs; reference as `@Image1`, `@Image2`. |
| `camera_trajectory[]` | array, 2–12 | `minimax-h3-max-multi-angle` only — see [recipe](#h3-max-multi-angle-camera-orbit). |
| `omni_reference_task_type` | `auto` / `reference` / `edit` / `extend` | `seedance-2-5-reference-to-video-basic` only (`editing` / `extension` accepted as aliases). `edit` / `extend` require `reference_video_urls`. Omitted with `reference_video_urls` present, Venice infers it from the prompt. |
| `bitrate_mode` | `standard` / `high` | Seedance 2.0 / 2.5 models (not 1.5). Default `standard`; does not change the price. |
| `image_references[]` | `{image_url, type?: subject\|background, ref_name?}` | Typed references (e.g. `pixverse-c1-reference-to-video`); reference as `@ref_name`. |
| `video_references[]` | `{video_url, ref_name?, audio_url?}` | Models with `per_reference_audio: true` (e.g. `wan-2-7-reference-to-video`): reference clips with optional per-entity voice. |
| `voice_id` | string | `grok-imagine-1-5-reference-to-video-private`: a preset Grok voice id (e.g. `eve`; an invalid id's `400` lists the allowed values); uploaded audio is not supported. |
| `consents` | object | Seedance face-consent attestation — see [Gotchas](#gotchas). Not used by any model that `/models` lists. |
| `anon_user_id` | string, ≤ 128 | Optional end-user identifier (printable ASCII, no `\|\|`). |

Every media URL must be a `data:` URL or an `http(s)://` URL on a public host — private, loopback, link-local, and cloud-metadata addresses are rejected with `400`. `bitrate_mode`, `image_references`, `video_references`, `voice_id`, and `anon_user_id` are accepted but not listed in the published OpenAPI schema.

### Reference media limits

The limits differ per model. Current caps for common R2V families (as of 2026-09-30):

| Model family | Ref images | Ref videos (per clip / total) | Ref audios (per clip / total) |
|---|---|---|---|
| `seedance-2-0-*-reference-to-video-basic` (incl. fast / mini) | 9 | 3 (2–15 s, ≤ 50 MB / 15 s) | 3 (2–15 s, ≤ 15 MB / 15 s) |
| `seedance-2-5-reference-to-video-basic` | 30 | 10 (2–30 s, ≤ 50 MB / 30 s) | 10 (2–30 s, ≤ 15 MB / 30 s) |
| `seedance-2-5-us-reference-to-video-private` | 30 | 10 (2–30 s, ≤ 200 MB / 30 s) | 10 (2–30 s, ≤ 15 MB / 30 s) |
| `wan-3-0-*reference-to-video` | 10 | 5 (1–15 s, ≤ 100 MB / 15 s) | 5 (1–15 s, ≤ 15 MB / 15 s) |
| `minimax-h3-reference-to-video`, `minimax-h3-max-reference-to-video` | 9 | 3 (2–15 s, ≤ 50 MB / 15 s) | 3 (2–15 s, ≤ 15 MB / 15 s; `audio_url` counts toward the 3) |
| `minimax-h3-enhanced-reference-to-video` | 9 | — | 3 (as above) |
| `kling-o3-{standard,pro}-reference-to-video`, `kling-v3-4k-reference-to-video` | 4 | — | — |
| `kling-o3-4k-reference-to-video`, `pixverse-c1-reference-to-video`, `grok-imagine-reference-to-video-private`, `grok-imagine-1-5-reference-to-video-private` | 7 | — | — |
| `gemini-omni-flash-1-1-reference-to-video` | 10 | — | — |
| `gemini-omni-flash-reference-to-video` | 3 | — | — |

Over-limit arrays are `400`. When a model lists `constraints.reference_image_min_aspect_ratio` / `reference_image_max_aspect_ratio` (0.4 and 2.5 on Seedance and MiniMax H3), images outside that width/height ratio are rejected; images below `reference_image_min_short_side_pixels` are upscaled automatically.

## Common recipes

### Text → video with audio

```json
{
  "model": "wan-2.6-text-to-video",
  "prompt": "A golden retriever chasing a frisbee in slow motion at sunset.",
  "duration": "10s",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "audio": true
}
```

### Image → video

```json
{
  "model": "wan-2.6-image-to-video",
  "prompt": "Camera slowly zooms out, revealing the cityscape.",
  "image_url": "https://example.com/cityscape.jpg",
  "duration": "5s",
  "resolution": "720p"
}
```

No `aspect_ratio`: this model's `aspect_ratios` list is empty, so the ratio follows the image and sending one is `400`.

### Video upscale

```json
{
  "model": "topaz-video-upscale",
  "video_url": "https://example.com/input.mp4",
  "upscale_factor": 2
}
```

No `prompt` or `duration` needed (duration is detected from the file); `resolution` is rejected. The source may be up to 300 s long.

### Multi-element consistency (Kling O3 R2V)

```json
{
  "model": "kling-o3-pro-reference-to-video",
  "prompt": "@Element1 walks toward @Element2 against @Image1.",
  "duration": "5s",
  "aspect_ratio": "16:9",
  "elements": [
    { "frontal_image_url": "https://example.com/char1.png", "reference_image_urls": ["https://example.com/alt1.png"] },
    { "frontal_image_url": "https://example.com/char2.png" }
  ],
  "scene_image_urls": ["https://example.com/street-scene.jpg"]
}
```

### Seedance 2.5 edit (match the source clip)

```json
{
  "model": "seedance-2-5-reference-to-video-basic",
  "prompt": "Strictly edit <Video 1>: make it snow, keep everything else unchanged.",
  "reference_video_urls": ["https://example.com/source.mp4"],
  "omni_reference_task_type": "edit",
  "duration": "auto",
  "aspect_ratio": "adaptive",
  "resolution": "720p"
}
```

`duration: "auto"` / `"-1"` needs a 4–30 s source clip (otherwise `400`). Quote it with the same `duration` / `aspect_ratio` plus `reference_video_total_duration` (required for source-matched quotes, otherwise `400`).

### H3 Max Multi-Angle (camera orbit)

```json
{
  "model": "minimax-h3-max-multi-angle",
  "image_url": "https://example.com/scene.jpg",
  "duration": "5s",
  "resolution": "768P",
  "camera_trajectory": [
    { "time": 0, "azimuth": 0, "elevation": 0, "distance": 1 },
    { "time": 1, "azimuth": 45, "elevation": 10, "distance": 1 }
  ]
}
```

`camera_trajectory`: 2–12 keyframes, each with exactly `time`, `azimuth`, `elevation`, `distance` (extra keys are `400`). `time` is 0–1 and strictly increasing, `azimuth` is signed degrees (total absolute travel ≤ 32 turns), `elevation` −90…90, `distance` > 0 relative to the initial camera (1 = unchanged). Omit it to let the model choose the path. `image_url` is required, `prompt` is optional, and the aspect ratio follows the image (sending `aspect_ratio` is `400`).

## `/video/transcriptions` (retired)

`POST /video/transcriptions` has been removed. Every request — authenticated or not — gets `410` with headers `Deprecation: true` and `Link: </api/v1/chat/completions>; rel="successor-version", </api/v1/models>; rel="describedby"`, and an `error` message pointing to the replacement (callers exceeding 60 requests/min per IP get `429` with the same message prefixed by `Rate limit exceeded.`).

Replacement: to analyze, summarize, or ask questions about a video (including YouTube URLs where the provider supports them), call `POST /chat/completions` with a `{"type":"video_url","video_url":{"url":"..."}}` content part on a model whose `model_spec.capabilities.supportsVideoInput` is `true` — at most 3 videos per request. See [`venice-chat`](../venice-chat/SKILL.md). For a verbatim transcript of an audio file, use [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md).

## Full polling loop

```ts
// Pass download_url from the queue response whenever it is present.
async function waitForVideo(model: string, queueId: string, downloadUrl?: string) {
  while (true) {
    const res = await fetch(`${base}/video/retrieve`, {
      method: 'POST', headers,
      body: JSON.stringify({ model, queue_id: queueId, delete_media_on_completion: true }),
    })
    const ct = res.headers.get('content-type') ?? ''
    if (res.ok && ct.startsWith('video/')) {
      return Buffer.from(await res.arrayBuffer())
    }
    const body = await res.json()
    if (!res.ok) {
      // Job failures are replayed here (e.g. 422 with credits_refunded). 429 / 502 / 503 are transient.
      if ([429, 502, 503].includes(res.status)) { await new Promise(r => setTimeout(r, 15000)); continue }
      throw new Error(`video failed (${res.status}): ${JSON.stringify(body)}`)
    }
    if (body.status === 'COMPLETED' && downloadUrl) {
      const v = await fetch(downloadUrl)
      return Buffer.from(await v.arrayBuffer())
    }
    if (body.status === 'COMPLETED') throw new Error('COMPLETED without download_url: pass download_url from the queue response')
    if (body.status !== 'PROCESSING') throw new Error(`unexpected ${body.status}`)
    await new Promise(r => setTimeout(r, 5000))
  }
}
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Invalid params (unsupported field for this model, bad enum, missing `prompt` / `image_url` / `video_url`, over-limit arrays, blocked or unreadable media URL, corrupted image). On `/video/retrieve`: `"Request ID is invalid."` for an unknown or expired `queue_id`. On `/video/complete`: the same message currently comes back for every `queue_id` issued by `/video/queue` — clean up with `delete_media_on_completion: true` instead (see [step 4](#4-clean-up-with-videocomplete)). |
| `401` | Authentication failed. |
| `402` | Insufficient balance or the API key's spend limit (checked on `/video/queue` before the charge). A wallet below the $0.10 floor gets the x402 `PAYMENT_REQUIRED` body and `PAYMENT-REQUIRED` header; a wallet above the floor but below this job's quote gets the plain `{"error":"Insufficient USD or Diem balance…"}` body with no header — top up via `/x402/top-up` and retry. |
| `403` | Model unavailable in your region, not permitted by the API key's model-privacy setting, or an unauthenticated upscale quote. |
| `404` | Model not found (any video endpoint). On `/video/retrieve`: media expired or already deleted. |
| `409` | `/video/queue` only, unlisted face-enabled Seedance models: `{"error":{"code":"needs_consent",...},"consent_flow":"seedance","face_media_roles":[...],"consent":{"consent_version","policy_text"},"docs_url"}`. |
| `410` | `/video/transcriptions` (retired). |
| `413` | Payload too large — shrink or host the media instead of inlining `data:` URLs. |
| `422` | Content policy or provider-side failure. Screening runs after the job is accepted, so these normally arrive on `/video/retrieve`: provider rejection `{"error":{"message","type":"provider_content_policy","credits_refunded",...}}` (may include `recommended_model`), or provider-side failure `{"error","credits_refunded"}` (plus `hint` when available). |
| `429` | Rate limit (`/video/queue` 40 req/min, `/video/retrieve` 120 req/min, authenticated upscale quotes 40 req/min — per user) or model overloaded. |
| `500` | Inference or internal failure. A `500` replayed by `/video/retrieve` is terminal for that `queue_id` — resubmit (after revising the prompt / media if it may have been blocked). |
| `502` | `/video/retrieve` only: the video finished but couldn't be fetched from the provider. Not recorded on the job — back off and poll again. |
| `503` | Model offline or at capacity — retry later. |

See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Gotchas

- **The quote validates less than the queue.** Quote drops unsupported fields; queue returns `400` for them. Build the queue body from `/models` constraints, not from a successful quote.
- **`aspect_ratio` is required on `/video/queue`** whenever the model lists aspect ratios, and forbidden when it lists none.
- **Queue success ≠ generation success.** Moderation and provider errors surface on `/video/retrieve`, with the refund status in `credits_refunded` where present. Always handle non-`200` retrieve responses. Runway content-policy rejections are not refunded.
- `download_url` is **only** returned for VPS-backed models (the Grok Imagine models) — check for the field, not the id. Handle both paths: binary from `/video/retrieve`, or `GET download_url` after `COMPLETED`. It expires within 24 h — download promptly.
- Upscale models use `upscale_factor`, never `resolution` (queue rejects `resolution`; quote accepts `1x` / `2x` / `4x` only as a deprecated alias).
- `GET /models` lists `"Auto"` as the duration for most upscale and video-to-video models, but `/video/queue` rejects the literal `"Auto"` — omit `duration` instead.
- **Seedance naming**: the listed Seedance ids end in `-basic` (e.g. `seedance-2-0-text-to-video-basic`), plus the separate `seedance-2-5-us-*-private` family. Neither uses `consents` / `needs_consent`, and media showing identifiable people may be rejected upstream. The face-consent flow (`consents.seedance` with `confirmed_terms_and_privacy`, `confirmed_legal_right`, `confirmed_screening_acknowledged` all `true`, resubmitted after a `409`) applies only to unlisted Seedance ids that `/models` does not return.
- Seedance source-matched values: `aspect_ratio: "adaptive"` / `"auto"` works on the `-basic` Seedance 2.0 / 2.5 R2V models, `duration: "-1"` / `"auto"` only on `seedance-2-5-reference-to-video-basic`. Both require `reference_video_urls` on queue and `reference_video_total_duration` on quote. The `seedance-2-5-us-*-private` models don't support them (`adaptive` is `400`, `auto` is an ordinary ratio option there). Elsewhere `"auto"` is also just an ordinary aspect-ratio option (e.g. Flux 3).
- MiniMax H3 and H3 Max reference-to-video models reject `image_url` / `end_image_url` combined with reference media, and count `audio_url` toward the reference-audio cap.
- `data:` URLs count toward payload size; large base64 videos can trip `413` — prefer hosted URLs.
- Prices are dynamic (resolution, duration, audio, reference media, promotions) — always quote; don't hard-code.
