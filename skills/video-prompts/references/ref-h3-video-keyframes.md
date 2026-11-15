# MiniMax H3 Frames target and keyframes — reference

Load this with `skill_view('film-suite:video-prompts', 'references/ref-h3-video.md')` when a shot is held by pictures: `minimax-h3-frames-v1`, or keyframes on
`minimax-h3-references-v1`. It covers how the server places pictures, the alignment line for every case, how to
read a keyframe before you write a word, and how to prepare a keyframe that a video model can start from (film
task T1 from the video side).

Tags as in the core file: `[official]`, `[code]`, `[local]`, `[community]`, `[house]`, `[hypothesis]`.

---

## 1. What the server does with keyframes

`keyframes: [{source, frame}]`, at most 10, one per frame, frame 0 to the last frame index `[code]`
h3_conditioning.py:375-391.

| Target | Keyframe at frame 0 | Keyframe at the last frame | Any other frame |
|---|---|---|---|
| Frames (fl2va) | `first_frame` → text encoder sees it as `<Picture 1>` | `last_frame` → `<Picture 2>` (or `<Picture 1>` when there is no first frame) | `MiniMaxH3AddGuide` latent anchor, **no label**, the text encoder never sees it |
| References (ref2va) | AddGuide, no label | AddGuide, no label | AddGuide, no label |

`[code]` h3_conditioning.py:658-670, `[local]` nodes_minimax_h3.py (ImageToVideo appends first then last to
`images`; the encoder prefixes `<Picture i>: ` per image).

- **Last frame index** = snapped frames − 1: 106 (4 s), 123 (5 s), 157 (6 s), 174 (7 s), 191 (8 s), 225 (9 s),
  242 (10 s) ... 361 (15 s). Any other high frame number is a mid-shot guide, not a last frame `[code]`.
- **Fit**: every keyframe is cropped to the canvas from the centre before upload (`fit: cover`) `[code]`
  :677. The node then stretches `first_frame` and cover-crops the others `[local]`; after the server's crop both
  are the same. Pick the canvas aspect of the keyframe, or frame the keyframe so a centre crop keeps what matters.
- **Anchors land on their exact frame**: measured PSNR 32-34 dB at the requested index vs 21-25 dB twelve frames
  away, best frame = requested index in 8/8 anchors `[house]`.
- `continuo_video_step_support` checks a planned keyframe set (frame grid, inside the shot, one per frame) without
  generating; `keyframes` may be given in seconds there and must land on a whole frame `[code]` video_steps.py.

## 2. The alignment line for every case

| Keyframes on Frames | First line of the prompt (then one blank line) |
|---|---|
| frame 0 only (I2VA) | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| frame 0 + last (FL2VA) | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` |
| last only (L2VA) | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` |
| mid-shot guides only, or guides + first/last | the line for the first/last pictures only; guides get no line `[hypothesis: no official form exists for mid-shot anchors]` |
| References with keyframes | no alignment line (six fields); describe the moment in `detailed_description` ("at 00:02.500 the shot passes through the pose of the keyframe") `[hypothesis]` |

`S.SS` = real length (5 s → `5.17`, 8 s → `8.00`, 10 s → `10.12`); `N` = number of the final shot `[official]`
`[code]`. With the `camera` arg and a frame-0 keyframe, leave the line out: the server writes it.

Known issue: with `camera` + a frame-0 keyframe **on References**, the server also prepends the I2VA line naming
`<Picture 1>`, which on References is the first reference image, not the keyframe `[code]` h3_conditioning.py:581.
Avoid that combination; write the camera sentence yourself on References.

## 3. Body patterns per case `[official]`

- **First frame (I2VA)**: anchor → onset → continuous development → result. Name the medium, then "the man shown in
  <Picture 1> stays at ...", then only what changes.
  `[Shot 1] Live-action, cinematic, the night-market cook shown in <Picture 1> stays behind his wok under the
  string lights. He tilts the wok, flips the noodles once, catches them and slides them onto a paper plate held
  by his other hand. Steam rises past his face. No one speaks.`
- **First + last (FL2VA)**: first state → observable intermediate changes → narrowing differences → last state,
  ending "... and settles into the pose, spacing and composition of Picture 2 at the end of the shot." One shot by
  default; the two pictures must differ in pose or position, not only in light: two near-identical anchors play
  as a still life, frozen until the change and after it `[house, measured]`.
- **Last only (L2VA)**: a plausible earlier state → explicit path → convergence → "settles into the exact
  arrangement, camera angle, light and composition of <Picture 1>." Good for reveals and focus pulls that must end
  on an approved picture; expect the pull to finish early and the framing to drift in the first second, so cut
  after it `[house]`.
- **Mid-shot guides**: the model passes through the guide at its frame; write the beat that arrives there with a
  timestamp at the guide's time (frame / 24) `[hypothesis on wording]`.

## 4. Read the keyframe before you write (the operator's pass)

