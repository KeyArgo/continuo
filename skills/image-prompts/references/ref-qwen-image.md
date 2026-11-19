# Qwen-Image 2.1 (Create, Edit, prompt enhancer): prompting reference

Load this when the target is `qwen-image-2.1-create-pe-v3-v2`, `qwen-image-2.1-edit-pe-v3-v2` or the area-edit
target `qwen-image-2.1-edit-pe-v3`. Tags: `[code]` Continuo source, `[local]` installed ComfyUI node source,
`[official]` Qwen, `[maintainer]` Comfy-Org / PrunaAI / node authors, `[community]` named and dated reports,
`[hypothesis]` untested inference. Sources accessed 2026-11-12.

## 1. Scope

| Target | Op | Inputs | Use it for |
|---|---|---|---|
| `qwen-image-2.1-create-pe-v3-v2` | create | 0-10 role-tagged references | stills with readable text, layouts, signage, title cards; new shots built from references (identity, outfit, location, style); transparent (RGBA) elements |
| `qwen-image-2.1-edit-pe-v3-v2` | edit (+ multi-reference) | image 1 = target, up to 9 references | instruction edits of a whole picture: swap a prop or garment, change copy on a sign, change season or time of day, put a cast member from a reference into the plate |
| `qwen-image-2.1-edit-pe-v3` | area edit (`continuo_image_edit`) | the selection crop only; references are ignored | Fill, Replace, Remove, Outpaint, Restyle, Relight inside a selection |

What it is: Qwen-Image-2.1 base (7B single-stream DiT, Qwen3-VL-8B text encoder, 64-channel RGBA VAE) `[official]`,
int8 repack by Comfy-Org, sped up with PrunaAI's 8-step distillation LoRA `[code]` `[maintainer]`. It is not the
Qwen-Image-2.1-Turbo checkpoint and not the older Qwen-Image-Edit-2509/2511.

