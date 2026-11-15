# MiniMax H3 video in Continuo — core reference

Load this when you write, check or repair a prompt for any local MiniMax H3 video target. It covers what the
server sends, the prompt grammar, description craft, camera, sound and dialogue, length, retakes and failure
modes. Companion files: `skill_view('film-suite:video-prompts', 'references/ref-h3-video-keyframes.md')` (Frames target, reading and preparing keyframes),
`skill_view('film-suite:video-prompts', 'references/ref-h3-video-references.md')` (six-field References target), `skill_view('film-suite:video-prompts', 'references/ref-h3-video-continuation.md')` (Extend, Prepend,
Fill gap, Finish), `skill_view('film-suite:video-prompts', 'references/ref-h3-video-film-tasks.md')` (worked recipes).

Evidence tags: `[official]` MiniMax H3 model card and prompt guides; `[code]` Continuo source; `[local]` installed
ComfyUI node source; `[community]` named, dated practitioner reports; `[house]` measured or decided in Continuo
work; `[hypothesis]` plausible, untested. Sources are listed at the end.

---

## 1. Scope: the eight targets

H3 is a 33B audio-video diffusion transformer that renders picture and stereo sound in one pass, 24 fps, 4-15 s,
about 768 px on the short edge `[official]`. The released checkpoints are CFG-distilled: there is no negative
prompt and no guidance scale `[official]`. Continuo runs two checkpoints, both int8: `fl2va` (text, first frame,
last frame) and `ref2va` (references) `[code]`.

| Target | Checkpoint + sampling (pinned) | Inputs | Prompt form |
|---|---|---|---|
| `minimax-h3-t2v` | fl2va, no turbo LoRA, res_multistep / simple / 20 steps, 1.0 MP only | text | three fields |
| `minimax-h3-t2v-sampling-v2` | same graph as t2v; exposes steps 1-100 (20), sampler res_multistep\|euler, scheduler simple\|beta, size Draft 0.5 \| Native 1.0 (1.0) | text | three fields (identical to t2v) |
| `minimax-h3-frames-v1` | fl2va + sigma shift 12/3 + turbo LoRA 0.8, er_sde / beta / 12 steps, Draft default | up to 10 keyframes, `sound_track`, `camera` | alignment line + three fields |
| `minimax-h3-references-v1` | ref2va + sigma shift 12/3 + turbo LoRA 0.8, er_sde / beta / 12, Draft default | up to 9 pictures, 3 clips, 1 motion guide, 3 voice/music files, keyframes, `sound_track`, `camera` | six fields |
| `minimax-h3-extend-mctx-v1` | ref2va, no turbo, res_multistep / simple / 20 | one take with `.mctx` sidecar | three fields, new part |
| `minimax-h3-prepend-mctx-v1` | same | one take with sidecar | three fields, lead-in |
| `minimax-h3-bridge-mctx-v1` ("Fill gap") | same | two takes, same size | three fields, the gap |
| `minimax-h3-finish-v1` | operation: latent upscale to 1.5 MP and/or RIFE 48 fps | one finished take with sidecar | **no prompt** |

`[code]` registry.py:831-1013, workflows/minimax-h3-*/workflow-api.json, h3_finish.py.

What the two newer targets mean for you:
- **`t2v-sampling-v2`** is not a new model or grammar. It is the same pinned Text to Video graph with steps,
  sampler, scheduler and a Draft size exposed. Write the same three-field prompt. Use it for cheap Draft trials of
  a text-only shot and for step tests; `minimax-h3-t2v` stays the byte-stable default `[code]`
  workflow_manifest.py:762-808, comfyui_provider.py:246-278.
- **`finish-v1`** takes no prompt (`prompt_sent: None`). Args are `{take, upscale, rife}`, at least one on.
  Upscale decodes the take's stored latent through the H3 latent upscaler to 1.5 MP; RIFE doubles to 48 fps. It
  only works on takes that carry their `.mctx.safetensors` sidecar `[code]` h3_finish.py:134-228. Details in
  the continuation reference.

H3 is for: short live-action or animated shots with synchronized sound and speech, camera moves from a closed
vocabulary, identity and voice from references, seamless extensions. It is not for: exact on-screen typography
(text renders, but treat it as a graphic task), dolly zoom, a world that holds dead still, dense dialogue between
two referenced voices, or shots longer than 15 s in one take.

