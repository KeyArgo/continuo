# MiniMax-H3-Image: prompting reference (Create, with references)

Load this when you write or repair a prompt for catalog family `minimax_h3_image`, target
`minimax-h3-image-create-v1`. This is MiniMax's official image model. It is **not** P-H3-Image (Pruna AI's LoRA
route); that model has its own reference (`ref-p-h3-image.md`) and its own prompt forms. Never carry one model's
syntax into the other.
Tags: `[official]` = MiniMax's model card, example files or released prompt-expander prompts · `[code]` = what the
Continuo server does (file:line in the repository) · `[local]` = the ComfyUI node and encoder that run it ·
anything not in the sources is marked **untested**.

---

## 1. Scope

- **What it is.** MiniMax-H3-Image is MiniMax's open image model from the H3 family: one checkpoint that generates
  images from text and edits one or more reference images `[official]`. Its transformer is the H3 architecture with
  the audio branch removed (33.1B parameters); the text encoder is MiniMax-H3's full Qwen3-VL encoder, unchanged
  `[official]`. It is distilled to **6 sampling steps with no classifier-free guidance** and generates about
  **16 MP directly, without an upscaler** `[official]`.
- **What Continuo runs.** The Comfy-Org quantized files: `minimax_h3_image_pruned_int8_convrot` (DiT),
  `qwen3vl_32b_minimax_h3_nvfp4_awq` (text encoder, `CLIPLoader` type `minimax`), `minimax_h3_image_vae_fp16` (VAE)
  `[code: model_catalog.v1.json, family minimax_h3_image, files; workflows/minimax-h3-image-create-v1/workflow-api.json nodes 1-3]`.
  It needs **ComfyUI 0.45.0 or newer** (`MiniMaxH3ImageConditioning` first shipped in 0.45.0)
  `[code: manifest.json descriptor.reason; local: comfy_extras/nodes_minimax_h3.py:711]`.
- **Not P-H3-Image.** P-H3-Image is Pruna's finetune run as a LoRA over the H3 FL2VA *video* transformer with a
  Qwen3-VL-4B encoder `[code: p_h3_image_workflow_adapter.py]`. MiniMax-H3-Image is the official image checkpoint
  with the full 32B encoder. Different weights, different prompt forms (§3), different recipe (§5). P-H3's
  `Edit <Picture 1>.` instruct form and six-section brief do **not** apply here.
- **Create only in Continuo.** One target, `minimax-h3-image-create-v1`: text to image, optionally with up to 9
  reference pictures. No edit variant, no area edits, no mask, no prompt enhancer
  `[code: manifest.json descriptor.capabilities]`. **No LoRAs**: the H3 video LoRAs were trained on another
  transformer and none is known to fit `[code: image_workflow_run.py:68]`.
- **Good at** `[official, card showcase]`: photorealistic photography, surreal editorial photographs, environment
  concepts, characters/creatures/props, painting and illustration styles, text rendering with reasoning (logic
  puzzle boards in English and Chinese, solved on the board), and reference edits (an untextured 3D render turned
  into a film still, a game map turned into a first-person view, ten references composed into one room).
- **Not for:** video or sound (single images). Long dense text is shown on the card but untested through Continuo.
- **No render through the Suite on record yet** `[code: model_evidence.v1.json has no minimax_h3_image entry]`.
  The pinned recipe is the artist's own, read from the API graphs in the PNG metadata of his renders of 13 Nov 2026
  on ComfyUI 0.45.0 `[code: manifest.json source.note]`.

## 2. What Continuo sends (do not duplicate it)

`continuo_image_workflow_submit`, target `minimax-h3-image-create-v1` `[code]`

- Your prompt goes **byte for byte** into the conditioning node (a `PrimitiveStringMultiline` feeds
  `MiniMaxH3ImageConditioning.prompt`). There is **no prompt expander**: MiniMax's official PE model and the
  Context-IR API exist `[official]`, but neither is installed here `[code: manifest.json descriptor.capabilities.prompt_enhancer=false; workflow-api.json has no expander node]`.
  You must write the expanded form yourself (§3). The server accepts up to 16,384 characters
  `[code: catalog_create_workflow_adapter.py:99]`; that is a server limit, not a target length.
- Encoding `[local: comfy/text_encoders/minimax.py:187-246]`: raw tokens, no chat template. Prompt weights are
  switched off (`disable_weights=True`), so `(word:1.3)` reaches the model as literal characters. There is no
  negative prompt: the graph runs CFG 1.0 against a zeroed negative (`ConditioningZeroOut`)
  `[code: workflow-api.json nodes 6, 11]`.
