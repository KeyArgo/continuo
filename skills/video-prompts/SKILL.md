---
name: video-prompts
description: "Use when writing or repairing a MiniMax H3 video prompt for a Continuo video take."
---

# Video prompts (MiniMax H3 in Continuo)

Every local video target sends your prompt to MiniMax H3 exactly as written. Hosted H3 rewrites requests first;
here nothing does, so write what its rewriter writes (MiniMax-H3 `docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md`,
`..._ref_en.md`). Free prose, camera jargon and mood words make it erratic. H3 has no negative prompt.

Load the reference you need before writing:
- `skill_view('film-suite:video-prompts', 'references/ref-h3-video.md')`: always. Targets, what the server writes, grammar, camera, sound, length, failures.
- `skill_view('film-suite:video-prompts', 'references/ref-h3-video-keyframes.md')`: Frames, or any keyframe. Alignment lines, reading and preparing frame 0.
- `skill_view('film-suite:video-prompts', 'references/ref-h3-video-references.md')`: References. Six fields, labels, markers, voice and music files.
- `skill_view('film-suite:video-prompts', 'references/ref-h3-video-continuation.md')`: Extend, Prepend, Fill gap, Finish.
- `skill_view('film-suite:video-prompts', 'references/ref-h3-video-film-tasks.md')`: worked prompts for dialogue, reaction, insert, action, establishing, montage,
  light change, music beat, held look.

## 1. The target decides the format

| Target | Inputs | Format |
|---|---|---|
| `minimax-h3-t2v`, `minimax-h3-t2v-sampling-v2` | none | three fields (sampling-v2 = same graph + steps/sampler/scheduler/Draft size) |
| `minimax-h3-frames-v1` | keyframes at any frame, `sound_track`, `camera` | alignment line + three fields |
| `minimax-h3-references-v1` | pictures, clips, motion guide, voice/music, keyframes | six fields |
| `minimax-h3-extend-mctx-v1`, `-prepend-`, `-bridge-` | a take with its .mctx sidecar | three fields, new part only |
| `minimax-h3-finish-v1` | a finished take with sidecar | no prompt: `upscale` (1.5 MP) and/or `rife` (48 fps) |

Three fields, this order, exact spelling: `integrated_multimodal_description:`, `overall_soundscape:`,
`non_diegetic_music:`. Six fields: `subject_definitions:`, `summary:`, `retention_analysis:`,
`detailed_description:`, `overall_soundscape:`, `non_diegetic_music:`, each label on its own line. The two never mix.

Frames: one alignment line first, then a blank line. Copy it exactly (the bracket difference is official):
- frame 0 only: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- frame 0 and last: `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.`
- last only: `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`

`N` = final shot number. `S.SS` = real length, two decimals: the server snaps `duration_seconds` to 17k+5 frames
at 24 fps (4 s = 4.46, 5 s = 5.17, 6 s = 6.58, 8 s = 8.00, 10 s = 10.12). The last frame is frames − 1 (5 s → 123);
any other frame is a mid-shot guide with no label and no line.

## 2. Before writing: look and decide

Open the keyframe at full size and decide: frame geometry and camera height (never write a framing the picture
does not show), who holds what with which grip, eyelines, light direction, text surfaces, what stays off-screen,
the end state. Then time it: each beat's start, each line's spoken length (read it aloud), the silences. Then word
each event at its true size: "fires" brings a muzzle flash and a bang; a dry click is "the hammer snaps on an empty
chamber: one dry metallic click".

## 3. The description

- Open `[Shot 1]` with medium and composition: `[Shot 1] Live-action, cinematic, a medium-wide shot frames ...`.
- Only what can be seen or heard: not "she feels guilty" but "she glances at the door and tightens her grip".
- Give the action a path and an end state. First frame: picture -> onset -> result. First + last: the path between them, one shot. Last only: a plausible earlier state -> landing exactly on the picture.
- With a keyframe, describe what changes, not the picture. The keyframe must show the prompt's scene, or the take holds it one frame and cuts away.
- `[Shot 1]` has no timestamp; later `[Shot 2] At 00:03.500, the camera cuts to ...`, increasing, inside the length. Every `[Shot N]` is a hard cut that must bring new information; for a size change move the camera. A timestamp without `[Shot N]` is a beat inside the shot.
- Restate light and time of day in every shot.
- Visible text in double quotes, verbatim. A surface that grows large (sign, vehicle front) gets a plain description ("a blank pale panel"), or H3 invents lettering on it.
- An off-screen cause stays in `overall_soundscape`; describing its visible effects pulls it into frame.
- Describe the wanted state; naming an excluded thing ("no cars") pulls it in.

