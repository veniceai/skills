---
name: venice-explainer-video
description: Narrated explainer video workflow with Venice. Use when a user wants a short explainer, product walkthrough or social video built from several generated clips with voiceover and background music. Covers writing and timing the script with a text model, splitting it into scenes that match model clip durations, keeping a consistent look across scenes, quoting the whole project before spending, generating clips, narration and a music bed, and assembling the final MP4 locally with ffmpeg. Uses venice_chat, venice_video_quote, venice_video_generate, venice_video_status, venice_tts, venice_audio_quote and venice_music_generate from the Venice MCP server, or the matching REST endpoints.
---

# Explainer videos with Venice

Venice generates the pieces: script, scene clips, narration and music. You assemble them into one MP4 on the user's machine with `ffmpeg`. Built on [`venice-create-video`](../venice-create-video/SKILL.md) and [`venice-create-audio`](../venice-create-audio/SKILL.md).

| Piece | Venice MCP tool | REST endpoint |
|---|---|---|
| Script and scene plan | `venice_chat` | `POST /api/v1/chat/completions` |
| Scene stills (optional) | `venice_image_generate` | `POST /api/v1/image/generate` |
| Scene clips | `venice_video_quote`, `venice_video_generate`, `venice_video_status` | `/api/v1/video/quote`, `/video/queue`, `/video/retrieve` |
| Narration | `venice_tts` | `POST /api/v1/audio/speech` |
| Music bed | `venice_audio_quote`, `venice_music_generate`, `venice_music_status` | `/api/v1/audio/quote`, `/audio/queue`, `/audio/retrieve` |

## Use when

- A user wants a 30-90 second explainer, demo or social video, not a single clip.
- The video needs a voiceover and background music.

## Workflow

### 1. Write the script and scene plan

Use `venice_chat` to draft the narration from the user's topic and audience, then split it into scenes. For each scene, record the narration line, what is on screen, and a target length. Speech runs at roughly 150 words a minute, so a 6 second scene holds about 15 words.

### 2. Fit scenes to clip lengths

Video models only make clips of fixed lengths. Read the chosen model's `durations` with `venice_model_details` (`type: "video"`) and give every scene one of those lengths. Merge or split scenes rather than forcing a length the model can't make.

### 3. Lock the look

Consistency across scenes is what makes generated clips feel like one video:

- Write one style line (palette, art style, camera feel) and append it to every scene prompt.
- For the strongest consistency, generate a still per scene with `venice_image_generate` (same style line, same `seed`), then animate each still with an image-to-video model via `image_url`.
- Use the same model and aspect ratio for every scene.

### 4. Quote the whole project, then confirm

Before generating anything, add up:

- `venice_video_quote` for each scene clip,
- `venice_audio_quote` for the music bed (instrumental, about the total length),
- narration, billed per character of the script.

Show the user the total and get a yes. This is the most expensive workflow in the catalog.

### 5. Generate the pieces

1. **Narration:** generate it first with `venice_tts`, scene by scene or as one file, so you know the real timing.
2. **Clips:** queue every scene with `venice_video_generate`, then poll each with `venice_video_status`. Queue them all before polling; they render in parallel.
3. **Music:** queue an instrumental with `venice_music_generate` (`force_instrumental: true` on models that support it), then poll with `venice_music_status`.

Save each piece to disk with the REST calls in [`venice-create-video`](../venice-create-video/SKILL.md#save-files) and [`venice-create-audio`](../venice-create-audio/SKILL.md#save-files).

### 6. Assemble with ffmpeg

Check timing first:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 narration.mp3
```

Join the clips in order (re-encoding keeps clips with slightly different settings compatible, and `-an` drops any model-generated audio):

```bash
printf "file '%s'\n" scene-1.mp4 scene-2.mp4 scene-3.mp4 > scenes.txt
ffmpeg -f concat -safe 0 -i scenes.txt -an -c:v libx264 -pix_fmt yuv420p video.mp4
```

Lay the narration over the video with the music underneath at a low volume:

```bash
ffmpeg -i video.mp4 -i narration.mp3 -i music.mp3 \
  -filter_complex "[2:a]volume=0.15[bed];[1:a][bed]amix=inputs=2:duration=first[audio]" \
  -map 0:v -map "[audio]" -c:v copy -c:a aac -shortest explainer.mp4
```

`duration=first` makes the mix as long as the narration, and `-shortest` ends the file at whichever is shorter. If the narration is longer than the joined clips, its end gets cut, so add or lengthen a scene first.

### 7. Deliver

Share the final MP4 plus the script, so the user can tweak a line and regenerate just that scene's narration and clip.

## Cost

Several video clips plus narration and music add up quickly. Always quote the whole project first, regenerate only the scenes that need it, and tell the user each retake is billed.

## Errors

| Status | Likely cause | What to do |
|---|---|---|
| `400` | A clip `duration` or `aspect_ratio` the model doesn't list | Re-read `venice_model_details`. |
| `402` | Balance ran out partway through | Stop, tell the user what finished, and resume after a top-up. |
| `422` | A scene was rejected by content policy | Rewrite that scene's prompt only. |
| `429` | Too many jobs queued or polled at once | Back off; poll every 10-20 seconds. |

Full error handling is in [`venice-errors`](../venice-errors/SKILL.md).

## Gotchas

- Keep narration lines short. Long sentences force long scenes that models can't make.
- Concatenating with `-c copy` fails when clips differ in resolution or codec; re-encode as above.
- Generated clips may include their own audio; drop it with `-an` unless the scene needs it.
- Keep every piece (script, prompts, seeds, queue ids) in a project folder, so a single scene can be redone without starting over.

## Related skills

- [`venice-create-video`](../venice-create-video/SKILL.md): clip generation, polling and saving.
- [`venice-create-audio`](../venice-create-audio/SKILL.md): narration, music and saving.
- [`venice-create-image`](../venice-create-image/SKILL.md): consistent stills for image-to-video.
- [`venice-chat`](../venice-chat/SKILL.md): chat completions for the script.
