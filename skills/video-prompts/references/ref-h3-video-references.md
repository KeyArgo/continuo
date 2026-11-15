# MiniMax H3 References target (six fields) — reference

Load this with `skill_view('film-suite:video-prompts', 'references/ref-h3-video.md')` for `minimax-h3-references-v1`: identity, location, style, motion, voice or music
from reference media. Tags as in the core file.

---

## 1. What the target takes and what the server does

| Input | Limit | Becomes | Note |
|---|---|---|---|
| `reference_images` | 9 | `<Picture 1..9>` in list order | aspect kept, scaled down to the canvas area (`ref_image_size: match`) `[code]` `[local]` |
| `reference_videos` | 3, mp4 | `<Video 1..3>` | text encoder sees the clip at 2 fps with timestamps; frames cut to the shot length and the 17k+5 grid `[local]` |
| `reference_video_sound` | indices | `<Audio N>` = that clip's soundtrack | default none; the clip's sound then becomes the take's sound almost verbatim `[code]` `[house, measured]` |
| `reference_audios` | 3, each 2-15 s, 15 s together | `<Audio N>` with role `voice_of` (subject k) or `music_bed` | needs at least one picture or clip `[code]` `[official]` |
| `control_video` | 1 | no label; Fun ControlNet union, strength 1.0, from frame 0 | cover-cropped; must be at least the shot length `[code]` |
| `keyframes` | 10 | AddGuide anchors, **no label** | see keyframes file |
| `sound_track` | 1 | no label; plays from frame 0, replaces the take's sound | `[code]` |
| `camera` | — | sentence after the `[Shot 1]` inside `detailed_description` | prefer writing it yourself here (core file §4) |

The official limit is 12 files in total across types `[official]`; Continuo checks only the per-type limits
`[code]`. Stay at 12 or fewer `[hypothesis: more is untested]`.

**Label numbering** `[local]` comfy/text_encoders/minimax.py, `[code]` h3_conditioning.py:587-595: pictures count
1..n in `reference_images` order; videos count 1..n in `reference_videos` order; audio counts in node order:
first each enabled clip soundtrack (in clip order), then the standalone `reference_audios`. Example: two clips,
sound of clip 2 enabled, one voice file → clip 2's sound is `<Audio 1>`, the voice file is `<Audio 2>`.
`continuo_h3_sound_check` reports the `<Audio N>` of every file before you submit.

**Lines the server adds** (one per audio reference, unless your section already names that `<Audio N>`)
`[code]` h3_conditioning.py:598-614:

| Role | `subject_definitions` | `retention_analysis` |
|---|---|---|
| `voice_of` k | `<Audio N> is the voice-timbre reference for <Subject k> (Sk).` | `<Audio N>: reference - <Subject k> speaks with <Audio N>'s voice timbre without copying the original signal or words.` |
| `music_bed` | `<Audio N> is the background music of this shot.` | `<Audio N>: partially_copy - the source audio is reused purely as the background music layer, leaving room for the model to generate and mix new foreground diegetic dialogue and sound effects on top.` |
| clip sound | `<Audio N> is the soundtrack of <Video k>.` | `<Audio N>: fully_copy - the soundtrack of <Video k> is reused unchanged as the sound of this shot.` |

Note the `voice_of` line writes `(Sk)` with k = the subject number: make that subject's speaker ID the same number
(subject 2 → `(S2)`), or write your own `<Audio N>` lines, which the server then keeps.

## 2. The six fields `[official]`

All six in English except `<d>` content and visible text. Labels keep one meaning across all sections.

1. **`subject_definitions`** — one line per tracked item: label, role, features to follow, source.
   `<Subject 1> is the motel night clerk whose face, hair and green cardigan come from <Picture 1>.`
   - A picture that only defines a person, place, costume or style is cited inside a `<Subject N>` line, never as
     its own `<Picture N>` line. A standalone `<Picture N>` line only for a concrete frame, composition anchor or
     storyboard: `<Picture 3> is a storyboard reference for [Shot 1] and [Shot 2], defining viewpoint and
     subject placement.`
   - `<Video N>` only for whole-video relationships: edited source, continued source, camera, cuts, rhythm or
     timing. A person or motion taken from a clip stays a `<Subject N>`.
   - Every attached file must be named, or it does nothing `[community, many reporters]`.
   - Fence what a picture must not bring (when its light, background or framing would leak):
     `<Picture 1> provides identity only; it does not provide lighting, background, pose or framing.`
     `[community]` A multi-view sheet: "use it for identity only, not layout or background" `[house]`.
2. **`summary`** — one short paragraph opening with the task type in brackets: `keyframe completion`,
   `reference generation`, `video editing`, `video continuation`, `audio reuse`, `audio reference`, joined with
   ` + `, none repeated. Presence of a file creates no task type: a clip used for camera or rhythm is
   `reference generation`. No new labels here.
3. **`retention_analysis`** — one line per label: `<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved -
   face, hair and cardigan stay the same.` Visual markers: `fully_preserved`, `partially_preserved`,
   `attribute_transfer`, `weak_reference`. Audio: `fully_copy`, `partially_copy`, `reference`, `weak_reference`.
   Never `(S1)` here. New actions or backgrounds are not losses: an identity role stays `fully_preserved`.
