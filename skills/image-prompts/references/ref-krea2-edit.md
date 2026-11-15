# Krea 2 Edit (Identity Edit V2, General Edit V2): prompting reference

Load this when a job edits a picture with Krea 2: restaging a person, putting a person into a scene, or making an
instruction edit (recolour, relight, restyle, background, outfit, add, remove, sign text). Evidence tags:
`[code]` Continuo source, `[local]` installed node pack and workflow files, `[official]` the LoRA author's model card,
node README and trainer README (the "official" docs for these community LoRAs; Krea itself does not publish them),
`[maintainer]` the author's replies in issues and discussions, `[community]` named, dated user reports,
`[hypothesis]` not yet measured. Sources are in section 8.

## 1. Scope

| Catalog family / variant | Continuo target | Reached through | What it is for |
|---|---|---|---|
| `krea2` / `identity_edit_v2` | `krea2-identity-edit-v2` | `continuo_image_workflow_submit` (catalog edit, 1–2 references) | One photo of a person in, the same person in a new scene, pose, outfit, light or framing out. Also: add that person to a scene picture. |
| `krea2` / `general_edit_v2` | `krea2-general-edit-v2` | `continuo_image_workflow_submit` | Instruction edits of a whole picture: remove, recolour, relight, season, background swap, add an object, sign text, outfit, restyle, flat lay. |
| `krea2` / `general_edit_v2` (area edits) | the Replace area target (a distilled Krea 2 fine-tune) (Replace, Fill, Remove, Outpaint, Box), `krea2-edit-turbo-v1` (Restyle, Relight) | `continuo_image_edit` with a selection | The same General Edit V2 LoRA on the crop around a selection. The server writes the sentence and pastes the result back inside the soft mask. |

Both edit LoRAs are community fine-tunes trained on Krea 2 Raw. They are not Krea products. They need the
`comfyui-krea2edit` ≥ 2.0.0 nodes, which feed the source picture twice: as VAE tokens (appearance) and into the
Qwen3-VL text encoder together with your instruction (meaning). `[official]`

Not for:
- head swaps, which turn into whole-person swaps;
- restoring low-resolution faces;
- reliable outpainting (the card lists both as unreliable);
- changing the camera angle or zooming in (not trained: crop the source instead);
- more than two pictures in one pass. `[official]` `[maintainer]`

Identity Edit is not a general editor: it tends to ignore removals, recolours and camera changes, so send those to
General Edit. `[official]`

## 2. What Continuo sends (do not duplicate it)

### 2a. Catalog path: `continuo_image_workflow_submit` (both V2 targets)
- **Your prompt is sent as written, byte for byte.** The server adds no template, no role text and no enhancer.
  The descriptor has `prompt_enhancer: false` and `effective_prompt: false`. `[code]` krea2_edit_workflow_adapter.py
- References: `[{image, role:"target"}, {image, role:"identity"}]`, in that order. Image 1 is required; image 2 is
  optional. With one picture the second loader and every `*_b` input are removed. `[code]`
- **The output takes image 1's aspect ratio** at the chosen megapixels, on a grid of 16. `[code]` `output_size`
- The node wraps your words in a fixed chat template: the system turn is *"Describe the image by detailing the colour,
  shape, size, texture, quantity, text, spatial relationships of the objects and background:"*, and the user turn is the
  picture tokens (scene, then subject) followed by your instruction. So the encoder sees the picture while it reads.
  Refer to things the way you would point at them: "the man on the left", "the sign above the door". `[local]`
- The negative is a second grounded encode with an empty prompt and the same pictures. That is the trained
  unconditional. It only acts when CFG > 1. You never write a negative. `[local]` `[official]`
- Exposed controls and pinned defaults `[code]` (manifests):

| Control | Identity V2 default | General V2 default | Range |
|---|---|---|---|
| model | `krea2_turbo_int8_convrot` | same | Turbo or Raw (int8) |
| lora_strength | 1.0 | 1.0 | 0–2 |
| steps / cfg | 8 / 1.0 | 8 / 1.0 | any |
| sampler / scheduler | euler / simple | euler / simple | all KSampler options |
| ref_boost (last picture) | **2.0** | **4.0** | 0–20 |
| ref_boost_a (picture 1 in two-picture mode) | 1.0 | 1.0 | 0–20 |
| grounding_px | 768 | 768 | 0–4096, step 64 |
| ref_position (last picture) | **beside (right of target)** | **aligned (trained)** | aligned / beside / bag of features |
| ref_position_a (picture 1, two pictures) | aligned | aligned | same |
| megapixels | 1.0 | 1.0 | 0.1–2.0 |

