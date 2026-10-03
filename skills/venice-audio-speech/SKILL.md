---
name: venice-audio-speech
description: Generate speech from text via POST /audio/speech, and clone a voice via POST /audio/voices. Covers TTS models (Kokoro, Qwen 3, xAI, Inworld, Chatterbox, Orpheus, ElevenLabs Turbo, MiniMax, Gemini Flash, Gradium), voices per model, cloned-voice handles and raw ElevenLabs Voice IDs, per-model output formats (model_spec.supported_formats / default_format), streaming, prompt/style control, temperature/top_p, speed clamping, and language hints.
---

# Venice TTS (`/audio/speech`)

`POST /api/v1/audio/speech` converts text to an audio stream or file. OpenAI-compatible — the OpenAI SDK's `audio.speech.create()` works as a drop-in.

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/api/v1/audio/speech` | Bearer key or x402 (SIWX) | JSON body, returns raw audio. Billed per input character. |
| `POST` | `/api/v1/audio/voices` | Bearer key or x402 (SIWX) | `multipart/form-data`. Clone a voice → `vv_…` handle. There is no `GET /audio/voices`. |

## Use when

- You want narration, voice replies, or UI audio from text.
- You need a specific voice family (ElevenLabs, Kokoro, xAI, Qwen 3, Orpheus, Chatterbox, MiniMax, Inworld, Gemini Flash, Gradium).
- You want streaming audio returned as it is generated.
- You need style/emotion control on supported models, or synthesis in a cloned voice.

For music, sound effects and the character-priced ElevenLabs TTS models — v3, v4, v4 Turbo, Multilingual v2 — (async), see [`venice-audio-music`](../venice-audio-music/SKILL.md). For transcription (audio → text), see [`venice-audio-transcription`](../venice-audio-transcription/SKILL.md).

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

Response is the raw audio. `Content-Type` is `audio/mpeg`, `audio/opus`, `audio/aac`, `audio/flac`, `audio/wav` or `audio/pcm` depending on the format actually produced.

## Request schema

The body is strict — unknown fields return `400`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `input` | string | — | **Required.** 1–4096 characters, must contain non-whitespace. Text that sanitizes to nothing speakable (e.g. only markup/emoji) → `400 "Input must contain speakable text"`. |
| `model` | string | — | **Send it.** The OpenAPI schema lists a `tts-kokoro` default, but that default is never applied: omitting `model` returns `400 "model is required"`. Unknown id → `404`. |
| `voice` | string, ≤ 512 | the model's default voice | Voices are model-specific; a voice from another model → `400`. Also accepts a cloned-voice handle (`vv_…`) from `POST /audio/voices` (same `model` that created it), and — on models with `supports_custom_voice_id: true` (currently `tts-elevenlabs-turbo-v2-5`) — a raw provider Voice ID. |
| `response_format` | `mp3` / `opus` / `aac` / `flac` / `wav` / `pcm` | the model's `default_format` | **Support is per model** — read `model_spec.supported_formats` / `default_format`. Requesting a format the model doesn't support → `400`. |
| `speed` | number | `1.0` | Schema range `0.25–4.0`. Passed to Kokoro unchanged; clamped by xAI (`0.7–1.5`), ElevenLabs Turbo (`0.7–1.2`) and MiniMax (`0.5–2`); ignored by the other models. |
| `streaming` | bool | `false` | `true` → chunked audio stream as it's generated. `false` → buffered file with `Content-Length`. |
| `language` | string, 2–32 chars | — | Optional hint; form is model-specific (see below). Gemini Flash drops values outside its locale list and ElevenLabs Turbo drops values longer than 5 chars; Qwen 3, MiniMax and xAI forward the value as given, and a value the model rejects returns `400 "Invalid request parameters: language"`. Other models ignore it. |
| `prompt` | string, ≤ 500 | — | Style/emotion instruction. Used by Qwen 3 and Gemini Flash (sent as style instructions); ignored elsewhere. |
| `temperature` | number, 0–2 | — | Used by Qwen 3, Orpheus, Chatterbox HD, Gemini Flash; ignored elsewhere. |
| `top_p` | number, 0–1 | — | Qwen 3 only; ignored elsewhere. |

`language` by model: Qwen 3 → full names (`English`, `Chinese`, …; default auto); xAI → ISO 639-1 (`en`), passed through as given, so send a valid code (default auto); ElevenLabs Turbo → ISO 639-1 (values longer than 5 chars dropped, shorter ones forwarded); MiniMax → full names (sent as a language boost, unchecked); Gemini Flash → full locale strings such as `English (US)` or `Japanese (Japan)` (anything else dropped). Kokoro, Inworld, Chatterbox, Orpheus and Gradium ignore it.

## Models

Every id below is in the live `GET /models?type=tts` list. Prices are `model_spec.pricing.input.usd` = **USD per 1M input characters**.

| Model ID | Default voice | Formats (default first) | Privacy | Notes |
|---|---|---|---|---|
| `tts-kokoro` | `af_sky` | mp3, opus, aac, flac, wav, pcm | private | Multilingual via voice prefix. `speed` passed through unclamped. |
| `tts-qwen3-0-6b` / `tts-qwen3-1-7b` | `Vivian` | mp3 | private | `prompt`, `temperature`, `top_p`, `language`. |
| `tts-xai-v1` | `eve` | mp3, wav, pcm | anonymized | 26 voices, ISO `language`. |
| `tts-inworld-1-5-max` | `Craig` | wav | anonymized | Low-latency; all voices are English. |
| `tts-chatterbox-hd` | `Aurora` | wav | private | `temperature`. **Voice cloning (zero-shot).** |
| `tts-orpheus` | `tara` | wav | private | `temperature`. |
| `tts-elevenlabs-turbo-v2-5` | `Rachel` | mp3 | anonymized | Accepts raw ElevenLabs Voice IDs as `voice`. |
| `tts-minimax-speech-02-hd` | `WiseWoman` | mp3, pcm, flac | anonymized | `language`. Cloning with this model is **not available** to regular keys (see below). |
| `tts-gemini-3-1-flash` | `Kore` | mp3, opus, wav | anonymized | `prompt`, `temperature`, locale `language`. |
| `tts-gradium-v1` | `Emma` | wav, pcm, opus | anonymized | The voice picks the language; no `language` param. |

Always inspect `GET /models?type=tts` before calling: `model_spec.voices` (authoritative voice list), `supported_formats`, `default_format`, `supports_custom_voice_id`, `privacy`, `pricing`, and — on cloning models — `voice_cloning`. Per-model parameter support (`prompt` / `temperature` / `top_p` / `language`) is **not** exposed on `/models`; use the table above.

A key with `modelPrivacy: PRIVATE_ONLY` gets `403` on the `anonymized` models (`PRIVATE_TEXT` keys are not restricted here).

## Voices (from `model_spec.voices`)

Case-sensitive. Omit `voice` to get the model's default.

- **Kokoro** — `<lang><gender>_<name>`: `a` American, `b` British, `z` Chinese, `f` French, `h` Hindi, `i` Italian, `j` Japanese, `p` Portuguese, `e` Spanish; `f`/`m` gender. Examples: `af_sky`, `af_bella`, `af_heart`, `am_adam`, `am_michael`, `bf_emma`, `bm_george`, `ff_siwis`, `jf_alpha`, `zf_xiaoxiao`, `ef_dora`, `pm_alex` (54 total).
- **Qwen 3** — `Vivian`, `Serena`, `Ono_Anna`, `Sohee`, `Uncle_Fu`, `Dylan`, `Eric`, `Ryan`, `Aiden`
- **xAI** — `eve`, `ara`, `rex`, `sal`, `leo`, `altair`, `atlas`, `carina`, `castor`, `celeste`, `cosmo`, `helios`, `helix`, `iris`, `kepler`, `lumen`, `luna`, `lux`, `naksh`, `orion`, `perseus`, `rigel`, `sirius`, `ursa`, `zagan`, `zenith`
- **Orpheus** — `tara`, `leah`, `jess`, `mia`, `zoe`, `leo`, `dan`, `zac`
- **Inworld** — `Craig`, `Ashley`, `Olivia`, `Sarah`, `Elizabeth`, `Priya`, `Alex`, `Edward`, `Theodore`, `Ronald`, `Mark`, `Hades`, `Luna`, `Pixie`
- **Chatterbox** — `Aurora`, `Britney`, `Siobhan`, `Vicky`, `Blade`, `Carl`, `Cliff`, `Richard`, `Rico`
- **ElevenLabs Turbo** — `Rachel`, `Aria`, `Sarah`, `Laura`, `Charlotte`, `Alice`, `Matilda`, `Jessica`, `Lily`, `Roger`, `Charlie`, `George`, `Callum`, `River`, `Liam`, `Will`, `Eric`, `Chris`, `Brian`, `Daniel`, `Bill` — or any ElevenLabs Voice ID
- **MiniMax** — `WiseWoman`, `FriendlyPerson`, `InspirationalGirl`, `CalmWoman`, `LivelyGirl`, `LovelyGirl`, `SweetGirl`, `ExuberantGirl`, `DeepVoiceMan`, `CasualGuy`, `PatientMan`, `YoungKnight`, `DeterminedMan`, `ImposingManner`, `ElegantMan`
- **Gemini Flash** — `Achernar`, `Achird`, `Algenib`, `Algieba`, `Alnilam`, `Aoede`, `Autonoe`, `Callirrhoe`, `Charon`, `Despina`, `Enceladus`, `Erinome`, `Fenrir`, `Gacrux`, `Iapetus`, `Kore`, `Laomedeia`, `Leda`, `Orus`, `Pulcherrima`, `Puck`, `Rasalgethi`, `Sadachbia`, `Sadaltager`, `Schedar`, `Sulafat`, `Umbriel`, `Vindemiatrix`, `Zephyr`, `Zubenelgenubi`
- **Gradium** — English: `Emma`, `Kent`, `Eva`, `Jack`. German: `Mia`, `Maximilian`. Spanish: `Valentina`, `Sergio`. French: `Elise`, `Leo`. Portuguese: `Alice`, `Davi`

A voice not in the chosen model's list (and not a valid handle / custom Voice ID where allowed) → `400`. An ElevenLabs Voice ID that the provider rejects also → `400` (not charged).

## Voice cloning — `POST /audio/voices`

Clone a voice from an audio sample and get back a handle (`vv_…`) to pass as `voice` on `/audio/speech`. `multipart/form-data` only; max 25 MB.

```bash
curl https://api.venice.ai/api/v1/audio/voices \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -F "model=tts-chatterbox-hd" \
  -F "file=@sample.wav"