- **No automatic prefix.** Unlike P-H3's node, `MiniMaxH3ImageConditioning` adds nothing to your text
  `[local: comfy_extras/nodes_minimax_h3.py:736-739]`. What you write is what the model reads.
- **References.** Up to **9** pictures `[code: h3_image_workflow_adapter.py:58]` (the card says up to 16
  `[official]`; the node itself takes 100 `[local: nodes_minimax_h3.py:729-730]`). They go into the conditioning's
  `images.image_N` in the order you send them and are named `<Picture 1>` … `<Picture 9>` in your prompt
  `[code: h3_image_workflow_adapter.py:151-156]`. Roles: `identity | outfit | location | style | composition |
  object | reference` `[code: manifest.json descriptor.media_roles]`. There is **no `target` role**: this is a
  create target, and the output size is the asked size — references never set it
  `[code: h3_image_workflow_adapter.py:177-179]`.
- **The server appends a role suffix** for every reference whose role is not the plain `reference`, joined with one
  space so it stays in your paragraph: your prompt + ` ` + `<Picture 2> is the identity reference.`
  `[code: h3_image_workflow_adapter.py:157-160]`. Do not write these lines yourself; make your own text carry the
  real job of each picture.
- Each picture reaches the encoder twice `[local: nodes_minimax_h3.py:692-709, 737-741]`: a vision copy with its
  short edge at 1024 px (about 1 MP), labelled `Picture N: ` before the vision block (the node's label has no angle
  brackets; in your prompt text write `<Picture N>` with them), and — because Continuo wires the VAE — a VAE
  reference latent (short edge 1024–2048 px) that anchors the picture for the transformer (`minimax_refs`).
- **The size hint.** With at least one reference and megapixels above 4, the submit answer carries the warning
  `reference_soft_above_4mp: with a reference picture, results turn soft above 4 MP`
  `[code: h3_image_workflow_adapter.py:181-194; image_workflow_run.py:239-242]`. Nothing is refused or lowered;
  the fact comes from the artist's renders of 13 Nov.
- Controls `[code: manifest.json descriptor.controls]`: `seed` (default 0), `aspect_ratio` (1:1, 2:3, 3:2, 3:4,
  4:3, 9:16, **16:9 default**, 21:9, 2.39:1 "Scope"; labels carry the name in brackets, e.g. `16:9 (Widescreen)`),
  `megapixels` 1–33 (**default 16**), `steps` 1–50 (default 6), `switch_at` (default 3), `sampler` (default
  `er_sde`), `lcm_noise` (default 0.95), `lcm_noise_end` (default 0.90), `second_pass_start` (default 4).
  `switch_at` and `second_pass_start` must be before the last step or the server refuses the control
  `[code: h3_image_workflow_adapter.py:116-123]`. The job returns the effective prompt (a `PreviewAny` echo), so
  read it back to check what the model got `[code: manifest.json outputs.effective_prompt, workflow-api.json node 90]`.

## 3. Grammar: the prompt form

The model expects **a detailed English description of the whole image** `[official, card "Full Workflow"]`. The
MiniMax API turns a short request in any language into such a description before generation (Context-IR), and the
released PE model does the same locally `[official]`. Continuo runs neither: a bare request ("a harbour at dawn")
is the expander's input, not the form the model was trained on. Whether a bare request degrades the picture on this
route is **untested** — write the full form anyway.

**Create form.** One fluent English paragraph describing the finished picture:
1. **Open by naming the picture.** The official expanded example opens "The image is an overhead, top-down
   photograph of a rustic farm-to-table feast …" `[official, examples/revised_prompt.t2i.txt]`. The artist's proven
   render prompts open "The target image is …", and the pinned graph's own placeholder reads "The target image is a
   quiet harbour at dawn." `[code: workflow-api.json node 4; manifest.json source.note]`. Use one of these openers
   and say what the picture is (photograph, film frame, painting, poster) in the first sentence.
2. **The subject and its materials**, caught in one state or action; counts as numbers.
3. **Placement in frame words** — "In the center … To the left … On the right side … Below … At the upper right"
   is the official example's structure `[official, examples/revised_prompt.t2i.txt]`. Layers near to far.
4. **Light with a source and a direction**, and what it hits; the official example ends on it: "The lighting is
   natural and warm, coming from the upper left and casting soft, long shadows to the lower right …"
   `[official, same file]`.