Strong at: exact quoted text (English and Chinese), dense layouts, local edits that keep the rest, product and
garment swaps, transparent cut-outs `[official]` `[community]`. Weak at: changing a reference person's pose or camera
angle (it tends to paste the face and keep the reference's angle and light), several views of one character as
references (duplicates the character), physical cause and effect, and photoreal skin without help `[community]`.
For an identity restage use Krea 2 Identity Edit; for a JSON-placed layout use Ideogram; for a video keyframe that
must look like H3 footage use P-H3-Image.

## 2. What Continuo sends (do not duplicate it)

**Fixed build.** Base int8 model + 8-step LoRA at strength 1, 12 steps, CFG 1.5, sampler `er_sde`, schedule `beta`,
denoise 1 (preset `turbo`) `[code]`. CFG 1.5 means **the negative prompt is applied**: ComfyUI skips the negative pass
only at exactly CFG 1 `[local]`.

**Catalog targets (`continuo_image_workflow_submit`).**
- Your prompt is sent byte for byte. If you attach references, the server appends:
  ```
  

  Reference roles:
  <image1>: edit target; preserve everything not requested.
  <image2>: identity reference.
  <image3>: location reference.
  ```
  (create: every line is `<imageN>: <role> reference.`) `[code]`. The block names the role only. **Your prompt must
  still say what each picture gives and where it goes.** Do not write your own "Reference roles" list.
- The text encoder itself puts `<image1>`, `<image2>` … in front of each picture, in upload order, before your
  words `[local]`. Write the tags exactly so: `<image1>`, no space, lower case.
- Edit output size = image 1 scaled to about `reference_resolution`² (default 1024 → about 1 MP), same aspect
  ratio. Create size = `aspect_ratio` × `megapixels` (default 1:1, 1.0 MP). `aspect_ratio` takes the option label
  (`"3:4 (Portrait Standard)"`, `"16:9 (Widescreen)"`); the short form `"3:4"` names the same option `[code]`. A
  refused value answers `accepted` with every option. Never write a ratio, resolution, "4K"
  or "8K" into the prompt `[code]` `[official]`.
- Batch: picture i uses seed + i `[code]`.
- Weights like `(word:1.3)` are not parsed; the tokenizer reads them as text `[local]`.

**Area-edit target (`continuo_image_edit`).** In template mode the server wraps your words. Send the thing, not a
sentence:

| Operation | Server sentence (abridged) | Your prompt |
|---|---|---|
| fill | "Fill the grey area with {prompt}. Keep everything else in the picture exactly the same." | `a coiled blue mooring rope on the deck` |
| replace | "Replace {target} completely with {prompt}, so that nothing of {target} remains, {light match}. Keep everything else …" | the new object; `options.target` = the old one |
| remove | background-only text (LaMa prefill) | nothing |
| outpaint | "Extend the picture into the grey area: continue the same scene … Do not add a frame or border." | optional: what the new area shows |
| restyle | "Redraw the whole picture as {prompt}. Keep the same composition … change only the rendering style. Keep every light source where it is and add none." | `a loose ink-and-wash drawing on cream paper` |
| relight | "Relight the photo with {prompt}. Make the shadows, highlights and the colour of the light match it. Change only the lighting; …" | `low warm sunset light from the left` |

`options.instruction_mode: "raw"` sends your text as is: then write a full edit instruction (section 4.2) `[code]`.
References are dropped on this route `[code]`.

**Prompt enhancer (`prompt_enhancer`, off unless true).** Qwen's own rewriters, fine-tuned Qwen3.5-9B: PE-T2I
without references, PE-I2I with any reference `[code]` `[official]`. How Continuo runs them on the Create and Edit targets, against Qwen's contract:

| | Continuo, texts present | Continuo, texts absent | Qwen's contract |
|---|---|---|---|
| system prompt | Qwen's own: the T2I text without references, the edit text with them | none | required, ships with each model |
| thinking | on | off | "required … degrade without it" |
| budget / penalty | 16256 tokens + presence 1.5 (T2I); 24000 + 0 (edit) | 8192 tokens + presence 0 | 16256 + presence 1.5 (T2I); 24000 + 0 (edit) |
| ratio answer | dropped: only `rewritten_prompt` reaches the image model | same | drives the canvas |

Continuo ships neither system prompt: they are model files, like the weights. Each one is read from the
machine next to its rewriter, in ComfyUI's `text_encoders` folder:
`qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.system_prompt.txt` and
`qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.system_prompt.txt`, byte for byte Qwen's `system_prompt.txt` of
that checkpoint. A file with another text counts as absent. Each text counts on its own: T2I without references,
edit with any reference. `continuo_models_missing` lists both as optional, with their sha256 and source.
Without the text for a run, the enhancer still runs, in the "texts absent" column, and the submit answer
carries `warnings: ["enhancer_system_prompt_absent: …"]`; the target stays ready either way `[code]`.

`[code]` `[official]`. Consequences: the rewrite replaces your prompt entirely; it decides the degree of a change and
can invent copy, brands and prices `[community, Pro API]`; when it returns word soup, grounding JSON or
nothing (a rewrite cut off while thinking), the server sends your own prompt instead, on area edits and on the
Create and Edit targets alike, with or without the texts; the enhancer samples with the run seed `[code]`. Without
its system prompt the rewriter follows no answer contract, so expect more refused rewrites (your own prompt
comes back) and looser rewrites; that is the state area edits always run in (no system prompt, no thinking,
8192 tokens), where it returned word soup or JSON in 6 of 29 runs, all Restyle `[code]`. **Relight never uses it** (it produced blown white "text
pages" and extra people in 6 of 8 tests) `[code]`. It adds about 55 s per run without thinking (texts absent); with the texts present it thinks with the larger budget and takes longer (not measured) `[code]`. The rewritten prompt comes back
as the effective prompt: read it before keeping the picture.

When to turn it on (only when the artist asks): a one-line brief for exploration; camera-angle or view changes on an
edit (users report they only worked with it) `[community]`. Keep it off for: anything with exact text, repeatable
retakes, relights, small local edits, and when you already wrote a full prompt.

## 3. Grammar

### 3.1 Create (enhancer off): write what the enhancer would write

The model was tuned on long observer-style captions; its rewriter targets them `[official]`. Write one English
paragraph in present tense that describes the finished picture as seen:

1. **Opening sentence, medium first** (about 20 words): `A wide 35 mm film photograph of …`, `A vertical flat-vector poster of …`, `A square ink illustration of …`. Name the medium noun every time.
2. **Background and surface** right after the opener.
3. **Walk the frame** with positional phrases (top band → left / centre / right → bottom band, or for one subject: placement → face → clothes → hands → edges). Start roughly a third of the sentences with the position: "On the right side of the frame, …".
4. **Each piece of text** with place, look and exact characters (section 3.3).
5. **A lighting sentence**: `The lighting is …` with source, direction, quality, where shadows fall.
6. **One closing sentence**: `The overall composition is …` (balance, palette, mood).

Rules `[official]`: no "you", "create", "make sure"; no quality boosters (masterpiece, 8K, highly detailed);
colours with a modifier (deep navy, muted olive); materials not bare nouns (weathered teak, brushed steel); counts
as words; people get build, posture, gaze, expression, hair, skin tone and each garment; age as a life stage
("in her forties"), never a number; objects by class, not brand. Physical coherence: shadows away from the light,
consistent scale.

Length: Qwen's rewriter writes 400-500 words. On this 8-step path aim for **150-300 words** and cut repeated
adjectives [hypothesis: one investigator saw long, high-variety prompts turn textures noisy, with and without speed
LoRAs (Banodoco #qwen-image, 2026-10-15); untested]. Put the things that must be right in the first
half `[community, single opinion]`. Never let two phrases contradict each other ("night" and "midday sun"): users
report that breaks it more than anything `[community]`.

Transparent element: `This is an RGBA image with transparency. <subject description>. The image has alpha channel
and the background is transparent.` `[official]`

### 3.2 Negative prompt
The negative is live at CFG 1.5. Leave it empty by default. If a defect repeats, add a short, concrete defect list
(`blurry, extra fingers, garbled text, watermark`), never scene content [hypothesis on benefit; mechanism is
`[local]`]. Exclusions you need for sure still go in the positive prompt as positive states: "the street is empty",
and for lettering "no other text anywhere in the image" `[community]`. "no lettering" on facades is the one negation
users report working on Qwen `[community]`.

### 3.3 Text rendering
- Every visible string in straight double quotes, exact case and characters, in its own script (Chinese, Japanese,
  Cyrillic … stay as written). Next to each quote: where it sits, typeface, weight, case, colour, relative size:
  `Across the top, a heavy condensed cream sans-serif headline reads "LAST FERRY".` `[official]` `[community]`
- One quote per line of text. A line break = "a second line below reads "…"", never a newline inside the quotes
  `[official]`.
- Close text-heavy prompts with `No other text anywhere in the image.` The model adds credits, second prices and
  labels where real designs carry them `[community, measured 38 renders]`.
- Background signs you do not want readable: "blurred, too small to read" `[official]`. No text wanted on a street
  or shop front: say "no lettering on the signs" `[community]`.
- Long body text works (121 words rendered clean on one of two seeds); one line in the middle can garble on one seed
  `[community]`. Render 2-4 seeds (batch) for anything with a paragraph, and zoom-check every line.
- Do not mix languages inside one quote; keep bilingual copy as two quoted lines `[official]`.

### 3.4 Edit grammar (catalog edit target, or `instruction_mode: raw`)
Form: **operation first → the change, pushed to an unmistakable degree → where → what stays, named by type and
position → physical consequences.**

`Change <thing in <image1>> from <old> to <new>, <material/colour/size detail>. <What follows from it: shadow,
reflection, newly visible area>. Keep <named items: the people, their faces and poses, the framing, the light, the
background> unchanged.`

- Name what stays; do not re-describe how it looks. A described "kept" thing gets redrawn `[official]`.
- Identity comes from a picture: say "the man from <image2>", never describe his face `[official]`.
- Moving a limb: state the end state of every hand involved ("her hands are no longer clasped") or it adds one
  `[community, measured]`.
- Removing or moving something: say what fills the uncovered area `[official]`.
- Text on a sign: quote the old and the new string: `Change the sign text from "OPEN" to "CLOSED", same red neon
  script, same size and position.` `[community, Pro API]`.
- Pointing at a region: paint a mark on image 1 in a colour that appears nowhere else, then
  `… inside the red circle … Remove the red circle.` `[official]` `[maintainer]` `[community]`.
- Extending the canvas: call it outpainting `[official]`.
- Affirmative wording ("keep X unchanged"), no hedging, no alternatives `[official]`.

### 3.5 Multi-reference grammar
Roll call, one sentence per picture, each with a short description of what to take and where it goes; end with
the keep clause `[official]` `[community]`:

`Place the deckhand from <image2>, in the yellow oilskin from <image3>, at the railing of the ferry in <image1>,
seen from the waist up and turned three-quarters to camera. Keep his face and hair exactly as in <image2>, the
oilskin's colour and seams as in <image3>, and the deck, sea, light and framing of <image1>.`

- Number each picture once, in upload order. Never "the first image", "image A" or a range like "<image2>-<image4>" `[official]`.
- Fewer references hold better; the speed LoRA was trained with at most 3 `[maintainer]`. Use one clean view per
  person; a character sheet duplicates the person `[community]`. If you must pass a sheet, say only "the person
  from <image2>", do not describe the sheet `[community]`.
- You may say what not to take from a reference: "take only her face from <image2>, not its lighting or
  background" `[community]`.
- Style transfer: `Redraw <image1> in the style of <image2>: …(name the style traits)… Keep the composition,
  people and objects of <image1>.` `[community]`.

## 4. Per operation

### 4.1 Create, no references
Section 3.1 paragraph. Pick `aspect_ratio` (16:9 or 21:9 for film frames) and `megapixels` (1.0 default; 2.0-2.5
for print or a sharper plate `[hypothesis: the LoRA was trained at 1 MP; see P6]`).

### 4.2 Create with references (new shot from references)
Same paragraph, plus a roll call naming each `<imageN>` and its contribution. Role tags in the request help the
server's roles block; they do not replace your sentence. Without a canvas the frame comes from `aspect_ratio`.

### 4.3 Edit (catalog)
Image 1 is the canvas; its framing survives. Section 3.4 form. One change per run for continuity work; chain runs
for several changes (feed the output back as image 1) `[community]`.

### 4.4 Area edit
Template mode: the THING only (section 2 table). Raw mode: a full section 3.4 sentence; the model sees only the
crop, so locate by "in the centre / at the top left of the picture". Restyle inside a mask reads for line styles
(ink), less for paint and tone styles (they read as a recolour) `[code]`. Strength below 100 % starts later on the model's own schedule (a measured
per-model table); under the older linear mapping 70 % left a watercolour restyle a photo `[code]`.

## 5. Film tasks

**T1 Keyframe / frame 0 for a video take.** Create, enhancer off, 16:9. Describe the instant before the action:
pose with weight and direction, gaze, props in hand, clear space where the motion goes. No motion blur, no text.
```
A wide 35 mm film photograph of a ferry deckhand at dusk, the moment before he throws a coiled mooring line toward
the pier. The steel deck is wet and dark grey, scattered with puddles that hold the orange sky. In the left third of
the frame, a man in his fifties with a grey beard stands side-on to camera, weight on his back foot, right arm drawn
back holding the coil of rope, eyes fixed on the pier off the right edge. He wears a yellow oilskin jacket with
reflective tape, black rubber boots and a navy knit cap. In the centre, a white railing with rust streaks runs
across the frame; behind it the pale grey sea and a low line of harbour lights. The right third is open water and
the edge of a timber pier with two iron bollards. The lighting is low warm sunset light from the right, rimming his
cap and shoulder, with cool blue fill on the deck and long shadows falling toward the left. The overall composition
is balanced and calm, with muted orange and steel-blue tones and clear space on the right for the throw.
```

**T2 One character across shots (identity).** Edit or create with the character as a reference.
```
Place the woman from <image2> behind the reception desk of the motel lobby in <image1>, standing, both hands flat on
the counter, looking toward the door on the left. She wears the same faded denim shirt as in <image2>. Keep her face,
hair and build exactly as in <image2>, and keep the lobby, the desk, the neon light and the framing of <image1>
unchanged.
```
Use one sharp, front-lit face view as `<image2>`, role `identity`. If the pose or angle will not change, generate
the new pose first without the reference, then swap the face in a second edit. For a strong restage use Krea 2
Identity Edit `[community]`.

**T3 Location / establishing plate.** Create, 21:9 or 16:9, region walk left → right; say "no people" as a positive
state ("the forecourt is empty") and "no lettering" unless a sign is wanted.
```
A wide establishing photograph of a single-storey desert motel at blue hour, seen from across an empty two-lane
road. Across the top, a deep indigo sky fades to pale orange at the horizon. On the left, a row of eight beige
stucco rooms with turquoise doors and one lit window. In the centre, a tall pole sign with a red neon arrow; the
sign's panel reads "VACANCY" in pink neon script, and no other text anywhere in the image. On the right, an empty
gravel lot with a dark pickup truck and a single sodium lamp. In the foreground, the cracked asphalt road with
faded yellow lines. The lighting is cool dusk ambient light with warm pools from the lamp and the window, soft long
shadows. The overall composition is wide and still, with indigo, turquoise and sodium-orange tones.
```

**T4 Insert / prop close-up.** Create, medium-first opener, material and wear, macro framing, light on the surface.
```
A square macro photograph of a brass ship's compass resting on a weathered teak chart table. The compass fills the
centre of the frame, its glass slightly scratched, the black card with white degree marks pointing north-east. A
corner of a paper sea chart with faded blue depth lines curls up at the lower left. The lighting is a hard warm lamp
from the upper right, a bright highlight on the brass rim and a short shadow to the lower left. The overall
composition is tight and tactile, with brass, teak and cream tones and a shallow depth of field.
```

**T5 Title card / typography / signage.** Create with text rules (3.3). Name every line, its place and style; close
with "No other text …". Generate 2-4 seeds and zoom-check.
```
A wide flat-graphic title card on a matte black background with fine film grain. In the centre, the title reads
"NIGHT MARKET" in tall white condensed sans-serif capitals with wide letter spacing. Directly below it, a second
smaller line reads "a film in four nights" in warm amber italic serif, lower case. At the bottom centre, a thin
amber rule with the small white text "2026" beneath it. No other text anywhere in the image. The lighting is flat
and even. The overall composition is symmetrical and quiet, with generous empty space around the title.
```
Signage inside a scene: edit the plate (`Change the sign text from "…" to "…", same …`).

**T6 Continuity repair.** Prefer `continuo_image_edit` (template mode) for a selection; catalog edit for whole-frame
fixes. Recolour / replace / remove / relight / extend:
- Recolour: `Change the deckhand's jacket in <image1> from yellow to faded red oilskin, keeping its reflective tape, seams and folds. Keep his face, pose, the deck, the sea, the light and the framing unchanged.`
- Remove (raw): `Remove the white plastic bucket at the bottom left of <image1> and continue the wet steel deck and its puddle reflections where it stood. Keep everything else unchanged.`
- Relight: area edit Relight with the light only (`low warm sunset light from the right, long shadows to the left`); enhancer is forced off.
- Extend frame: area edit Outpaint, or catalog edit "outpaint the left side …" with a wider canvas.
Expect a small frame shift on whole-picture edits (median 35 px on style edits) `[community]`: paste back or use the
area-edit route when the cut must line up.

**T7 Look / style transfer.** Catalog edit with the style picture as `<image2>`, role `style`; name the traits:
`Redraw <image1> in the style of <image2>: coarse charcoal lines, smudged grey shading, cream paper grain. Keep the
composition, the two people, their poses and the market stalls of <image1>.` Area-edit Restyle for a crop.

**T8 Storyboard frame.** Create, state the medium and panel look; keep text out unless needed:
`A wide black-and-white storyboard panel drawn in loose pencil on white paper …` with blocking, camera height and
arrows described as drawn marks. Qwen renders multi-panel pages with correct lettering, but staging can drift
(characters appear in the wrong panel) `[community]`: one panel per render.

**T9 Poster / key art.** Create, 2:3, layout by bands (top headline, central image, bottom billing). Quote every line,
say "No other text anywhere in the image.", check the billing block: invented credit rows are the most common fault
`[community]`. Ideogram for exact multi-block layouts.

**T10 Unique to Qwen: transparent elements and copy edits.** RGBA wrapper (3.1) for a prop, sign or logo to
composite; copy changes on existing signs and labels in the plate's own typeface (3.4).

## 6. Parameters

| Control | House value | Official | Effect |
|---|---|---|---|
| steps | 12 (`turbo`); 8 (`fastest`); 40-50 with LoRA 0 (`quality`); 25 (`template`) | base 40 `[official]`; Comfy template 25 `[maintainer]`; LoRA 8 with its own sigmas `[maintainer]` | more steps: settles hands and fine detail; on the LoRA path beyond ~12 can over-sharpen `[hypothesis]` |
| cfg | 1.5 | 1 `[official]` `[maintainer]` | >1 turns on the negative and tightens dense text and numbers; ~2 sharpens edges; ≥3 brightens or darkens exposure; 5 degrades; <1 breaks `[maintainer]` `[community]` |
| sampler / schedule | er_sde / beta | euler / simple | house choice from the artist's workflow `[code]` |
| lora_strength | 1 | 1 `[maintainer]` | 0 = base model (use with the `quality` preset, 40+ steps) |
| megapixels | 1.0 | 2K native base; LoRA trained at 1K | above ~4 MP adherence drops `[maintainer]` |
| reference_resolution | 1024 | 1024 node default | 0 = native size (slow); sets the edit canvas |
| denoise | 1 | 1 | below 1 on catalog edit only lowers sampling of an empty latent; use the area-edit Strength instead `[local]` `[code]` |
| prompt_enhancer | false | "recommended" | see section 2 |

## 7. Failure modes → cause → fix

| Symptom | Cause | Fix |
|---|---|---|
| Extra credits, a second price, labels nobody asked for | model fills design conventions | "No other text anywhere in the image."; batch 2-4; check corners |
| One line of a paragraph garbled | seed-dependent | batch; shorten that line; split into two quoted lines |
| Edit applied faintly / not at all | under-specified degree | name the change to an unmistakable degree; one change per run |
| Untargeted things changed (colour shift, cleaned clutter, new light) | preserved items described in detail, or no keep list | keep list by name, not description; area edit for local work |
| Face looks pasted, wrong scale or colour | reference identity transfer | one clean reference; describe light on the subject in the target scene; second pass in Krea 2 Identity Edit |
| Character duplicated | several views of one person as references | one view; "the person from <imageN>" |
| Third hand / wrong limbs after a pose change | old pose kept | state the end state of every hand |
| Output slightly shifted or zoomed | known whole-picture edit drift | area-edit route; paste back |
| Prompt text appears as literal "(word:1.3)" or JSON in the image | weights/JSON are read as text | plain prose only |
| Noisy, grainy textures on a long prompt | high-variety long prompt `[hypothesis]` | cut to 150-300 words; drop adjective chains |
| Enhancer output odd (invented copy, changed degree) | the rewrite replaces your prompt; word soup and JSON already fall back to your prompt; with `enhancer_system_prompt_absent` in the answer it ran without Qwen's system prompt | read the effective prompt; turn the enhancer off and write the prompt; for the full contract the artist places the missing text (`continuo_models_missing`) |
| Effective prompt is exactly your own text with the enhancer on | the rewrite was refused (soup, JSON, or cut off while thinking); more often without the system prompt texts | retake with another seed, or turn the enhancer off |
| Relight made blown white pages or extra people | enhancer on relight | already forced off; relight text = light only |
| Medium drifts to photoreal on a drawn style | distilled speed path `[community, for the Turbo checkpoint]` | open with the medium noun; `quality` preset (LoRA 0, 40 steps) |
| Fine checkerboard texture in photo detail | stock VAE decoder | texture-fix VAE (catalog allows it) `[maintainer]` |

## 8. Sources (accessed 2026-11-12)

`[official]` Qwen/Qwen-Image-2.1 model card, https://huggingface.co/Qwen/Qwen-Image-2.1 · QwenLM/Qwen-Image-2.1
README, https://github.com/QwenLM/Qwen-Image-2.1 · rewriter system prompts
`prompt_rewrite/prompts/system_prompt_t2i.txt` and `system_prompt_edit.txt`, `prompt_rewrite/pe_core.py`,
`prompt_rewrite/README.md` in that repo · PE cards https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I,
https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I · Turbo card https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo
`[maintainer]` https://huggingface.co/Comfy-Org/Qwen-Image-2.1 · https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1 ·
Comfy-Org workflow_templates `image_qwen_image_2_1_{t2i,image_edit,turbo_image_edit}.json` ·
https://huggingface.co/PrunaAI/P-Q-Image-2.1 · ComfyUI core `comfy_extras/nodes_qwen.py`,
`comfy/text_encoders/qwen_image21.py`, `comfy/samplers.py`
`[community]` Runware Qwen-Image-2.1-Pro guides (prompting, editing images, multi-reference, prompt extension),
https://runware.ai/docs/models/alibaba-qwen-image-2-1-pro/guides · https://stablediffusion.fr/guide/qwen-image-2-1
(2026-10-16) · https://civitai.com/articles/35700 (2026-09-24) · https://civitai.com/models/2969862 (2026-09-30) ·
https://huggingface.co/Qwen/Qwen-Image-2.1/discussions/27 (2026-09-22) and /64 (2026-10-17) ·
Reddit r/StableDiffusion 1wlo06m, 1wokni7, 1wq3lga, 1wwi34c; r/comfyui 1wpwyri (2026-09/10) ·
Banodoco Discord #qwen-image, 2026-09-19 to 2026-11-10
`[code]` Continuo `qwen_image_workflow_adapter.py`, `qwen_image_edit_adapter.py`, `image_edit_contract.py`,
`model_catalog.v1.json`, `image_edit_capabilities.v1.json`, pinned workflows `qwen-image-2.1-*`
