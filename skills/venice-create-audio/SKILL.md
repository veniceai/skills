---
name: venice-create-audio
description: End-to-end audio creation workflow with Venice. Use when a user wants finished audio - "write and produce a jingle", "make a 30 second lo-fi loop", "add a voiceover", "I need a whoosh sound effect". Covers choosing between a song with lyrics, an instrumental, a sound effect, a seamless loop and spoken narration, reading each music model's lyrics, duration and loop support from the live catalog, quoting before queuing, polling, cleanup, picking a TTS voice, and saving files. Uses the Venice MCP tools (venice_audio_quote, venice_music_generate, venice_music_status, venice_tts, venice_voice_clone, venice_list_models, venice_model_details) when available, or /audio/quote, /audio/queue, /audio/retrieve and /audio/speech otherwise.
---

# Create audio with Venice

A workflow for music, sound effects and voiceover. Music and sound effects are asynchronous jobs that are quoted, queued and polled. Speech is a single synchronous call. Every field is documented in [`venice-audio-music`](../venice-audio-music/SKILL.md) and [`venice-audio-speech`](../venice-audio-speech/SKILL.md).

| Step | Venice MCP tool | REST endpoint |
|---|---|---|
| Find music models and their features | `venice_list_models` (`type: "music"`), `venice_model_details` | `GET /api/v1/models?type=music` |
| Price a music job | `venice_audio_quote` | `POST /api/v1/audio/quote` |
| Queue music or a sound effect | `venice_music_generate` | `POST /api/v1/audio/queue` |
| Poll, then collect the audio | `venice_music_status` | `POST /api/v1/audio/retrieve` |
| List voices | `venice_voice_clone` (`action: "list"`) | `GET /api/v1/models?type=tts` |
| Speak text | `venice_tts` | `POST /api/v1/audio/speech` |

## Use when

- The user wants a song, an instrumental bed, a loop or a sound effect produced.
- A video, ad or explainer needs narration or a soundtrack.
- You need to price an audio job before committing to it.

## Pick the right kind of audio

| The user wants | Use | Model feature to check |
|---|---|---|
| A song with sung lyrics | `venice_music_generate` with `lyrics_prompt`, or `lyrics_optimizer: true` to write lyrics from the prompt | `supports_lyrics`, `supports_lyrics_optimizer`, lyrics character limit |
| Background music, no vocals | `venice_music_generate` with `force_instrumental: true` | `supports_force_instrumental` |
| A sound effect | `venice_music_generate` on a sound-effects model | model type and duration options |
| A seamless loop | `venice_music_generate` with `loop: true` | `supports_loop` |
| Spoken narration | `venice_tts` | voices for the TTS model |

## Workflow: music and sound effects

### 1. Pin down the brief

Ask for genre or mood, tempo or energy, length, whether it needs vocals, and where it will be used. For a song, agree on the lyrics (or let the model write them) before spending anything.

### 2. Pick a model

Call `venice_list_models` with `type: "music"`, then `venice_model_details` for the candidate with `type: "music"`. Check the features in the table above plus the duration rules: some models take `duration_seconds` within a range or from a fixed list, and some take no duration at all. Sending a field the model does not support is a `400`.

### 3. Quote and confirm

Call `venice_audio_quote` with `model`, plus `duration_seconds` for models that take a duration, or `character_count` for models priced per thousand characters. It is free. Tell the user the price and get a yes.

### 4. Queue

Call `venice_music_generate` with `model` and `prompt`, plus whichever of `duration_seconds`, `lyrics_prompt`, `lyrics_optimizer`, `force_instrumental` or `loop` the model supports. Keep the returned `queue_id` together with the `model`.

Use `lyrics_prompt` and `force_instrumental`. The older `lyrics` and `instrumental` names are deprecated.

### 5. Poll, collect, clean up

Call `venice_music_status` with `queue_id`, `model` and `delete_media_on_completion: true`. While it says `PROCESSING`, it reports `average_execution_time` and `execution_duration` in milliseconds; poll every 2-5 seconds. When it completes, the result is the audio, embedded or as a `download_url` link.

