# MiniMax H3 continuation and finishing — reference

Load this with `skill_view('film-suite:video-prompts', 'references/ref-h3-video.md')` for `minimax-h3-extend-mctx-v1` (Extend), `minimax-h3-prepend-mctx-v1`
(Prepend), `minimax-h3-bridge-mctx-v1` (Fill gap) and `minimax-h3-finish-v1` (Finish). Tags as in the core file.

---

## 1. What a continuation is

Every local H3 take is saved as a pair: the mp4 and a `.mctx.safetensors` sidecar with the take's audio-video
latent and lineage `[code]` workflows (`H3TrimAndSaveVideoWithMCtx`). A continuation loads that latent and pins a
window of it into a new generation as fixed context `[local]` obvpm-timeline docs/h3.md:

| Target | Pinned window | Where it sits in the new clip | Pin mode |
|---|---|---|---|
| Extend | the source take's tail (or the frame you pick) | first 39 frames | `masked` |
| Prepend | the source take's head (or the frame you pick) | last 39 frames | `both` |
| Fill gap | source tail + target head | first 39 and last 39 frames | `masked` / `both` |

`[code]` workflows/minimax-h3-{extend,prepend,bridge}-mctx-v1, h3_continuation.py:47,175-191.

- The pinned frames are re-rendered as part of the take and **trimmed before delivery**: the delivered take holds
  only the new frames; the sidecar records the seam so `place_with_parent` can join it frame-exactly on the
  Timeline `[local]` `[code]`.
- Pinned audio is carried too, so speech and ambience continue across the seam `[local]`.
- Use `continuo_take_lineage` first: it says whether a take is continuable and offers extend/prepend/bridge. A take
  without sidecar is refused (`no_sidecar`), a changed file with `pair_broken` `[code]`.
- `source_frame` (Extend/Prepend only): continue after / lead into a chosen frame instead of the end/start; it is
  snapped to the 17-frame grid and refused with the bound named when no 39-frame window fits `[code]`.
- Size and aspect follow the source take; Fill gap needs two takes of the same size `[code]`.

## 2. Model and sampling: not the parent's

Continuations run the **ref2va** checkpoint, no turbo LoRA, res_multistep / simple / 20 steps, sigma shift 12/3
`[code]` workflow-api.json. Takes from Frames ran fl2va + turbo 0.8 at 12 steps. Expect a slight change of look
across the seam on long continuations; in production, extends drifted in face and colour `[house]`. More steps
without turbo at the seam held audio level where 8-step turbo did not `[house, measured]`.

## 3. Length: what `duration_seconds` buys

The new clip is `39 + 51k` raw frames; `duration_seconds` picks k (2-14 s accepted) `[code]` h3_continuation.py:175-191:

| `duration_seconds` | Extend / Prepend: raw clip | new frames delivered | Fill gap: raw clip | gap delivered |
|---|---|---|---|---|
| 2-3 | 90 f = 3.75 s | 51 f = 2.13 s | 141 f = 5.88 s | 63 f = 2.63 s |
| 4-5 | 141 f = 5.88 s | 102 f = 4.25 s | 192 f = 8.00 s | 114 f = 4.75 s |
| 6-7 | 192 f = 8.00 s | 153 f = 6.38 s | 243 f = 10.12 s | 165 f = 6.88 s |
| 8-9 | 243 f = 10.12 s | 204 f = 8.50 s | 294 f = 12.25 s | 216 f = 9.00 s |
| 10-11 | 294 f = 12.25 s | 255 f = 10.63 s | 294-345 f | 216-267 f |
| 12-13 | 345 f = 14.38 s | 306 f = 12.75 s | 345-396 f | 267-318 f |
| 14 | 396 f = 16.50 s | 357 f = 14.88 s | 396 f = 16.50 s | 318 f = 13.25 s |

Odd seconds round to the same grid step as the even one below or above: ask for the step you want. The raw clip
can exceed H3's 15 s trained range at 14 s `[local]`.

## 4. Prompt

Three fields, no alignment line, no six-field form, no `<Video N>` labels `[code: graph has no references]`.

