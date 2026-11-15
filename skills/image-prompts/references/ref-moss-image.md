# MOSS-Image SFT — prompting reference for Continuo

Load this when the target is `moss-image-sft-create-v1`. Tags: `[official]` OpenMOSS repo, model card, user guide,
technical report (arXiv 2610.23374); `[maintainer]` ComfyUI source / Comfy docs / named node authors; `[code]` what Continuo
sends; `[community]` named and dated; `[hypothesis]` untested.

## 1. Scope

- Catalog family `moss_image`, variant `sft`, target `moss-image-sft-create-v1`, grammar `moss_prose` (name only: the
  model also reads tags and a JSON layout, see 3). Text to image only in Continuo: no references, no edit, no mask `[code]`.
- MOSS-Image is a 5B single-stream DiT pretrained from scratch by OpenMOSS / MOSI.AI, frozen Qwen3.5-9B text encoder,
  frozen FLUX.2 VAE [official report]. **SFT** = MOSS-Image-Base fine-tuned on curated data; same architecture and
  pipeline; "clearer text grouping and a more organized layout" [official model card]. It is not distilled: 50 steps with
  real CFG `[official]`.
- Continuo files: `moss_image_sft_bf16` (default) or `moss_image_sft_int8_convrot`, text encoder
  `qwen3.5_9b_int8_convrot`, VAE `flux2-vae` `[code]`. Apache-2.0 `[official]`.
- **Use it for:** long or dense in-image text (paragraphs, menus, boards, newspapers, UI and control panels), Chinese text,
  posters and title cards, many constraints in one long prompt (up to ~4K tokens), storyboards and illustration
  [official LLTB 96.3 % text coverage; community]. It also has a real negative prompt.
- **Weak at / not for:** deep-focus photographs (the SFT blurs backgrounds), large smooth skies and walls (vertical
  banding), clean character sheets of people (adds suggestive posing), editing or identity from a reference (no input).

## 2. What Continuo sends

- Positive: your prompt string unchanged into CLIPTextEncode; no length rule beyond the API's 16,384 characters, no JSON
  check, no enhancer, no rewrite [code catalog_create_workflow_adapter.py; workflow-api.json node 2/14].
- ComfyUI trims surrounding whitespace and wraps the text in `<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n<think>\n`
  [maintainer comfy/text_encoders/moss_image.py]. Do not add chat tokens yourself.
- Negative: control `negative` (textarea), default `nsfw, worst quality, bad anatomy, watermark, jpeg artifact`, encoded by
  the same text encoder `[code]`. Keep it unless the artist asks; extend it for the task (section 6).