- `delete_media_on_completion` is safe on every poll: Venice deletes its stored copy only once the audio has been returned. The MCP tool ignores it for a `download_url` result, so download that file first, then call `venice_music_complete`.
- A failed job is refunded and returns its error here. Stop polling it; only a `429` or `503` is worth retrying after a backoff.

## Workflow: voiceover

1. Write the script. Short sentences read better; keep each call to a paragraph or two.
2. Call `venice_voice_clone` with `action: "list"` to see the voices each TTS model offers. Pick the model and a voice that suits the brief.
3. Call `venice_tts` with `input`, `model` and `voice`. Optional: `speed`, `response_format` (`mp3`, `wav`, `opus`, `aac`, `flac`, `pcm`). Some models understand inline tags such as `[whispers]`; check the model's documentation before relying on them.
4. To speak in a specific voice, clone it first with `venice_voice_clone` (`action: "create"`, `sample_url` pointing at a public audio file), then pass the returned `vv_...` handle as `voice` with the same `model`. Only clone a voice with its owner's permission.

## Save files

The MCP tools return audio inline. To save files, call the REST endpoints from a shell with the user's key in `VENICE_API_KEY`:

```bash
# Narration: the response body is the audio file
code=$(curl -sS https://api.venice.ai/api/v1/audio/speech \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-kokoro","voice":"af_sky","input":"Welcome to the launch."}' \
  --output voiceover.mp3 -w '%{http_code}')
[ "$code" = 200 ] || { echo "speech failed ($code):"; cat voiceover.mp3; rm -f voiceover.mp3; }

# Music: only a 200 with an audio/ content type is the finished track
result=$(curl -sS https://api.venice.ai/api/v1/audio/retrieve \
  -H "Authorization: Bearer $VENICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"elevenlabs-music","queue_id":"<queue_id>","delete_media_on_completion":true}' \
  --output track.mp3 -w '%{http_code} %{content_type}')

case "$result" in
  "200 audio/"*) echo "saved track.mp3" ;;
  "200 "*)       cat track.mp3; rm -f track.mp3 ;;  # PROCESSING: poll again in 2-5 seconds. COMPLETED: use its download_url
  429*|503*)     rm -f track.mp3; echo "busy, poll again later" ;;
  *)             cat track.mp3; rm -f track.mp3 ;;  # failed: stop polling
esac
```

An error body is written to the output file just like audio would be, which is why both calls check the status before keeping the file.

A `200` JSON body is either still `PROCESSING` or `COMPLETED` with a `download_url` instead of the audio. For a link, download the file from it, then call `POST /api/v1/audio/complete` (`venice_music_complete`) with the same `queue_id` and `model` to delete the stored copy. The MCP tool ignores `delete_media_on_completion` for a link, so that call is what cleans up.

## Cost

Music jobs are charged when queued and refunded if they fail. Speech is billed per input character. Quote music first, and tell the user before generating several takes or long narration.

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | A field the model doesn't support (lyrics, duration, loop), a duration outside its range, or lyrics over the limit | Re-read `venice_model_details`. |
| `402` | Insufficient balance | Tell the user; don't retry. |
| `422` | Content policy rejection | Revise the prompt or lyrics. |
| `429` | Rate limit while queuing or polling | Back off, then retry. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- Some lyric models need lyrics of a minimum length unless `force_instrumental` or `lyrics_optimizer` is set.
- `lyrics_optimizer` writes lyrics from your prompt; leave `lyrics_prompt` empty when you use it.
- `loop` only works on models that report loop support.
- Output formats differ between TTS models; check the model before asking for a specific `response_format`.
- Stored results don't last forever: once media expires or is deleted, retrieve returns `404`. Collect finished audio promptly.

## Related skills

- [`venice-audio-music`](../venice-audio-music/SKILL.md): every music field, voices, pricing shapes and refunds.
- [`venice-audio-speech`](../venice-audio-speech/SKILL.md): TTS models, voices, cloning and formats.
- [`venice-create-video`](../venice-create-video/SKILL.md): pair a soundtrack or voiceover with a clip.
- [`venice-errors`](../venice-errors/SKILL.md): error shapes and retries.