---

## 2. What Continuo sends (do not duplicate it)

- **Your prompt goes to H3 literally.** The hosted H3 service runs a rewriter ("H3-Context-IR") that turns a free
  request into the structured prompt; Continuo has none and never rewrites `[official]` README, `[code]`
  `prompt_policy: literal`. Write the structured prompt yourself.
- **The text encoder sees raw text, no chat template.** On Frames it sees `<Picture 1>: [image]` (and
  `<Picture 2>: [image]` for a last frame) before your prompt; on References `<Picture i>: `, `<Audio j>: `,
  `<Video k>: ` with the clip's frames at 2 fps and timestamps, then your prompt `[local]` comfy/text_encoders/minimax.py.
  Mid-shot keyframes (guides) never reach the text encoder: they are latent-only, so they have no label.
- **The `camera` arg** (Frames and References only): the server writes
  `The camera performs <a Push In | an Arc Shot to the left | an Arc Shot to the right | a Shake> with <large|small>
  amplitude at <slow|fast> speed: <one consequence sentence>` right after `[Shot 1]` (with six fields: the `[Shot 1]` inside `detailed_description`), and on Frames
  prepends the frame-0 alignment line when a keyframe sits at frame 0 `[code]` h3_conditioning.py `camera_prompt`.
  It refuses the request if your prompt already contains "the camera performs", a bracketed camera tag or a
  `[Shot 2]` or later. Allowed values: `arc_shot` (direction left|right, amplitude large|small, speed slow|fast),
  `push_in` (large|small, slow|fast), `shake` (large + fast only) `[code]` :505-545.
- **Audio references** (References only): for each `reference_audios` entry and each clip in
  `reference_video_sound` the server adds one `subject_definitions` line and one `retention_analysis` line unless
  your section already names that `<Audio N>` `[code]` :598-655. Full wording in the references file.
- **Sizes** `[code]` h3_conditioning.py:174-208, `[local]` ResolutionSelector:

| Aspect | Frames / References Draft | Frames / References Native | t2v + sampling-v2 at 1.0 | sampling-v2 at 0.5 |
|---|---|---|---|---|
| 16:9 | 864x480 | 1344x768 | 1376x768 | 960x544 |
| 21:9 | 992x416 | 1536x672 | 1568x672 | 1120x480 |
| 4:3 | 640x480 | 1024x768 | 1184x896 | 832x640 |
| 1:1 | 480x480 | 768x768 | 1024x1024 | 736x736 |
| 3:4 | 480x640 | 768x1024 | 896x1184 | 640x832 |
| 9:16 | 480x864 | 768x1344 | 768x1376 | 544x960 |

  Frames/References follow the official H3 canvas (768 short edge, area cap 768x1344); the two Text to Video
  targets use a generic megapixel selector, so at 4:3, 1:1 and 3:4 they render above the official canvas
  (1024x1024 vs 768x768) `[code]` `[local]` comfy_extras/nodes_resolution.py. `[hypothesis]` slightly off-distribution.

- **Length** snaps up to 17k+5 frames at 24 fps `[code]` `[local]`. The alignment line and every timestamp use
  the snapped length:

| `duration_seconds` | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frames | 107 | 124 | 158 | 175 | 192 | 226 | 243 | 277 | 294 | 328 | 345 | 362 |
| real length, `S.SS` | 4.46 | 5.17 | 6.58 | 7.29 | 8.00 | 9.42 | 10.12 | 11.54 | 12.25 | 13.67 | 14.38 | 15.08 |
| last frame index | 106 | 123 | 157 | 174 | 191 | 225 | 242 | 276 | 293 | 327 | 344 | 361 |

  The node notes the trained range as about 124-362 frames `[local]` nodes_minimax_h3.py:126: a 4 s take
  (107 frames) is below it `[hypothesis: slightly less reliable]`.
- Keyframes and the motion guide are cropped to the canvas from the centre before upload; reference pictures and
  reference clips keep their own aspect `[code]` registry.py:716, h3_conditioning.py:673-695. Put the subject where
  a centre crop keeps it, or pick the canvas aspect of the keyframe.

---

## 3. Grammar

### 3.1 The two schemas

Three fields (Text to Video, Frames, Extend/Prepend/Fill gap), this order, exact spelling `[official]`:

