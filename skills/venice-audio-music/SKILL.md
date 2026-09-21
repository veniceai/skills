---
name: venice-audio-music
description: Async music / audio-track generation via Venice. Covers the /audio/quote + /audio/queue + /audio/retrieve + /audio/complete lifecycle, lyrics vs instrumental, voice selection, duration, language, speed, model capability probing, and webhook-free polling.
---

# Venice Music / Async Audio

Music (and long-form voice) generation is **asynchronous**. The flow is:

```
POST /api/v1/audio/quote      → price in USD
POST /api/v1/audio/queue      → { queue_id }      (funds reserved)
POST /api/v1/audio/retrieve   → status or binary audio
POST /api/v1/audio/complete   → finalize & delete media
```

For short text-to-speech, use the synchronous [`venice-audio-speech`](../venice-audio-speech/SKILL.md) endpoint instead. For speech-to-speech conversion of an existing recording, use [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md) (`/audio/voice-changer/*`) — those models are rejected here.

## Use when

- You need songs, jingles, score, soundscape, or long narration.
- The selected model uses **duration-based** or **character-based** pricing and must be priced before submission.
- The expected generation time is long enough (> 20 s) that sync call would time out.

## Lifecycle

### 1. `POST /audio/quote` — price it first

```bash
curl https://api.venice.ai/api/v1/audio/quote \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "elevenlabs-music",
    "duration_seconds": 60
  }'
```

Response: `{"quote": 0.48}` (USD).

| Field | Notes |
|---|---|
| `model` | Required. Music/audio model from `GET /models?type=music`. |
| `duration_seconds` | Integer or numeric string. Only if the model reports duration metadata. |
| `character_count` | Required for models with `pricing.per_thousand_characters` (long narration). |

### 2. `POST /audio/queue` — enqueue

```bash
curl https://api.venice.ai/api/v1/audio/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "elevenlabs-music",
    "prompt": "Uplifting indie-folk acoustic track, 120 BPM, major key.",
    "lyrics_prompt": "Verse 1: Walking through the city lights...\nChorus: We are the dreamers...",
    "duration_seconds": 60,
    "voice": "Aria",
    "language_code": "en",
    "speed": 1.0,
    "force_instrumental": false,
    "lyrics_optimizer": false
  }'
```

Response: `{ "model": "...", "queue_id": "uuid" }`.

| Field | Notes |
|---|---|
| `model` | Required. |
| `prompt` | Required. Describe genre, mood, tempo, instruments. Length caps in `/models`. |
| `lyrics_prompt` | Lyrics. **Required** when `lyrics_required=true`, **rejected** when `supports_lyrics=false`. |
| `duration_seconds` | Integer or string. Model-dependent. |
| `force_instrumental` | Only when `supports_force_instrumental=true`. |
| `lyrics_optimizer` | Auto-generate lyrics from `prompt`. Requires `supports_lyrics_optimizer=true`. `lyrics_prompt` must be empty. |
| `voice` | For voice-enabled models. See `voices` + `default_voice` in `/models`. |
| `language_code` | ISO 639-1. Requires `supports_language_code=true`. |
| `speed` | Requires `supports_speed=true`. Use model's `min_speed`/`max_speed`. |

### 3. `POST /audio/retrieve` — poll status / download

```bash
curl https://api.venice.ai/api/v1/audio/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-music","queue_id":"..."}' \
  --output track.mp3
```

- If still processing: JSON `{"status":"PROCESSING","average_execution_time":...,"execution_duration":...}`.
- If done: binary audio body (`audio/mpeg` or similar). Save the bytes.
- Set `delete_media_on_completion: true` to skip step 4.

Poll every 2–5 s; use `average_execution_time` (ms, P80) as a guideline for your first poll delay.

### 4. `POST /audio/complete` — cleanup

```bash
curl https://api.venice.ai/api/v1/audio/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-music","queue_id":"..."}'
```

Removes the media from Venice storage after you've downloaded it. Required unless you used `delete_media_on_completion: true` on retrieve.

