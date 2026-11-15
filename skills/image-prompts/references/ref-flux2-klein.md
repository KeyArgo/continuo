# FLUX.2 Klein 9B (KV, distilled): prompting reference

Load this when you write a prompt for `flux2-klein-9b-t2i-v1` (create) or for a FLUX.2 Klein area edit through
`continuo_image_edit` (`flux2-klein-9b-kv-edit-v1`). Evidence tags: `[code]` Continuo source, `[local]` installed
node or workflow, `[official]` Black Forest Labs (BFL), `[community]` named and dated, `[hypothesis]` untested.

## 1. Scope

| Catalog | Target | Operation | Runnable? |
|---|---|---|---|
| `flux2_klein` / `t2i` | `flux2-klein-9b-t2i-v1` | create | yes `[code]` |
| `flux2_klein` / `compose` | none | multi_reference (image 1 + up to 3) | **no**: the variant has no workflow descriptor and no `suite_targets`; it is inventory only `[code]` |
| edit capability `flux2-klein` / `edit-9b-kv` | `flux2-klein-9b-kv-edit-v1` | fill, replace, remove, restyle, relight, outpaint, box (add + keep only) | yes, one picture (the Suite's crop); references not wired `[code]` |

The model: `flux-2-klein-9b-kv-fp8` = FLUX.2 [klein] 9B with KV caching of reference tokens (faster
multi-reference editing), "9B flow model with 8B Qwen3 text embedder, step-distilled to 4 inference steps"
`[official]`. Encoder file `qwen_3_8b_fp8mixed`, VAE `flux2-vae` `[code]`. It is the distilled model, not the
50-step Base 9B (CFG 4) `[official]`.

Use it for: fast drafts and look tests (about 3-11 s per picture in Continuo `[code]`), quick relights (the
strongest light of the three edit families in Continuo's bench), the Move completion pass (the server uses it).
Not for: final Fill and Remove (weakest in Continuo's bench: pale fills, ghosts `[code]`), dense or long text
(garbled text in infographics `[community]`), exact brand colours without checking (hex adherence varies by seed
`[community]`), multi-reference compose (not wired; see section 4).

## 2. What Continuo sends

**Create** (`flux2-klein-9b-t2i-v1`) `[code]`
- Your prompt goes byte for byte into the prompt node. No prefix, no enhancer, no negative (the negative is your
  own conditioning zeroed; CFG 1). `capabilities.prompt_enhancer: false`.
- ComfyUI wraps it in Qwen3's chat template (`<|im_start|>user ... <|im_end|> <|im_start|>assistant <think></think>`)
  and tokenizes with weights disabled: `(word:1.3)` is read as literal text `[local]`.
- Graph: FluxKVCache -> CFGGuider (cfg 1) -> Flux2Scheduler (steps) -> SamplerCustomAdvanced (euler).
- Controls: `seed`, `steps` (default 4), `sampler` (default `euler`), `aspect_ratio` (8 presets, default 1:1),
  `megapixels` (0.1-4.0, default 1.0, sides snapped to 16). No scheduler control (Flux2Scheduler is fixed).

**Area edits** (`flux2-klein-9b-kv-edit-v1`, via `continuo_image_edit`) `[code]`
The Suite crops the selection with context, sends the crop (about 1 MP) as the one reference latent, and pastes the
result back inside a soft mask. In template mode your `prompt` is the THING; the server writes the sentence:

| Operation | What the model reads |
|---|---|
| fill | `Add {prompt}{where}. Keep everything else in the picture exactly the same.` (FLUX.2 sees the ORIGINAL crop, located by words: a grey area came back unchanged) |
| replace | `Replace {target} completely with {prompt}, so that nothing of {target} remains, {light clause}. Keep everything else in the picture exactly the same.` |
| remove | LaMa pre-fills, then `The background continues seamlessly: ... nothing else is there.` (your prompt is not sent) |
| restyle | `Redraw the whole picture as {prompt}. Keep the same composition, every subject and the whole background; change only the rendering style. Keep every light source where it is and add none.` |
| relight | `Relight the photo with {prompt}. Make the shadows, highlights and the colour of the light match it. Change only the lighting; keep the composition, every subject, their pose, face and clothes and the whole background exactly the same.` |
| outpaint | `Extend the picture into the grey area: continue the same scene ..., with {prompt}. Do not add a frame or border. ...` |
| box | Add boxes become one Fill mask (Keep boxes cut out); Change, Move, Remove are FLUX.3-only |

`{where}` is " at the top left of the picture", " in the center of the picture" etc., computed from the selection inside the crop; empty when the
selection covers most of the crop. `options.instruction_mode: "raw"` sends your prompt as the whole instruction.
No upsampler exists in this graph; `prompt_enhancer: true` has no effect on what the model reads.

## 3. Grammar

BFL for [klein]: "No prompt upsampling - be descriptive yourself"; "narrative prose"; "Write like a novelist
describing a scene"; "Front-load your subject (word order critical)"; "Emphasize lighting descriptions heavily";
"Keep prompts moderately detailed (40-70 words)" `[official]`. The FLUX.2 overview repeats: "FLUX.2 [klein] does
not include prompt upsampling. Write detailed, descriptive prompts" `[official]`.

1. **Subject and action first**, then setting, then details and materials, then light, then camera/medium.
2. **Light is the strongest lever:** source, direction, quality, colour temperature, what it hits.
3. **Name materials:** "brushed aluminium", "oxblood wool", "rust-streaked white enamel".
4. **40-70 words** for most pictures. Longer is allowed (the encoder reads full sentences), but every clause must
   add a visible fact; past about 100 words practitioners report confusion `[community]`.
5. **No negatives** (no field, CFG 1); describe the positive state.
6. **No quality tags, no weights.**
7. **Text:** quote it, short (1-4 words most reliable), say where and in what type. BFL's own FLUX.2 upsampler
   prompt: "Always provide explicit quoted text for objects that would contain text in reality (signs, labels,
   screens) - without it, the model generates gibberish" `[official]`.
8. **Hex colours:** `#RRGGBB` with a colour name, bound to one object, 3-5 colours max `[official]`. In practice
   matching is loose and varies by seed `[community]`: render 2-3 seeds and check, or recolour in post.

The FLUX.3 caption style (100-350 words, medium opener) is not FLUX.2's form; FLUX.2 was not trained on that
upsampler. Write FLUX.2 shorter and subject-first.

Annotated example (create, 16:9, 58 words):
```
A ferry deckhand in a yellow oilskin coils a wet blue mooring rope on the steel deck at dusk, breath visible in
the cold air. Rust streaks run down the white railing behind him; a life ring reads "MARIA". Flat grey light from
the overcast sea on the left, one warm amber cabin window on the right. 35 mm documentary photograph, eye level.
```
(Subject + action first; materials named; light with sides; one short quoted word; medium last.)

## 4. Per operation

**Create.** Section 3. For variety, change one clause at a time with a fixed seed.

**Area edit, template mode.** `prompt` = the new thing with size and material: `a small wooden rowing boat with a
red hull`. For Fill on FLUX.2 the model sees the original picture and only the location words, so name the thing
fully; no "add"/"fill" verbs. Relight: `low warm sunset light from the left, long shadows to the right`.

**Area edit, raw mode.** BFL's FLUX.2 edit rules (its Space upsampler system prompt): one instruction, 50-80 words
(about 30 for a brief edit); say what changes AND what stays (face, lighting, composition); reference elements
actually in the picture; negatives as "keep X"; abstractions made concrete ("futuristic" -> "glowing cyan neon,
metallic panels") `[official]`. BFL examples that work as short instructions: "Change it to Night", "Replace the
flower in image 1 with a slice of lemon", "Remove all of the sprinkles while keeping the rest of the image
unchanged" `[official]`.

**Multi-reference compose (not runnable in Continuo today).** For the record, BFL's grammar: refer to inputs as
"image 1", "image 2" ... in the order sent, give each a role ("the person from image 1 wears the jacket from image 2
and stands in the kitchen from image 3"), up to 4 references on [klein], image 1 sets the output frame `[official]`.
ComfyUI's own 9B-KV template example says "Figure 1 / Figure 2" instead `[local]`; the encoder sees either as
plain text. Do not promise compose to the artist: tell them it is catalogued, not wired.

## 5. Film tasks

**T1 keyframe / frame 0 (draft).** Use FLUX.2 to try framings fast, then finish on a stronger create model.
```
A woman in a mustard raincoat steps off the curb of a wet night market street toward the camera, holding a paper
bag of oranges. Bare warm bulbs hang overhead; a red neon "OPEN" sign glows on the right; steam rises from a noodle
stall on the left. Low eye-level wide shot, reflections on the asphalt, 35 mm photograph.
```
**T3 location / establishing plate.** Lead with the place, then ground, buildings, sky and light.
```
A desert motel at the edge of a two-lane highway at blue hour, a single-storey row of twelve doors with peeling
turquoise paint and a lit "VACANCY" sign on a pole. Gravel lot, one dusty pickup, power lines crossing a violet sky.
Cold ambient light, warm sodium lamps over the doors. Wide-angle photograph, eye level.
```
**T4 insert / prop close-up.** Object first, material and wear, one light. Short text only.
**T6 continuity repair.** Relight is its best edit op (10 of 12 in Continuo's bench; clothing colours can drift:
check them) `[code]`. For Remove and Fill prefer Qwen-Image Edit or Krea Edit.
**T7 look / style transfer.** `restyle` with Strength: FLUX.2's measured schedule is gentler than FLUX.3's (its 70 %
starts at 0.29 of the schedule) `[code]`; template prompt = the look in concrete terms: `a loose ink-and-wash
drawing in sepia on cream paper`.
**T8 storyboard frame.** Fast and cheap: `A black-and-white pencil storyboard sketch: [shot size], [subject +
action], [one background cue]. Loose graphite lines, grey tone, white paper.`
**T10 uniquely good at.** Speed: a 4-step model for iterating composition and light before spending a slow render.

## 6. Parameters

| Knob | Official | Continuo | Effect / note |
|---|---|---|---|
| steps | 4 (distilled) `[official]` | 4 | Step-distilled; more steps are not expected to add detail `[hypothesis]` (vendor guides say it can break) |
| CFG | 1.0 distilled (Base 4.0) `[official]` | 1, fixed | Not exposed; no negative |
| sampler | euler (template) | euler; any ComfyUI sampler selectable | Change only to test |
| resolution | up to 4 MP (API) | 1 MP default, 0.1-4.0 | Below ~768 px per side quality drops `[community]` |
| Restyle Strength | n/a | start table 1.0 -> 0.0 (70 % = 0.29) | `[code]` |

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Flat, generic picture | Short prompt; no light | 40-70 words, subject first, light with direction and source |
| Wrong subject leads | Subject buried after scene | Move it to the first clause |
| Unwanted thing appears | Named to forbid it | Describe what is there instead |
| Garbled text | Long or unquoted text | 1-4 quoted words; Ideogram 4 or FLUX.3 for real typography |
| Colour off target | Hex matched loosely | Hex + name on one object; several seeds; recolour in post |
| Fill pale or cut off at the edge | Measured FLUX.2 weakness `[code]` | Use Qwen-Image Edit; or a larger selection |
| Ghost after Remove | Measured `[code]` | Qwen-Image Edit or FLUX.3 box Remove |
| Outpaint margin darker | Measured on flat pictures `[code]` | Another edit model, or colour-correct |
| Relight shifts clothing colour | Measured `[code]` | Name the clothing colours to keep in raw mode |
| `(word:1.4)` text appears or nothing changes | Weights disabled `[local]` | Use words, order and repetition, not weights |

## 8. Sources (accessed 2026-11-12 unless dated)

- `[code]` Continuo 9f7510c0: `model_catalog.v1.json` flux2_klein (variants compose, t2i); `workflows/flux2-klein-9b-t2i-v1/*`; `workflows/flux2-klein-9b-kv-edit-v1/*` (manifest `source.note`, `measured`); `generation/flux2_klein_edit_adapter.py:110-140`; `generation/image_edit_contract.py:131-159, 305-328, 837-909`; `generation/image_box.py:167-188, 281-292`; `image_edit_capabilities.v1.json` (flux2-klein); `model_evidence.v1.json` (flux2_klein/t2i 10.9 s; edit 3.6 s); `generation/model_catalog.py:884-938`.
- `[local]` ComfyUI 2f8943324 `comfy/text_encoders/flux.py:150-203` (KleinTokenizer template, `disable_weights=True`); template `image_flux2_klein_9b_kv_image_edit.json` (package 0.1.112).
- `[official]` BFL skill `flux-image-best-practices@master`: `rules/flux2-models.md`, `rules/multi-reference-editing.md`, `rules/hex-color-prompting.md`, `rules/negative-prompt-alternatives.md` (https://github.com/black-forest-labs/skills); https://docs.bfl.ml/flux_2/flux2_overview ; https://docs.bfl.ml/guides/prompting_editing_single_reference ; https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv-fp8 (README); https://huggingface.co/black-forest-labs/FLUX.2-klein-9B ; Space `black-forest-labs/FLUX.2-klein-9B` `app.py` (system prompts, defaults 4 steps/CFG 1, Base 50/4). The former Klein guide https://docs.bfl.ai/guides/prompting_guide_flux2_klein returns 404 on 2026-11-12.
- `[community]` HF FLUX.2-klein-9B discussion 32 (2026-03-15, hex inconsistent across seeds); github.com/black-forest-labs/flux2/issues/31 (2026-01-21, garbled infographic text); fal.ai Klein prompt guide (over 100 words confuses); deapi.ai blog 2026-04-29 (40-120 words, >=768 px, 4 steps fixed); Reddit r/StableDiffusion 1qlihrk (~2026-01, showcase prompts were upsampled), 1tflqso (~2026-05, weights disabled, tag soup weak)
