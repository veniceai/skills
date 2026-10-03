---
name: venice-audio-music
description: Async music, sound-effect and long-form voice generation via Venice. Covers the /audio/quote + /audio/queue + /audio/retrieve + /audio/complete lifecycle, lyrics vs instrumental and the lyrics optimizer, duration options, seamless loop (ElevenLabs sound effects), voice selection incl. custom ElevenLabs Voice IDs, language, speed, model capability probing via /models?type=music, pricing shapes, refunds, and polling.
---

# Venice Music / Async Audio

Music, sound effects and character-priced voice generation are **asynchronous**:

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/audio/quote` | **None required** (key optional) | Price in USD. |
| `POST` | `/api/v1/audio/queue` | Bearer key or x402 (SIWX) | Charges and enqueues → `queue_id`. 40 req/min per user. |
| `POST` | `/api/v1/audio/retrieve` | Bearer key or x402 (SIWX) | Status JSON or the audio bytes. 120 req/min per user. |
| `POST` | `/api/v1/audio/complete` | Bearer key or x402 (SIWX) | Delete the stored media. |

For short synchronous text-to-speech use [`venice-audio-speech`](../venice-audio-speech/SKILL.md). Voice-changer (speech-to-speech) models are **refused** on these four endpoints with a `400` pointing at `/audio/voice-changer/*` (callers who can't see the model get `404` instead) — see [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md).

## Use when

- You need songs, jingles, score, soundscapes, sound effects, or long narration.
- The model uses duration-, per-second-, per-job- or character-based pricing and you want a price before submitting.
- Generation takes long enough that a synchronous call would time out.

## Models

Query `GET /models?type=music` for the current list and each model's `model_spec`. Representative ids (all in the live list):

| Kind | Examples |
|---|---|
| Instrumental / songs | `elevenlabs-music`, `elevenlabs-music-v2-5`, `lyria-3-pro`, `sonilo-v1-1-music`, `stable-audio-25` |
| Songs with lyrics | `minimax-music-v25`, `minimax-music-v26`, `minimax-music-v2` (lyrics required), `ace-step-15` (lyrics optional) |
| Sound effects | `elevenlabs-sound-effects-v2` (supports `loop`), `sonilo-v1-1-sound-effects`, `mmaudio-v2-text-to-audio` |
| Voice (text in `prompt`) | `elevenlabs-tts-v4`, `elevenlabs-tts-v4-turbo`, `elevenlabs-tts-v3`, `elevenlabs-tts-multilingual-v2`, `seed-audio-1-0` |

## Lifecycle

### 1. `POST /audio/quote` — price it first

```bash
curl https://api.venice.ai/api/v1/audio/quote \
  -H "Content-Type: application/json" \
  -d '{ "model": "elevenlabs-music", "duration_seconds": 60 }'
```

Response: `{"quote": 0.69}` (USD). No API key needed; sending one lets you price models only your account can see.

| Field | Notes |
|---|---|
| `model` | Required. |
| `duration_seconds` | Integer or numeric string. Only for models that expose duration metadata (`min_duration` / `max_duration` / `duration_options`) — **rejected** otherwise. Omit to price the model's `default_duration`. |
| `character_count` | Integer ≤ `prompt_character_limit`. **Required** for models priced by `per_thousand_characters`. |

Unknown fields → `400`.

### 2. `POST /audio/queue` — enqueue

```bash
curl https://api.venice.ai/api/v1/audio/queue \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "elevenlabs-music",
    "prompt": "Uplifting indie-folk acoustic track, 120 BPM, major key.",
    "duration_seconds": 60,
    "force_instrumental": true
  }'
```

Song with lyrics (`minimax-music-v25` supports lyrics, the optimizer and instrumental mode, but no `duration_seconds`):

```json
{
  "model": "minimax-music-v25",
  "prompt": "Warm indie-pop ballad, female vocals, acoustic guitar.",
  "lyrics_prompt": "[Verse]\nWalking through the city lights...\n[Chorus]\nWe are the dreamers..."
}
```

Response: `{ "model": "...", "queue_id": "...", "status": "QUEUED" }`.

The body is strict: every optional field below is **rejected with `400`** when the model's `model_spec` says it isn't supported.

| Field | Notes |
|---|---|
| `model` | Required. |
| `prompt` | Required. Between `min_prompt_length` (default 10) and `prompt_character_limit`; trimmed. For the voice models this is the text to speak. |
| `lyrics_prompt` | Up to `lyrics_character_limit` (default 4096). Required when `lyrics_required=true`; rejected when `supports_lyrics=false`. |
| `duration_seconds` | Integer or numeric string. Must be one of `duration_options` when present, else within `min_duration`–`max_duration`. Defaults to `default_duration`. |
| `force_instrumental` | `supports_force_instrumental=true` only. |
| `lyrics_optimizer` | Auto-writes lyrics from `prompt`. `supports_lyrics_optimizer=true` only; `lyrics_prompt` must then be empty. |
| `loop` | Render a seamless loop (end splices into start). `supports_loop=true` only — currently `elevenlabs-sound-effects-v2`. |
| `voice` | Voice-enabled models only. One of `voices`; defaults to `default_voice`. Models with `supports_custom_voice_id=true` (the ElevenLabs TTS models) also accept a raw ElevenLabs Voice ID. |
| `language_code` | ISO 639-1. `supports_language_code=true` only — no model in the current list sets it. |
| `speed` | `supports_speed=true` only, within `min_speed`–`max_speed`. |

Model-specific rules also apply: `minimax-music-v25` needs a `lyrics_prompt` of at least 10 chars unless `force_instrumental` or `lyrics_optimizer` is `true`; `minimax-music-v26` needs the same unless `force_instrumental` is `true`; `minimax-music-v2` needs a non-blank `lyrics_prompt`.

### 3. `POST /audio/retrieve` — poll / download

```bash
curl https://api.venice.ai/api/v1/audio/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-music","queue_id":"..."}' \
  --output track.mp3
```

- Still running: `200` JSON `{"status":"PROCESSING","average_execution_time":<ms, P80 estimate>,"execution_duration":<ms since queued>}`.
- Done: `200` with the audio bytes. `Content-Type` is the audio type; headers `x-venice-audio-format`, `x-venice-inference-time` (s), `x-venice-model-id`, `x-venice-model-name`, and for Seed Audio also `x-venice-audio-duration` and `x-venice-audio-subtitle`.
- `delete_media_on_completion: true` deletes the media after this download, so you can skip step 4.

If generation fails (content policy, capacity, provider validation), the charge is refunded (except a DIEM charge from a previous epoch) and the error is returned here.

### 4. `POST /audio/complete` — cleanup

```bash
curl https://api.venice.ai/api/v1/audio/complete \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-music","queue_id":"..."}'
```

Returns `{"success": true}` once the stored media is deleted (`false` if the delete didn't go through). Use it after you've saved the bytes, unless you retrieved with `delete_media_on_completion: true`.

## Full loop (TypeScript)

```ts
import fs from 'node:fs/promises'

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
      body: JSON.stringify({ model, queue_id, delete_media_on_completion: true }),
    })
    if (!res.ok) throw new Error(`retrieve failed: ${res.status} ${await res.text()}`)
    const ct = res.headers.get('content-type') ?? ''
    if (!ct.startsWith('application/json')) {
      await fs.writeFile('track.mp3', Buffer.from(await res.arrayBuffer()))
      break
    }
    const { status } = await res.json()
    if (status !== 'PROCESSING') throw new Error(`unexpected ${status}`)
    await new Promise(r => setTimeout(r, 3000))
  }
  // delete_media_on_completion: true made /audio/complete unnecessary
}
```

## Capability probing

Each `GET /models?type=music` entry's `model_spec` exposes:

- `supports_lyrics`, `lyrics_required`, `lyrics_character_limit`, `supports_lyrics_optimizer`
- `supports_force_instrumental`, `supports_loop`, `supports_language_code`
- `supports_speed`, `default_speed`, `min_speed`, `max_speed`
- `voices[]`, `default_voice`, `supports_custom_voice_id`
- `duration_options[]`, `min_duration`, `max_duration`, `default_duration`
- `min_prompt_length`, `prompt_character_limit`
- `supported_formats`, `default_format` (the output container — informational, not a request field)
- `voice_changer: true` marks speech-to-speech models that belong on `/audio/voice-changer/*`
- `pricing`, one of:
  - `durations` — `{ "<tier>": { usd, diem, min_seconds, max_seconds } }` (e.g. `elevenlabs-music`, `ace-step-15`)
  - `generation` — flat per job (e.g. `minimax-music-v25`, `lyria-3-pro`, `stable-audio-25`)
  - `per_second` — per generated second (e.g. `elevenlabs-sound-effects-v2`, `sonilo-v1-1-music`, `seed-audio-1-0`)
  - `per_thousand_characters` — by `prompt` length (the ElevenLabs TTS models)

## Errors

| Code | Meaning |
|---|---|
| `400` | Schema error (strict body), unsupported option for the model, bad `duration_seconds`, `lyrics_optimizer` + `lyrics_prompt`, voice-changer model on these endpoints, a provider-side validation failure reported on retrieve (refunded), or an unknown / foreign `queue_id` on retrieve/complete (`"Request ID is invalid."`). Voice errors include `details.supported_voices`. |
| `401` | Authentication failed. |
| `402` | Insufficient balance. Bearer → `{"error":"Insufficient USD or Diem balance…"}`, or `"API key USD|DIEM spend limit exceeded…"` when the key's own cap is hit (no `code` field). x402: below the $0.10 floor → `PAYMENT_REQUIRED` body with top-up info; above the floor but below the quote → the same plain `{"error":"Insufficient USD or Diem balance…"}` body (no `code`) — check `/x402/balance/{wallet}` and top up. |
| `403` | A `PRIVATE_ONLY` key calling an `anonymized` model, or region restriction. |
| `404` | Unknown `model`; or on retrieve, media not found / expired / already deleted. |
| `422` | Content policy violation (queue or retrieve). May include `suggested_prompt`. Charge refunded (except a DIEM charge from a previous epoch). |
| `429` | Rate limited (40/min queue, 120/min retrieve, per user). |
| `500` | Inference failure. |
| `503` | Model at capacity — retry later. |

See [`venice-errors`](../venice-errors/SKILL.md) for body shapes.

## Gotchas

- **Quote before queue.** Queue charges up front (credits) or checks your x402 balance against the quote. With an API key, compare the quote to `data.balances` from [`GET /api_keys/rate_limits`](../venice-api-keys/SKILL.md), which works with an INFERENCE key and is already capped at the key's spend limit; the request is charged to the first currency that covers the whole quote (DIEM, then earned credits, then bundled credits, then USD; `balances` doesn't list earned credits). With a wallet, use [`/x402/balance/...`](../venice-x402/SKILL.md).
- Sending an unsupported option (`lyrics_prompt`, `voice`, `speed`, `language_code`, `loop`, `duration_seconds`, …) is a `400`, not a silent no-op. Build the body from `model_spec`.
- Store `queue_id` **and** `model` — every later call needs both.
- Media is ephemeral. Save the bytes on retrieve; after `complete` (or `delete_media_on_completion`) the audio is gone.
- `seed-audio-1-0` takes no `duration_seconds`: it reserves its 120 s output cap at queue time and settles on the actual length when done.
- Poll every 2–5 s; use `average_execution_time` to pick the first delay. Faster polling doesn't speed the job up and eats the 120/min retrieve limit.