5. **Quoted text exactly**, placed on its surface; literal text keeps its own language while the description stays
   English `[official, PE card]`.

**Length.** The official expanded T2I example is **256 words / 1,504 characters**; the expanded edit example is
480 words `[official, examples/revised_prompt.t2i.txt, revised_prompt.edit.txt]`. Aim for that density. No measured
minimum or maximum exists in the sources; the API truncates at 4,096 tokens `[official, card request parameters]`,
and the local encoder refuses a segment beyond its supported length `[local: minimax.py:199-200]`. Very short and
very long prompts: **untested** on this route.

**Rules from the released expander prompts** (they describe what the trained form contains) `[official, PE
prompt/t2i/task_prompt.txt]`:
- Preserve every hard fact: exact text, named entities, counts, formulas, left/right/top/bottom order.
- Required content must be **visible, not implied**: if text or a label is requested, place it on the surface and
  say where it sits.
- Replace abstract mood and generic adjectives with specific visible cues; style comes after content.
- Keep the requested subject count; background crowds read as small silhouettes, not extra main subjects.
- For active bodies, state the camera-relative orientation (front-facing, left-facing profile, …) and a
  frame-absolute motion direction; keep one frozen phase of the action.

**Do not write:** weights or tag lists (weights are off `[local]`); P-H3's `Edit <Picture 1>.` instruct form, its
six-section brief or `[keyframe completion]` (wrong model); H3 video fields (`[Shot N]`, sound sections, camera
moves, alignment line); a negative prompt (none exists). Whether hype words like "cinematic" harm this model is
**untested** — the measured gloss effect belongs to P-H3's card, not this one; the expander's rule against generic
adjectives `[official, PE]` is the only sourced guidance.

**Worked examples** (written for this reference in the official form; they are not renders):

Create, location plate, 16:9 at 16 MP:
```
The target image is a wide documentary photograph of a small ferry deck at dusk, taken from deck height on a 35mm
lens. A deckhand in his fifties, in a yellow oilskin coat and black rubber boots, stands frame-left with knees bent,
both hands gripping a heavy wet rope that runs from a steel bollard toward the open railing on the right, his weight
leaning back as he starts to haul. Rust streaks run down the white railing; a coiled life ring hangs on it. Behind
him the pale grey sea meets low cloud. Cold overcast light from the left falls across his face and the wet oilskin;
one warm cabin window glows behind him. Fine spray hangs in the air. Palette of grey, rust, yellow and one warm
amber light, natural film colour, fine grain.
```

Create, prop close-up:
```
The target image is a close-up photograph on a 100mm macro lens of a brass ship's compass resting on a scarred oak
chart table. The glass is cracked across the north mark and the needle has settled on west. A pencil and a folded
paper chart lie beside it, the chart edge soft with damp. A single oil lamp just out of frame on the right throws
warm light low across the brass, catching every scratch and the engraved word "BALTIC" on the rim, no other text.
The table falls into brown shadow toward the top of the frame. Shallow depth of field, natural colour, fine grain.
```

## 4. With references: the edit/composition form

With reference pictures the trained form is the official **edit expansion**: one continuous paragraph, no line
breaks, three parts in this order `[official, PE prompt/edit/task_prompt.txt; examples/revised_prompt.edit.txt]`:

1. **Definitions.** Element-first sentences that bind each reused thing to its source picture:
   `The man on the left in a dark sweater and wristwatch in <Picture 1> is <Subject 1>.` Every definition names its
   `<Picture N>` and enough visible cues to identify the thing uniquely. Define only what stays visible,
   transfers a property, or is borrowed; brand-new content gets no `<Subject N>`.
2. **Overview + relationships.** One sentence beginning `The target image` that states the finished result using
   the defined subjects, then one relationship clause per subject:
   - `<Subject N> is fully preserved.` — its own short sentence, nothing appended, when the whole subject is
     unchanged.
   - `<Subject N> is partially preserved; <what stays>, while <what changes>.`
   - Transfer: `<Subject 1> supplies the exact color transferred to <Subject 2>.`
   - Weak reference: `<Subject 1> serves as a weak palette reference for the new composition.`
3. **The visual delta.** Describe only the changed and new content and how it integrates (shadows, contact,
   light). Never re-describe a fully preserved subject; a bare `<Subject N>` token may anchor a new object's
   position. Write changed or new text in full, exactly.

