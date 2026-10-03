---
name: venice-audio-voice-changer
description: Async speech-to-speech voice conversion via Venice — re-record a source recording in a different voice while keeping delivery and timing. Covers POST /audio/voice-changer/quote (unauthenticated), /queue (multipart file or JSON audio_url), /retrieve and /complete, how to discover voice-changer models (model_spec.voice_changer on /models?type=music), accepted formats, the source-length cap, whole-minute billing, refunds, and what each endpoint refuses. Note that no voice-changer model is currently open to regular API keys.
---

# Venice Voice Changer (`/audio/voice-changer/*`)

Speech-to-speech conversion: upload a recording, get the same speech back in a different voice, with the original pacing, emotion and timing preserved. It's asynchronous, with its own quote → queue → retrieve → complete family (parallel to, but separate from, [`venice-audio-music`](../venice-audio-music/SKILL.md)).

> **Availability (checked 2026-09-30):** the endpoints are in the public API spec, but the only voice-changer model, `elevenlabs-voice-changer`, is not yet open to regular API keys. It is not listed by `GET /models`, and regular keys (or no key) get `404 "Specified model not found"` from every endpoint below. Before using this skill, confirm that a model with `model_spec.voice_changer: true` shows up in `GET /models?type=music` for your key; if none does, the feature isn't available to you.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/audio/voice-changer/quote` | **None required** (key optional) | Price for a source of N seconds. |
| `POST` | `/api/v1/audio/voice-changer/queue` | Bearer key or x402 (SIWX) | `multipart/form-data` (`file`) **or** JSON (`audio_url`). Charges and enqueues. 40 req/min per user. |
| `POST` | `/api/v1/audio/voice-changer/retrieve` | Bearer key or x402 (SIWX) | Status JSON or the converted audio. 120 req/min per user. |
| `POST` | `/api/v1/audio/voice-changer/complete` | Bearer key or x402 (SIWX) | Release the provider-held media. |

Each endpoint only accepts voice-changer models (`400` otherwise, naming the endpoint to use instead), and `/audio/quote`, `/audio/queue`, `/audio/retrieve`, `/audio/complete` refuse voice-changer models the same way.

## Use when

- You have a real recording (voice-over, dialogue, a take) and want it in another voice without re-performing it.
- You want to keep the timing of the original exactly — e.g. dubbing against picture.

For text → speech use [`venice-audio-speech`](../venice-audio-speech/SKILL.md); to create a reusable voice from a sample, see voice cloning there.

## Discover models

There is no `?type=voice-changer` filter. Voice-changer models are music-type models whose `model_spec` carries:

| Field | Meaning |
|---|---|
| `voice_changer` | `true` on voice-changer models only. |
| `accepted_audio_formats` | Containers accepted for the source, judged from the file's bytes (not its name or `Content-Type`). `mp4` covers M4A. |
| `max_source_audio_duration_seconds` | Longest source accepted; longer → `422` before any charge. |
| `supports_background_noise_removal` | Whether `remove_background_noise` is honored. |
| `supports_seed` | Whether `seed` is honored. |
| `voices`, `default_voice`, `supports_custom_voice_id` | Target voices; with `supports_custom_voice_id: true` you may pass a provider Voice ID. |
| `pricing.durations` | Whole-minute price tiers keyed by source length. |

`elevenlabs-voice-changer` supports: formats `mp3`, `wav`, `ogg`, `mp4`, `aac`; max source 300 s; noise removal and seed supported; the curated ElevenLabs voices (`Aria` default, `Roger`, `Sarah`, …) or any ElevenLabs Voice ID; output `mp3`. Read its price tiers from `pricing.durations` rather than hard-coding them.

## Lifecycle

### 1. `POST /audio/voice-changer/quote`

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/quote \
  -H "Content-Type: application/json" \
  -d '{ "model": "elevenlabs-voice-changer", "duration_seconds": 52 }'
```

Response: `{ "quote": <USD>, "duration_seconds": 52 }`.

| Field | Notes |
|---|---|
| `model` | Required. A voice-changer model. |
| `duration_seconds` | **Required.** Positive integer or numeric string, ≤ `max_source_audio_duration_seconds`. |

This is an estimate for the length you declare. The actual charge uses the length Venice measures when you queue; if both round up to the same whole minute the price is identical.

### 2. `POST /audio/voice-changer/queue`

Supply the source **exactly once** — a multipart `file` or a JSON `audio_url`. Both or neither → `400`.

```bash
# Upload
curl https://api.venice.ai/api/v1/audio/voice-changer/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "model=elevenlabs-voice-changer" \
  -F "file=@take-03.wav" \
  -F "voice=Roger" \
  -F "remove_background_noise=true"

# By URL
curl https://api.venice.ai/api/v1/audio/voice-changer/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "elevenlabs-voice-changer",
    "audio_url": "https://example.com/take-03.mp3",
    "voice": "Roger",
    "seed": 42
  }'