Takes needed many rounds when the prompt ignored what an attentive camera operator sees in frame 0. Look at the
picture (open it at full size) and answer every line. Write the answers into the prompt as anchors and into a
note to the artist as decisions.

1. **Medium and look**: live action or animation, period, colour or black-and-white, grain. Write the medium
   from the picture.
2. **Frame geometry**: shot size, camera height and angle, horizon, what touches each frame edge, what is cut by
   the frame. The take starts from exactly this geometry: never write a camera position, distance or framing the
   picture does not show. To change it, move the camera with one listed move, or change the picture.
3. **Blocking**: who is where, facing where, eyelines; for each hand: free or holding what, with which grip, at
   what height. Every gesture you write must be possible from that grip ("lifts the cup to her lips", not "taps
   the ash with her index finger" when the cigarette is pinched between thumb and fingertips) `[house]`.
4. **Bodies in transit**: a limb caught mid-motion comes out malformed and H3 carries it until it settles.
   Prefer a keyframe where the moving part is still off-screen, and let H3 bring it in from the frame edge
   `[house]`.
5. **Readable action onset**: what is the first thing that moves, and is there room in frame for the motion
   (space in the direction of travel, head room for a stand-up)?
6. **Light**: key direction, practicals, time of day. Restate it; a light change is a written event with a hard
   sound, from a before-picture (section 5).
7. **Text surfaces**: signs, labels, vehicle fronts, paper. Wanted text in quotes; unwanted surfaces "plain,
   unmarked, stay bare".
8. **Off-screen boundaries**: what must stay out of frame (an unseen cause, a second character). Keep it in
   `overall_soundscape` only.
9. **Background figures**: give them breathing and small motion only, unless their line is written in `<d>`.
10. **Sound of the frame**: what the space sounds like before anything happens (room tone, rain, traffic).
11. **End state** the cut needs: where the body, camera and light are on the last frame.

## 5. Preparing a keyframe for video (T1 from the video side)

What makes a still a good frame 0 for H3:

- **Aspect = canvas aspect.** Crop or render the still in one of 21:9, 16:9, 4:3, 1:1, 3:4, 9:16. Keep the subject
  inside the centre crop `[code]`.
- **Resolution**: at least the Native canvas (1344x768 at 16:9); more is downscaled `[local]`.
- **The scene the prompt describes.** A frame anchor whose scene the prompt contradicts holds for one frame and
  then hard-cuts to the prompt's scene (frame 0→1 difference 23x the median) `[house, measured]`. No character
  sheets, turnarounds, grey plates or panel layouts as frame 0; those are References material.
- **A moment before the action.** Start one beat before the event so it happens inside the take and the cut can
  land on it (a door still closed, a foot not yet in frame, a hand resting) `[house]`.
- **Colour**: a black-and-white take needs a true greyscale keyframe; colour in frame 0 survives every word and a
  tinted keyframe drifts red `[house, measured]`.
- **Clean surfaces** where the motion will bring things close; no small text you do not want animated.
- **Faces big enough**: a face that is small in frame does not hold at Draft/1 MP; frame tighter or plan a larger
  final render `[house]`.
- **Avoid baked-in motion blur and mid-blink**; the model continues whatever it sees.

## 6. Choosing Frames vs other routes

| Need | Route |
|---|---|
| The approved picture IS the shot, it only comes to life | Frames, frame 0 |
| The approved picture is the END of a move (reveal, focus pull) | Frames, last frame only |
| A path between two different poses or positions | Frames, frame 0 + last |
| A state change in a living shot (light switch, weather turn) | Frames, frame 0 = the before picture, change written in the prompt; never two near-identical anchors |
| Identity from a sheet, the take may re-stage the world | References |
| The motion must follow a guide clip | References with `control_video` |
| A later shot of the same moment, edit puts other shots between | Frames from a clean late frame of the earlier take (artist picks it) |
| Must be seamless with an existing take | Extend / Prepend (continuation file) |

## 7. Worked prompt (Frames, frame 0 + last, 5 s)

Keyframes: frame 0 = a ferry deckhand standing at the bow rail holding a coiled rope; frame 123 = the same
deckhand kneeling at the bollard, rope tied off.

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 5.17-second mark of the target video.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, the deckhand in the yellow oilskin begins in the position and framing of Picture 1 at the bow rail under low grey dusk cloud. The camera holds a static shot. At 00:00.60 she steps forward two paces, drops to one knee beside the steel bollard and throws two quick turns of the wet rope around it. At 00:03.20 she pulls the end tight with both hands and leans back once to test it; the rope holds. She settles into the pose, spacing and composition of Picture 2 at the end of the shot. No one speaks.

overall_soundscape:
Diesel engine throb and steady wind across the deck. Boots thud twice on wet steel, the rope rasps around the bollard and creaks as it pulls tight.

non_diegetic_music:
N/A
```