## 4. Camera

Closed list: Zoom In/Out, Push In/Pull Out, Pan, Truck, Tilt, Pedestal (Up/Down, Left/Right), Arc Shot, Tracking Shot,
Static Shot, Shake Slightly/Strongly, POV, Roll, plus `with small|large amplitude` and `at slow|fast speed`. Write a
sentence in the shot ("The camera pushes in with small amplitude at slow speed toward the letter."), never a bracket
tag; one move per shot. No camera words = drift: write "The camera holds a static shot." to lock it. A move goes as
far as its named destination ("until the whole pier is in frame"), not as far as the amplitude word.

Or, on Frames or References with no keyframe or only a frame-0 keyframe, pass `camera` {move arc_shot (direction
left|right) | push_in | shake, amplitude, speed} in args: the server writes the sentence after `[Shot 1]` (with six
fields: the `[Shot 1]` inside `detailed_description`) and, on Frames, the frame-0 line itself. Then write no camera words, no tag, no `[Shot 2]` (refused) and no alignment line. On
References write the sentence yourself instead. After a camera take read `continuo_take_freeze_check`. A locked shot
with a small moving subject can read as frozen while right: let the artist look. Frozen although the prompt asked
for motion = same args, seed + 1.

## 5. Sound

- Speech: speaker outside the tag, `The old fisherman with a low, rough voice (S1) says: <d>[English] Leave the light on.</d>`. Inside `<d>` only the language tag and the exact words in their own language, no quotation marks (quotes render as subtitles), no ellipses or dashes (they turn speech into babble). IDs follow speaking order and stay fixed; two at once `(S1,S2)`. Voiceover: `says in an off-screen voiceover: <d>...</d> while his lips remain completely closed.` A line that runs across a cut gets `<scenetrans>` on both sides plus "her voice continues seamlessly across the cut"; speech cut off by the clip's end gets `<cutoff>`. These two markers are plain text to the model: the sentence carries the meaning.
- One continuous line = one `<d>` block, delivery outside it ("says in one breath"), and a visible end ("At 00:03.20 he stops talking and closes his mouth"). A clip longer than its content fills the gap with pauses, invented words or slow motion.
- Nobody speaks: write "No one speaks." H3 invents speech that is not addressed, most often when the clip is longer than what is written.
- `overall_soundscape`: 1-4 sentences of concrete sources (rain on glass, a hinge). No dialogue, no music. `N/A` only for total silence. Every named sound is rendered, big in a short take.
- `non_diegetic_music`: 1-3 sentences of instruments, tempo, dynamics (no mood words), or `N/A`. For a take without score write `N/A` and keep musical words ("swell", "melody") out of every field. A radio in the scene belongs in the description.
- `reference_audios` (`voice_of` subject k, or `music_bed`): the server writes their definition and retention lines; `voice_of` k writes `(Sk)`, so give that subject speaker ID k. A `sound_track` replaces the shot's sound from frame 0; keep its words in `<d>`.

## 6. References (six fields)

- All six fields in English except `<d>` and visible text. `subject_definitions`: one line per tracked item and its job: `<Subject 1> is the woman whose face, hair and coat come from <Picture 1>.` A reference the text never names does nothing. A standalone `<Picture N>` line only for a frame or storyboard anchor. Pictures count in `reference_images` order; `<Video N>` (only for a whole clip that is edited, continued or copied for pacing) counts separately; `<Audio N>` counts enabled clip soundtracks first, then `reference_audios` (`continuo_h3_sound_check` lists them); keyframes and the motion guide get no label.
- `summary`: one paragraph opening with the task type in brackets: `keyframe completion`, `reference generation`, `video editing`, `video continuation`, `audio reuse`, `audio reference`, joined by ` + `. No new labels.
- `retention_analysis`: `<Subject 1> (appears in [Shot 1]): fully_preserved - face, hair and coat stay the same.` Visual labels: `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`. Audio: `fully_copy`, `partially_copy`, `reference`, `weak_reference`. Never `(S1)` here.
- `detailed_description`: one or two style sentences, then the shots, 350-500 words. Do not re-describe what a reference supplies. A character sheet is for identity only, not layout.