- Catalog presets `[code]`:
  - Identity: `restage` (ref_boost 2), `add_to_scene` (2.5), `face_locked` (1.5).
  - General: `edit` (ref_boost 4) and `removal_raw` ("Removals (Raw)": the Raw model, steps 20, CFG 3). The preset
    selects the Raw model itself; do not set `model` by hand.

### 2b. Area path: `continuo_image_edit` (model `krea2`)
One picture: the crop around your selection at about 1 MP. Settings are fixed: 8 steps, CFG 1, ref_boost 4, grounding
768, euler/simple, LoRA 1.0. No references, no enhancer, no live preview. `[code]` krea2_edit_adapter.py,
capabilities.

In the default `instruction_mode: "template"`, your `prompt` is the **thing**, not a sentence. The server writes the
sentence `[code]` image_edit_contract.py `instruction()`:

| Operation | Base | What the server sends | Write in `prompt` | Measured |
|---|---|---|---|---|
| replace | the fine-tune, latent mask | `Replace {target} completely with {prompt}, so that nothing of {target} remains, {light match}. Keep everything else in the picture exactly the same.` | The new object as a noun phrase. Name the old one in `options.target`. | 8/8 usable or good: the strongest Krea area edit |
| restyle | Krea 2 Turbo | `Redraw the whole picture as {prompt}. Keep the same composition, every subject and the whole background; change only the rendering style. Keep every light source where it is and add none.` | The medium: `a loose watercolour on rough paper` | whole picture 4/4, inside a selection 4/4 |
| relight | Krea 2 Turbo | `Change the lighting to {prompt}. Keep everything else in the picture exactly the same.` (a Krea-only short text) | A light that completes "Change the lighting to …": `low warm sunset light from the left` | 4/4 good or usable; it may add the light source itself (a moon) |
| fill | the fine-tune | `Fill the grey area with {prompt}. Keep everything else …` (the selection painted grey) | The object | warning: on flat pictures the grey stays grey |
| remove | the fine-tune | LaMa pre-fill, then `The background continues seamlessly: the same ground, water, sky, walls and buildings, …; nothing else is there.` at denoise 0.5 | **ignored** | warning: the object stays, or a grey smear is left |
| outpaint | the fine-tune | `Extend the picture into the grey area: continue the same scene … , with {prompt}. Do not add a frame or border. …` | optional: what the new area shows | warning: the margin stays grey on flat pictures |
| box | the fine-tune | Add boxes become one Fill mask | the `desc` of each box | as Fill |

`instruction_mode: "raw"` sends your prompt alone. Use it only when you write the whole Krea-style sentence yourself
(see 3). Restyle is the only Krea area operation that takes `strength`. The prompt is capped at 2000 characters.

Operations that carry a `warning` still run when asked. Say what the warning means; do not refuse.
`[code]` agent_tools.py capabilities text.

## 3. Grammar: plain imperative English, describing the end state

The models were trained on natural-language instructions. There are no trigger words, no keyword list, and "please"
does nothing. Plain imperative sentences work best ("Remove the …", "Change the … to …"). `[maintainer]` `[community]`

**General Edit V2: one short imperative sentence, plus a keep clause where it helps.** The card's own showcase
prompts `[official]`:
- `Remove the tourist in the red cap.`
- `Change the sign text to KREA CAFE.`
- `Add a ginger cat curled up asleep on the armchair.`
- `Replace the background with a snowy mountain landscape, keep the person unchanged.`
- `Relight the scene with warm golden hour sunlight coming from the left.`
- `Dress him in a black tuxedo with a bow tie.`
- `Turn this into a high-quality anime illustration, keeping the person recognizable.`
- `Make it a snowy winter evening, keep everything else the same.`
- `Create a flat lay image of this person's outfit and accessories on a white background.`

Pattern: *verb + the exact thing (located by a visible feature) + the new state*, 6–15 words, optionally `, keep …`.

**Identity Edit V2: one full sentence that describes the new picture, starting with "This person".** The card's
showcase prompts are 25–45 words `[official]`:
- `This person hiking along a misty Scottish mountain ridge in a bright yellow rain jacket, waxed hiking trousers and muddy leather boots, a backpack on his shoulders, wind in his hair, photographed from a low angle.`
- `This person sitting cross-legged on a log by a campfire at night in a chunky fair-isle sweater, cargo trousers and hiking boots, face lit warmly from below, telling a story.`
- `This person seen from behind on a rooftop at dusk in [outfit], turning to look back over her shoulder at the camera.`
- Two people: `These two people dancing together at a wedding reception, her in a flowing lilac dress and heels, him in a light grey suit and brown shoes, …`
- Into a scene (two pictures): `Add this person to the scene, sitting in the armchair reading a newspaper.`
- Sheet: `Create a character reference sheet of this person: front, three-quarter, side and back views, full body, plain light grey background.`