- Sampling: KSampler, Euler / sgm_uniform, 50 steps, CFG 3, model shift 5 (ComfyUI's MOSS default), Skip Layer Guidance on
  the unconditional pass at single layer 22 for the whole run (fixed) `[code; maintainer supported_models.py]` = the official
  defaults [official card].
- Controls: `model` (bf16 / int8), `negative`, `seed`, `steps` 1-10000, `cfg` 0-100, `sampler` (all ComfyUI samplers),
  `scheduler`, `aspect_ratio` (1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9), `megapixels` 0.1-4 `[code]`. LoRAs load on the
  model node [code image_workflow_run.py:44].
- Output size = aspect + megapixels, each side rounded to 16 [maintainer ResolutionSelector]. You need it for a layout:

| MP | 1:1 | 3:2 / 2:3 | 4:3 / 3:4 | 16:9 / 9:16 | 21:9 |
|---|---|---|---|---|---|
| 1.0 | 1024x1024 | 1248x832 | 1184x880 | 1360x768 | 1568x672 |
| 1.5 | 1248x1248 | 1536x1024 | 1456x1088 | 1680x944 | 1920x816 |
| 2.0 | 1456x1456 | 1776x1184 | 1680x1248 | 1936x1088 | 2208x944 |

## 3. Grammar

MOSS was trained on three forms through the same text interface [official report §3.2, App. C.3]:
1. **Captions** written by a VLM at three granularities — one sentence, one paragraph, or a long description of composition,
   subjects, scene attributes and every visible text — sampled 1:1:1, plus 20 % original web captions. Visible text is
   transcribed verbatim **with its line breaks**.
2. **Tag sequences** (documented for Base): order quality -> score -> meta -> year -> character -> series -> artist ->
   general, e.g. `best quality, highres, 1girl, blue hair` [official user guide].
3. **Layout JSON** (`summary` + `items`, boxes in pixels from the centre) for a subset of high-quality data `[official]`.

Write prose by default. Rules:
- **Describe the finished picture, not a request.** "A risograph poster of ..." not "make a poster" [official prompt
  enhancer skill; maintainer Comfy docs].
- **Write it out.** Detailed prompts scored 1509 Elo, directly expanded 1541, short requests 1082 in the authors' arena
  [official report §5.4.1]. Short prompts vary much more by seed [community, developer comment on Reddit ~2026-10-20, via
  study] and break text-heavy layouts [community HF discussion 16, 131 images, 2026-10-28]. Aim for 80-250 words for a
  scene, more for designed pieces. Up to 4,096 tokens were seen in training `[official]`.
- Order: what the picture is (medium, genre, framing) -> main subject and action -> other subjects with positions in words
  ("in the lower left", "behind her") -> setting -> light (source, direction) -> palette and texture -> every visible text
  with where it sits and how it looks.
- **Visible text:** quote it exactly (`"PIER 7"`), say where and how it is set, and put a real line break (or `\n`) where a
  line must break — line-broken prompts settle each line's characters earlier in denoising [official report §6, user
  guide; community Civitai staff 2026-10-17]. Quote every required string; an unquoted descriptive phrase can be printed or
  dropped. To remove a text, delete its description too [community HF discussion 16].
- **Language:** English prose (most training data); text to render may be in any language, Chinese renders well `[official]`.
- No quality tag lists in prose captions (the enhancer skill forbids "redundant quality tags"); quality words belong in the
  negative [official skill + user guide]. No `(word:1.3)` weights `[hypothesis: not in any training format]`.
- Say what you do not want in the **negative**, not in the positive. Unlike most models here, MOSS's training captions
  name defects (watermarks, blurry faces, compression artifacts are annotated, not filtered) — that is why naming them in
  the negative works [official report §3.1 "annotate rather than filter"; community "it needs negatives like old SDXL"].

### Layout JSON (when placement matters)
Use for title cards, posters, panels and exact text placement — not for ordinary scenes [official skill]. The prompt is one
line of JSON; Continuo passes it through unchanged `[code]`, but this path is untested in Continuo.
```
{"summary":{"meta":["poster"],"canvas":"single","caption":"<whole picture, style, light>"},
 "items":[{"label":"text","caption":"<how it looks>","text":"EXACT\nTEXT","bbox":[y0,x0,y1,x1]},
          {"label":"object"|"character","caption":"<appearance>","bbox":[y0,x0,y1,x1]}],
 "bbox_coord_space":"abs_centralized","bbox_format":"yxyx"}
```
- Boxes are **integer pixels, origin at the canvas centre, y first**: `[top-H/2, left-W/2, bottom-H/2, right-W/2]` using
  the exact W x H from the table above [official user guide]. Floor top/left, ceil bottom/right [official compile_prompt.py].
  Not 0-1000 like Ideogram: the authors found centred pixel boxes generalise better across sizes [official report §6].
- `label`: `text`, `object`, `character`. Optional `tags`, `palette` (hex list). No other fields. `canvas`: `single`,
  `multi_panel` or `collage` [official layout.md].
- A box is placement, not a frame: it does not draw a border. Boxes may overlap. Draw background first, foreground last
  `[official; maintainer Comfy docs]`.
