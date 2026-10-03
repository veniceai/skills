---
name: venice-audio-transcription
description: Transcribe audio files to text via POST /audio/transcriptions. Covers supported models (Parakeet, Whisper, Wizper, Scribe, xAI STT), accepted containers (wav/flac/m4a/aac/mp4/mp3/ogg/webm), response formats (json/text only), per-model timestamps (word/segment/char), language hints, the 25 MB cap, and per-audio-second pricing. OpenAI-compatible multipart.
---

# Venice Transcription (`/audio/transcriptions`)

`POST /api/v1/audio/transcriptions` takes an audio file and returns text. It's OpenAI-compatible with `multipart/form-data` — the OpenAI SDK's `audio.transcriptions.create()` works unchanged.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/audio/transcriptions` | Bearer key or x402 (SIWX) | `multipart/form-data`, file field `file`, max 25 MB. Billed per second of audio. |

## Use when

- You need STT (speech-to-text) for voice notes, meetings, podcasts, short audio.
- You need word/segment timestamps for subtitles or chapters.
- You want to pick between Venice-hosted Parakeet, Whisper-family models, ElevenLabs Scribe, or xAI STT.

For video, there is no transcription endpoint any more — `POST /video/transcriptions` is retired and returns `410`. Extract the audio track and send it here, or ask a video-capable chat model via [`venice-chat`](../venice-chat/SKILL.md).

## Minimal request

```bash
curl https://api.venice.ai/api/v1/audio/transcriptions \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "file=@./meeting.m4a" \
  -F "model=nvidia/parakeet-tdt-0.6b-v3" \
  -F "response_format=json" \
  -F "timestamps=false"
```

```json
{ "text": "Alright everyone, let's kick off the meeting...", "duration": 184.2 }
```

With `timestamps=true`, the JSON also carries a `timestamps` object (see below).

## Request (`multipart/form-data`)

Only the fields below are read; anything else in the form is ignored.

| Field | Type | Default | Notes |
|---|---|---|---|
| `file` | binary | — | **Required.** Real file part (no base64). Accepted: `wav`/`wave`, `flac`, `m4a`, `aac`, `mp4`, `mp3`, `ogg`/`oga`, `webm`. Checked by extension/MIME and then by binary signature. Max **25 MB**. |
| `model` | string | — | **Send it.** The OpenAPI schema lists `nvidia/parakeet-tdt-0.6b-v3` as default, but that default is never applied: omitting `model` returns `400 "model is required"`. |
| `response_format` | `json` / `text` | `json` | Only these two. `text` returns a `text/plain` body with just the transcript. |
| `timestamps` | bool (`true`/`false` as form string) | `false` | Adds `timestamps` to the JSON response. |
| `language` | string | — | ISO 639-1 hint (`en`, `ja`, …). Forwarded by Whisper, Wizper, Scribe and xAI STT; ignored by Parakeet (auto-detects). |

## Response

```json
{
  "text": "…",
  "duration": 184.2,
  "timestamps": {
    "word":    [{ "word": "Alright", "start": 0.12, "end": 0.48 }],
    "segment": [{ "text": "Alright everyone…", "start": 0.12, "end": 4.9 }],
    "char":    [{ "char": "A", "start": 0.12, "end": 0.15 }]
  }
}
```

`duration` (seconds) and `timestamps` are optional. Which timestamp arrays appear depends on the model:

| Model | Timestamp granularity |
|---|---|
| `openai/whisper-large-v3` | `segment` + `word` |
| `fal-ai/wizper` | `segment` |
| `elevenlabs/scribe-v2` | `word` |
| `stt-xai-v1` | `word` |
| `nvidia/parakeet-tdt-0.6b-v3` | may include `segment`, `word` and/or `char` |

## Models

All five are in the live `GET /models?type=asr` list. Price is `model_spec.pricing.per_audio_second.usd`.

| Model ID | Privacy | Notes |
|---|---|---|
| `nvidia/parakeet-tdt-0.6b-v3` | private | Venice-hosted, fast. Ignores `language`. |
| `openai/whisper-large-v3` | private | Multilingual; `language` hint; segment + word timestamps. |
| `fal-ai/wizper` | private | Whisper v3 variant; `language` hint; segment timestamps. |
| `elevenlabs/scribe-v2` | anonymized | `language` hint; word timestamps. |
| `stt-xai-v1` | anonymized | `language` hint; word timestamps. |

A key with `modelPrivacy: PRIVATE_ONLY` gets `403` on the `anonymized` ones (`PRIVATE_TEXT` keys are not restricted here). Failed transcriptions are not charged.

## OpenAI SDK

```ts
import OpenAI from 'openai'
import fs from 'node:fs'

const client = new OpenAI({
  apiKey: process.env.VENICE_API_KEY,
  baseURL: 'https://api.venice.ai/api/v1',
})

const out = await client.audio.transcriptions.create({
  file: fs.createReadStream('meeting.m4a'),
  model: 'openai/whisper-large-v3',
  response_format: 'json',
  language: 'en',
  // @ts-expect-error — Venice-specific extra, passes through multipart
  timestamps: true,
})

console.log(out.text)
```

## Long files

There's no server-side chunking, and uploads are capped at 25 MB. Split long recordings client-side (on silence, or fixed segments), transcribe each chunk, then concatenate with offset timestamps.

```bash
ffmpeg -i long.mp3 -f segment -segment_time 600 -c copy chunk_%03d.mp3
```

## Errors

| Code | Meaning |
|---|---|
| `400` | Missing `model`, bad params (e.g. `response_format` not `json`/`text`), no `file` part (including a JSON body instead of multipart → `"No audio file provided"`), unsupported extension/MIME, or unrecognized binary signature. |
| `401` | Authentication failed. |
| `402` | Insufficient balance. Bearer → `{"error":"Insufficient USD or Diem balance…"}`, or `"API key USD|DIEM spend limit exceeded…"` when the key's own cap is hit (no `code` field); x402 → `PAYMENT_REQUIRED`. |
| `403` | A `PRIVATE_ONLY` key calling an `anonymized` model, or region restriction. |
| `404` | Unknown `model`. |
| `413` | File larger than 25 MB (`{"code":"PAYLOAD_TOO_LARGE","error":"File exceeds the maximum allowed size of 25 MB."}`). |
| `422` | Upstream provider couldn't process the audio (zero-length, silent, corrupt, unsupported format or language, provider-side refusal). No `suggested_prompt`. |
| `429` | Rate limited. |
| `500` | Inference failure. |
| `502` | Temporary upstream ASR failure — `{"error":"Audio transcription failed due to a temporary upstream error. Please retry."}` (no `code` field). Retry with backoff. |
| `503` | Model temporarily offline — retry with jitter. |

See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Gotchas

- Always send `model` — the documented default never applies.
- `file` must be a real multipart file part. JSON + base64 is **not** supported.
- There is no `verbose_json`, `srt` or `vtt`. For subtitles, use `response_format=json` + `timestamps=true` and render the timings yourself. `text` drops timestamps entirely.
- Check which granularity your model returns before building on `timestamps.word` vs `timestamps.segment`.
- A file with a valid extension but a non-audio binary signature is rejected; re-encode to a standard profile (e.g. MP3 44.1 kHz or 16 kHz).
- On `429`, back off; throttle big batches rather than firing everything in parallel.
