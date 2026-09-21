---
name: venice-audio-speech
description: Generate speech from text via POST /audio/speech, and clone a voice via POST /audio/voices. Covers TTS models (Kokoro, Qwen 3, xAI, Inworld, Chatterbox, Orpheus, ElevenLabs Turbo, MiniMax, Gemini Flash, Gradium), voices per family, cloned-voice handles, output formats (mp3/opus/aac/flac/wav/pcm), streaming, prompt/emotion styling, temperature/top_p, and language hints.
---

# Venice TTS (`/audio/speech`)

`POST /api/v1/audio/speech` converts text to an audio stream or file. OpenAI-compatible — the OpenAI SDK's `audio.speech.create()` works as a drop-in.

## Use when

- You want narration, voice replies, or UI audio from text.
- You need a specific voice family (ElevenLabs, Kokoro, xAI, Qwen 3, Orpheus, Chatterbox, MiniMax, Inworld, Gemini Flash).
- You want streaming audio returned sentence-by-sentence.
- You need style/emotion control on supported models.

For music generation (lyrics + instrumental), see [`venice-audio-music`](../venice-audio-music/SKILL.md). For speech-to-speech conversion of an existing recording, see [`venice-audio-voice-changer`](../venice-audio-voice-changer/SKILL.md) — that is not TTS and not cloning. For transcription (audio → text), see [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md).

## Minimal request

```bash
curl https://api.venice.ai/api/v1/audio/speech \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-xai-v1",
    "voice": "eve",
    "input": "Hello, welcome to Venice Voice.",
    "response_format": "mp3",
    "speed": 1.0,
    "streaming": false
  }' --output hello.mp3
```

Response is the raw audio (`Content-Type` matches `response_format`).

## Request schema

| Field | Type | Default | Notes |
|---|---|---|---|
| `input` | string | — | **Required.** Up to **4096** characters. |
| `model` | enum | `tts-kokoro` (OpenAPI schema default) | See model list below. `tts-xai-v1` is the recommended frontier default; pick the model that fits your voice + language needs. |
| `voice` | string, ≤ 512 | model-specific (e.g. `eve` for `tts-xai-v1`) | **Voice is model-specific** — wrong combo = `400`. See voice families. Also accepts a cloned-voice handle (`vv_…`) from `POST /audio/voices`, paired with the same `model` that created it. |
| `response_format` | `mp3` / `opus` / `aac` / `flac` / `wav` / `pcm` | `mp3` | `pcm` returns 24 kHz signed-16 LE for pipelines. |
| `speed` | number | `1.0` | Range `0.25–4.0`. |
| `streaming` | bool | `false` | `true` → streamed sentence-by-sentence as audio continues to generate. |
| `language` | string | — | Optional hint. Accepted form depends on model (Qwen 3 = full names like `English`; xAI / ElevenLabs = ISO 639-1 like `en`; MiniMax = full names). Unsupported values silently ignored. |
| `prompt` | string, ≤ 500 | — | Emotion / style cue. Only for models with `supportsPromptParam` (Qwen 3 currently). Examples: *"Very happy."*, *"Sad and slow."*. |
| `temperature` | 0–2 | — | Sampling temperature. Only for models with `supportsTemperatureParam` (Qwen 3, Orpheus, Chatterbox HD). |
| `top_p` | 0–1 | — | Only Qwen 3 currently. |

## Models

| Model ID | Family | Highlights |
|---|---|---|
| `tts-xai-v1` | xAI | **Recommended default.** Conversational style, ISO 639-1 language hints. |
| `tts-kokoro` | Kokoro | OpenAPI schema default. Multilingual, many voices across languages. |
| `tts-qwen3-0-6b` / `tts-qwen3-1-7b` | Qwen 3 | Emotion control via `prompt`, temperature, top_p. |
| `tts-inworld-1-5-max` | Inworld | Character-driven voices (Craig, Ashley, …). |
| `tts-chatterbox-hd` | Chatterbox | HD voices (Aurora, Blade, …), temperature. |
| `tts-orpheus` | Orpheus | Conversational (tara, leah, jess, leo, …), temperature. |
| `tts-elevenlabs-turbo-v2-5` | ElevenLabs Turbo | Rachel, Aria, Charlotte, Roger, … |
| `tts-minimax-speech-02-hd` | MiniMax | WiseWoman, DeepVoiceMan, … Supports **persistent** voice cloning. |
| `tts-gemini-3-1-flash` | Gemini Flash | Star-named voices (Achernar, Achird, Zephyr, …). |
| `tts-gradium-v1` | Gradium | Multilingual across en/de/es/fr/pt, where the **voice picks the language** (there is no separate language parameter). Proprietary upstream, so `capabilities.private` is `false`. |