4. **`detailed_description`** — one or two style sentences before `[Shot 1]` ("The target video is live-action,
   cinematic, with sodium-orange night light and light film grain."), then the shots with composition, position,
   light, action, camera, sound and where each reference takes effect. Generation: normally 350-500 words;
   dialogue-heavy: fit the full spoken timeline first. A speaking referenced subject carries both labels:
   `<Subject 1> (S1) leans on the counter and says: <d>[English] Room six is upstairs.</d>`
5. **`overall_soundscape`** and 6. **`non_diegetic_music`** as in the core file. When a reference audio is copied,
   name it in the matching field (`non_diegetic_music: <Audio 2> plays as the score.`).

Write every section label alone on its own line (the server matches whole lines) `[code]`.

## 3. Which marker for which job

| Job | Definition shape | Marker |
|---|---|---|
| identity of a person/animal/object | `<Subject k> is the X whose face/fur/shape ... come from <Picture i>` | `fully_preserved` |
| identity, costume changed by the prompt | "... ; her costume is newly specified by the prompt" | `fully_preserved` (role-relative) or `partially_preserved` |
| location / set | `<Subject k> is the diner interior in <Picture i>: counter, booths, neon` | `fully_preserved` |
| style or look only | `<Subject k> is the grade and lighting style of <Picture i>, applied to rendering only, not to composition or identity` | `attribute_transfer` |
| concept only, look free | `<Subject k> is the premise of <Picture i> ...` | `weak_reference` |
| motion/performance from a clip onto a new character | `<Subject k> is the walking motion from <Video n>` | `attribute_transfer` |
| camera path / cut rhythm of a clip | `<Video n> is the camera-movement reference for [Shot 1]` | `weak_reference` or `partially_preserved` `[official example uses weak_reference for pacing]` |
| storyboard / composition frame | standalone `<Picture i>` line | `fully_preserved` |
| voice timbre | server line, or your own `voice-timbre reference for <Subject k> (Sk)` | `reference` |
| background music | server line | `partially_copy` |

## 4. Practice and limits

- **Fewer, well-separated references beat many** `[community]`. Role clarity before count. Two similar people (two
  women) swap or blend more easily than two very different subjects; describe what separates them `[community]`.
- **Do not re-describe what a reference supplies**; spend the words on action, staging, camera, light. Re-assert a
  short identity list at each shot boundary where drift is likely `[community]`.
- **Likeness falls with framing distance**: medium close-ups hold, wide full-figure shots garble faces; give a
  close reference for the face even when the shot is wide `[community]`.
- **Reference video motion is approximate**, direction more than magnitude (an orbit overshot at 12 turbo steps,
  undershot at 20) `[house]` `[community]`. Use `control_video` when the motion must follow exactly.
- **Voice reference**: works for one speaker; timbre transfers (speaker similarity 0.72 vs 0.09 control), words
  come from the prompt, level and EQ follow the reference, lip-sync loosens `[house, measured]`. Two referenced
  voices in one take is unreliable; generate separately `[community]`. Some practitioners report babble with
  voice references and better results describing the voice in words `[community 2026-09-11, 2026-10-20]`.
- **Music bed** plays verbatim from frame 0 about 10-15 dB under dialogue `[house, measured]`.
- **Clip sound**: off by default; on, it replaces the take's sound even when the prompt never names it `[house]`.
- **Over-long or mis-schemed prompts silently behave like text-to-video**: references stop applying while
  everything runs. Check the schema and the role lines first, then shorten `[community]`.
- **Turbo LoRA and reference adherence**: the target runs turbo 0.8 by default; reports say turbo cuts adherence on
  complex prompts `[community 2026-11-08]`. Test `turbo: false` with more steps when references are ignored and the
  prompt is correct `[hypothesis]`.
- Never mark a grey mannequin or pose dummy `fully_preserved` as a frame anchor: H3 renders the mannequin `[house]`.

## 5. Worked prompt (identity + location + voice, 6 s)

Inputs: `reference_images` = [clerk close-up, motel lobby]; `reference_audios` = [{voice file, role voice_of,
subject 1}] → `<Audio 1>`; the server adds the two audio lines.

```
subject_definitions:
<Subject 1> is the motel night clerk whose face, short grey hair and green cardigan come from <Picture 1>; <Picture 1> provides identity only, not lighting or background.
<Subject 2> is the motel lobby in <Picture 2>: wood-panelled counter, key rack, buzzing vending machine, glass door to the parking lot.

summary:
[reference generation + audio reference] <Subject 1> stands behind the counter of <Subject 2> at night, slides a room key across the counter and speaks one line with the voice timbre of <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - face, grey hair and green cardigan stay the same.
<Subject 2> (appears in [Shot 1]): fully_preserved - counter, key rack, vending machine and glass door keep their layout.

detailed_description:
The target video is live-action, cinematic, lit by warm tungsten lamps inside and cold blue parking-lot light through the glass door, with light film grain.
[Shot 1] A medium shot from the guest side of the counter frames <Subject 1> behind the counter of <Subject 2>, the key rack behind his left shoulder and the vending machine glowing at frame right. The camera holds a static shot. At 00:00.50 he lifts a brass key from the rack with his right hand and slides it across the counter toward the camera; it stops at the counter edge. At 00:01.60 he looks up and <Subject 1> (S1) says in a dry, unhurried voice, in one breath: <d>[English] Room six. Ice machine's broken.</d> He stops talking at 00:03.40, closes his mouth and rests both hands flat on the counter. A car's headlights sweep once across the glass door behind the camera. He holds the look until the end of the shot; the warm lamps and blue door light stay unchanged.

overall_soundscape:
Fluorescent buzz and the vending machine hum fill the lobby. The key scrapes over the wooden counter and taps against its edge; a car passes outside on wet asphalt.

non_diegetic_music:
N/A
```

The server adds `<Audio 1> is the voice-timbre reference for <Subject 1> (S1).` and its `reference` retention
line. About 230 words of description: below the official 350-500 because the shot is one line and one action; a
longer clip needs more.