- Prose and layout can be combined; the `summary.caption` is the scene prose `[official]`.
- Many boxes with near-identical captions confuse which content goes where [community 2026-10-16, 2026-10-20]; give each a
  distinct caption.

## 4. Operation: create

Only create exists in Continuo. Edit and colour/depth control exist for MOSS in ComfyUI as LoRAs (`TextEncodeMOSSImageEdit`,
`MOSSImageControl`) but are not wired into any Continuo target [maintainer nodes_moss_image.py; code]. Do not promise them.

## 5. Parameters

| Knob | Official | Continuo / house | Effect and community notes |
|---|---|---|---|
| steps | ≥50 best (user guide), 50 default | 50 | 25 often fine for drafts [community 2026-10-16]; 100 adds detail at 4K [community 2026-10-18] |
| cfg | 3; 3-6, raise for short prompts (Base) | 3 | high CFG drifts toward cartoon/anime and colour shifts `[community, Banodoco 2026-10-23/27]`; raise to 4-5 for short prompts or >2 MP |
| sampler / scheduler | Euler / sgm_uniform (shift 5) | same | community likes `er_sde` 25 steps [community 2026-10-18]; keep Euler for repeatable results |
| SLG layer 22 (uncond) | on | on, fixed | off = more realistic but details can collapse `[official]` |
| size | 1-2 MP recommended, 0.25-4 MP | 1 MP default; catalog 512-2048 px | adherence drops above ~2 MP [community 2026-10-18/27] |
| model file | — | bf16 default | int8: composition and text survive, fine detail differs (3 prompts) `[community, HF quantization card, 3 prompts]` |
| negative | `nsfw, worst quality, bad anatomy, watermark, jpeg artifact` (guide); card: empty | guide's tags prefilled | see 6 |

## 6. Film tasks

Negative baseline (N0) = the default. Add per task; keep it short [maintainer Comfy docs].

**T1 keyframe / frame 0** — readable onset, room for the move, deep focus asked for but expect a softer background.
```
A 35mm film still, medium-wide shot at eye level, of a young ferry deckhand on the open stern deck of a small car ferry at
dusk. She stands in the left third of the frame, mid-twenties, light brown skin, dark hair tied back under a black knit
cap, orange waterproof rain jacket, dark work trousers and black rubber boots. She is bent forward, both hands already
pulling a wet blue mooring rope into a coil at her feet, eyes on the rope. The deck is wet grey steel with painted yellow
safety lines and a white railing running along the right side of the frame toward the bow. Beyond the railing, grey choppy
water and a low harbour quay with a few amber sodium lamps. Overcast dusk sky, soft cool light from frame right, small
warm highlights on the wet deck. Muted naturalistic colour, fine film grain, the quay still readable in the distance.
```
Negative: N0 + `, heavy blur, bokeh, text, logo`.

**T3 establishing plate** — no people unless asked; put "empty" in prose and `people` in the negative.
```
A wide establishing photograph of a roadside desert motel at blue hour, seen from across an empty two-lane highway. A
single-storey row of beige stucco rooms with turquoise doors runs from the centre to the right edge; the office sits at
the left end under a tall steel sign frame. Gravel parking lot, two parked pickup trucks, a vending machine glowing by
the office door. Flat desert scrub and dark low hills behind, the sky fading from deep blue to a thin orange line on the
horizon. Cool ambient light, warm practical lights in the office window. Deep focus, every door and window sharp.
```
Negative: N0 + `, people, heavy blur, bokeh`.

**T4 insert with printed matter** (quote and break every line):
```
A macro photograph of a creased cream paper ferry ticket held between a thumb and index finger above a weathered wooden
bench. A red stripe runs along the ticket's top edge. Printed in bold black condensed sans-serif across the top: "HARBOUR
LINE". Below it in smaller black monospace print, on two lines:
"PIER 7 → ISLAND
23:40"
Soft overcast daylight from the upper left, shallow depth of field, the bench out of focus.
```