```

```json
{ "id": "vv_…", "model": "tts-chatterbox-hd" }
```

| Field | Notes |
|---|---|
| `file` | The voice sample, multipart field `file`. Validated by extension/MIME **and** binary signature. Aim for a clean speech recording of at least 5 s (`voice_cloning.min_sample_seconds`; advisory — Venice does not measure duration). |
| `model` | Defaults to `tts-chatterbox-hd`, the only cloning model open to regular API keys. |

`tts-chatterbox-hd` advertises its cloning contract on `/models` as `model_spec.voice_cloning`:

```json
{ "mode": "zero_shot", "accepted_formats": ["mp3", "wav", "flac", "mp4"], "min_sample_seconds": 5, "retention_days": 7 }
```

- **Zero-shot**: no voice template is derived; the reference audio is stored with a TTL and re-read on every synthesis call. Handles stop working **7 days after creation**, regardless of use.
- `mp4` covers M4A. Samples in other containers (or with a non-audio signature) → `400` before anything is uploaded.
- Each successful clone is charged a flat per-clone fee; synthesis is billed separately per character on `/audio/speech`.

`tts-minimax-speech-02-hd` also appears in the `model` enum in the OpenAPI spec, but cloning with it isn't open to regular keys, which get `403 "Voice cloning … is not available on your account"`. Its model spec on `/models` carries no `voice_cloning` object — use that as the signal.

A handle is bound to the model that created it. Pass it with a model that has no cloning support → `400`; pairing it with a different cloning model fails.

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

With `streaming: true`, the body is a chunked (`Transfer-Encoding: chunked`) audio stream — decode as it arrives. `pcm` (where supported: Kokoro, xAI, MiniMax, Gradium) is convenient for raw Web Audio playback. If the stream fails before headers are sent you get `500 {"error":"Stream error"}`; after that the connection just ends.

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

## Style / emotion (Qwen 3, Gemini Flash)

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

`tts-gemini-3-1-flash` also takes `prompt` (style instructions) and `temperature`, but not `top_p`. For other families, delivery comes from the **voice choice itself** (e.g. Inworld `Hades` vs `Pixie`); `prompt` / `temperature` / `top_p` are silently ignored.

## Errors

| Code | Meaning |
|---|---|
| `400` | Missing `model`, schema error (strict body, `input` > 4096 / empty / unspeakable), voice not valid for the model, unsupported `response_format`, bad cloning sample (`/audio/voices`), handle paired with a non-cloning model. |
| `401` | Authentication failed. |
| `402` | Insufficient balance. Bearer → `{"error":"Insufficient USD or Diem balance…"}`, or `"API key USD|DIEM spend limit exceeded…"` when the key's own cap is hit (no `code` field); x402 → `PAYMENT_REQUIRED` with top-up info. |
| `403` | A `PRIVATE_ONLY` key calling an `anonymized` model, region restriction, or a cloning model not open to your account on `/audio/voices`. |
| `404` | Unknown `model`. |
| `413` | `/audio/voices` sample over 25 MB. |
| `429` | Rate limited. |
| `500` | Inference failure / stream error. |
| `502` | Temporary upstream TTS failure — `{"error":"Speech synthesis failed due to a temporary upstream error. Please retry."}` (no `code` field). Retry with backoff. |
| `503` | Model temporarily offline — retry with jitter. |

See [`venice-errors`](../venice-errors/SKILL.md) for body shapes and retry strategy.

## Gotchas

- Always send `model` — the documented default never applies.
- `input` hard cap is 4096 chars. For long content, split on sentence boundaries and concatenate audio client-side.
- Don't assume `mp3`: Inworld, Chatterbox, Orpheus and Gradium default to `wav`, and any `response_format` outside a model's `supported_formats` returns `400`. Omit `response_format` or check `/models` first.
- `speed` is only applied by Kokoro (unclamped), xAI, ElevenLabs Turbo and MiniMax (clamped). Keep `0.8–1.3` for natural narration.
- `streaming` is a Venice-specific field that isn't in the OpenAI SDK's types; pass it as an extra body field, or call the REST endpoint directly and consume the body.
- Voice names are case-sensitive (`eve` ≠ `Eve`, `af_sky` ≠ `AF_SKY`). Note `leo` (xAI/Orpheus) vs `Leo` (Gradium, French).
- Chatterbox cloned handles expire 7 days after creation. Re-clone rather than storing handles long-term.
- Gradium has no `language` parameter — pick the voice for the language you want.
