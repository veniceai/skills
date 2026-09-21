---
name: venice-audio-voice-changer
description: Async speech-to-speech voice conversion via POST /audio/voice-changer/quote, /queue, /retrieve, and /complete. Convert a source recording into another voice while preserving delivery, pacing, and timing. Not TTS, not voice cloning, and not /audio/queue.
---

# Venice Voice Changer (speech-to-speech)

Voice Changer re-records a source file in a different voice. It is **asynchronous** and uses its own four endpoints — not [`/audio/queue`](../venice-audio-music/SKILL.md), not [`/audio/speech`](../venice-audio-speech/SKILL.md), and not [`/audio/voices`](../venice-audio-speech/SKILL.md) cloning.

```
POST /api/v1/audio/voice-changer/quote      → { quote, duration_seconds }
POST /api/v1/audio/voice-changer/queue      → { model, queue_id, status: "QUEUED", duration_seconds }
POST /api/v1/audio/voice-changer/retrieve   → PROCESSING JSON or audio/mpeg bytes
POST /api/v1/audio/voice-changer/complete   → { success }
```

Base URL: `https://api.venice.ai/api/v1`.

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/audio/voice-changer/quote` | None (same as `/audio/quote`) | Estimate USD cost from a **declared** source length. |
| `POST` | `/audio/voice-changer/queue` | Bearer or SIWX | Start conversion. **Charged immediately.** Not safe to retry. |
| `POST` | `/audio/voice-changer/retrieve` | Bearer or SIWX | Poll. JSON while running; `audio/mpeg` when done. |
| `POST` | `/audio/voice-changer/complete` | Bearer or SIWX | Release stored media. Idempotent. |

## Use when

- You have an existing recording and want it spoken in another voice, keeping timing.
- You need a quote before spending.

Do **not** use this for text-to-speech, cloning a voice from a sample to use later on `/audio/speech`, or generating music.

## Discover a model

There is **no** `?type=voice-changer` filter. Voice-changer models are music-catalog rows with `model_spec.voice_changer === true`:

```bash
curl "https://api.venice.ai/api/v1/models?type=music" \
  -H "Authorization: Bearer $VENICE_API_KEY"
```

Pick an `id` where `model_spec.voice_changer` is `true`. Then read, on that same row:

| Field | Use |
|---|---|
| `voices` / `default_voice` | Target voice names. Omit `voice` to use the default. |
| `supports_custom_voice_id` | Whether `voice` also accepts a provider Voice ID. |
| `accepted_audio_formats` | Source containers, validated from the **file bytes**, not the filename. |
| `max_source_audio_duration_seconds` | Longest source the model accepts. Over-length / oversize is rejected **before charge**. |
| `pricing.durations` | Whole-minute price tiers (same buckets the quote uses). |

The OpenAPI example ID `elevenlabs-voice-changer` is **not** currently in the public catalog — do not hard-code it. Resolve `$VOICE_CHANGER_MODEL` from `/models` on every run.

## 1. `POST /audio/voice-changer/quote`

Required: `model`, `duration_seconds` (integer **> 0**, or a numeric string). This prices the length you declare. The charge is computed later from the length Venice **measures** at queue time, rounded up to the next whole minute.

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/quote \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VOICE_CHANGER_MODEL\",
    \"duration_seconds\": 60
  }"
```

```json
{ "quote": 0.35, "duration_seconds": 60 }
```

`quote` is USD. Unknown model → `404`. A music/TTS model that is not a voice changer → `400` telling you to use `/audio/quote` instead.

```ts
const quote = await fetch('https://api.venice.ai/api/v1/audio/voice-changer/quote', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ model: process.env.VOICE_CHANGER_MODEL, duration_seconds: 60 }),
}).then((r) => r.json())
```

## 2. `POST /audio/voice-changer/queue`

Required: `model`, plus **exactly one** of `file` (multipart field name `file`) or `audio_url` (JSON `http(s)` URL). Both or neither → rejected.

When you pass a URL, Venice fetches and validates the bytes itself and forwards only those bytes to the provider — the URL is never handed onward.

Optional (schema): `voice`, `remove_background_noise` (bool), `seed` (integer ≥ 0). Extra fields a given model rejects return `400` — probe `/models` before sending them.

```bash
# multipart file
curl https://api.venice.ai/api/v1/audio/voice-changer/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "model=$VOICE_CHANGER_MODEL" \
  -F "voice=Aria" \
  -F "file=@./source-recording.mp3"

# JSON URL
curl https://api.venice.ai/api/v1/audio/voice-changer/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VOICE_CHANGER_MODEL\",
    \"voice\": \"Aria\",
    \"audio_url\": \"https://example.com/source-recording.mp3\"
  }"
```

```json
{
  "model": "…",
  "queue_id": "0190f2c4-9c1e-7a3b-8f42-2c9d5e7a1b34",
  "status": "QUEUED",
  "duration_seconds": 52
}
```

Save `model` and `queue_id`. `duration_seconds` here is the **billed** measured length — reconcile against the quote.