Order: *who (this person) → action and pose → place and time → each garment by name → light (where it lands) →
camera (side view, from behind, low angle)*.

The card's three Identity rules ("prompting matters more than the dials") `[official]`:
1. **Say how much of the person is visible.** "Standing on a ridge" copies the photo's head-and-shoulders crop. Get the
   whole figure with "in muddy leather boots", "sitting cross-legged on a log" or "full body".
2. **Name the outfit concretely and say what is gone.** The model leans on the reference clothes. Write "wearing only
   a white tank top, bare shoulders" or "remove her coat", not just a new garment name.
3. **Describe light by where it lands.** "A magenta sign paints the left half of her face pink" beats "neon lighting".

Common rules for both:
- **Positive end states.** Naming a thing to forbid it can render it. Describe what is in the frame.
  `[community]` (house renders)
- **No negatives, weights or quality tags.** CFG 1 ignores the negative, and `(word:1.3)` does not exist here.
- **Text to render:** quote it, keep it short: `Change the sign text to "NIGHT FERRY".` The card shows a clean result;
  house tests got garbled letters. Expect retries (section 7).
- **Length.** Reports conflict (section 8): one practitioner found long prompts deform the picture, another
  found that a longer enumerated scene description raised edit strength. Working rule: General Edit stays short;
  Identity restages get one sentence that names every visible garment and the framing. Do not pad either.

## 4. Per operation

**Single-picture restage (Identity V2).**
- Use image 1 = the person and `ref_position: beside` (the target default). `beside` frees the layout. With
  `aligned`, the photo's crop and pose stick and usually only the outfit changes. `[official]` `[community]`
- ref_boost: 2. Use 1–2 with `aligned` for a face-locked portrait that keeps the photo's framing.
- The output has image 1's aspect ratio. For a full-body portrait result from a landscape head shot, pad or recrop
  image 1 to 2:3 first (house practice `[hypothesis]` for the Suite; measured in house renders).

**Person into a scene (Identity V2, two pictures).**
- Image 1 = the scene, image 2 = the person. That order was trained, and the scene must be image 1. `[official]` `[local]`
- Placement: scene `aligned`, person `beside` (the defaults). Boost: person 2–3 (`ref_boost`), scene 1
  (`ref_boost_a`). `[official]`
- Prompt: `Add this person to the scene, <pose/action at a named place in the scene>.`
- Give image 2 a person on a plain background. Objects around the person in that photo can leak into the scene.
  `[official]` (limitations) `[community]`
- Groups: add people one pass at a time, up to about seven. For exactly two people, put both in one pass.
  `[official]`

**Instruction edit (General V2, one picture).**
- Defaults: Turbo, 8 steps, CFG 1, ref_boost 4, `aligned`. One change per pass; chain passes for compound edits
  (the card shows a chained recolour). `[official]`

**Removal (General V2).**
- Catalog path: apply the `removal_raw` preset (Raw model, steps 20, CFG 3; the grounded negative is already wired). Turbo at CFG 1 "will
  usually re-render the subject instead of removing it". `[official]`
- Name the thing by a visible feature: `Remove the man in the orange vest on the left.`
- Small background objects can survive even on Raw (house renders `[community]`). The area tool's Remove carries a
  warning on Krea; for a clean plate prefer another family's Remove or the catalog Raw path.

**General Edit with two pictures.** Image 2 gets `ref_boost` 4, image 1 gets `ref_boost_a` 1, both `aligned`. Say what
image 2 contributes ("Dress the man in the jacket from the second picture"). This is off the card: the card documents
two pictures only for Identity. `[hypothesis]`

**Inpaint / box / outpaint.** The LoRAs have no mask input. Continuo makes them local by crop and paste-back (2b).
Outpaint is officially unreliable. `[official]` `[code]`

## 5. Film tasks

**T2: one character across shots (the core job of Identity V2).**
1. Make one clean identity photo: a single person, face clearly visible, plain or neutral background, about 1 MP.
   Avoid sheets, multi-view panels and busy surroundings. Identity Edit returns sheets when fed sheets, and the author
   says identity separation is weakest with sheet references. `[maintainer]` `[community]`