## Full loop (TypeScript)

```ts
const base = 'https://api.venice.ai/api/v1'
const headers = {
  Authorization: `Bearer ${process.env.VENICE_API_KEY}`,
  'Content-Type': 'application/json',
}

async function generateTrack() {
  // 1. Quote
  const quote = await fetch(`${base}/audio/quote`, {
    method: 'POST', headers,
    body: JSON.stringify({ model: 'elevenlabs-music', duration_seconds: 60 }),
  }).then(r => r.json())
  console.log('price:', quote.quote)

  // 2. Queue
  const { queue_id, model } = await fetch(`${base}/audio/queue`, {
    method: 'POST', headers,
    body: JSON.stringify({
      model: 'elevenlabs-music',
      prompt: 'Uplifting indie-folk acoustic track, 120 BPM.',
      duration_seconds: 60,
      force_instrumental: true,
    }),
  }).then(r => r.json())

  // 3. Poll
  while (true) {
    const res = await fetch(`${base}/audio/retrieve`, {
      method: 'POST', headers,
      body: JSON.stringify({ model, queue_id }),
    })
    const ct = res.headers.get('content-type') ?? ''
    if (ct.startsWith('audio/')) {
      const buf = Buffer.from(await res.arrayBuffer())
      await fs.writeFile('track.mp3', buf)
      break
    }
    const { status } = await res.json()
    if (status !== 'PROCESSING') throw new Error(`unexpected ${status}`)
    await new Promise(r => setTimeout(r, 3000))
  }

  // 4. Complete
  await fetch(`${base}/audio/complete`, {
    method: 'POST', headers,
    body: JSON.stringify({ model, queue_id }),
  })
}
```

## Capability probing

Before calling `/audio/queue`, inspect the model entry returned by `GET /models?type=music` — each row's `model_spec` exposes (among other fields):

- `supports_lyrics`, `lyrics_required`, `supports_lyrics_optimizer`
- `supports_force_instrumental`, `supports_speed`, `supports_language_code`
- `voices[]`, `default_voice`
- `min_prompt_length`, `prompt_character_limit`
- `min_speed`, `max_speed`
- `pricing.generation` (per-job), `pricing.per_second` (per second generated), `pricing.per_thousand_characters` (character-priced narration), or `pricing.durations` (duration-tiered map: `{ "<tier>": { usd, diem, min_seconds, max_seconds } }`) — each model uses one of these shapes
- `voice_changer` — when `true`, this is a speech-to-speech model. Do **not** send it to `/audio/quote` or `/audio/queue`; use [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md).

## Errors

| Code | Meaning |
|---|---|
| `400` | Wrong params (lyrics on an instrumental-only model, `duration_seconds` outside allowed range, voice not in model's list). |
| `401` | Auth / Pro-only model. |
| `402` | Insufficient balance. Bearer → `INSUFFICIENT_BALANCE`; x402 → `PAYMENT_REQUIRED`. |
| `404` | On `retrieve`/`complete`: unknown / expired `queue_id`. |
| `422` | Content policy violation. `ContentViolationError` may include `suggested_prompt`. |
| `429` | Rate limited. |
| `500` / `503` | Inference or capacity issue. |

## Gotchas

- **Quote before queue** — music is pay-per-second; unexpected `duration_seconds` can blow through a budget. Use `/audio/quote` to gate the `queue` call against your available balance (`/billing/balance` or `/x402/balance/...`).
- `queue_id` is UUIDv4. Store it alongside the `model` — both are required for every subsequent call.
- Media URLs are ephemeral. Download during `retrieve` and store yourself; after `complete`, Venice deletes the file.
- `lyrics_optimizer: true` and a non-empty `lyrics_prompt` is a `400`.
- Poll rate: don't hammer `/retrieve`. 2–5 s is plenty — the job queue is the same regardless of poll frequency.
- `execution_duration` from the retrieve status is cumulative (ms since enqueue); `average_execution_time` is the P80 expected total.