## 7. Continuation (Extend, Prepend, Fill gap)

Three fields, no alignment line, only the new seconds (args `prompt`, `duration_seconds`, `seed`, `steps`,
`sampler_name`, `scheduler`, `source`, `target` for Fill gap, optional `source_frame`). The model sees the 39 held
frames (1.63 s) too: open with the held state and put no new event in the first 1.7 s. Extend starts from the take's
last state, Prepend ends in its first state, Fill gap joins two takes. Repeat only what drifts (identity, costume,
light), then the new action, then a clear end state. A take without score keeps `non_diegetic_music: N/A`.
Continuations run ref2va without turbo: expect slight drift; if the cut puts other shots between the parts, shoot
the later part from a late frame on Frames instead.

## 8. Length and retakes

- `duration_seconds` is 4-15 (continuations: 2-14 new seconds, on a 39+51k frame grid). H3 fits the written action into the clip: a fast beat in a long clip plays slow, a calm beat in a short clip turns hectic. Size the clip to the action; trim in the Cut.
- A three-field description of about 100 words works; more beats than seconds get dropped.
- Slow motion is the default drift: timestamp the beats, use brisk verbs, never "slowly" on a gesture.
- Draft size for trials, Native for keepers. Canvas aspect = keyframe aspect; stills are cropped from the centre.
- Black and white: a greyscale keyframe; its colour beats every word.
- One change per retake: a prompt fix keeps the seed; a take frozen although the prompt asked for motion keeps the words and takes seed + 1.

## 9. Example (Text to Video, 5 s)

```
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a wide shot frames an empty ferry deck at dusk under low grey cloud. The camera trucks right with small amplitude at slow speed as a deckhand in a yellow oilskin coils a wet rope, drops it on the bollard and walks out of frame left. No one speaks.

overall_soundscape:
Diesel engine throb under wind gusts; the rope slaps the steel deck; gulls cry far off.

non_diegetic_music:
N/A
```
More: `skill_view('film-suite:video-prompts', 'references/ref-h3-video-film-tasks.md')`.

## 10. Keyframes from image models; H3 video is not P-H3 image

A keyframe made for a take (film task T1) comes from an image model (`film-suite:image-prompts` picks it): render it
at the take's aspect, show the onset of the action, no motion blur, plain surfaces where the camera will get close,
and use the same nouns in `[Shot 1]` that the keyframe prompt used. Check it at full size before writing (section 2).

P-H3-Image runs on the same transformer with a LoRA but reads another grammar: no shots, sound, camera or alignment
line; it opens by naming the kind of picture ("a 35 mm documentary photograph"), never "cinematic" (a hype word
there). Its edits begin `Edit <Picture 1>.`; with references it can also take H3's six-section brief, but as the
edit of ONE picture: `[keyframe completion]` once in `summary`, no `[Shot N]`, no timestamps, both sound fields
`N/A`. Do not paste a video prompt into P-H3 or a P-H3 prompt into a take.

## 11. Failures and fixes

- Burned-in subtitles or text on signs: quotes around speech. Use `<d>`.
- Invented speech or babble: silence not stated, clip longer than content, ellipses in `<d>`. "No one speaks.", shorter clip, plain punctuation.
- A pause in the middle of a line: line split or clip too long. One `<d>`, "in one breath", end anchor.
- Music in a score-free take: musical words somewhere. `N/A`, concrete sources only.
- Unwanted cut: a second `[Shot N]`. One shot, move the camera.
- Cut away after frame 0: keyframe and prompt disagree. Describe the keyframe's scene.
- Slow motion: clip too long for the action. Shorter clip, timestamped beats.
- Barely moves although the prompt asked for motion: frozen seed. Seed + 1, same words. A locked shot with small motion is right: leave it.
- An event reads bigger than meant: loaded verb. Describe the exact small physical event and its sound.
- References ignored: no role line, three-field prompt, or too long. Name each job.
- A thing you excluded appears ("no cars"): naming it pulls it in. Describe what is there.