2. Keep that photo as image 1 for every shot (catalog path, Identity target, `beside`, ref_boost 2). Restage from the
   same source each time. Chaining output into output drifts `[hypothesis]`.
3. Write each shot as one sentence: framing, action, place, every garment, light where it lands, camera side.
4. **Expression is copied with the face.** "Neutral" loses to a smiling reference, especially in close-ups. Phrase it
   concretely: "closed mouth, relaxed lips, no smile, calm face". Mid framings (waist to thigh) steer best. If the
   expression must change, lower ref_boost to 0.7–0.9. `[maintainer]` Users report V2 grips the face even harder.
   `[community]`
5. Hold wardrobe by repeating the garment words verbatim in every shot.

Example:
```
This person standing at the stern rail of a small ferry at dusk, framed from the knees up, in a yellow oilskin
jacket over a grey wool jumper, dark work trousers and black rubber boots, coiling wet rope in both hands, the cold
blue sky lighting the left side of his face, the warm cabin window behind him rim-lighting his shoulder.
```

**T6: continuity repair.**
- Recolour or replace a prop:
  - Area tool replace on the fine-tune, `prompt: "a dented red enamel coffee pot"`, `options.target: "the silver kettle on the stove"`.
  - Or catalog General: `Change the silver kettle on the stove to a dented red enamel coffee pot.`
- Remove a crew member or modern object: catalog General on Raw 20 / CFG 3: `Remove the man in the black cap standing behind the motel sign.` Check the result; reroll the seed before you rewrite the prompt.
- Relight to match the next shot:
  - Area relight, `prompt: "hard white midday sun from the upper right, short sharp shadows"`.
  - Or catalog: `Relight the scene with hard white midday sun from the upper right, short sharp shadows under the eaves.`
- Wardrobe fix: General, `Change his jacket to a faded navy canvas work jacket, keep everything else the same.`
  Identity Edit would ignore a recolour.
- Season or time: `Make it a wet winter night, keep everything else the same.` Snow on the ground may still leave
  summer trees green, as in the card's own example. If the trees matter, name them: "bare trees".
- Extend frame: avoid Krea (officially unreliable); use another family's Outpaint.

**T7: look transfer.**
- Area restyle on Turbo: `prompt: "a two-colour risograph print, teal and orange, coarse grain"`. Strength 70 % is the
  default. The style only arrives at the low end of the start schedule. `[code]`
- Or catalog General: `Turn this into a loose ink-and-wash drawing, keep the composition and every person recognizable.`

**T1: keyframe from an existing frame.** Use Identity restage with the full figure stated, plus the action onset:
`This person at the night-market stall, full body, reaching for a paper lantern with her right hand, …`. Video models
want one readable action.

**T3: location plate.**
- General: `Replace the background with an empty desert motel parking lot at noon, keep the person unchanged.`
- Empty a plate: use a removal (Raw), and expect retries.

**T4: insert.** Crop the source to the prop first, then edit. Zooming in by prompt is not trained. `[maintainer]`

**T5: signage.** `Change the sign text to "VACANCY".` Short words, quoted, one sign per pass. Garbled letters → retry
seeds, or render the sign with a typography model.

**T8: storyboard.** Restyle a frame: `Turn this into a rough pencil storyboard sketch with grey marker shading, keep
the composition.`

**T10: what it is uniquely good at.**
- A person from one casual photo, restaged anywhere with real light on the face. Both the card and the community put
  this ahead of other open edit models. `[community]`
- Character turnaround sheets from one photo, and outfit flat lays.

## 6. Parameters