**T5 title card, prose** (16:9 at 1 MP):
```
A film title card. A dim, grainy dawn photograph of an empty tidal flat fills the frame: wet sand reflecting a pale grey
sky, a thin line of sea along the lower third. Centred just above the middle, the title "LOW TIDE" in large cream
hand-painted serif capitals with wide letter spacing. Directly beneath it, smaller, in a light cream sans-serif:
"a film by the harbour collective". Generous empty space, restrained and elegant.
```
**T5 title card, layout JSON** (16:9 at 1 MP = 1360x768; compiled with the official `compile_prompt.py`):
`{"summary":{"meta":["film title card","photograph with typography"],"canvas":"single","caption":"A film title card: a dim, grainy dawn photograph of an empty tidal flat with wet sand reflecting a pale grey sky, overlaid with the title LOW TIDE in large cream serif capitals and a small credit line beneath, generous empty space, restrained and elegant."},"items":[{"label":"text","caption":"Large cream hand-painted serif capitals, widely letter-spaced, centred.","text":"LOW TIDE","bbox":[-124,-440,56,440]},{"label":"text","caption":"Small lowercase cream sans-serif credit line, light weight, centred.","text":"a film by the harbour collective","bbox":[86,-240,126,240]}],"bbox_coord_space":"abs_centralized","bbox_format":"yxyx"}`

**T9 poster / key art** (2:3 at 1.5 MP = 1024x1536, layout JSON, compiled with `compile_prompt.py`):
`{"summary":{"meta":["movie poster","key art"],"canvas":"single","caption":"A vertical theatrical poster: a small passenger ferry with warm amber cabin windows on black still water under a very large pale moon, one silhouetted figure in a long coat at the stern rail, a tagline at the top, the title NIGHT FERRY in large cream condensed serif letters near the bottom and a small amber release line beneath it. Moody, high contrast, fine grain."},"items":[{"label":"text","caption":"Small widely spaced cream sans-serif tagline.","text":"SOME CROSSINGS DON'T END","bbox":[-708,-362,-618,362]},{"label":"object","caption":"A small passenger ferry seen side-on, a row of warm amber cabin windows reflected in the black water.","bbox":[-188,-392,292,408]},{"label":"character","caption":"A lone silhouetted figure in a long coat standing at the stern rail, facing the moon.","bbox":[-128,58,92,148]},{"label":"text","caption":"Large bold cream condensed serif title.","text":"NIGHT FERRY","bbox":[362,-412,552,412]},{"label":"text","caption":"Small amber uppercase sans-serif release line.","text":"IN CINEMAS THIS WINTER","bbox":[582,-292,652,292]}],"bbox_coord_space":"abs_centralized","bbox_format":"yxyx"}`