```ts
const form = new FormData()
form.set('model', process.env.VOICE_CHANGER_MODEL!)
form.set('voice', 'Aria')
form.set('file', new Blob([sourceBytes]), 'source-recording.mp3')

const queued = await fetch('https://api.venice.ai/api/v1/audio/voice-changer/queue', {
  method: 'POST',
  headers: { Authorization: `Bearer ${process.env.VENICE_API_KEY}` },
  body: form,
}).then(async (r) => {
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<{ model: string; queue_id: string; duration_seconds: number }>
})
```

## 3. `POST /audio/voice-changer/retrieve`

Required: `model`, `queue_id`. Optional: `delete_media_on_completion` (default `false`) — if `true`, media is released when audio is returned and cannot be retrieved again.

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VOICE_CHANGER_MODEL\",
    \"queue_id\": \"$QUEUE_ID\"
  }" --output response.bin
```

Inspect `Content-Type`:

| Content-Type | Meaning | Action |
|---|---|---|
| `application/json` | Still running (`status: "PROCESSING"`) | Read timing, wait, poll again. |
| `audio/mpeg` | Done | Save the binary body as `.mp3`. |

Processing body:

```json
{
  "status": "PROCESSING",
  "average_execution_time": 10000,
  "execution_duration": 4200
}
```

Both timing values are milliseconds. `average_execution_time` is recent average end-to-end time for the model (use it to pace polling). `execution_duration` is elapsed since queue.

Completed audio also carries `x-venice-audio-format`, `x-venice-audio-duration`, `x-venice-inference-time`, `x-venice-model-id`, and `x-venice-model-name`.

Only the account that queued the job can poll it. Unknown / other-account / expired `queue_id` → `404`.

If the provider fails the conversion, the charge is refunded automatically and the error body includes `credits_refunded`. Polling again **replays** that result rather than refunding twice. When `credits_refunded` is `false` after a charged failure, follow the `error` message (contact support / poll again) — do not queue a duplicate.

```ts
const res = await fetch('https://api.venice.ai/api/v1/audio/voice-changer/retrieve', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ model: queued.model, queue_id: queued.queue_id }),
})
const ct = (res.headers.get('content-type') ?? '').split(';')[0]
if (ct === 'audio/mpeg') {
  const buf = Buffer.from(await res.arrayBuffer())
} else {
  const status = await res.json()
}
```

## 4. `POST /audio/voice-changer/complete`

Required: `model`, `queue_id`. Safe to call more than once, and safe if the conversion never reached the provider. Skip if you already passed `delete_media_on_completion: true` on retrieve.

```bash
curl https://api.venice.ai/api/v1/audio/voice-changer/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$VOICE_CHANGER_MODEL\",
    \"queue_id\": \"$QUEUE_ID\"
  }"
```

```json
{ "success": true }
```

```ts
await fetch('https://api.venice.ai/api/v1/audio/voice-changer/complete', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ model: queued.model, queue_id: queued.queue_id }),
})
```

## Errors

| Status | When | What to do |
|---|---|---|
| `400` | Bad params; model is not a voice changer; unsupported optional field. | Fix input. Do **not** re-queue. |
| `401` | Auth failed, or Pro-only model. | Fix credentials. |
| `402` | Insufficient balance (Bearer) or x402 payment required. | Top up. See [`venice-errors`](../venice-errors/SKILL.md). |
| `404` | Quote: unknown model. Retrieve: unknown/expired/`queue_id` not yours. | Do not re-queue a job whose `queue_id` you already have. |
| `413` | Payload too large on queue. | Shrink the source file. |
| `422` | Content policy. | Do not retry the same source. |
| `429` | Rate limited. | Back off. |
| `500` / `503` | Inference / capacity. | Retry **retrieve**, never queue. |
| `504` | Retrieve: conversion never reached the provider and cannot complete. Charge refunded unless the body says otherwise. | Stop polling. Do not treat as "try queue again" unless you intend a new paid job. |

Queue, retrieve, and complete also accept x402 (`SIGN-IN-WITH-X`). Quote does not bill and does not require auth.

## Gotchas

- **Queue is not idempotent.** A `200` has already been charged. If the response is lost, poll retrieve with the same `queue_id` — do not queue the recording again.
- Voice-changer models are rejected on `/audio/quote` and `/audio/queue` (and vice versa).
- Source format is taken from the **binary signature**, not the filename or `Content-Type`.
- Poll every few seconds; `average_execution_time` is a better first delay than hammering retrieve.
- Examples in the OpenAPI spec / published docs use `elevenlabs-voice-changer`. Live `GET /models?type=music` (this sweep) listed **zero** rows with `voice_changer: true`, and quoting that ID returned `404 Specified model not found`. Always resolve from `/models`.

Related: [`venice-audio-speech`](../venice-audio-speech/SKILL.md), [`venice-audio-music`](../venice-audio-music/SKILL.md), [`venice-models`](../venice-models/SKILL.md), [`venice-errors`](../venice-errors/SKILL.md).