| Knob | Official | House / Continuo | Effect |
|---|---|---|---|
| model | Turbo for most work. Raw only for removals (General). `[official]` | Area path: the fine-tune for Replace/Fill/Remove/Outpaint/Box, Turbo for Restyle/Relight `[code]`. The fine-tune barely changes a whole picture (Restyle and Relight were no-ops in the study). | Raw at CFG 3 can delete; Turbo re-renders the subject. |
| steps | 8 (V2 card) | v1.2 workflow note: 8 = composition adherence, 12 = face detail, 10 balanced `[local]` | Over 8 on Turbo: more face detail, weaker edit `[hypothesis]` for V2 |
| CFG | 1 (Turbo); 3 (Raw removals) | — | CFG > 1 activates the grounded empty negative |
| ref_boost | Identity 2 (person 2–3, face-locked 1–2), General 4 | v1.2 note: >10 over-copies (removals fail), <1 frees the result `[local]` | Pull toward the last picture's appearance. Too high and the edit stops happening. |
| ref_boost_a | scene 1 | — | Same pull for image 1 in two-picture mode |
| ref_position | Identity restage: `beside` or `aligned`; composite: person `beside`. Trained on `aligned` only. | — | `beside` = free layout. It may shift people to the right or crop the right edge `[community]`. |
| grounding_px | 768 (trained 384–768) | Lower = edit adherence, higher = likeness; duplicates → lower it `[official]`. No measurable effect on whole-scene references `[community]`. | Size of the picture the encoder reads |
| megapixels | ≤ 2 MP | 1.0 default. About 1–1.5 MP is most reliable `[maintainer]`. | Above that, bleed and duplicates |
| lora_strength | 1.0, one LoRA per task | Both LoRAs at 1.0 = noise; about 0.6 each if combined `[official]` (not exposed as two LoRAs in Continuo) | — |
| sampler | euler/simple | Prefer ODE samplers. SDE (er_sde) breaks outpaint coherence `[official]` v1.2.4 | — |
| size | multiples of 16 | Other widths give coloured streaks on the right or bottom edge `[community]` | Continuo rounds to 16 `[code]` |

## 7. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Restage keeps the photo's crop, only the clothes change | `aligned`, or the prompt never says how much body is visible | `beside`; name the shoes, or say "full body" or "sitting cross-legged" |
| Old coat or turtleneck survives under the new outfit | Reference clothing carries over | Name the new garment concretely and add "remove his coat" |
| Objects from the person photo appear in the scene | Busy reference | A plain-background person photo; reroll; describe the scene more fully |
| Identity Edit ignores "remove/recolour/turn the camera" | Wrong LoRA | Use General Edit |
| Removed object comes back (Turbo) | Distilled model at CFG 1 | `removal_raw` preset: Raw, 20 steps, CFG 3 (catalog path) |
| Remove in the area tool leaves a smear | Measured Krea limit | Another family for Remove |
| Grey patch stays grey (Fill, Box, Outpaint, flat pictures) | The model reads grey as content | Use Replace (latent mask) or another family |
| Face won't change expression | Appearance copy includes the expression | Concrete words ("closed mouth, no smile"), ref_boost 0.7–0.9, mid framing |
| Faces look generic or alike | Reference pull too weak | Raise ref_boost; describe the distinctive features in the prompt `[local]` |
| Duplicated person, split composition | Above 2 MP, or grounding too high | ≤ 1.5 MP; grounding 512–640 |
| Relight invents people or a moon | A long relight text (people); light-source wording (moon) | The Suite's short Krea relight; name the light, not a sky object |
| Garbled sign letters | Model limit | Retry seeds; shorten the word; typography model |
| Picture drifts warm or sepia | Reported tone shift, unexplained `[community]` | A colour-match step afterwards; see open questions |
| Streaks on the right or bottom edge | Width or height not a multiple of 16 | Sizes on 16 |
| Person shifted right or cropped (`beside`) | Placement bias `[community]` | "centred in the frame" in the prompt `[hypothesis]`; or `aligned` |

## 8. Sources (accessed 2026-11-12)

- `[official]` Model card, raw README: https://huggingface.co/conradlocke/krea2-identity-edit (settings tables,
  "Prompting matters more than the dials", known limitations, reference placement); showcase images with their printed
  prompts in `/showcase/v2_*.jpg`.
- `[official]` Node pack README + CHANGELOG 2.0.0 / 1.2.4: https://github.com/lbouaraba/comfyui-krea2edit
- `[official]` Trainer README (grounding 384–768 jitter; captions are instructions): https://github.com/lbouaraba/krea2edit-trainer
- `[local]` Installed node source 2.0.0 (grounded template, `_place_refs`, ref_boost semantics) and its
  `workflows/krea2_identity_edit.json` notes.
- `[maintainer]` HF discussion #43 (no keyword list), #36 (sheet references weakest), #35 (zoom not trained,
  1–1.5 MP); GitHub issue #14 (expression is copied; concrete neutral wording; ref_boost < 1).
- `[community]` HF discussions #59, #60, #61, #63, #65, #54, #32, #30; GitHub issues #28, #32, #35; Banodoco
  `krea-2-image` (2026-08 → 2026-11).
- `[code]` Continuo 9f7510c0: `krea2_edit_workflow_adapter.py`, `krea2_edit_adapter.py`, `image_edit_contract.py`
  (instruction templates, latent-mask specs, strength schedule), `image_edit_capabilities.v1.json`,
  `model_catalog.v1.json`, `workflows/krea2-*/manifest.json`.