**T10 dense in-world text** (MOSS's strongest case: a menu board, newspaper, departures board, UI panel):
```
A photograph of a hand-painted chalkboard menu on the wall of a small harbour fish stall, seen straight on. Black
chalkboard in a worn wooden frame, white and yellow chalk lettering. At the top in large yellow brush capitals:
"CATCH OF THE DAY". Below, in white handwritten chalk, one dish per line with its price aligned to the right:
"Grilled sardines ........ 7.50
Mussels in cider ........ 9.00
Fish soup with bread .... 6.50
Smoked mackerel roll .... 5.00"
At the bottom in small white capitals: "CASH ONLY · CLOSED MONDAYS". A small chalk drawing of a fish in the lower right
corner. Soft daylight from the open stall front, faint chalk dust smudges on the board.
```
Negative: N0 + `, misspelled text, extra text`.

**T8 storyboard frame:** "A rough film storyboard panel drawn in graphite pencil with grey marker shading on white paper,
inside a thin black frame..." then the staging, an arrow for movement, and a quoted panel label `"SC 12 / SH 3"`.
Negative: N0 + `, colour, photograph`.

**T2 one character across shots:** no reference input. Write one fixed character paragraph (age, skin tone, hair, each
garment with colour, one distinctive prop) and paste it verbatim into every prompt; vary only shot, action and setting.
Expect drift in face `[hypothesis]`. Use a model with references for identity.
**T6 / T7:** not possible on this target.

## 7. Failure -> cause -> fix

| Symptom | Cause | Fix |
|---|---|---|
| Background soft despite "f/16, sharp" | SFT trait in blocks 21-41, decided in the first ~12 steps; prompt words barely help [community GitHub issue #35, measured 2026-11-08; HF discussions 9/12] | add `heavy blur, bokeh` to the negative [community 2026-10-17]; accept it or use another model for deep-focus plates |
| Faint vertical colour stripes in skies, fog, walls | SFT banding, strong at 768-1024 px wide, wavy at 1536+; 1280 px wide was clean in one sweep `[community, HF DeBand LoRA card]` | avoid big empty gradients; add texture (clouds, grain); test 1280 px width (untested); a DeBand LoRA if installed |
| Picture changes a lot between seeds | prompt too short | write 80-250 words; raise CFG to 4-5 for a short one |
| Wrong or merged lines of text | no explicit breaks; long unbroken text | real line breaks; quote each string; layout box per block |
| Unasked text appears | the prompt described signage without quotes, or expansion invented copy | quote only what must appear; add `text, logo, watermark` to the negative when no text is wanted |
| Suggestive poses / revealing clothes on people | unfiltered training data | keep `nsfw` in the negative; describe clothing and pose concretely [community 2026-10-21, 2026-11-05] |
| Cartoon look, odd colours | CFG too high | back to 3-4; add `cartoon, anime` to the negative for photos |
| Detail falls apart at 3-4 MP | beyond the 1-2 MP sweet spot | 1.5-2 MP; upscale elsewhere |
| Layout boxes ignored / content swapped | boxes for a different canvas size; near-identical captions | recompute boxes for the exact W x H; distinct captions |

## 8. MOSS-Image or Ideogram 4?

MOSS for: paragraphs and long lists of text, Chinese, dozens of labels, long multi-constraint prompts, negative control,
commercial use (Apache-2.0), no blocked-card risk. Ideogram for: strict palette control, poster/title polish with a few
text blocks, 0-1000 boxes without size arithmetic. In the MOSS authors' benchmark, Ideogram 4 refused 61 of 160
short-English-text prompts [official report, third-party for Ideogram].

## 9. Sources (accessed 2026-11-12)

`[official]` github.com/OpenMOSS/MOSS-Image: README.md, USERGUIDE.md, skills/moss-image-prompt-enhancer/SKILL.md,
references/layout.md, scripts/compile_prompt.py, comfyui/moss-image/example_workflows/moss-image-api.json ·
huggingface.co/OpenMOSS-Team/MOSS-Image-SFT · arxiv.org/abs/2610.23374 (HTML v1: §3.1-3.3, §5.4.1, §6, App. C.3, G.1).
`[maintainer]` ComfyUI comfy/text_encoders/moss_image.py, comfy/supported_models.py (MOSSImage shift 5),
comfy_extras/nodes_moss_image.py, nodes_slg.py, nodes_resolution.py (commit 2f89433) · docs.comfy.org/tutorials/image/moss-image/moss-image
· KJNodes author on Banodoco #moss-image 2026-10-16/17.
`[community]` github.com/OpenMOSS/MOSS-Image issues #12, #31, #33, #35 · HF MOSS-Image-SFT discussions 9, 16 ·
huggingface.co/MATLOWAI/MOSS-Image-SFT-DeBand · huggingface.co/nif0/MOSS-Image-SFT-ComfyUI · civitai.com/articles/36843 ·
Banodoco #moss-image 2026-10-16..11-10.
`[code]` Continuo 9f7510c0: workflows/moss-image-sft-create-v1/*, model_catalog.v1.json, catalog_create_workflow_adapter.py.