```

Response:

```json
{ "model": "elevenlabs-voice-changer", "queue_id": "…", "status": "QUEUED", "duration_seconds": 52 }
```

`duration_seconds` is the source length measured server-side — the exact quantity billed.

| Field | Notes |
|---|---|
| `model` | Required. |
| `file` | Multipart source recording, max 25 MB. |
| `audio_url` | Public `http(s)` URL. Venice fetches it (30 s timeout, 25 MB cap), validates the bytes, and forwards only the bytes — the URL itself is never passed to the provider. |
| `voice` | 1–60 chars. A curated voice or provider Voice ID. Defaults to `default_voice`. Not checked against `voices` at queue time — an unknown Voice ID fails with `400` at queue or on retrieve. |
| `remove_background_noise` | Boolean (`"true"` / `"false"` in multipart). |
| `seed` | Non-negative integer, for reproducible output. |

The body is strict — unknown fields → `400`. Format, length, seed and balance are checked **before** you're charged. A voice the provider rejects at queue time returns `400`, and any charge is refunded immediately.

### 3. `POST /audio/voice-changer/retrieve`

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-voice-changer","queue_id":"..."}' \
  --output converted.mp3
```

- Still running: `200` `{"status":"PROCESSING","average_execution_time":<ms>,"execution_duration":<ms since queued>}`.
- Done: `200` with the audio bytes, plus `x-venice-audio-format`, `x-venice-inference-time` (s), `x-venice-model-id`, `x-venice-model-name`, and `x-venice-audio-duration` when known.
- Failed: an error status with `{ "error": "…", "credits_refunded": true|false }`. If the provider accepted then failed the job, the charge is refunded; when `credits_refunded` is `false`, the message says whether anything is owed. The verdict is stored, so later polls return the same answer without a second refund.
- `delete_media_on_completion: true` releases the provider copy as soon as the audio is returned.

**The audio is delivered once.** After a successful download, the next retrieve for that `queue_id` returns `404`. Save the bytes on the first success.

### 4. `POST /audio/voice-changer/complete`

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-voice-changer","queue_id":"..."}'
```

Returns `{"success": true}` once the provider-held media is released (`false` if the delete didn't go through). Safe to call more than once. Skip it if you retrieved with `delete_media_on_completion: true`.

## Full loop (TypeScript)

```ts
import fs from 'node:fs/promises'

const base = 'https://api.venice.ai/api/v1'
const auth = { Authorization: `Bearer ${process.env.VENICE_API_KEY}` }
const model = 'elevenlabs-voice-changer'

async function convert(path: string, voice: string) {
  const form = new FormData()
  form.append('model', model)
  form.append('voice', voice)
  form.append('file', new Blob([await fs.readFile(path)]), 'source.wav')

  const queued = await fetch(`${base}/audio/voice-changer/queue`, { method: 'POST', headers: auth, body: form })
  if (!queued.ok) throw new Error(`queue ${queued.status}: ${await queued.text()}`)
  const { queue_id, duration_seconds } = await queued.json()
  console.log('billed seconds:', duration_seconds)

  while (true) {
    const res = await fetch(`${base}/audio/voice-changer/retrieve`, {
      method: 'POST',
      headers: { ...auth, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, queue_id, delete_media_on_completion: true }),
    })
    if (!res.ok) throw new Error(`retrieve ${res.status}: ${await res.text()}`)
    if (!(res.headers.get('content-type') ?? '').startsWith('application/json')) {
      await fs.writeFile('converted.mp3', Buffer.from(await res.arrayBuffer()))
      return
    }
    await new Promise(r => setTimeout(r, 3000))
  }
}
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Strict-body error; both or neither of `file` / `audio_url`; `audio_url` unreachable or unusable; source not in `accepted_audio_formats`, has a video track, or its length can't be read; voice rejected by the provider (at queue, or later on retrieve — then refunded); non-voice-changer model; unknown / foreign `queue_id` (`"Request ID is invalid."`). |
| `401` | Authentication failed. |
| `402` | Insufficient balance (checked against the price for the measured length). Wallet callers above the $0.10 floor but below the price get the plain `{"error":"Insufficient USD or Diem balance…"}` body, not `PAYMENT_REQUIRED`. |
| `403` | A `PRIVATE_ONLY` key calling an `anonymized` model, or region restriction. |
| `404` | Model not found (today: every regular API key); on retrieve, media expired or already delivered. |
| `413` | Uploaded file over 25 MB. |
| `422` | Source longer than `max_source_audio_duration_seconds` (at queue, not charged); or, on retrieve, a provider content-policy rejection (refunded). |
| `429` | Rate limited (40/min queue, 120/min retrieve, per user). |
| `500` | Inference failure; body carries `credits_refunded` on retrieve. |
| `503` | Model at capacity. |
| `504` | On retrieve: the provider never accepted the job and it can no longer complete (after ~10 min); charge refunded. |

See [`venice-errors`](../venice-errors/SKILL.md) for general body shapes.

## Gotchas

- **Check availability first** — see the note at the top. A `404` on quote with a correct model id means your key can't use it.
- Billing is on the **source** length, measured server-side and rounded up to whole minutes. A 61 s clip costs the 2-minute tier; trim silence before uploading.
- Don't blindly retry a queue call: a `200` means you've been charged. Keep the `queue_id` and poll instead.
- Save the audio on the first successful retrieve — there's no second download.
- Mislabelled files are fine (the bytes decide the format); a video file is rejected even if it's an MP4 with audio — extract the audio track first.