Always inspect the entry for your model in `GET /models?type=tts` — `model_spec.voices` is the authoritative voice list. Per-model toggles like `supportsPromptParam`, `supportsTemperatureParam`, `supportsTopPParam` live on the internal model definitions but are not currently exposed on `/models` — treat the request schema below (`instructions`, `temperature`, `top_p`) as the support matrix.

## Voice families (by prefix)

- **Kokoro** — lowercase + language/gender prefix:
  - `af_*`, `am_*` — American female / male
  - `bf_*`, `bm_*` — British female / male
  - `zf_*`, `zm_*` — Chinese
  - `ff_*`, `hf_*`, `hm_*`, `if_*`, `im_*`, `jf_*`, `jm_*`, `pf_*`, `pm_*`, `ef_*`, `em_*` — French, Hindi, Italian, Japanese, Portuguese, Spanish
  - Examples: `af_sky`, `af_bella`, `am_adam`, `bm_george`, `zf_xiaoxiao`
- **Qwen 3** — `Vivian`, `Serena`, `Ono_Anna`, `Sohee`, `Uncle_Fu`, `Dylan`, `Eric`, `Ryan`, `Aiden`
- **xAI** — 26 voices. Original five: `eve`, `ara`, `rex`, `sal`, `leo`. Flagship multilingual set: `altair`, `atlas`, `carina`, `castor`, `celeste`, `cosmo`, `helios`, `helix`, `iris`, `kepler`, `lumen`, `luna`, `lux`, `naksh`, `orion`, `perseus`, `rigel`, `sirius`, `ursa`, `zagan`, `zenith`
- **Orpheus** — `tara`, `leah`, `jess`, `mia`, `zoe`, `dan`, `zac`
- **Inworld** — `Craig`, `Ashley`, `Olivia`, `Sarah`, `Elizabeth`, `Priya`, `Alex`, `Edward`, `Theodore`, `Ronald`, `Mark`, `Hades`, `Luna`, `Pixie`
- **Chatterbox** — `Aurora`, `Britney`, `Siobhan`, `Vicky`, `Blade`, `Carl`, `Cliff`, `Richard`, `Rico`
- **ElevenLabs Turbo** — `Rachel`, `Aria`, `Laura`, `Charlotte`, `Alice`, `Matilda`, `Jessica`, `Lily`, `Roger`, `Charlie`, `George`, `Callum`, `River`, `Liam`, `Will`, `Chris`, `Brian`, `Daniel`, `Bill`
- **MiniMax** — `WiseWoman`, `FriendlyPerson`, `InspirationalGirl`, `CalmWoman`, `LivelyGirl`, `LovelyGirl`, `SweetGirl`, `ExuberantGirl`, `DeepVoiceMan`, `CasualGuy`, `PatientMan`, `YoungKnight`, `DeterminedMan`, `ImposingManner`, `ElegantMan`
- **Gemini 3 Flash** — star names: `Achernar`, `Achird`, `Algenib`, `Algieba`, `Alnilam`, `Aoede`, `Autonoe`, `Callirrhoe`, `Charon`, `Despina`, `Enceladus`, `Erinome`, `Fenrir`, `Gacrux`, `Iapetus`, `Kore`, `Laomedeia`, `Leda`, `Orus`, `Pulcherrima`, `Puck`, `Rasalgethi`, `Sadachbia`, `Sadaltager`, `Schedar`, `Sulafat`, `Umbriel`, `Vindemiatrix`, `Zephyr`, `Zubenelgenubi`
- **Gradium** — the voice selects the language. English: `Emma` (default), `Kent`, `Eva`, `Jack`. German: `Mia`, `Maximilian`. Spanish: `Valentina`, `Sergio`. French: `Elise`, `Leo`. Portuguese: `Alice`, `Davi`

