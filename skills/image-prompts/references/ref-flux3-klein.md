# FLUX.3 Klein (distilled): prompting reference

Load this when you write a prompt for `flux3-klein-sd-create-v1` (create), or for a FLUX.3 Klein edit through
`continuo_image_edit` (`flux3-klein-sd-edit-v1` for area edits, `flux3-klein-box-edit-v1` for box edits).
Evidence tags: `[code]` Continuo source, `[local]` installed node or workflow, `[official]` Black Forest Labs (BFL),
`[maintainer]` node maintainer, `[community]` named and dated, `[hypothesis]` not yet tested.

## 1. Scope

| Catalog | Target | Operation | What runs |
|---|---|---|---|
| `flux3_klein` / `sd` ("Distilled") | `flux3-klein-sd-create-v1` | create | `flux3_image_klein_sd_int8_convrot`, Qwen3-VL-4B encoder, 16 steps, CFG 1, `er_sde`/`simple`, optional BFL prompt upsampler (Qwen3.5-9B fine-tune, int8) `[code]` |
| edit capability `flux3-klein` / `edit-distilled` | `flux3-klein-sd-edit-v1` | fill, replace, remove, restyle, relight, outpaint | the same model, one picture (the Suite's crop) as `<ref_image_0>`, 16 steps, `euler`/`simple`, optional edit upsampler `[code]` |
| same | `flux3-klein-box-edit-v1` | box (add, change, move, keep, remove) | the same model through NKD Klein Presampling ("Klein 3"); no upsampler `[code]` `[local]` |

What it is: BFL's 5.6B open-weights image model "designed for image editing": edit by instruction, text to image,
up to 10 references, layout with bounding boxes `[official]`. The `_sd_` file is the distilled checkpoint
(16 steps, no CFG). It is not the 50-step Base model `[official]`.

Use it for: box edits (it is the only Continuo model that reads boxes itself, including Move and mixed intents),
layout-planned pictures, quick drafts in caption form, dense typography and posters when you write the full caption.

Not for: identity-critical faces in text to image (practitioners report weak faces and anatomy in text to image,
and the model card's own pitch is editing `[community]`); final area edits where Qwen-Image 2.1 Edit is available
(Continuo measured Qwen better in every edit operation `[code]`). Multi-reference compose is not wired: the
FLUX.3 edit target takes one picture (`references.max 0`, `wired: false`); extra references only produce a
`references_ignored` warning `[code]`.

## 2. What Continuo sends

**Create** (`flux3-klein-sd-create-v1`) `[code]`
- Your prompt goes byte for byte into the prompt node. Nothing is added: no prefix, no style text, no canvas line.
- The negative is an empty string; CFG 1, so it does nothing. There is no negative field to fill.
- Controls: `prompt_upsampler` (bool, default **false**), `seed`, `steps` (default 16), `sampler` (default `er_sde`),
  `scheduler` (default `simple`), `aspect_ratio` (8 presets), `megapixels` (0.1 to 4.0, default 1.0; sides snapped to 16).
- Upsampler ON: your prompt goes to `TextGenerate` with BFL's t2i system prompt (verbatim, `max_length` 3584,
  `top_k 1`, so greedy: the seed does not change the caption). Its output replaces your prompt. The job returns it
  as the effective prompt; show it to the artist. Upsampler OFF: the branch is pruned from the graph; your words
  are the caption.
- With the upsampler on, its input opens with `TARGET CANVAS: W:H` from `aspect_ratio`, the first line BFL's
  system prompt expects `[code]` `[official]`.

**Area edits** (`flux3-klein-sd-edit-v1`, via `continuo_image_edit`) `[code]`
- In `template` mode (default) your `prompt` is a THING, and the server writes the sentence:

| Operation | What the model reads |
|---|---|
| fill | `Fill the grey area with {prompt}, the whole of it small enough to fit inside the area, with the surrounding scene continuing all around it. Keep everything else in the picture exactly the same.` (FLUX.3 gets the "fits inside" clause; without it the object was cut off at the edge) |
| replace | `Replace {target} completely with {prompt}, so that nothing of {target} remains, {light clause}. Keep everything else ...` |
| remove | LaMa pre-fills the area, then `The background continues seamlessly: the same ground, water, sky, walls and buildings, with the same light, colour, texture and perspective; nothing else is there.` Your prompt is not sent. |
| restyle | `Redraw the whole picture as {prompt}. Keep the same composition, every subject and the whole background; change only the rendering style. Keep every light source where it is and add none.` |
| relight | `Relight the photo with {prompt}. Make the shadows, highlights and the colour of the light match it. ...` (the upsampler is forced off for relight) |
| outpaint | `Extend the picture into the grey area: continue the same scene ... , with {prompt}. Do not add a frame or border. ...` |

- `options.instruction_mode: "raw"` sends your prompt as the whole instruction.
- The model sees only a crop of the picture at about 1 MP, as `<ref_image_0>`. The Suite pastes the result back
  inside a soft mask and colour-matches it.
- `options.prompt_enhancer: true` runs the edit upsampler (ComfyUI's template system prompt) on the sentence above
  with the crop attached; the result is returned as the sent prompt. Off by default.

**Box edits** (`flux3-klein-box-edit-v1`) `[code]`
- Boxes: `{id, intent: add|change|move|keep|remove, desc (one line, max 160 chars), bbox: [x, y, w, h] in picture
  pixels, target_bbox for move}`; up to 16 boxes; ids are letters/digits/underscores.
- The server builds the final prompt (`image_box.compile_prompt`): your caption, then one sentence for each box
  your caption does not cite as `<id>` (the first one prefixed "In <ref_image_0>, " when your caption has no
  `<ref_image_` token), and, only when such sentences were added and your caption lacks the words "everything else",
  "Keep everything else in the image exactly unchanged."; then BFL's element list
  `[{id, from, src_bbox, tgt_bbox, desc}]` on a 0-1000 grid of the crop, `[top, left, bottom, right]`.
- Row mapping: add/change -> `from: null`, `src_bbox: null`, `tgt_bbox` = box; remove -> `tgt_bbox: null`;
  keep -> `src_bbox == tgt_bbox`; move -> both.
- Move is not a regenerate: the Suite removes the object at the source (its own FLUX.3 job), pastes the object's
  own pixels at the target and blends a ring, then a FLUX.2 Klein job completes hidden parts and ground `[code]`.
- Read the final text with `continuo_image_box_prompt` before running. Colour match is on by default (the model
  brightens the whole crop) `[code]`.

## 3. Grammar: the caption the model was trained on

BFL: "Do not use either model without the prompt upsampler. The model is trained on the captions it writes; a
prompt sent as typed gives noticeably weaker results." `[official]` The ComfyUI files card: turn the upsampler off
only "when your prompt already is a full caption" `[official]`. Continuo keeps it off by default (artist's rule:
enhancers are opt-in) `[code]`. So: **with the upsampler off, you are the upsampler. Write the caption it would
write.** The rules below are BFL's own t2i upsampler system prompt (the 20 reference captions it ships run
196-437 words) `[official]`.

1. **Open with the medium as an attribute**, no "This image shows": `Full-color outdoor photograph, ...`,
   `Full-color indoor photograph, ...`, `Studio photograph, ...`, `Close-up photograph, ...`. Training captions also
   open with `Cinematic portrait photograph, graded with ...`, `Black and white cinematic photograph, high-contrast
   chiaroscuro style, ...`, `Anime-style illustration of ...`, `Flat vector illustration ...`, `Digital painting in ...`.
2. **Never call a photograph "photorealistic"**: that opener "indexes the synthetic-render cluster". Keep
   "Photorealistic" for 3D renders or paintings with a lifelike finish.
3. **Order:** medium and style -> scene, light (source, direction, hardness, colour temperature) and camera (shot
   size, angle; optics only when wanted) -> subjects with concrete colours, materials, state -> layout.
4. **People in focus get a profile:** ethnicity, gender, age range, skin tone ("fair skin", "brown skin", "olive
   skin", "dark skin"; no invented compounds), hair, each garment.
5. **Layout in words:** sentence-initial anchors ("On the left, ...", "In the background, ..."), frame-relative
   words (frame-left, foreground, midground), relations (holds, faces, behind, sits on). Up to about ten instances
   one by one; beyond that an exact count and arrangement.
6. **Plane legibility:** out-of-focus or distant planes are shapes, colours and silhouettes, never identities,
   garments or readable text. Background gets about a sixth of the caption (roughly 40 words).
7. **Be definite:** no hedges (slightly, gently, softly), no quality or emotion words (stunning, cinematic mood,
   breathtaking), no closing sentence about atmosphere. A mood becomes a physical fact: "tense" -> "his jaw set,
   both hands flat on the table".
8. **No negatives:** say what is there ("an empty platform", not "no people"). There is no negative field.
9. **Text:** every visible word verbatim in double quotes, in its language; multi-line text with `\n` inside the
   quotes; then its typography, colour and placement. Text the request needs but does not give: author it.
   Text described abstractly comes out as gibberish.
10. **One block of prose, English, no line breaks, no bullets, no "Style: ... Camera: ..." tails.**
11. **Length:** 100-350 words typical (upsampler rule); reference captions are 200-350, complex scenes to 500.
    A two-line prompt sent as typed is the main failure on this model.
12. **Weights do nothing:** the encoder tokenizes with weights disabled; `(word:1.3)` reaches it as literal text `[local]`.

Annotated example (create, upsampler off, 16:9):
```
Full-color outdoor photograph, eye-level medium shot at dusk under a low overcast sky, the light flat and cool
from the open sea frame-left, with one warm practical lamp in the wheelhouse frame-right. In the center
foreground, a South Asian man in his forties with brown skin, a short grey-flecked beard and close-cropped black
hair stands on the wet steel deck of a small car ferry, coiling a thick blue nylon mooring rope over his left
forearm. He wears a faded yellow PVC oilskin jacket, open at the collar over a navy wool jumper, black rubber
boots and orange work gloves darkened by water. Behind him on the right, the white-painted wheelhouse has rust
streaks running down from its rivets, and its single square window glows amber. On the left, a chipped white
railing runs toward the bow, a red-and-white life ring hangs on it, its band lettered "MARIA" in black capitals.
In the background, the grey sea and a darker grey headland are flat masses of colour under the cloud.
```
(Medium first; light with source and direction; one person profiled; positions per element; background as masses;
the one text quoted with placement; no mood words.)

## 4. Per operation

**Create, upsampler on.** Write the request plainly but completely: every subject, count, colour, text and
constraint you need. The upsampler keeps every explicit fact and decides the rest; it drops appraisal words and
turns moods into physical facts `[official]`. Do not write hedged alternatives ("a cat or a dog"). If the frame is
wide or tall, say so in words ("a wide frame, the ferry small on the right, open sea filling the left two thirds"),
because the canvas line is not sent `[code]`. Always show the returned caption: if it dropped or changed
something, re-run with the upsampler off and send the corrected caption yourself.

**Create, upsampler off.** Write the full caption (section 3). This is Continuo's default path.

**Create with a layout (boxes in text to image).** The model's own prompt format for a planned layout is
`<caption citing each element as <id>> [{"id": "...", "bbox": [top, left, bottom, right], "desc": "..."}, ...]`
on a 0-1000 grid of the output frame; BFL's reference code sends exactly `caption + " " + json(rows)` to the model
`[official]`. Continuo's create target writes your prompt byte for byte, so this form reaches the model when the
upsampler is **off** `[code]`. With the upsampler on it is lost: Continuo's t2i system prompt forbids JSON,
coordinates, ids and angle brackets in its output, and Continuo does not use BFL's `t2i_bbox` prompt `[code]`.
Rules `[official]`: ids are a class noun plus index (`person_1`, `En_Text_1` for text); cite every id once in the
caption next to its noun; `desc` opens with the element's identity and holds its appearance, not its position;
one row per text block with the words quoted in `desc`; overlap boxes when objects overlap; the grid stretches
with the frame, so draw boxes for the aspect you send (on 16:9 a square object is about 56 units wide per 100
tall). Not yet rendered through Continuo: treat as a probe (untested).

**Area edit, template mode.** `prompt` = the new thing, described by appearance and size: `a small wooden rowing
boat with a red hull and two oars shipped along its sides`. Do not write "fill", "add", "replace" or "keep"; the
server writes them. Replace needs `options.target` (the old thing, named by appearance).

**Area edit, raw mode.** BFL's single-reference edit form `[official]`:
1. Name the target so only one thing matches (position, size, colour, what it is next to).
2. Say what changes and into what; give end states concretely (hex colour, size, pose, material).
3. Name what fills a removed area; cover shadows, reflections and light of new content.
4. Close with one clause naming what stays: "Keep the deck, the railing, the sea and the light exactly unchanged."
For a multi-part edit: "Modify <ref_image_0> by making two changes. On the left, ... . On the right, ... . Keep the
rest of the scene exactly unchanged, preserving ..." `[official]`. Remember the model sees only the crop.

**Box edit.** The caption you write is BFL's "edit record". Write it yourself; do not leave it to the auto-sentences:
- Start with `In <ref_image_0>, ` and cite every box as `<id>` right after the noun it names:
  `remove the parked delivery van <van_1>`.
- "Say it twice": every addition and removal stated in the caption and in the row `[official]`.
- Put the end state in the caption (new colour, new text in quotes); put static appearance in `desc`.
- Remove: say what fills the place ("the cobbled street continues where the van stood") and name what it leaves
  behind (its shadow) `[official]`. The NKD node maintainer measured it: a bare "Remove ..." kept a detected dog; the
  "In <ref_image_0>, ... Keep everything else ..." form removed it in 2 of 3 seeds, and naming what fills the hole
  ("empty sand") worked in 3 of 3 `[maintainer]`.
- Anchor anything that must not move with a Keep box, especially neighbours that overlap a Remove box: boxes guide,
  they do not clip `[official]`.
- New content needs room: a box about 40 x 25 px often produced nothing `[official]`. Size it like similar objects.
- Change (recolour, swap) = a box whose `desc` is the result: `desc: "a deep teal #1F6F78 painted wooden door"`.
- End with one clause on what stays. If your caption cites every `<id>`, the server adds nothing, so this clause
  must be yours `[code]`.

## 5. Film tasks

**T1 keyframe / frame 0.** Create, upsampler off. One readable action at its onset, the subject large enough to
animate, light source named, background as masses. Avoid motion blur words.
```
Full-color outdoor photograph, low eye-level wide shot of a night market street just after rain, lit by strings of
bare warm-white bulbs overhead and a red neon sign frame-right, the wet asphalt reflecting both. In the center
midground, an East Asian woman in her twenties with fair skin and a black bob, wearing a mustard raincoat and white
canvas shoes, steps off the curb toward the camera, her right foot lifted above a puddle and a paper bag of
oranges held against her chest. On the left, a food stall with a striped red-and-white awning sends a column of
steam up past a hanging menu board reading "NOODLES 8" in white hand-painted letters. Frame-right, the neon sign
reads "OPEN" in red tubes above a shuttered shop. In the background, the street narrows into dark silhouettes of
stalls and a few blurred figures under umbrellas.
```
**T3 location / establishing plate.** Wide frame described left to right; give the architecture, ground and sky
concrete materials; keep people as silhouettes unless they matter. 21:9 or 16:9 with the width filled in words.
**T4 insert / prop close-up.** `Close-up photograph, ...` or `Studio photograph, ...`; the object fills the frame,
material, wear and marks in detail; one light described by where it lands; any text quoted verbatim.
```
Close-up photograph, top-down view of a motel room key resting on a scratched walnut-veneer counter, lit by hard
afternoon sun from a window frame-left that throws a long shadow of the key to the right. The key is brass, worn
silver along its teeth, on a green plastic diamond-shaped fob with white embossed text reading "DESERT ROSE\n12".
A ring of dried coffee sits on the veneer near the upper right corner, and the edge of a folded paper map in pale
blue enters the frame along the bottom.
```
**T5 title card / signage.** Quote every word, `\n` for line breaks, typography + colour + placement per block;
give each block its own position. For an exact layout use a box edit on a plate, or Ideogram 4.
**T6 continuity repair.** Box edit: Remove + Keep for neighbours, or Change with the target colour as hex.
Example caption: `In <ref_image_0>, remove the plastic water bottle <bottle_1> standing on the dashboard and let
the cracked black dashboard surface continue where it stood; keep the driver <person_1> and the rear-view mirror
<mirror_1> exactly as they are. Keep everything else in the image exactly unchanged.` (boxes: bottle_1 remove,
person_1 keep, mirror_1 keep).
**T7 look / style transfer.** Area edit `restyle` (template: `prompt` = the look, e.g. `a two-colour risograph print
in teal and coral with visible misregistration`) and Strength (FLUX.3's measured table starts the style only below
start 0.15 `[code]`). For a create, put the medium first in the caption.
**T8 storyboard frame.** Create with an illustration medium opener: `Black-and-white pencil storyboard sketch on
white paper, loose graphite lines and grey tone, ...`; describe the shot size and the one action.
**T9 poster / key art.** Caption with every text block quoted and placed (title top, credit block bottom),
background compressed; proofread every string in the result.
**T10 what it is uniquely good at.** Box edits with mixed intents and Move in one job; captions where layout is
spelled out element by element. Use it when "this exact thing, here, and nothing else moves" matters.

## 6. Parameters

| Knob | Official | Continuo default | Effect / note |
|---|---|---|---|
| steps | 16 (distilled) `[official]` | 16 | Fewer: softer, unfinished; more: no gain expected for a distilled model `[hypothesis]` |
| CFG | none / 1 `[official]` | 1, empty negative | Not exposed. Base model uses CFG 3.5-4 and 50 steps; that guidance does not transfer |
| sampler / scheduler | flow-map sampling in BFL code `[official]` | create `er_sde`/`simple` (BFL's distilled template); edit `euler`/`simple` | Change only to test |
| resolution | up to 4K `[official]` | 1 MP; 0.1-4.0 MP | Practitioners report better results around 2 MP with upsampled captions `[community]` |
| upsampler | always on `[official]` | off; opt-in | Greedy; edit upsampler seed = run seed `[code]` |
| Restyle Strength | n/a | 70 % default | Mapped to a schedule start; FLUX.3 changes style only below start 0.15 `[code]` |

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Generic, flat, stock-like picture | Short prompt sent as typed | Write the full caption (sec. 3) or turn the upsampler on and show its caption |
| Plastic "AI render" look | "photorealistic", "hyper-detailed", "8k" | Medium convention opener; drop appraisal words `[official]` |
| Background sharp and busy, subject loses weight | Background enumerated in detail | Compress it to masses, about 40 words `[official]` |
| Unasked text or gibberish signs | Text named abstractly ("a sign") | Quote the words, or describe the surface as blank |
| Edit changes things outside the area | Model re-tones the whole crop | Expected; the Suite pastes back with colour match; add Keep boxes in box edits |
| Removed object comes back / ghost | Remove worded without what fills it | Use template Remove (LaMa prefill); in boxes, say what continues there and anchor neighbours |
| Replace leaves the old object, only recoloured | Measured on FLUX.3 (harbour, seed 7) `[code]` | Use Qwen-Image Edit or Krea Edit for Replace |
| Filled object cut at the selection edge | Box or area too tight | Larger area; the server already adds "fits inside" |
| Box element missing | Box too small | Bigger box, sized like real objects nearby |
| Upsampler output lost a detail | Long request rewritten | Correct its caption and resend with the upsampler off |
| Faces and hands broken in T2I | Model limit `[community]` | Faces from Qwen/Krea/P-H3; use FLUX.3 for edits and layout |

## 8. Sources (accessed 2026-11-12 unless dated)

- `[code]` Continuo 9f7510c0: `model_catalog.v1.json` flux3_klein; `workflows/flux3-klein-sd-create-v1/{manifest,workflow-api}.json` (nodes 2, 14-17, 30-33); `workflows/flux3-klein-sd-edit-v1/*` (nodes 17, 34, 47, 48, 51); `workflows/flux3-klein-box-edit-v1/*`; `generation/catalog_create_workflow_adapter.py:89-117`; `generation/flux3_klein_edit_adapter.py:106-133`; `generation/flux3_klein_box_adapter.py:99-115`; `generation/image_edit_contract.py:131-161, 672-690, 828-909`; `generation/image_box.py:1-25, 118-164, 256-292`; `image_edit_capabilities.v1.json` (flux3-klein); `model_evidence.v1.json`; `agent_tools.py:66, 168`.
- `[local]` ComfyUI `comfy/text_encoders/flux.py:205-247` (Flux3 tokenizer, weights disabled via Qwen3VL tokenizer); `comfy_extras/nodes_edit_model.py` (ReferenceMultiLatent); NKD Klein Tools 1.13.2 `box_prompt.py`, `upsampler.py`, `upsampler_prompts.json`; ComfyUI templates `image_flux3_klein_distilled_t2i.json`, `image_flux3_klein_distilled_image_edit.json` (package 0.1.112).
- `[official]` https://github.com/black-forest-labs/flux-3-image-klein (README; `src/flux3/pup.py`, `bbox.py`, `generate.py`, `pup_prompts_external_vlm.json`; `examples/base/man_dog.json`); https://huggingface.co/black-forest-labs/flux-3-image-klein ; https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy ; https://huggingface.co/black-forest-labs/flux-3-image-klein-pup ; https://docs.bfl.ml/flux_3/flux3_image_klein ; https://docs.bfl.ml/flux_3/flux3_image_bounding_boxes ; https://docs.bfl.ml/flux_3/flux3_image_layout ; https://docs.bfl.ml/guides/prompting_layout ; https://docs.bfl.ml/guides/prompting_editing_single_reference ; https://docs.bfl.ml/guides/prompting_editing_multi_reference ; https://docs.bfl.ml/guides/prompting_unified_style ; https://docs.bfl.ml/guides/prompting_unified_technical
- `[maintainer]` NKD Klein Tools `box_prompt.py:98-105` (measured note on the edit record form), a9cc507, 2026-10-20.
- `[community]` Banodoco `flux3-image-model`: 2026-10-15 1560399688375472154 (upsampler beats JSON prompts), 1560418806130540689 (long upsampled prompt + boxes + 2 MP looks better), 1560381734174982225 and 1560383384168046735 (edits change unmentioned elements; boxes safer but not a hard limit), 2026-10-15 1560440575696703580 (needs more prompt and boxes), 2026-10-18 1561324757310247072 (faces weak in T2I); Reddit r/StableDiffusion 1x6u9vt, r/comfyui 1x8qn3d (vendor/ComfyUI staff: upsampler essential).