```
integrated_multimodal_description:
[Shot 1] ...

overall_soundscape:
...

non_diegetic_music:
...
```

Six fields (References only): `subject_definitions:`, `summary:`, `retention_analysis:`,
`detailed_description:`, `overall_soundscape:`, `non_diegetic_music:` `[official]`. The schemas never mix.

The official base guide prints the value on the same line (`integrated_multimodal_description: [Shot 1] ...`), the
reference guide puts it on the next line; both are official. On References put every label alone on its line:
the server finds `subject_definitions:` and `retention_analysis:` only as whole lines, and otherwise prepends
duplicate sections when it adds audio lines `[code]` h3_conditioning.py:617-655.

### 3.2 Alignment line (Frames only, first line, then one blank line) `[official]`

- first frame only: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- first and last: `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.`
- last only: `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`

Copy them exactly: the em dash and the bracket difference between the lines are official. `N` = the final shot
number, `S.SS` = the real length from the table above. Text to Video, References and continuations take no
alignment line. With the `camera` arg and a frame-0 keyframe the server writes the first line for you.

### 3.3 The description field, in order

1. **Medium and composition first.** `[Shot 1] Live-action, cinematic, a medium-wide shot frames ...` The guide
   lists `Cinematic`, `live-action`, `2D-animated`, `3D CG`, `claymation`, `watercolor`, `vintage film`; with a
   keyframe derive the medium from the picture `[official]`. Naming the medium first also reduces slow-motion
   drift `[house]`.
2. **Starting state.** Text to Video: what is in frame before anything moves. With a keyframe: only what changes,
   plus a short anchor ("the man in <Picture 1> stays at the counter").
3. **Action as an arc: start → path → end state.** Name the terminal event; multi-stage actions stall before it
   when it is not named ("draws, steadies, releases; the arrow leaves the bow") `[community]`.
4. **Physical consequence in words** ("the boot splashes water outward, drops fall back on the stones").
5. **One camera sentence** (section 4).
6. **Speech and shot-synced sound** inside this field; ambience goes to `overall_soundscape`.
7. **End state as a positive, visible state** ("she stays seated, hands on the letter, camera still").

Only what can be seen or heard: not "she feels guilty" but "she glances at the door and tightens her grip on the
envelope" `[official]`. Small integers where count matters ("two knocks", "one nod").

### 3.4 Shots and cuts

- `[Shot 1]` has no timestamp. Later shots: `[Shot 2] At 00:03.500, the camera cuts to ...`, strictly increasing,
  inside the real length `[official]`.
- Every `[Shot N]` is a hard cut; a cut must bring new information about subject, space, state, viewpoint or time.
  For a size change move the camera instead `[official]`.
- A timestamp alone does not cut: `At 00:02.400, the kettle clicks off.` stays inside the shot. Timestamped beats
  are your strongest tempo and pause control `[house]`.
- Restate light and time of day in every shot; a night that was named only in Shot 1 rendered as day after the
  cut `[house]`.
- In-take cuts land close to their timestamps (within about 2 frames in house tests) `[house]`; multi-shot
  montages inside one take work (section 7 of the film-task file).

### 3.5 Visible text

On-screen text goes in English double quotes, verbatim, in its own language: `A neon sign reading "OPEN" hangs
in the window.` `[official]`. A surface that comes close to the lens without wanted text gets a positive plain
description in every take ("a plain, unmarked steel panel; it stays bare as it comes closer"), or H3 invents
lettering on it `[house]`. Never put speech in quotes (section 5).

### 3.6 Negatives and weights

There is no negative prompt and no weight syntax `[official: CFG-distilled]`. Naming an unwanted thing tends to
pull it in. Describe the wanted state positively; keep a negation only as a bounded qualifier on a positive action
("lifts the cup without spilling", "single continuous shot") `[community]` `[house]`. Escalating "freeze / hold /
unchanged" language makes results worse `[community]`.

---

## 4. Camera

Closed vocabulary `[official]`: `Zoom In/Out` (lens only), `Push In/Pull Out` (body moves), `Pan Left/Right`,
`Truck Left/Right`, `Tilt Up/Down`, `Pedestal Up/Down`, `Arc Shot`, `Tracking Shot`, `Static Shot`,
`Shake Slightly/Strongly`, `POV`, `Roll Clockwise/Counterclockwise`; modifiers `with small|large amplitude`,
`at slow|fast speed` (omit them for medium/normal).

