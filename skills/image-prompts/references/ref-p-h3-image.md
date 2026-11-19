# P-H3-Image: prompting reference (Create, Edit with references)

Load this when you write or repair a prompt for catalog family `p_h3_image` (targets `p-h3-image-lora-t2i-v1`,
`p-h3-image-lora-edit-v1`) or for a `continuo_image_edit` area edit that routes to `p-h3-image-lora-crop-edit-v1`.
Tags: `[official]` = vendor card, vendor code or MiniMax guide · `[code]` = what the Continuo server does · `[local]` = the
ComfyUI node and encoder that run it · `[community]` = dated practitioner reports · `[hypothesis]` = untested; test it before relying on it.

---

## 1. Scope

- **What it is.** P-H3-Image is Pruna AI's image model, finetuned from MiniMax-H3, the video model `[official]`.
  Continuo does **not** run the standalone P-H3 checkpoint. It runs Pruna's **LoRA route**: the H3 FL2VA video
  transformer (`minimax_h3_fl2va_pruned_int8_convrot`), with `p-h3-image_lora_bf16` in bypass mode at 1.0, plus P-H3's own
  Qwen3-VL-4B text encoder (int8) and its single-frame VAE (int8) `[code]`. Pruna documents this route as the way to
  run P-H3-Image on an H3 install, and says pruned and quantized FL2VA files work too `[official]`.
- **Variants.** `create` (text to image, no inputs) · `edit` (Picture 1 = the picture to edit + up to 7 references,
  roles `identity | outfit | location | style | composition | object | reference`) `[code]`. The area-edit route
  (`continuo_image_edit`: fill, replace, remove, restyle, relight, box) sends only the crop, with no references `[code]`.
- **Good at** `[official]`: documentary and editorial photography, portraits with real skin texture, film frames,
  TV-frame anime, ink and charcoal drawings, screen-printed posters, flat graphic design with short quoted text,
  8 MP stills in 8 steps, and composing up to 8 pictures into one scene.
- **Not for:** video or sound (single images only `[official]`). Long or dense text (it turns into pseudo-text
  `[official]`; use Ideogram). Outpaint (measured failure in Continuo: a flat grey margin or a hard seam `[code]`; use
  Qwen-Image 2.1 or FLUX.2 Klein). Small crowds in the background (they distort `[official]`).
- **Not H3 video.** It runs on the same transformer but reads a different prompt. Create takes prose, with no fields,
  `[Shot N]`, sound, camera moves or alignment line. Edit has its own instruction form, and it **can** also read
  H3's six-section reference brief (§4.3).

## 2. What Continuo sends (do not duplicate it)

**Create** (`continuo_image_workflow_submit`, target `p-h3-image-lora-t2i-v1`) `[code]`
- Your prompt goes byte for byte into the conditioning node. There is **no prompt upsampler**: Pruna's Qwen3.5-9B
  rewriter is stripped from the pinned graph, so you have to write what it would have written. The server accepts up
  to 16,384 characters, but that is a server limit, not a target length.
- Encoding `[local]`: raw tokens with no chat template and no special tokens. Prompt weights are switched off, so
  `(word:1.3)` reaches the model as literal characters. There is no negative prompt and no CFG.
- Controls: `seed`, `aspect_ratio` (1:1, 2:3, 3:2, 3:4, 4:3, 9:16, **16:9 default**, 21:9; the option label is
  `"3:4 (Portrait Standard)"`, and the short form `"3:4"` names the same option `[code]`), `megapixels` 1–16
  (**default 8**), `lora_strength` 0–2 (default 1.0), `steps` 4–16 (default 8), `sampler` (default `euler`). The
  job returns the effective prompt, so read it back to check what the model got.

**Edit** (`continuo_image_workflow_submit`, target `p-h3-image-lora-edit-v1`) [code + local]
- `references[0]` must have role `target`. It becomes **Picture 1** and is scaled to `megapixels` (1–8,
  **default 4**) at its own aspect. **The output takes Picture 1's aspect and size.** There is no aspect control.
- `references[1..7]` become Pictures 2–8 in the order you send them. The node never scales them up. It scales them
  down to about 8.5 MP only if they are larger.
- Every picture also reaches the text encoder as a vision block of about 1 MP, labelled `<Picture N>: `, before your
  text `[local]`.
- **The server appends a role suffix** whenever there is at least one reference, joined with one space so it stays
  in your paragraph: your prompt + ` ` + `<Picture 2> is the identity reference. <Picture 3> is the location reference.`
  Do not write these lines yourself.