**Timing inside the prompt** (decide this first). The prompt conditions the whole raw clip, held window included.
A practitioner found that timestamps written from 0:00 of the new part, ignoring a 39-frame overlap, cut the first
shot short by 1.63 s and caused babble at its start `[community 2026-09-02]`. The shipped skill and the tool text
say "times from the new part's start" `[code]` agent_tools.py:33. Until a test settles it, write
continuation prompts so both readings work:

- **Extend**: open with the held state ("The shot continues from the previous moment: the deckhand still kneels
  at the bollard with the rope in both hands."), put **no new event before 00:01.70**, then time the new beats on
  the raw clip (new part starts at 00:01.63). End with a clear landing state.
- **Prepend**: time the new beats on the raw clip, and finish the new action before the last 1.63 s; end with
  "and arrives at the moment the next take begins: <describe the source take's first frame>".
- **Fill gap**: first 1.63 s = the source take's ending state, last 1.63 s = the target take's opening state;
  write the path between, as in First + Last frames.

**Content** `[house]` `[community]`:
- Repeat only what drifts: identity (one short list), costume, light, camera state. Do not re-describe the whole
  parent prompt.
- Inherit every state of the parent's end: positions, held objects, lighting, camera lock, speaker IDs, ambience,
  score (`N/A` stays `N/A`). Do not silently restore an older state.
- A lock (camera static, a figure off-screen) holds until you release it in words.
- Dialogue that continues: a new `<d>` block with the same `(Sx)`, starting after the held window; never invent
  words for "continues speaking". A sentence the parent already finished must not restart: if the parent ended
  mid-speech, extend from a frame where the speaker has finished, or end the line visibly ("he stops talking and
  looks down") `[community 2026-09-03]`.
- Name the new action as an arc with an end state the next extension can start from.

**Prepend is harder for the model than extend**: convergence into the pinned head is seed-dependent; reroll the
seed when the seam reads as a cut `[local]` `[house: 1 of 3 seeds barely moved]`.

## 5. When not to continue

- If the cut puts other shots between the two parts, the join is never on screen: render the later part as its own
  Frames take from a clean late frame of the first take (the artist picks it). Extends drift and chains are
  fiddly `[house]`.
- A take made before sidecars existed, an import or an edited file cannot be continued locally; use Frames with an
  exported frame.
- Do not use Extend to fix a shot's beginning or middle; re-shoot it, or Fill gap between two good parts.

## 6. Worked prompt (Extend, `duration_seconds` 6 → raw 8.00 s, 6.38 s new)

```
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, the shot continues from the previous moment on the ferry's bow at dusk under low grey cloud: the deckhand in the yellow oilskin kneels at the steel bollard, both hands on the tied-off rope. The camera holds a static shot. At 00:02.00 she stands up in one quick move, wipes her palms on the oilskin and turns toward the wheelhouse at frame left. At 00:03.40 she raises her right arm high and waves once. At 00:04.60 she walks out of frame left with brisk steps; the empty deck, the bollard and the taut rope remain in frame until the end, the grey dusk light unchanged. No one speaks.

overall_soundscape:
Diesel engine throb and steady wind continue from the previous moment. Her boots strike the wet steel four times and fade toward frame left; the rope creaks once under tension.

non_diegetic_music:
N/A
```

## 7. Finish (`minimax-h3-finish-v1`)

An operation on one finished take, **no prompt** `[code]` h3_finish.py:134-228, agent_tools.py:151:

- `upscale` (default on): the take's stored latent goes through the MiniMax H3 latent upscaler 3D to 1.5 MP (grid
  32) and is decoded with the take's VAE; no VAE round trip before the upscale.
- `rife` (default off): RIFE v4.26 x2, 24 → 48 fps.
- At least one on; the result is a new take linked to its source; the source is untouched. Continuation takes are
  finished exactly as delivered (pinned frames cut away). Temporal 2x/3x is not offered.
- Needs the sidecar. Call through `continuo_take_finish`, poll with `continuo_video_poll`.

When to use: finishing a keeper after the cut is decided. It adds resolution from the latent, not new facial
detail in small faces; a face that was too small at render time needs a larger render, not an upscale `[house]`.
A take that already has the right size needs neither. Upscaling does not change motion or sound.