Write `<Picture N>` and `<Subject N>` directly, without backticks `[official, PE]`. This is **not** P-H3's
instruct form and **not** the six-section brief; no prefix is added by the node `[local: nodes_minimax_h3.py:736-739]`.
The server's role suffix (§2) lands at the end of the paragraph; let your definitions carry the real roles.

Worked example (Picture 1 = the ferry plate, role `reference`; Picture 2 = one clean portrait, role `identity`):
```
The ferry deck at dusk in <Picture 1> is <Subject 1>. The deckhand's face, short grey beard and weathered skin in
<Picture 2> are <Subject 2>. The target image shows <Subject 1> with a deckhand coiling wet rope at the starboard
railing, his face and beard from <Subject 2>. <Subject 1> is fully preserved. <Subject 2> is partially preserved;
the face, beard and skin remain, while the body is new, in a yellow oilskin coat and black rubber boots. The new
deckhand stands frame-right at the railing, about as tall as the cabin door behind him, both hands coiling the rope
over his forearm; cold overcast light from the left lights the side of his face, and his breath is visible in the
cold.
```

**How strongly references are followed.** The card claims strong instruction following and up to 16 references
`[official]`; the node anchors every picture as a vision block and a VAE reference latent (§2) `[local]`. Measured
identity hold, the best number of references, and whether an unnamed picture is ignored: **untested** through
Continuo. Start with 1–2 references and add more only once those hold (advice, untested). One clean view per
identity, never a character sheet (shared skill rule; untested on this model). The one measured fact: with a
reference, results turn soft above about 4 MP `[code: image_workflow_run.py:239-241, from the artist's renders]`.
At 16 MP with references, expect softness or render the plate without references and compose at a smaller size —
the trade-off itself is untested.

## 5. The recipe Continuo runs, and sizes

**One pass, up to 16 MP** `[code: workflow-api.json; manifest.json source.note; the artist's renders of 13 Nov 2026]`:
- 6 steps on the `simple` schedule, CFG 1.0 against a zeroed negative (the checkpoint is distilled to 6 steps with
  no CFG `[official]`).
- `SplitSigmas` after step 3 (`switch_at`): **steps 1–3 run `er_sde`** with the seed's noise (`RandomNoise` →
  `SamplerCustomAdvanced`); **steps 4–6 run `SamplerLCM`** with no new noise (`DisableNoise`), its noise multiplier
  falling from 0.95 to 0.90 (`s_noise` / `s_noise_end`, `noise_clip_std` 0).
- Width and height go straight into `MiniMaxH3ImageConditioning`; each side sits on the node's 32 px grid
  `[code: h3_image_workflow_adapter.py:59, 69-73; local: nodes_minimax_h3.py:31, 725-728]`.

**Second pass, above 16 MP up to 33 MP** `[code: h3_image_workflow_adapter.py:125-175; workflow-api.json nodes 41-44]`:
pass 1 makes the picture at 16 MP in the chosen format; then lanczos scale to the asked size → VAE encode →
`KSamplerAdvanced` **euler / simple**, the same total steps, starting at `second_pass_start` (default 4 of 6), the
same seed, on pass 1's conditioning. The conditioning does not depend on the size, so the 32B encoder runs once
`[local: nodes_minimax_h3.py:736-745]`. The second pass's euler sampler is pinned; the `sampler` control only
chooses pass 1's sampler `[code: workflow-api.json node 43; h3_image_workflow_adapter.py:171-174]`. Whether the
second pass keeps the composition through the Suite is **untested** (the artist's own 33 MP render used this pass
`[code: manifest.json source.note]`).

**Sizes.** The card's working range is about **4–20 MP, best around 16 MP** `[official]`. Card sizes at 16 MP:
1:1 4096x4096 · 4:3 4736x3552 · 3:2 5024x3360 · 16:9 5472x3072 · 21:9 6272x2688 (portrait swapped) `[official]`.
Continuo offers the same formats plus **2.39:1 (Scope)**, which is not on the card; the artist rendered it
`[code: manifest.json descriptor.controls; source.note]`. The adapter rounds each side to the 32 grid, so a size
can differ slightly from the card's table `[code: h3_image_workflow_adapter.py:69-73]`. Megapixels above 16 engage
the second pass; the control caps at 33 `[code: manifest.json descriptor.controls]`. Fix format and size before
hunting seeds (advice; whether composition shifts with size on this model is untested).

## 6. Parameters