- Write one sentence inside the shot: `The camera pushes in with small amplitude at slow speed toward the letter.`
  Never a bracket tag, never a separate `Camera:` line. One move per shot.
- **Lock the camera explicitly** when composition matters later: `The camera holds a static shot.` Omitting camera
  words gives drift, not stillness `[community]`. A "slight" push on a two-shot still pushed until a foreground hat
  filled half the frame `[house]`.
- **Distance comes from a named destination, not from the amplitude word.** A reveal pull-out moved far only with
  a short take, "one fast, accelerating rush", a concrete end ("until the whole harbour wall and the moored ferry
  are in frame") and "stops dead at 00:01.80" `[house]`.
- Dolly, crane, handheld, focal lengths and "locked off" are not in the list: translate to framing + a listed term
  (handheld → `Shake Slightly`; crane → `Pedestal Up`). Dolly zoom does not work as a prompt `[house]`.
- Movement along the lens axis is foreshortened to nothing; put the camera off the travel axis or describe what
  the moving edge sweeps across `[community]`.
- **`camera` arg instead of words** (Frames/References): when you pass it, write no camera words, no bracket tag,
  no `[Shot 2]` and (with a frame-0 keyframe) no alignment line. Measured: arc and push move with large/slow;
  shake only with large/fast `[code]` h3_conditioning.py:498-517. On References prefer writing the camera sentence
  yourself: the server inserts the arg's sentence after the **first** `[Shot 1]` in the text, which in a six-field
  prompt is usually inside `retention_analysis` ("appears in [Shot 1]") `[code]` :575-580.
- **Frozen takes.** A keyframe-anchored camera move is seed-bistable: same words, one seed moves, another freezes
  `[house]`. After a take that asked for motion read `continuo_take_freeze_check`; frozen = both global and local
  motion below 1.0/255 `[code]` h3_media.py:53,509-514. Frozen although motion was asked: same words, seed + 1. A
  locked shot with a small moving subject can read frozen and be right: let the artist look.

---

## 5. Sound and dialogue

### 5.1 Speech

`The ferry deckhand with a low, rough voice (S1) says: <d>[English] Tie her off.</d>` `[official]`

- Speaker description, ID, action and delivery outside the tag; inside only `[Language]` and the exact words in
  their own language. `<d>` and `</d>` are real tokens of the H3 tokenizer `[local]`.
- **No quotation marks around speech**: quotes mean visible text and burn subtitles into the picture `[community]`.
- **No ellipses or decorative punctuation inside `<d>`**: ellipses turned clean dialogue into babble
  `[community 2026-10-09]`. The official guide says to keep the user's punctuation verbatim; in Continuo the house
  rule wins: rewrite "No... wait" as "No. Wait." and tell the artist.
- IDs follow the order of vocal events and stay fixed; two at once `(S1,S2)`. Characters who never vocalise get no
  ID `[official]`. Two speakers: tell them apart by age, sex, clothing and voice, not by name alone `[community]`.
- Voiceover: `says in an off-screen voiceover: <d>...</d> while his lips remain completely closed.` `[official]`
- A line across a cut: `<scenetrans>` on both sides plus a sentence such as "her voice continues seamlessly across
  the cut"; speech cut by the clip's end: `<cutoff>` `[official]`. These two are plain text to the model, not
  tokens (the tokenizer has `<|cutoff|>`, not `<cutoff>`) `[local]`; the English sentence carries the meaning
  `[community]`. Keep the sentence, never rely on the marker alone.
- 11 languages are stable (Arabic, Chinese, English, French, German, Italian, Japanese, Korean, Portuguese, Russian,
  Spanish) `[official]`.

### 5.2 Timing a line (decide before writing)

- Read the line aloud and time it. A 4-6 word line needs about 1.2-1.5 s; H3 tends to speak slower than the
  timestamps ask (a line set at 2.40 s ran 2.46-4.52 s) `[house]`.
- **One continuous line = one `<d>` block**, no ellipsis, no dash, no action written in the middle of it, and a
  clip only as long as the line plus its lead-in and reaction. When the clip is longer than the written content
  H3 fills the time: invented words, babble or a long pause inside the line `[community]` `[hypothesis for the
  mid-line pause]`. Say the delivery outside the tag: "says in one breath, without stopping".
- Anchor the line's end with an action: "... </d> He stops talking at 00:03.20, closes his mouth and looks down."
  Ending dialogue with a visible action keeps later timing on schedule `[community 2026-09-29]`.
- Two lines: give each its own timestamp and a breath beat between them `[house]`.
- Plan to cut in the edit; check delivered words with a word-timestamp transcription before showing `[house]`.

### 5.3 Silence

If nobody speaks, write it: `No one speaks.` H3 invents speech that is not addressed, most often when the clip is
longer than what is written `[community, many reporters]`. Keep background figures to breathing and small
gestures; a background figure given a murmur spoke gibberish `[house]`.

### 5.4 `overall_soundscape` and `non_diegetic_music`

- `overall_soundscape`: 1-4 sentences, one paragraph, concrete sources: ambience bed first, then the discrete
  sounds in screen order ("Diesel throb and wind under it; the rope slaps the steel deck twice") `[official]`.
  No dialogue, no music. `N/A` only for requested total silence.
- `non_diegetic_music`: 1-3 sentences of instruments, tempo, rhythm, dynamics and an end ("solo cello, slow,
  stops under the final pose"), no mood words `[official]`. A take without score: exactly `N/A`, and no musical
  words ("swell", "melodic hum", "tonal") in any field `[house]`. A radio or band in the scene is diegetic and
  goes in the description.
- Every sound you name gets rendered, and in a short take it gets rendered big: name only events the shot needs
  `[house]`. An off-screen cause stays in `overall_soundscape`; describing its visible effects pulls it into frame
  `[house]`.
- `sound_track` (Frames, References): the file plays exactly from frame 0 and replaces the take's own sound for
  its length; the picture follows it. Keep its spoken words in `<d>` so the lips match `[code]` `[house]`.

---

## 6. Length

- **Three-field description: about 100 words** (published working prompts 59-133) `[community corpus]`.
  **Six-field `detailed_description`: 350-500 words** for generation `[official]`. Locally nothing truncates a
  long prompt; adherence thins instead `[local]` `[community]`.
- **More beats than seconds get dropped; fewer beats than seconds get padded** with invented motion, speech or
  slow motion `[community]`.
- **Clip length is a tempo control.** H3 fits the written arc into the clip: a fast beat in a long clip plays in
  slow motion, a calm beat in a short clip turns hectic `[house]` `[community]`. Size the take to the action's
  natural duration, not to its slot in the cut; trim in the Cut. Continuo submits whole seconds 4-15.
- **Slow motion is the default drift.** Against it: the medium opener, timestamped beats with short windows
  ("At 00:01.20, in one quick snap lasting a quarter of a second, ..."), brisk verbs (snaps, slams, stops dead),
  a moving cause that keeps running until its trigger, and never "slowly" or "gradually" on gestures `[house]`.

---

## 7. Parameters

| Knob | Official / pinned | House use |
|---|---|---|
| steps | t2v 20 (fixed); Frames/References 12 with turbo; continuations 20 | keep defaults; more steps do not fix fast-motion smear (one latent frame spans 4 picture frames) `[official]` `[community]` |
| sampler / scheduler | er_sde / beta with turbo; res_multistep / simple without | change only for a deliberate test |
| megapixels | Draft (~0.4 MP) / Native (~1 MP) | Draft for trials, Native for keepers; a face that is small in frame needs more pixels than 1 MP gives `[house]` |
| seed | 0-4294967295 | one change per retake; frozen take → seed + 1 |
| `count` (Frames/References) | 1-8 takes, seeds seed+i | cheap way to find a seed that moves |
| turbo, turbo_strength, recipe, sigma shift, LoRAs, attention, cache | `continuo_h3_controls` lists them with proof state | quality/speed tools, not prompt tools; leave pinned unless testing. Turbo LoRAs are reported to cut prompt adherence on complex timelines `[community 2026-11-08]` |

---

## 8. Before you write: the operator's checklist

Decide each of these and write the decision into the prompt or into a note to the artist:

1. **Target and form**: text only → t2v; pictures at exact frames → Frames; identity/voice/style references →
   References; continues a take → Extend/Prepend/Fill gap.
2. **The keyframe as a director reads it** (Frames): who is where, which hand holds what, eyelines, camera height,
   what touches the frame edges, light direction, any text surface. The action must be possible from that exact
   pose; never fight the picture's geometry. Full list in the keyframes file.
3. **Time budget**: real length from the table; each beat's start and end; the line's spoken length.
4. **Sound plan**: who speaks what and when; the moments of silence; every named sound and its size; score or `N/A`.
5. **Event wording**: say exactly the physical event, at the size wanted. "Pulls the trigger" or "fires" brings
   a muzzle flash, recoil and a bang; a dry-fire beat is "the hammer snaps down on an empty chamber: one dry
   metallic click; the hand and barrel stay still" plus "a single dry click" in the soundscape `[house lesson]`.
6. **Boundaries**: what stays off-screen, what may enter or leave frame, camera locked or moving.
7. **End state** the next shot or extension starts from.

---

## 9. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Burned-in subtitles | quotes around speech | `<d>` without quotes |
| Speech or babble nobody wrote | silence not stated; clip longer than content; ellipses in `<d>` | "No one speaks."; shorter clip or more written action; plain punctuation |
| Long pause inside one line | line split, action inside it, clip too long | one `<d>`, delivery "in one breath", end-anchor action, shorter clip |
| Music in a score-free take | musical words anywhere; field not `N/A` | `N/A`, concrete sources only |
| Unwanted cut | a second `[Shot N]` | one shot, move the camera |
| Holds frame 0, then cuts away | keyframe and prompt disagree | describe the keyframe's scene; change the picture, not the words |
| Action stalls before its end | terminal event not named | name the end state |
| Slow motion | clip too long for the action; soft verbs | shorter clip, timestamps, brisk verbs |
| Hectic, invented motion | clip too short for a calm beat | 4-5 s take, cut later |
| Camera drifts | no camera words | `The camera holds a static shot.` |
| Barely moves although asked | frozen seed | same words, seed + 1 |
| Event reads bigger than meant (a click becomes a shot) | loaded verb, event named loudly | describe the exact small physical event; size the sound |
| Off-screen cause appears | its visible effects were described | keep it in `overall_soundscape` only |
| Gibberish lettering on a close surface | surface left undescribed | "plain, unmarked ..., stays bare" |
| Night turns to day after a cut | light not restated | restate light per shot |
| A light flicker reads as defects | flicker prompted | steady light; flicker in the grade |
| `camera` refused | prompt names a camera move, tag or second shot | remove it or drop the arg |
| References ignored | missing role line, three-field prompt, too long | see references file |
| An excluded thing appears ("no cars") | naming pulls it in | describe what is there |

---

## 10. Sources (accessed 2026-11-12 unless dated)

- `[official]` MiniMax H3 model card, huggingface.co/MiniMaxAI/MiniMax-H3 (README: specs, CFG-distilled
  checkpoints, Context-IR, 11 languages, example Context-IR prompts).
- `[official]` `docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md` and `docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` in the
  same repo; byte-identical copies ship as `skills/h3-prompt-writing/references/{base-en,ref-en}.txt` in
  github.com/MiniMax-AI/MiniMax-H3.
- `[official]` docs.comfy.org/tutorials/video/minimax/minimax-h3 (templates, ~1 MP / 768 px open weights).
- `[local]` ComfyUI core `comfy_extras/nodes_minimax_h3.py` (frame grid, canvas, first frame stretched, guides
  cover-cropped, trained range) and `comfy/text_encoders/minimax.py` (presentation, special tokens).
- `[code]` Continuo release candidate: `generation/registry.py`, `h3_conditioning.py`, `h3_controls.py`,
  `h3_continuation.py`, `h3_finish.py`, `h3_megapixels.py`, `h3_media.py`, `workflow_manifest.py`,
  `comfyui_provider.py`, `workflows/minimax-h3-*`.
- `[community]` Banodoco Discord, channels minimax_h3_chatter / _gens / _resources (2026-08 to 2026-11): tokenizer
  special tokens (2026-08-21/22), `<scenetrans>` is not a magic token (2026-10-29), ellipses break dialogue
  (2026-10-09), gibberish when the prompt does not fill the clip (2026-09-12, 2026-10-30), dialogue end anchored by
  an action (2026-09-29), extension overlap shifts timestamps (2026-09-02), turbo vs adherence (2026-11-08).
- `[house]` Continuo test renders and a production shoot (measured camera, conditioning and audio studies;
  production notes on tempo, events, keyframe blocking).
