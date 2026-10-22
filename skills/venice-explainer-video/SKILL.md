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

- `venice_video_quote` for each scene clip. It prices only `model` and `duration`, so if resolution or audio changes the price for that model, quote through `POST /api/v1/video/quote` with those fields too, as [`venice-create-video`](../venice-create-video/SKILL.md) does.
- `venice_audio_quote` for the music bed (instrumental, about the total length).
- Narration, billed per character of the script.

Show the user the total and get a yes. This is the most expensive workflow in the catalog.

### 5. Generate the pieces

1. **Narration, one file per scene:** generate each scene's line with `venice_tts` and check its length (see below). If a line runs longer than its scene's clip, shorten the line or give the scene a longer duration now, before any video is paid for.
2. **One clip first:** queue the first scene with `venice_video_generate`, poll it with `venice_video_status`, and show it to the user. Confirm the look before queuing the rest, or a wrong style line gets paid for in every clip.
3. **The remaining clips:** queue them all, then poll each. They render in parallel.
4. **Music:** queue an instrumental with `venice_music_generate` (`force_instrumental: true` on models that support it), then poll with `venice_music_status`.

Save each piece to disk with the REST calls in [`venice-create-video`](../venice-create-video/SKILL.md#save-files) and [`venice-create-audio`](../venice-create-audio/SKILL.md#save-files).

### 6. Assemble with ffmpeg

Check that every narration line fits its clip. Each `narration-N.mp3` must be no longer than `scene-N.mp4`:

```bash
for f in narration-*.mp3 scene-*.mp4; do
  printf '%s %s\n' "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"
done
```

Join the clips in order (re-encoding keeps clips with slightly different settings compatible, and `-an` drops any model-generated audio):

```bash
printf "file '%s'\n" scene-1.mp4 scene-2.mp4 scene-3.mp4 > scenes.txt
ffmpeg -f concat -safe 0 -i scenes.txt -an -c:v libx264 -pix_fmt yuv420p video.mp4
```

Pad each scene's narration with silence to exactly its clip's length, then join the pieces, so every line starts with its scene:

```bash
for i in 1 2 3; do
  len=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "scene-$i.mp4")
  ffmpeg -i "narration-$i.mp3" -af "apad,atrim=end=$len" -ar 44100 -ac 2 "narration-$i.wav"
done
printf "file '%s'\n" narration-1.wav narration-2.wav narration-3.wav > narration.txt
ffmpeg -f concat -safe 0 -i narration.txt narration.wav
```

Lay the narration over the video with the music underneath at a low volume, and cut the result to the video's exact length:

```bash
len=$(ffprobe -v error -show_entries format=duration -of csv=p=0 video.mp4)
ffmpeg -i video.mp4 -i narration.wav -i music.mp3 \
  -filter_complex "[2:a]volume=0.15[bed];[1:a][bed]amix=inputs=2:duration=first:normalize=0[audio]" \
  -map 0:v -map "[audio]" -c:v copy -c:a aac -t "$len" explainer.mp4
```

`normalize=0` keeps the narration at full volume; by default `amix` turns every input down. `duration=first` makes the mix as long as the narration, and `-t` ends the file exactly where the video does.

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
- Use the same model and aspect ratio for every scene. Joining scales every clip to the first clip's size, so a clip with a different aspect ratio comes out stretched.
- Generated clips may include their own audio; drop it with `-an` unless the scene needs it.
- Keep every piece (script, prompts, seeds, queue ids) in a project folder, so a single scene can be redone without starting over.

## Related skills

- [`venice-create-video`](../venice-create-video/SKILL.md): clip generation, polling and saving.
- [`venice-create-audio`](../venice-create-audio/SKILL.md): narration, music and saving.
- [`venice-create-image`](../venice-create-image/SKILL.md): consistent stills for image-to-video.
- [`venice-chat`](../venice-chat/SKILL.md): chat completions for the script.
