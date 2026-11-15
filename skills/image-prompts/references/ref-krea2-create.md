# Krea 2 Create (Turbo, Raw): prompting reference

Load this when you write a prompt for catalog family `krea2`, variant `turbo` or `raw` (Suite target
`krea2-turbo-t2i-create`). Edits (Identity Edit V2, General Edit V2) have their own reference.
Evidence tags: `[code]` Continuo source, `[local]` the installed engine, `[official]` Krea / diffusers / Comfy-Org,
`[community]` named practitioners, `[hypothesis]` not yet measured. Sources are listed in section 8.

## 1. Scope

- **Krea 2** is a text-to-image DiT trained from scratch by Krea AI for broad aesthetic range: photographs,
  paintings, anime, collage, ink, 3D. Its text encoder is Qwen3-VL-4B, which reads sentences, so it follows
  spatial relations, possessives and counts `[official]`.
- **Turbo** is the 8-step distilled checkpoint, built for inference. **Raw** is the undistilled base. Krea says
  Raw is "not recommended for inference use": train LoRAs on Raw, run them on Turbo `[official]`.
- In Continuo, Turbo and Raw are two presets of one target. The files are `krea2_turbo_int8_convrot` /
  `krea2_raw_int8_convrot` (community INT8 ConvRot quants, not Krea's BF16 weights), `qwen3vl_4b_fp8_scaled`
  and `qwen_image_vae` `[code]`.
- **Use it for:** film keyframes, location plates, inserts, look development, key art and storyboards in any
  style. It is fast enough (8 steps) to explore several seeds per idea.
- **Do not use it for:** editing an existing picture (use Krea 2 Edit or another edit model); carrying a person
  from a reference picture (T2I takes no picture input); posters with a lot of text (use Ideogram 4);
  strong negative emotions. Practitioners report angry, crying and pained faces coming out flattened by the
  safety tuning `[community]`.

## 2. What Continuo sends

- **Your prompt goes to the encoder verbatim.** The manifest says `prompt_policy: literal`; the adapter writes
  the text into `CLIPTextEncode.text` and nothing else `[code]`. There is **no prompt enhancer**. That matters
  because the official Comfy-Org Krea 2 template expands every prompt with an LLM by default (Krea's
  `expansion.txt` system prompt), and Krea calls that expander part of how the model reaches its quality
  `[official]`. In Continuo you have to write the expanded caption yourself.
- **The engine adds a hidden system line.** ComfyUI wraps the prompt in the same chat template Krea trained
  with: *"Describe the image by detailing the color, shape, size, texture, quantity, text, spatial relationships
  of the objects and background:"*. It then strips that prefix from the conditioning `[local]` `[official]`.
  The model was trained on captions of that kind, so write the caption that line asks for.
- **Graph.** Turbo: `CLIPTextEncode → KSampler`, negative = `ConditioningZeroOut` (no negative text).
  Raw: the same graph with the Raw UNet and a real negative `CLIPTextEncode` (empty by default) `[code]`.
  Validation rejects a negative on Turbo `[code]`.
- **LoRAs** are chained as `LoraLoaderModelOnly` nodes between the UNet and the sampler, strength 0–2. They
  are model-only, so **a trigger word reaches the model only if it is in your prompt text** `[code]`.
  `continuo_image_action select_tile` toggles at most 4 builder LoRAs; a `render_spec` takes up to 32.
  On Raw the Image pane multiplies every LoRA strength by **0.6** (house rule, after the artist judged style
  LoRAs stronger and better on Turbo) `[code]`.
- **Controls** (`continuo_image_action set_sampling`): `profile turbo|raw`, `steps 1–100`, `cfg 0.1–20`,
  sampler, scheduler, `negative` (Raw only). `set_size`: aspect presets 1:1, 4:5, 3:4, 2:3, 9:16, 16:9,
  3:2, 21:9 at a chosen MP; the renderer allows 512–2048 px per side in steps of 16 and at most 4.19 MP
  (2048×2048). Batch 1–8, picture *i* uses `seed + i` `[code]`.
- **Presets** `[code]`: Turbo = 8 steps, CFG 1.0, euler/simple, denoise 1. "Official Turbo" = CFG 1.0 (Krea's
  CFG 0 in ComfyUI terms; ComfyUI's Krea 2 model already samples at Krea's fixed shift of 1.15 `[local]`, so there
  is no mu control). Raw (the default Raw preset) = 52 steps, ComfyUI CFG 3.5 (= Krea 2.5). "Raw, official" = 52
  steps, ComfyUI CFG 4.5 (= Krea's official 3.5).

### The builder writes text too
In builder mode the pane writes the prompt from tiles in a fixed order, verbatim:
`character → outfit → (palette, one character only) → shot → "She is " + scene → LoRA trigger texts → style → your intent text (set_intent)` `[code]`.
Consequences:
- Your `set_intent` text comes **last**, after everything else. Write only what the tiles do not say (the
  action, a prop, one light detail). Do not restate the subject or the scene, or the model may draw it twice
  `[hypothesis]`.
- Most shot and scene tiles are written for one specific female character ("she", "her hair", "She is ...").
  The pane flags these with `written_for_...` warnings. For your own characters, objects or empty plates, use
  **manual mode** (`set_manual_prompt`), not the tiles.
- The builder puts the style sentence near the end. Krea's own examples lead with the medium (section 3).
  When the look matters, write a manual prompt `[hypothesis]`.
- Several builder LoRA tiles carry no trigger text even though their trainers list one (section 4.3).

## 3. Grammar: the trained form

**One English paragraph of descriptive prose: the caption a careful describer would write for the finished
picture.** Krea trains mainly on long, dense, OCR-aware captions and also on short and medium versions of
them `[official]`. All 20 official sample prompts are plain description: no weights, no quality tags, no
negatives, no instructions `[official]`.

**Order: medium → subject + action → details → place → light → texture words.**
- **Open with what the picture is.** In 14 of the 20 official prompts the medium sits in the first eight
  words: "A minimalist flat-color illustration of ...", "3D rendered matte black designer toy figure ...",
  "1990s vintage anime style cel animation, ...", "A close-up portrait of ..." `[official]`. A medium that
  only appears in the last clause competes with everything said before it `[hypothesis, house tests]`.
- **Subject and the one action next.** What comes first reads as the subject: "a brass compass on a chart"
  keeps the compass; "a chart with a compass on it" gives the frame to the chart `[community]`.
- **Group each subject with its own attributes** (clothes, materials, colours), then place it in the frame
  ("in the lower left foreground", "frame right") `[official expansion rules]`.
- **Light with a source and a direction.** "Cold blue daylight from the open door on the left, a warm tungsten
  bulb overhead." Prompts with no stated light are the most common cause of mushy results `[community]`.
- **Close with texture and finish words** that bracket the medium: "visible brushstrokes", "fine film grain",
  "ligne claire", "flat shading" `[official sample pattern]`.

**Length**
- Official samples run 10–180 words, median about 75 `[official, counted]`. Krea: "Long detailed prompts yield
  best results, but the model is capable of generating high quality images with minimal prompt engineering"
  `[official]`.
- In Continuo nothing expands a short prompt, so **aim for 60–150 words** for keepers. Short prompts (under
  ~25 words) work, but the model fills in the rest and takes control of composition `[community]`.
- Krea's reference encoder truncates at **512 tokens** (roughly 350–400 English words). ComfyUI does not
  truncate `[official]` `[local]`. Practitioners report that 650-token prompts are still followed
  `[community]`. Past ~350 words you are outside the training range, so make that a deliberate choice.

**Wording rules**
- **Concrete nouns and named colours:** "oxblood wool coat", "brushed aluminium", "a tiled 1970s stairwell".
  Specific beats loud: "oxblood" works where "very red" fights the model `[community]`.
- **Counts as words or numbers:** "two deckhands", "a 4×3 grid of windows". Counts mostly hold `[community]`.
- **No quality spam** ("masterpiece, 8k, best quality"): it is ignored `[community]`. For photoreal frames,
  avoid "cinematic": one user traced Krea's "3D rendered looking" photos to it and fixed them with "candid
  still" `[community]`. Name the photographic medium instead ("a 35mm film still", "a candid documentary
  photograph").
- **No `(word:1.3)` weights.** Continuo has no weighting node, so the parentheses go to the encoder as text.
  For emphasis, put the thing earlier or describe it twice in different words ("a rusted gate, orange
  corrosion eating through the hinges") `[community]`.
- **Describe what is there, not what is absent.** "The empty platform", not "no people". Turbo has no negative.
- **Shot words that need a second person** ("over-the-shoulder", "two-shot", "reverse shot") can duplicate a
  lone character. For one figure, describe the gaze instead: "looking back over her right shoulder" (the
  official corpus uses exactly that) `[hypothesis, house tests]`.
- **Metaphors become objects.** "A crown of leaves" puts a crown on the head. Describe shape as shape
  ("hair tapering to sharp points") `[hypothesis, house tests]`.
- **Light can turn into material.** "Highlight bands on her hair" can render as dyed streaks. Use a light verb
  and a direction: "light catches the crown of her hair in a hard band running across it"
  `[hypothesis, house tests]`.
- **A colour or mood with no owner applies to the whole picture.** "Everything stays monochrome" overrides the
  style. Tie it to its owner: "her clothes stay black and grey" `[hypothesis, house tests]`.

**Text in the picture**
- Put the exact words in double quotes: `a hand-painted sign above the door reading "NIGHT FERRY"` `[official]`.
  Keep it short (1–4 words), say where it sits and what it is painted, printed or lit on.
- Quality sits between SDXL and Ideogram: fine for a shop sign, weak for a poster headline `[community]`. Krea
  trained with an OCR-aware caption pipeline and a text-rendering reward `[official]`. For several lines or
  real layout, use Ideogram 4.
- The Comfy-Org expander forbids text unless the user asks and appends "no text, no letters ..." to every
  prompt `[official template]`. Krea does add stray lettering when not asked. With a large sign, label or
  screen, describe the surface as blank ("a blank pale enamel panel") when you want no text
  `[hypothesis]` (untested).

**Negatives (Raw only)**
- Official default: an empty negative `[official]`. Practitioners say LLM-encoder models gain little from
  negatives `[community]`. Leave it empty. If one recurring defect survives several seeds on Raw, add a short
  natural-language negative ("plastic skin, blurry background figures") and change nothing else
  `[community]`.

## 4. Operations

### 4.1 Create on Turbo (default)
Preset 8 steps / CFG 1.0 / euler / simple. Write the full caption (section 3). To explore, **change the seed**
(batch 4 to 8) before you change words. Once a composition lands, keep the seed and change one clause at a
time `[community]`.

### 4.2 Create on Raw
Use it only when the artist asks, when Turbo's results look too alike across seeds, or when you need a real
negative. Raw is slower (52 steps), more varied, and in ComfyUI often "baked" or noisy at the preset
`[community]`.
- **CFG convention trap.** Krea's code and diffusers compute `cond + g·(cond − uncond)`, which equals
  standard CFG at **g + 1**. So Krea's official Raw "CFG 3.5" is **4.5 in ComfyUI's KSampler** (the "Raw, official"
  preset), and Continuo's default Raw preset of 3.5 is official guidance 2.5. Turbo's official 0.0 is ComfyUI 1.0,
  which both Turbo presets match `[official]` `[local]` `[code]`. Which Raw preset looks better is untested: keep
  the default unless the artist asks, and offer "Raw, official" when Raw follows the prompt too loosely.
- Raw in ComfyUI also samples at the fixed Turbo shift (1.15). Krea's Raw code derives the shift from
  resolution (about 0.9 at 1 MP) `[local]` `[official]`. Neither preset reproduces the official Raw schedule
  exactly; test before relying on it.
- Use the same prompt as on Turbo. Prompts carry over from Turbo to Raw "somewhat consistently" `[community]`.
- LoRAs on Raw: the pane applies ×0.6. The artist's comparisons found style LoRAs clearly better on Turbo
  `[code note]`.

### 4.3 Create with a style LoRA
- Krea trains its own LoRAs on Raw and publishes them for Turbo at strength 1.0 `[official]`. Community LoRA
  pages give their own strengths (often 0.6–1.5). Start at the card value; the Comfy-Org template defaults to
  0.8 `[official template]`.
- **Trigger placement.** Krea's own example puts the trigger phrase at the end: `"A deer grazing in the forest,
  monochrome ink wash style"`. The Comfy-Org template appends `, <trigger>` to the prompt `[official]`. Some
  community triggers are made-up tokens (`crtvaporwave`, `DCVSTEXP.` with its full stop, `YFG-Fwshn`,
  `@imperfecta`, `yasya_style`). Copy them exactly from `continuo_image_lora_info` or the LoRA card.
- **Keep the rest of the prompt about content.** A prompt that asks for "photorealistic" while a tarot LoRA
  pushes tarot art makes the LoRA "do nothing" `[community]`. Drop your own style words, or make them agree
  with the LoRA.
- **Scene fit.** A LoRA looks weakest on subjects it never saw. Pick a subject close to the card's examples
  for a first test `[hypothesis, house tests]`.
- Some builder tiles carry no trigger text for LoRAs whose trainers list one (Midjourney-style
  `midjourney`, IMPERFECTA `@imperfecta`, Yasya `yasya_style`) `[local]`. Type the trigger yourself when you
  want the trained look.
- Stacking: no official guidance. Two LoRAs at their card strengths can overcook; lower each by 0.2 first
  `[hypothesis]`. Several practitioners report that some LoRAs "destroy prompt adherence and make details
  blurry" `[community]`.

### 4.4 Not on this target
Image-to-image, inpaint, reference pictures, style reference and identity carry-over are not wired into
`krea2-turbo-t2i-create` `[code]`. Use the Krea 2 Edit targets, the Image page edit tools, or a multi-reference
model.

## 5. Film tasks

### T1 Keyframe / frame 0 for a video take
- **Aspect = the take's aspect.** Video keyframes are centre-cropped, and the canvas aspect must equal the
  keyframe aspect `[code: video skill]`. For a 16:9 take use `set_size {format: "16:9", mp: 2}` (1936×1088) for
  keepers, or 1 MP (1360×768) for drafts.
- **Show the onset, not the climax.** Freeze the instant the action starts: weight shifted, hand reaching,
  head turning. The video prompt then describes the path from that pose to the end state.
- **Staging the video model can continue** `[hypothesis]`: subject sharp; moderate depth of field (no extreme
  bokeh or motion blur, which the video model would have to animate); room in frame toward where the subject
  will move; light source named so the take can repeat it; no large blank surfaces that a video model would
  fill with invented lettering, or describe them as plain.
- **The keyframe must match the video prompt's scene.** If they disagree, the take cuts away after frame 0
  `[code: video skill]`. Reuse the keyframe's subject, place and light wording in the video prompt.
- Example (Turbo, 16:9, 2 MP):
  ```
  A 35mm film still, eye-level medium-wide shot on the open stern deck of a small car ferry at dusk. A
  deckhand in a yellow oilskin jacket and black rubber boots has just bent to lift a coil of wet mooring rope
  from the steel deck, his weight on his front foot and both hands closing on the rope. Rust streaks run down
  the white railing behind him; beyond it the grey sea and a low line of harbour lights sit on the horizon in
  the right third of the frame, leaving open deck to his left. Overcast cold light from the sky, one warm
  sodium lamp on the cabin wall lighting his right shoulder. Moderate depth of field, the deck and railing in
  focus, fine natural film grain.
  ```

### T2 One character across shots (identity)
- T2I has no identity channel. Consistency comes from a **fixed identity block**: the same words in the same
  order at the start of every prompt, followed by that shot's framing, action, place and light.
- Put in the block only what belongs to the person: face, hair shape and colour, build, age, one signature
  garment or accessory. Leave out pose effects, situational light and palette rules for the whole picture
  `[hypothesis, house tests]`.
- Keep the block under ~80 words so the shot still has room. A long, illustration-flavoured identity block
  ("large almond-shaped eyes", "a single catchlight") drags every style toward anime
  `[hypothesis, house tests]`.
- Name what must not vary in concrete terms ("a faded navy watch cap with a frayed brim"). Unnamed details are
  re-invented per seed.
- For real cross-shot identity, generate a reference here, then restage it with Krea 2 Identity Edit V2 or a
  multi-reference model.

### T3 Location / establishing plate
Medium first, then the place and its scale, time of day and light, foreground-to-background layers. State
"empty" or "deserted" positively. Example:
```
A wide establishing photograph of a desert motel at blue hour: a single-storey row of eight pale green doors
under a flat roof, a dry swimming pool fenced in chain-link in the foreground, a tall unlit roadside sign on a
steel pole at frame left, the empty asphalt lot reflecting the last cyan light in the sky. Two windows glow
warm orange; the rest are dark. Deep focus, everything sharp from the pool fence to the low mountains on the
horizon, subtle film grain.
```

### T4 Insert / prop close-up
Use the official macro pattern: subject + material + what the hand or surface does, then "macro photograph",
the focal plane and the background falloff. Example: `A macro photograph of a weathered brass ship's compass
resting on a folded paper chart, the needle trembling near north-east, salt crust in the bezel engraving. The
focus falls on the needle tip; the chart dissolves into soft warm bokeh. Low raking lamp light from the left
picks out scratches on the glass.`

### T5 Title card / typography / signage
Short words only, quoted, placed, with their material: `a night-market stall banner of red cloth hand-lettered
in white brush script reading "NOODLES"`. Title cards with layout or several lines: use Ideogram 4. Check
spelling on every seed; re-roll the seed before rewording.

### T6 Continuity repair
Not this target: use the edit tools (Krea 2 General Edit V2, area edits on the Image page).

### T7 Look / style
Lead with the medium and its era or process ("A 1970s Italian thriller film still, saturated red and blue gel
light, deep black shadows, coarse grain"), then the content, then texture words. If the prompt cannot reach a
look, use a style LoRA (4.3). When a look fails, test it on its own (style + a simple subject) before blaming
the model `[hypothesis, house tests]`.

### T8 Storyboard frame
One panel per picture: `A rough graphite storyboard sketch, loose construction lines and grey tonal shading on
white paper, wide shot of ...`. Krea can draw multi-panel comic grids when asked panel by panel `[community]`,
but one frame per render keeps each shot's composition under control.

### T9 Poster / key art
Strong single composition, the medium first, a palette tied to its objects, negative space described where
type will go ("an empty dark sky across the top third"). Add the title afterwards in a layout tool or
Ideogram; let Krea render at most a short quoted title.

### T10 What Krea is best at
Range of looks from words alone: painterly, ink, cel animation, collage, analogue photography, 3D toy
renders, with fast 8-step iteration. Use it for look development and shot exploration: one idea × 4–8 seeds,
then lock the best seed.

## 6. Parameters

| Knob | Official | Continuo house | What it does |
|---|---|---|---|
| Steps, Turbo | 8 `[official]` | 8 `[code]` | Distilled to 8; more steps do not add detail. Community runs 8–12, some LoRA authors 10 `[community]`. |
| CFG, Turbo | 0.0 (Krea convention) = **1.0 in ComfyUI** `[official]` | 1.0 `[code]` | Keep 1.0. Above 1 the negative is `ConditioningZeroOut`, which practitioners report adds grain; strong CFG gives "weird glitches" `[community]`. Never set 0.1 to mean "off": in ComfyUI that is almost unconditional. |
| Steps, Raw | 52 `[official]` | 52 `[code]` | Community: good results at 40–60 `[community]`. |
| CFG, Raw | 3.5 (Krea) = **4.5 ComfyUI** `[official]` | 3.5 `[code]` (= Krea 2.5, default Raw preset); 4.5 in the "Raw, official" preset | Higher follows the prompt harder, then over-bakes. Vary offers 3.5 / 4.5 / 5.5 `[code]`. The right Raw value is untested. |
| Sampler / scheduler | Euler ODE `[official]` | euler / simple `[code]` | Keep. Practitioners also like er_sde/simple and res_2s; SDE samplers at 8 steps can leave JPEG-like specks `[community]`. |
| Shift (mu) | Turbo 1.15 fixed; Raw resolution-derived `[official]` | ComfyUI model default 1.15, not exposed `[local]` | A ComfyUI node maintainer: no resolution shift on Turbo `[community]`. |
| Size | Turbo 1k–2k; Raw up to 1k `[official]` | 1 MP default, 512–2048 px, ≤4.19 MP `[code]` | Krea's samples are 2k Turbo. Use 1.5–2 MP for Turbo keepers, 1 MP for Raw and drafts. Duplication shows past ~4k `[community]`. |
| LoRA strength | 1.0 (Krea LoRAs) `[official]` | card value, ×0.6 on Raw `[code]` | Higher = stronger look, weaker prompt adherence. |
| Seed | `seed + i` per picture `[official]` | same `[code]` | Seeds vary composition strongly; explore seeds first. |

## 7. Failures → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Generic, safe composition | Short prompt with no expander | Write the caption out: medium, subject + action, place, light, texture (60–150 words). |
| Photo looks like a 3D render | "cinematic" or no photographic medium named | "A 35mm film still" / "a candid documentary photograph"; name the lens or film stock if needed. |
| Style ignored | Medium only at the end, or a long description in another style's vocabulary | Medium first; shorten the identity block; or use a LoRA. |
| LoRA "does nothing" | Trigger missing (model-only LoRA) or prompt style words fight it | Add the exact trigger; remove contradicting style words. |
| Picture washed out or mostly noise on Turbo | cfg set to 0.1 or 0 to mean "off" | cfg 1.0. |
| Grainy or glitchy Turbo | cfg > 1 with the zeroed negative | Back to cfg 1.0. |
| Raw baked, noisy or stippled | ComfyUI guidance/shift differ from Krea's Raw recipe; or Raw used for a Turbo job | Use Turbo; or try the "Raw, official" preset (ComfyUI cfg 4.5, the official equivalent) and 40–52 steps (untested). |
| Same character twice | Two-person shot words, or the subject restated in builder intent | Describe gaze, not camera position; do not repeat the subject. |
| Unwanted thing appears | Named in order to forbid it | Describe the positive state ("the empty platform"). |
| Garbled or extra lettering | Long or unquoted text, or a large blank surface | Quote short text; describe surfaces as plain; Ideogram for layouts. |
| Flat face where anger or grief was asked for | Expression suppression in the model `[community]` | Describe visible physical cues (clenched jaw, wet red eyes, tears on the cheek); otherwise use another model. |
| Wrong pronouns or hair wording | Builder tiles written for one character | Manual mode for other subjects. |
| Duplicated limbs or subjects at huge sizes | Above the trained size | Stay ≤ 2048 px per side (the renderer enforces it). |

## 8. Sources (accessed 2026-11-12)

- `[official]` Krea 2 README (Raw 52 steps / CFG 3.5 / up to 1k; Turbo 8 / CFG 0 / mu 1.15 / 1k–2k; "train on
  Raw, run on Turbo"): https://github.com/krea-ai/krea-2
- `[official]` Prompting guide + 20 sample prompts: https://raw.githubusercontent.com/krea-ai/krea-2/main/docs/prompting.md
- `[official]` Expander system prompt: https://raw.githubusercontent.com/krea-ai/krea-2/main/docs/expansion.txt
- `[official]` Reference code: `encoder.py` (system template, max_length 512), `sampling.py`
  (`v = cond + guidance·(cond − uncond)`, empty negative, mu schedule), `inference.py` (defaults) in the same
  repo.
- `[official]` Technical report (captioning, long + short captions, RL rewards incl. text rendering, CFG,
  TDM distillation, prompt expander): https://www.krea.ai/blog/krea-2-technical-report
- `[official]` HF cards: https://huggingface.co/krea/Krea-2-Turbo, https://huggingface.co/krea/Krea-2-Raw
  ("not recommended for inference use"); LoRA card example: https://huggingface.co/krea/Krea-2-LoRA-darkbrush
- `[official]` diffusers `Krea2Pipeline` docstring ("equals the usual CFG formulation with scale
  1 + guidance_scale"): https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/krea2/pipeline_krea2.py
- `[official]` Comfy-Org tutorial + template `image_krea2_turbo_t2i` (8 steps, CFG 1, euler/simple, prompt
  enhance on by default, LoRA triggers appended, strength 0.8): https://docs.comfy.org/tutorials/image/krea/krea-2
- `[local]` ComfyUI `comfy/text_encoders/krea2.py` (template, 12-layer tap), `comfy/supported_models.py`
  (Krea2 shift 1.15), `comfy/samplers.py` (cfg 1 skips the negative).
- `[code]` Continuo: `workflows/krea2-{turbo,raw}-t2i-create`, `generation/krea2_create_adapter.py`,
  `krea2_render_spec.py`, `model_catalog.v1.json`, `image_bridge.py`, builder `compileKrea2Prompt`.
- `[community]` InstaSD "Krea 2 Prompt & Style Guide" (2026-07): https://www.instasd.com/post/krea-2-prompt-and-style-guide-comfyui
- `[community]` Banodoco `krea-2-image` channel, June–Nov 2026 (a node maintainer on negatives and shift; reports on
  Raw baking, expressions, duplication, samplers, 650-token prompts).
- `[community]` r/StableDiffusion "KJ nodes: Krea2PromptWeight node and CFG >1 findings" (2026-07-14).