Pass a voice that isn't in the chosen model's list and you get `400`.

## Voice cloning — `POST /audio/voices`

Clone a voice from an audio sample and get back a handle (`vv_…`) you can pass
as `voice` on `/audio/speech`. `multipart/form-data` only.

```bash
curl https://api.venice.ai/api/v1/audio/voices \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "model=tts-chatterbox-hd" \
  -F "file=@sample.wav"
```

| Field | Notes |
|---|---|
| `file` | The voice sample, multipart field name `file`. Accepted containers depend on the model. Aim for a clean speech recording of at least 5–10 seconds. |
| `model` | `tts-chatterbox-hd` (default) or `tts-minimax-speech-02-hd`. |

| Model | Containers | Persistence | Availability |
|---|---|---|---|
| `tts-chatterbox-hd` | MP3, WAV, FLAC, M4A | **Zero-shot.** No voice template is derived; the reference audio is stored with a TTL and re-read on every synthesis call. Handles expire after **7 days**, full stop. | Regular users. |
| `tts-minimax-speech-02-hd` | MP3, WAV only | **Persistent.** The provider derives a voice template that survives across calls. Auto-deleted after **7 days without use**; each successful TTS request resets the window. | Limited access — contact support@venice.ai to have it enabled. |

A handle is bound to the model that created it. Pass a `vv_…` handle with a
different `model` on `/audio/speech` and the call fails.

Samples in a container outside the per-model allowlist are rejected with `400`
before anything is uploaded. Beyond the shared TTS error codes, this endpoint
also returns `403` and `413` (sample too large).

## Streaming

```json
{
  "model": "tts-xai-v1",
  "voice": "eve",
  "input": "Hello, this is a long document to narrate. ...",
  "streaming": true,
  "response_format": "mp3"
}
```

With `streaming: true`, the HTTP body is a chunked audio stream. Decode as it arrives — useful for latency-sensitive UIs. `response_format: pcm` pairs well with browser Web Audio API for raw playback.

## OpenAI SDK

```ts
import OpenAI from 'openai'
import fs from 'node:fs/promises'

const client = new OpenAI({
  apiKey: process.env.VENICE_API_KEY,
  baseURL: 'https://api.venice.ai/api/v1',
})

const mp3 = await client.audio.speech.create({
  model: 'tts-xai-v1',
  voice: 'eve',
  input: 'Hello from Venice.',
  response_format: 'mp3',
})

await fs.writeFile('hello.mp3', Buffer.from(await mp3.arrayBuffer()))
```

## Emotion / style (Qwen 3 only)

```json
{
  "model": "tts-qwen3-1-7b",
  "voice": "Vivian",
  "input": "We did it!",
  "prompt": "Excited and energetic.",
  "temperature": 0.9,
  "top_p": 0.95
}
```

For other families, emotion comes from the **voice choice itself** (e.g. Inworld `Hades` vs `Pixie`). `prompt` / `temperature` / `top_p` are silently ignored.

## Errors

| Code | Meaning |
|---|---|
| `400` | Bad voice/model combo, input too long (>4096), language hint rejected by a strict model, invalid voice for the chosen model. |
| `401` | Auth / Pro-only model. |
| `402` | Insufficient balance. |
| `429` | Rate limited. |
| `500` / `503` | Inference / capacity issue — retry with jitter. |

## Gotchas

- `input` hard cap is 4096 chars. For books / long content, split on sentence boundaries and concatenate audio client-side.
- `streaming: true` + SDKs: some OpenAI SDK versions don't expose streaming for `audio.speech.create`; call the REST endpoint directly and consume the HTTP body.
- `speed` compounds with model internal speech rate — extreme values (`0.25`, `4.0`) often sound unnatural; keep within `0.8–1.3` for narration.
- Voice names are case-sensitive (`eve` ≠ `EVE`, `af_sky` ≠ `AF_SKY`).
- Cloned voices expire. Chatterbox handles die 7 days after creation no matter what; MiniMax handles die after 7 days of no use. Re-clone rather than assuming a handle you stored last month still resolves.
- Gradium has no `language` parameter. Pick the voice for the language you want.