- **The node adds the prefix** `Edit <Picture 1>. ` to the front of the whole text, unless the text already starts
  with `Edit <Picture N>` or `subject_definitions:`. In that case it is sent as written `[local]`.
- The controls are the same as Create, minus `aspect_ratio`.

**Area edit** (`continuo_image_edit` → `p-h3-image-lora-crop-edit-v1`) `[code]`
- The crop is edited at 4 MP and pasted back inside the soft mask. In template mode your prompt is the **thing**,
  and the server writes the sentence around it. P-H3's Fill and Remove see the original crop, with the area
  located by words:
  - fill → `Add {prompt}{where}. Keep everything else in the picture exactly the same.`
  - remove → `Remove {what}{where} and fill that area with the surrounding background, matching its texture, colour and lighting. Keep everything else …`
  - replace / restyle / relight use the shared templates (`Replace {target} completely with {prompt}, …`,
    `Redraw the whole picture as {prompt}. …`, `Relight the photo with {prompt}. …`).
  - None of these start with `Edit <Picture`, so the node puts `Edit <Picture 1>. ` in front of them.
  - `instruction_mode: raw` sends your sentence instead. Write it in the instruct form from §4.2.

## 3. Grammar: create

The model renders the prompts its upsampler writes much better than short requests `[official]`. The vendor's
showcase prompts (9 prompts in the official demo, of which the card's one-line quickstart is a short version) are
your target form `[official; that they mirror upsampler output is a hypothesis]`. Measured on those 9: **88–200
words, 520–1,150 characters**, plain prose, sometimes 2–4 paragraphs separated by blank lines.

**Order** (taken from the vendor prompts and the card's four rules):
1. **What the picture is.** One opening sentence that names the real object: "A photograph by an experienced
   landscape photographer, …", "A frame from a feature film: …", "A frame from a Japanese anime television series,
   hand-drawn cel animation over a painted background, …", "A two-color risograph print on cream paper, …". This sets
   the look more reliably than any style word `[official]`. Shot size, angle and lens fit here: "a wide establishing
   shot from a low angle … with a 35mm lens", "shot at eye level … 35mm lens at f/2.8".
2. **One main subject caught in a moment.** Give age, build, clothes and materials, their wear and state, and one
   physical action in progress ("one boot sinking into the snow", "caught mid-step as if listening").
3. **A few supporting elements and the setting in layers**, near to far ("Behind him … Farther back …").
4. **Light with a source and a direction**, and what it hits: "Moonlight comes from high upper left, pale and cool,
   lifting the frost on the bark and the rim of his pauldron, while the forest floor falls into deep blue shadow
   where texture remains visible."
5. **Atmosphere you can see** (drifting mist, fine rain dimpling the water, dust in the light).
6. **Palette and finish**: "a restrained palette of slate blue, grey-white snow, muted brown leather and tarnished
   steel, neutral white balance, fine film grain".
7. **Closure where it matters**: quoted text plus "no other text". For art media add "filling the whole picture edge to
   edge, with no frame or border". The vendor also ends a fashion prompt with "No text, no other objects."

**Rules**
- **Length:** 80–200 words. Both very short prompts and very long ones make the picture worse `[official]`. The 200-word
  ceiling comes from the vendor corpus, not from a measured limit `[hypothesis]`.
- **No hype words:** stunning, epic, **cinematic**, vibrant, hyper-detailed, 8k and masterpiece push the picture
  glossy, oversaturated and airbrushed `[official]`. For a film look, write "a frame from a feature film" or name the
  camera and lens, never "cinematic".
- **Text:** quote every string exactly, keep each one short, say where it sits, and end with "no other text". If you
  want no text, do not mention signs, labels or screens at all `[official]`.
- **Negatives:** there is no negative prompt. Describe the state you want ("the empty platform"). Closing phrases like
  "no other text" and "with no frame or border" are vendor usage. Do not use long lists of things to exclude.
- **No** weights, tag lists, quality tags, `<Picture N>` labels, H3 fields or `[Shot N]` in Create.
- **Language:** write in English. Keep quoted on-screen text in its own language. That P-H3 handles other languages
  well is a `[hypothesis]`.
- **Left and right:** no source defines whether this means the viewer's side or the figure's own. Write "on the left
  of the frame" or "frame-left" for the viewer's side, and check the result.

**Annotated example (T3 plate, 16:9, 8 MP), about 150 words**
```
A frame from a feature film: a wide establishing shot of a roadside desert motel at blue hour, taken from across
the empty two-lane highway at standing eye height with a 35mm lens.
A single-storey row of twelve doors in faded turquoise paint runs left to right, each with a dented metal chair
beside it. Only the third window is lit, a warm tungsten rectangle behind a thin curtain. A dusty white pickup is
parked nose-in at the far end. Behind the roof, a ridge of bare rock fades into violet haze.
The sky holds the last cold light low on the right, so the stucco reads blue-grey and the shadows under the eaves
are deep but keep their texture. A tall pole sign beside the office reads "VACANCY" in red neon tubing, no other
text.
Palette of dusty turquoise, sand, violet and one warm amber window; natural film colour, fine grain.
```
The first line says what the picture is. Then come the subject (the building) and its supporting objects, the layers,
the light source and direction, one quoted string with its closure, and the palette.

## 4. Edit

### 4.1 Choose a form

The model was trained to edit from **two** prompt forms. Pruna's pipeline accepts exactly these as written and
prefixes everything else `[official]`:

| Form | Use it for | Shape |
|---|---|---|
| **Instruct** | one picture, a local change (recolour, add, remove, relight, retext, small pose change) | ONE paragraph, starts `Edit <Picture 1>.`, contains `Keep`, no line breaks |
| **Brief** (six sections) | combining references (a person or prop into a plate, several references into one scene) | H3's reference schema: `subject_definitions:` … `non_diegetic_music:`, with `[keyframe completion]` |

Bare short requests ("make it snow") are the upsampler's input, not the model's. Typed as-is, P-H3 often **redraws
the whole scene** `[official]`. Never send one bare.

### 4.2 Instruct form (single paragraph)

`Edit <Picture 1>. <the change, described as the finished result>. Keep <everything that must stay> exactly as it is.`
`[official]`
- **Point to the exact thing and where it is:** "the old man's faded blue cap", not "his hat" `[official]`. "The woman
  in the centre is wearing a green shirt" works where "she's wearing a green shirt" fails `[community, 2026-11-07]`.
- **Describe the result, not the action.** Give new things a size relative to something already there ("about the
  size of the cat's head") `[official]`.
- **Say what stays:** faces, poses, background, light and framing. Without this list P-H3 tends to redraw the whole
  picture `[official]`.
- **Quote new text exactly** and name the text around it that must stay `[official]`.
- **No line breaks.** Write `<Picture 1>` with the angle brackets and the space.
- Example (T6 recolour):
  `Edit <Picture 1>. The pickup truck parked at the far end of the motel row is now a faded dark-green pickup with the same dents and dust, still parked nose-in. Keep the motel, the lit third window, the neon "VACANCY" sign, the sky, the light and the framing exactly as they are.`

**With references in the instruct form.** You may name `<Picture 2>` … in the paragraph ("the man from `<Picture 2>`
stands at the railing"). The server then appends its role sentences after one space, so the prompt the model gets
stays one paragraph. Which form follows references better is untested: the instruct form is the short one; the brief
(below) carries more structure for several references.

### 4.3 Brief form (six sections, for references)

This is the H3 reference schema, used as the edit of one keyframe [official: Pruna's pipeline checks for exactly
these six sections in this order, `[keyframe completion]` exactly once, and every `retention_analysis` line naming a
`<Picture i>` or `<Subject i>` with one of the four markers]. Strict format:
- Each header sits alone on its line (`subject_definitions:` with nothing after the colon), and its body starts on
  the next line. Order: `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`,
  `overall_soundscape`, `non_diegetic_music`.
- `summary` contains the literal tag `[keyframe completion]`, once. **Do not combine it** as
  `[keyframe completion + reference generation]`: that string is not `[keyframe completion]` and fails the check.
- Every `retention_analysis` line follows this shape:
  `<Picture 1> (edited keyframe): partially_preserved - …` or `<Subject 1> (appears in the edited picture): fully_preserved - …`
  The markers are `fully_preserved`, `partially_preserved`, `attribute_transfer` and `weak_reference`. Keep the
  parenthesis free of `)`.
- `<Subject N>` is reusable content (a person, prop, outfit or place) and names the picture it comes from. Give each
  item its own line and say its job: `<Subject 1> is the deckhand whose face, hair, beard and build come from <Picture 2>.`
  `[official, H3 reference guide]`.
- Fill the two sound sections with `N/A`. They are left over from video. H3's guide uses `N/A` for "none", while
  Pruna's test stubs use `Silence.` and `None.`, and it is unknown which one the upsampler writes `[hypothesis]`.
- `detailed_description`: begin with one sentence on the medium and look, then describe the **finished picture** in
  the create order from §3, with labels at first mention. Do not write `[Shot N]`, camera moves, timestamps or
  dialogue `[hypothesis: there is one frame]`.
- **Role suffix:** the server's `<Picture N> is the <role> reference.` lands after `non_diegetic_music: N/A`, inside
  that section. The brief still passes Pruna's own format check (checked against `is_edit_prompt`); an
  instruct paragraph with the suffix is now one paragraph too (not re-checked against `is_edit_prompt`). Make `subject_definitions` carry the real roles, so the suffix only
  repeats them (untested).
- The node adds no prefix to a brief. Start the prompt with `subject_definitions:`.

Example (T2: a cast member into an existing plate; Picture 1 = the ferry plate, 16:9; Picture 2 = one clean portrait,
role `identity`):
```
subject_definitions:
<Picture 1> is the picture to edit: a 35 mm documentary photograph of a small ferry deck at dusk.
<Subject 1> is the deckhand whose face, short grey beard, weathered skin and stocky build come from <Picture 2>.
summary:
[keyframe completion] The edited <Picture 1> shows <Subject 1> coiling wet rope at the starboard railing; the deck, sea, sky, light and framing of <Picture 1> stay.
retention_analysis:
<Picture 1> (edited keyframe): partially_preserved - deck, rust-streaked railing, life ring, grey sea, sky, light and framing stay; one person is added.
<Subject 1> (appears in the edited picture): fully_preserved - face, beard, skin and build.
detailed_description:
A 35 mm documentary photograph with natural film colour and fine grain. <Subject 1> stands frame-right at the starboard railing, about as tall as the cabin door behind him, in a yellow oilskin coat and black rubber boots, both hands coiling a wet rope over his forearm, his breath visible in the cold. Cold overcast light from the left lights the side of his face and the wet oilskin; the warm cabin window behind him stays the only warm light. The deck, railing, life ring, sea and sky are exactly as in <Picture 1>.
overall_soundscape:
N/A
non_diegetic_music:
N/A
```

### 4.4 References: how many, and how to choose them

- Technically: Picture 1 + 7 `[official; the node itself takes 9]`. Pruna's showcase composes 8 portraits from one
  sentence, but through the upsampler `[official]`. Without the upsampler, every reference needs a stated job, and a
  picture the text never names is ignored or copied loosely [hypothesis carried over from H3 video's rule]. **Start with 1–2
  references, and add more only once those hold** (untested).
- Use one clean view per identity, never a character sheet or contact sheet (in H3 video a sheet leaks layout). The
  vision encoder sees each picture at about 1 MP, so crop the face or prop to fill the frame.
- **Style comes from the reference more than from the words.** One tester reran the same scenes with a
  medium-first prompt and the pictures "barely changed" `[community, 2026-11-11]`. If a reference's look is wrong, swap
  the reference instead of rewording.
- Scale and placement are weak spots: a Continuo run with `<Picture 2>` "ignored the scale request" [code evidence,
  2026-11-07]. Give the size relative to an object already in Picture 1 ("about as tall as the cabin door").
- One tester reports faces and references hold better than with MiniMax's own image model. Another saw smoother,
  retouched skin `[community, 2026-11-11]`. Judge on your own material.

## 5. Film tasks

**T1: frame 0 for an H3 video take (the main use).** Create at the video's aspect (16:9 → 3872×2176 at 8 MP). H3
Frames centre-crops keyframes to the canvas `[code]`, so a mismatched aspect loses the edges.
- Show the **onset** of the action: the subject has room to move in the direction of travel, weight is set for the
  first movement, and hands and props are clearly separated. Avoid frozen peaks (mid-air, mid-swing) and motion blur.
- Put nothing in the frame that the video prompt will contradict: H3 holds a keyframe whose scene the prompt
  contradicts for one frame, then cuts `[code: video-prompts]`. Reuse this prompt's nouns in the video prompt's
  `[Shot 1]`.
- Keep surfaces that will come close to the lens plain ("a blank pale panel"). Avoid quoted text unless the shot
  needs it.
- Use no hype words: oversaturation in frame 0 carries into the take `[hypothesis]`. For black and white, convert the
  keyframe to true greyscale `[code: video-prompts]`.
- **Last frame for FL2VA:** make it from frame 0 with an instruct edit that changes only the end pose and keeps
  everything else. The two frames then share scene, light and grain. 4 MP is enough, because H3 renders far below that.

```
A frame from a feature film: a medium-wide shot from deck height on a small ferry at dusk, on a 35mm lens.
A deckhand in his fifties in a yellow oilskin coat and black rubber boots stands frame-left, knees bent, both hands
gripping a heavy wet rope that runs from a steel bollard toward the open railing on the right, his weight leaning
back as he starts to haul. Rust streaks run down the white railing; a coiled life ring hangs on it. Behind him the
pale grey sea meets low cloud. Cold overcast light from the left falls across his face and the wet oilskin; one warm
cabin window glows behind him. Fine spray hangs in the air. Palette of grey, rust, yellow and one warm amber light,
natural film colour, fine grain.
```

**T2: one character across shots.** Create the plate first (T3), then use the edit brief with Picture 1 = plate and
Picture 2 = one clean portrait (role `identity`), plus `outfit` if the costume comes from another picture. Describe
in words only what the reference does not supply: pose, action, position, light. For each new shot, use the same
portrait and the same `<Subject 1>` sentence. The output aspect follows the plate.

**T3: location / establishing plate.** Create at 8 MP. To get no people, describe the empty state; do not write
"no people". Keep any people mid-ground and few, because small background figures distort `[official]`. See the example
in §3.

**T4: insert / prop close-up.** Create: "A close-up product photograph …" or "A macro photograph …", then the
material, its wear, the surface it rests on, and a light source raking across the texture. Quote any engraving.
```
A close-up photograph on a 100mm macro lens: a brass ship's compass rests on a scarred oak chart table, its glass
cracked across the north mark, the needle settled on west. A pencil and a folded paper chart lie beside it, the
chart edge soft with damp. A single oil lamp just out of frame on the right throws warm light low across the brass,
catching every scratch and the engraved word "BALTIC" on the rim, no other text. The table falls into brown shadow
toward the top of the frame. Shallow depth of field, natural colour, fine grain.
```

**T5: title card / signage.** Use a graphic medium ("A screen-printed poster …", "flat graphic design …") and at most
1–3 short quoted strings, each placed, then "no other text". For body copy or credits use Ideogram.
```
A two-color screen-printed title card on off-white paper, flat graphic design. Centred in the upper third, the words
"NIGHT MARKET" in tall condensed red capitals; below it, smaller and in deep blue, "PART ONE", no other text. Beneath
the type, a simple blue silhouette of paper lanterns strung between two stalls. Slight misregistration between the red
and blue passes, visible paper texture, the print filling the frame edge to edge with no border.
```

**T6: continuity repair** (remove, replace, recolour, relight, retext). To change one area and keep the rest
pixel-identical, use `continuo_image_edit`; write only the **thing** in template mode (`a dark-green pickup with
dust on the doors`). Use the catalog edit in instruct form for whole-picture changes such as a global relight or
time of day. Never use outpaint here; it was measured broken.

**T7: look / style transfer.** Use instruct for a medium change: `Edit <Picture 1>. The whole picture is now a
two-color risograph print in fluorescent pink and deep blue with visible halftone dots. Keep the composition, every
subject, their poses and the light direction exactly as they are.` To match an existing look, put a `style` reference
in the brief (`<Subject 2> is the colour grade, grain and lighting style of <Picture 3>` with `weak_reference` or
`attribute_transfer`). The reference outweighs the words.

**T8: storyboard frame.** Create with a drawn medium (ink and charcoal work well `[official]`):
```
A loose charcoal storyboard panel on white paper, drawn quickly with confident strokes and grey smudged tone. A
wide frame of a night market alley seen from a low angle: a girl in a hooded raincoat runs toward the camera between
two lit food stalls, her arm raised against the rain, steam rising from a wok on the left. Lanterns are suggested with
a few circles and smudges; the background dissolves into hatching. The drawing fills the panel edge to edge, no
text.
```

**T9: poster / key art.** Create at 2:3, 8 MP, with a screen-print or photographic medium, one subject, and the title
plus at most one tagline in quotes.

**T10: what it is uniquely good at.** 8 MP stills that look like film frames or editorial photographs in 8 steps.
Multi-picture composition (up to 7 references into one scene). And because it shares H3's transformer, frames made
for H3 video takes [hypothesis that this transfers better than other models' frames].

## 6. Parameters

| Knob | Official | Continuo | What it does |
|---|---|---|---|
| Steps | 8 on the checkpoint's own sigma grid `[official]` | 4–16; N≠8 resamples the same grid `[code]` | "More steps do not add detail" (ComfyUI docs). Keep 8. |
| CFG / negative | none (guidance-distilled) `[official]` | none | — |
| Sampler | `euler` `[official]` | free choice | Others are untested by the vendor. Stay on `euler`. |
| Megapixels, create | 8 MP; 1 MP waxy, 2–4 MP more face/hand artefacts `[official]` | 1–16, default 8 | **Composition changes with size**, because the noise changes `[official]`. Fix the size before hunting seeds. |
| Megapixels, edit | 4 or 8 MP `[official]` | 1–8, default 4 | Changes the output size. Use 8 for faces in wide shots. |
| Aspect | 7 card ratios `[official]` | + 21:9 (not on the card) | 21:9 is untested by the vendor. |
| LoRA strength | 1.0 `[official]` | 0–2 | Community: skin looks more natural without it, and one tester saw no difference on his own stack `[community]`. Keep 1.0 unless the artist asks. |
| Seed | — | free; `batch` 1–8 gives seed+index | Re-roll the seed for anatomy; re-word for content. |

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Glossy, oversaturated, crushed contrast | hype words, or no opener saying what the picture is `[official]`; also reported without either `[community]` | Start with the medium sentence, drop hype words, add "natural film colour, fine grain" |
| Waxy faces, broken hands, distorted background people | low resolution `[official]` | 8 MP for create; fewer small background people |
| Edit redrew the whole picture | bare request; no keep list `[official]` | Instruct form with an explicit Keep list |
| Edit changed the wrong person or thing | a pronoun or a vague target `[community]` | Name it by place and look ("the woman in the centre") |
| Reference ignored or only loosely copied | no job stated; too many references; a sheet as identity `[hypothesis]` | Brief with `<Subject N>` definitions; 1–2 references; one clean view |
| New object at the wrong scale | scale not anchored [code evidence] | Give the size relative to an existing object |
| Style ignored in favour of the reference | reference outweighs words `[community]` | Change or remove the style reference |
| Pseudo-text | long, small or unquoted text `[official]` | Short quoted strings plus "no other text"; Ideogram for layouts |
| Literal "(word:1.3)" or stray brackets | weights are off `[local]` | Plain words |
| Grey margin or hard seam at the edge | outpaint `[code]` | Use another model for outpaint |
| Brief behaves like an instruction | malformed brief (combined tag, missing section, text after a header colon) | Fix the format as in §4.3 |

## 8. Sources (accessed 2026-11-12 unless noted)

- `[official]` P-H3-Image model card, Prompting / Editing / Limitations / Performance — https://huggingface.co/PrunaAI/P-H3-Image
- `[official]` P-H3-Image-Comfy card (files, LoRA route, sizes, upsampler, editing) — https://huggingface.co/PrunaAI/P-H3-Image-Comfy (pinned rev 44a0fb73)
- `[official]` Pruna LoRA workflows `p-h3-image_lora_text_to_image.json`, `p-h3-image_lora_edit.json` (same rev)
- `[official]` diffusers `modular_pipelines/p_h3_image/prompt_upsampler.py`, `encoders.py`, docs `api/pipelines/p_h3_image.md` (PR #15171 by Pruna, merged 2026-11-03) — https://github.com/huggingface/diffusers
- `[official]` Official demo Space example prompts — https://huggingface.co/spaces/PrunaAI/P-H3-Image (`examples.py`)
- `[official]` MiniMax-H3 `docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` (six-section reference schema) — https://huggingface.co/MiniMaxAI/MiniMax-H3
- `[official]` ComfyUI tutorial "P-H3-Image in ComfyUI" — https://docs.comfy.org/tutorials/image/pruna/p-h3-image
- `[local]` ComfyUI `comfy_extras/nodes_minimax_h3.py` (`PH3ImageConditioning`), `comfy/text_encoders/minimax.py` (commit "Support PH3Image", 2026-11-03)
- `[code]` Continuo `p_h3_image_workflow_adapter.py`, `p_h3_image_edit_adapter.py`, `image_edit_contract.py`, workflow manifests `p-h3-image-lora-{t2i,edit}-v1`, `model_evidence.v1.json`, `h3_media.py`
- `[community]` Hugging Face discussions on P-H3-Image-Comfy #5, #8, #12 (2026-11-04 … 11-11); Banodoco `minimax_h3_chatter` (2026-11-03 … 11-10)