| Knob | Official | Continuo | What it does |
|---|---|---|---|
| Steps | 6 (distilled; the API rejects other values) `[official]` | 1–50, default 6 `[code]` | Other counts are untested; keep 6. |
| CFG / negative | none (guidance-distilled; the API rejects a negative) `[official]` | CFG 1.0 pinned, zeroed negative `[code]` | — |
| Sampler | not named on the card | pass 1 free, default `er_sde`; pass 2 pinned euler `[code]` | The proven recipe is er_sde + LCM; others untested. |
| switch_at | — | default 3, must be < steps `[code]` | Where er_sde hands over to LCM. |
| LCM noise | — | 0.95 → 0.90 (`lcm_noise`, `lcm_noise_end`) `[code]` | The recipe's falling noise; other values untested. |
| second_pass_start | — | default 4, must be < steps `[code]` | Where the >16 MP refine pass starts. |
| Megapixels | about 4–20 MP working range, best about 16 `[official]` | 1–33, default 16 `[code]` | >16 runs two passes (§5). With references, soft above about 4 `[code]`. |
| Aspect | 7 card ratios `[official]` | + 2.39:1 (artist-rendered, not on the card) `[code]` | Output size is explicit; references never set it. |
| Seed | recommended `[official]` | default 0; feeds both passes `[code]` | Re-roll the seed for anatomy; re-word for content. |
| LoRA | — | none accepted `[code: image_workflow_run.py:68]` | H3 video LoRAs fit another transformer. |

## 7. What to avoid (failure modes)

| Symptom / risk | Cause | Fix |
|---|---|---|
| Prompt in the wrong model's syntax | P-H3's `Edit <Picture 1>.`, six-section brief, `[keyframe completion]`, H3 video fields | Use §3/§4 of this file; the forms are not transferable |
| Bare short request | the trained form is the expanded description `[official]`; local effect untested | Write the full paragraph (§3) |
| Literal `(word:1.3)` | weights are off `[local]` | Plain words |
| Soft results with a reference above 4 MP | measured on the artist's renders `[code: image_workflow_run.py:239-241]` | Render at ≤4 MP with references, or accept the warning; nothing is refused |
| Reference ignored or loosely copied | job not stated; too many references (untested) | Definitions with `<Subject N>` and a stated job; start with 1–2 |
| Preserved subject re-described in the delta part | breaks the official edit form `[official, PE]` | Fully preserved subjects get their one clause and no later description |
| `switch_at` / `second_pass_start` refused | value ≥ steps `[code: h3_image_workflow_adapter.py:116-123]` | Keep both before the last step |
| Garbled text | long, unquoted or unplaced strings (untested on this model) | Quote exactly, place it, check every seed; the card shows strong text but Continuo has no render on record |
| Glossy "AI look" from hype words | untested on this model | Follow the expander rule: specific visible cues instead of generic adjectives `[official, PE]` |

## 8. Sources (accessed 2026-11-19)

- `[official]` MiniMax-H3-Image model card, pinned rev 8ced6006 (the pin in `manifest.json source.path`) —
  https://huggingface.co/MiniMaxAI/MiniMax-H3-Image (Introduction, Sizes, Full Workflow, request parameters,
  Showcase, License: minimax-h3-image-community-license-agreement)
- `[official]` Official example files at the same rev: `examples/instruction.t2i.txt`,
  `examples/revised_prompt.t2i.txt` (256 words), `examples/instruction.edit.txt`,
  `examples/revised_prompt.edit.txt` (480 words)
- `[official]` MiniMax-H3-Image-PE card and released prompts (main rev):
  https://huggingface.co/MiniMaxAI/MiniMax-H3-Image-PE — `prompt/t2i/task_prompt.txt`,
  `prompt/edit/task_prompt.txt` (the three-part edit form, preservation clauses)
- `[local]` ComfyUI 0.45.0 `comfy_extras/nodes_minimax_h3.py` (`MiniMaxH3ImageConditioning` :711-746, `_image_refs`
  :692-709, constants :31-41), `comfy/text_encoders/minimax.py` (`MiniMaxH3Tokenizer.tokenize_with_weights`
  :187-246, weights disabled)
- `[code]` Continuo `h3_image_workflow_adapter.py`, `workflows/minimax-h3-image-create-v1/manifest.json` and
  `workflow-api.json`, `model_catalog.v1.json` (family `minimax_h3_image`), `image_workflow_run.py:68, 239-242`,
  `catalog_create_workflow_adapter.py:99`, `model_evidence.v1.json` (no entry yet). The recipe's provenance: the
  artist's renders of 13 Nov 2026, API graphs read from their PNG metadata (`manifest.json source.note`).
