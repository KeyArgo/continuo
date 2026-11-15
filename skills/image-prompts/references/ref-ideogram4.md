# Ideogram 4 (JSON caption) — prompting reference for Continuo

Load this when the target is `ideogram4-create-v1`. Every claim is tagged: `[official]` Ideogram repo/docs/blog,
`[maintainer]` ComfyUI or KJNodes source/maintainer, `[code]` what Continuo sends, `[community]` named and dated reports,
`[hypothesis]` not yet tested.

## 1. Scope

- Catalog family `ideogram4`, variant `create`, target `ideogram4-create-v1`, grammar `ideogram_json`. Text to image only:
  no edit, no references, no mask, no image-to-image, no prompt enhancer `[code]`.
- Ideogram 4 is a 9.3B single-stream DiT trained from scratch, Qwen3-VL-8B text encoder (13 hidden layers concatenated),
  FLUX VAE, flow matching with asymmetric CFG `[official]`. Continuo runs the INT8 ConvRot build of both the conditional and
  the separate unconditional model, `qwen3vl_8b_fp8_scaled` text encoder, `flux2-vae` `[code]`.
- **Use it for:** title cards, posters/key art, signage and printed props inside a scene, lower thirds, any frame where
  several text blocks, exact placement and an exact palette matter (T5, T9, T4, T3 with signage, T8) [official: best open
  model on 7Bench layout and X-Omni text; ContraLabs typography win].
- **Do not use it for:** editing or repairing a picture (T6), identity from a reference (T2), style transfer from an image
  (T7). It cannot see pictures. For dense, long or Chinese text prefer MOSS-Image (see 9).
- **Licence:** the weights are under the Ideogram 4 Non-Commercial licence `[official]`. Tell the artist before using a
  result in commercial work.

## 2. What Continuo sends (do not duplicate it)

- Your `prompt` string goes unchanged into the text encoder (node 2 -> CLIPTextEncode). The server only checks that it
  parses as a non-empty JSON object; prose is refused with `prompt must be a JSON object` [code
  catalog_create_workflow_adapter.py:97-103]. It does **not** run Ideogram's CaptionVerifier, reorder keys, minify, or
  expand a short idea. There is no magic prompt `[code]`. Key order, key names and serialization are your job.
- ComfyUI wraps the text in the Qwen chat template `<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n` — the same
  template the reference pipeline uses [maintainer comfy/text_encoders/ideogram4.py; official pipeline_ideogram4.py].
- There is **no negative prompt**. The unconditional branch is a second model fed zeroed text features
  (ConditioningZeroOut) [code workflow-api.json nodes 11, 15, 17]. Never write "no X" anywhere: describe what is there.
- Guidance: DualModelGuider CFG 7 (control `cfg`), and a fixed CFGOverride of 3 for the last 30 % of the schedule. With the
  Ideogram4Scheduler sigmas that is 3 low-CFG steps at 20 steps and 7 at 48 steps; Ideogram's own presets use 2 and 3
  [code + computed from comfy_extras/nodes_ideogram4.py; official sampler_configs.py]. You cannot change the override.
- Controls you can set: `seed`; `steps` 1-200 (default 20); `cfg` 0-100 (default 7); `mu` -10..10 (default 0); `std`
  0.1-5 (default 1.75); `aspect_ratio` 1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9; `megapixels` 0.1-4 (default 1; lowered at submit when the format would pass 2048 px per side) `[code]`.
  Size = ResolutionSelector, multiple of 16. LoRAs go onto both models at the same strength [code image_workflow_run.py:52-62].
- When an artist's plain words become a caption, send the words as `title` too; Jobs and Media show the title [code
  workflow_1.py:33-35]. The Image page's own builder (plain words -> photo caption with one boxed element) is a UI fallback
  for terse words, not a model to imitate: write the full caption yourself.

## 3. Grammar: the caption the model was trained on

Ideogram 4 was trained exclusively on JSON captions. Plain text "will not work and will likely trigger a safety warning"
[official docs/prompting.md]. The schema and order below are exactly what Ideogram's CaptionVerifier checks [official
caption_verifier.py].

```
{"high_level_description": str,                       # strongly recommended; hosted docs: required
 "style_description": {                              # optional; if present needs aesthetics, lighting, medium
   PHOTO:     "aesthetics","lighting","photo","medium","color_palette"
   NON-PHOTO: "aesthetics","lighting","medium","art_style","color_palette"},
 "compositional_deconstruction": {                    # required
   "background": str,                                 # required, before elements
   "elements": [                                      # required (may be empty, but do not leave it empty)
     {"type":"obj","bbox":[y0,x0,y1,x1],"desc":str,"color_palette":[...]},
     {"type":"text","bbox":[y0,x0,y1,x1],"text":str,"desc":str,"color_palette":[...]}]}}
```

Rules, all `[official]` unless marked:
- Top-level keys in this order, no other keys. `photo` XOR `art_style`, never both, never neither. `color_palette` is the
  only optional style key and must come last. `bbox` and `color_palette` are optional inside an element but keep their slot.
- `bbox` = `[y_min, x_min, y_max, x_max]`, integers 0-1000, origin top-left, **y first**. Both axes are normalised to
  the frame, so `[0,0,500,500]` is a wide rectangle on 16:9. For a round or square object make `(x1-x0)/(y1-y0) = H/W`
  (16:9: x-span about 0.56 x the y-span; 2:3: 1.5 x). Ideogram's magic prompt writes this ratio as W/H, which is inverted;
  trust the arithmetic. Most box failures (duplicates, mis-scaled subjects) come from this [official magic prompt v1;
  arithmetic]. Swapped axes rotate the layout (a 16:9 request rendered as a rotated
  portrait) [community GitHub issue #21, 2026-06-07].
- Palettes: up to 16 colours in style, up to 5 per element, uppercase `#RRGGBB` only (the hosted docs accept lowercase; the
  open verifier does not, so use uppercase). Put the background colour and both highlight and shadow colours in the palette.
- `text` holds the exact characters; `desc` says how they look. Use `\n` inside `text` for line breaks in one block, a
  separate element for each visually separate block. Stack a long hero title over 2-3 lines with `\n`: long one-line
  stylised titles drop letters [official magic prompt v1].
- Serialize compact: `json.dumps(caption, separators=(",",":"), ensure_ascii=False)` — no indentation, literal non-ASCII
  (no `\uXXXX`) `[official]`. "Only the compact json is what's exactly what the model was trained on" [maintainer, KJNodes author,
  Banodoco #ideogram 2026-06-14]. Pretty JSON changes the picture for the same seed `[community, Banodoco 2026-06-10]`.
- Nothing before or after the braces: stray words bring the blocked card back `[community, Reddit 2026-06-05, via study]`.
- Limit: 2048 text tokens in the reference pipeline `[official]`. Hosted docs: long captions can lose their last elements,
  so list the most important elements first [official docs.ideogram.ai].

### How Ideogram's own caption writer fills the fields (copy this style) [official magic prompt v1]
- `high_level_description`: one long sentence (two at most), at most 50 words, starts with the subject, names the medium
  and overall composition; no "this image shows". Continuo house rule: at least 20 words — terse fragments here rendered
  the blocked text painted over a real scene [code caption-json.js, live test 2026-11-09].
- One coherent subject = one `obj` element; parts (limbs, wheels, roof) go in its `desc`. Several subjects = several elements.
- `desc`: 30-60 words, identity first ("Woman walking on the platform, ..."), then major attributes: people get skin tone,
  hair colour and style, each garment with colour, expression, pose, held prop; objects get shape, material, colour,
  distinctive parts. Anchor placement to named things ("on the lower-right corner of the table in front of the laptop").
- Not in `desc`: shadows, lens/focus/bokeh/grain language (viewpoint words are allowed once), impression words (luminous,
  vibrant, stunning, gorgeous), lighting repeated per element.
- `background` is the empty shell: walls, floor/ground and its state (wet, puddles, reflections), sky, weather, distant
  crowd or skyline, scene-wide light. The ground is never an element (it buries the subject's feet). Furniture, people,
  vehicles, signs are elements, not background. A sign or board built into a wall: mention it in `background` AND emit it
  first in `elements` as "the primary background element".
- Commit: no "or", "such as", "various", "implied", "maybe". Typography: one category (serif / sans-serif / script /
  display / monospace), one weight, one style.
- Photographs: avoid "warm" as a grading word (it gives the amber AI look); name warm sources concretely ("sodium
  streetlamp", "candle"). Prefer off-centre framing unless asked. No motion blur in candid shots.
- Transparent background: the model only paints a fake checkerboard (FLUX VAE has no alpha) [community issue #35,
  2026-06/08]. Ask for a flat solid background and key it out later.

## 4. The blocked card ("Image blocked by safety filter")

The model itself paints a grey card with that text; ComfyUI cannot switch it off [official prompting.md; maintainer Comfy
blog]. Off-distribution captions collapse to it [maintainer, KJNodes author, 2026-06-03/04: "the model just collapses to that output
too easily"]. Continuo reports such a run as a finished job: look at the picture.
Raise your odds, in order of evidence:
1. Valid compact JSON, nothing outside the braces, schema order exact `[official; community]`.
2. A full `high_level_description` sentence (20-50 words) [code live test; official].
3. Boxed `obj` elements for the main subjects. The docs' own sunset example without `bbox` was "always" blocked and
   rendered once a box was added [community issue #13, 2026-06-05]; "more than 3 boxes dramatically reduces" blocks
   [community Banodoco 2026-06-15]; a single full-frame box still triggered it [community 2026-06-07].
   Conflict: Ideogram's own magic prompt strips boxes and its captions render [official magic_prompt.py; community
   2026-06-15]. Those captions are long and rich. Thin caption + no box is what fails.
4. Sparse, large text is the riskiest content: 61 of 160 short-English-text prompts came back blocked at CFG 4, none of
   the long-text ones [third-party, MOSS-Image technical report App. G.1]. A title card therefore needs a described
   background and at least one `obj` element besides the text.
5. Rare reports that `style_description` raised block rates [community issue #14, 2026-07-23, single]. Keep it: Continuo's
   live tests and the official examples render with it.
6. If blocked: change the seed first, then enrich the caption. It is seed-dependent [community issue #14 sweep].

## 5. Operation: create (the only one)

Write in this order: decide the frame (aspect + megapixels) -> place boxes for that frame -> background shell -> elements
by importance -> style block -> palette -> one-sentence summary -> serialize compact -> verify (below).
Self-check before submit: parses; key order; `photo` xor `art_style`; every bbox 4 ints, 0-1000, y0<y1, x0<x1; palettes
uppercase, ≤16/≤5; every quoted word of the artist appears verbatim in a `text` field; no `\uXXXX`; under ~1,500 words.

## 6. Film tasks

Pretty-printed once for reading; send every caption compact. The examples below pass Ideogram's CaptionVerifier.

**T5 title card** (16:9). A described photographic or painted background and one `obj` make it safer than text on black.
```json
{
 "high_level_description": "A film title card with the title LOW TIDE in large hand-painted serif capitals over a dark, grainy photograph of an empty tidal flat at dawn, with a small credit line beneath.",
 "style_description": {
  "aesthetics": "restrained, elegant, cinematic title design, generous negative space",
  "lighting": "flat pre-dawn light, low contrast",
  "medium": "graphic_design",
  "art_style": "film title card, photographic background with typography, subtle film grain",
  "color_palette": [
   "#1C2328",
   "#3A4750",
   "#8A949A",
   "#E9E2D0",
   "#C8A15A"
  ]
 },
 "compositional_deconstruction": {
  "background": "A dim photograph of a flat tidal beach at dawn: wet sand reflecting a pale grey sky, a thin line of sea at the horizon across the lower third, empty and still.",
  "elements": [
   {
    "type": "text",
    "bbox": [
     360,
     180,
     560,
     820
    ],
    "text": "LOW TIDE",
    "desc": "Large cream hand-painted serif capitals, widely letter-spaced, centred horizontally just above the middle of the frame.",
    "color_palette": [
     "#E9E2D0"
    ]
   },
   {
    "type": "text",
    "bbox": [
     600,
     330,
     650,
     670
    ],
    "text": "a film by the harbour collective",
    "desc": "Small lowercase cream sans-serif credit line, centred below the title, light weight.",
    "color_palette": [
     "#E9E2D0"
    ]
   },
   {
    "type": "obj",
    "bbox": [
     700,
     0,
     760,
     1000
    ],
    "desc": "Thin horizontal band of distant grey sea along the horizon line."
   }
  ]
 }
}
```
Compact form to send:
`{"high_level_description":"A film title card with the title LOW TIDE in large hand-painted serif capitals over a dark, grainy photograph of an empty tidal flat at dawn, with a small credit line beneath.","style_description":{"aesthetics":"restrained, elegant, cinematic title design, generous negative space","lighting":"flat pre-dawn light, low contrast","medium":"graphic_design","art_style":"film title card, photographic background with typography, subtle film grain","color_palette":["#1C2328","#3A4750","#8A949A","#E9E2D0","#C8A15A"]},"compositional_deconstruction":{"background":"A dim photograph of a flat tidal beach at dawn: wet sand reflecting a pale grey sky, a thin line of sea at the horizon across the lower third, empty and still.","elements":[{"type":"text","bbox":[360,180,560,820],"text":"LOW TIDE","desc":"Large cream hand-painted serif capitals, widely letter-spaced, centred horizontally just above the middle of the frame.","color_palette":["#E9E2D0"]},{"type":"text","bbox":[600,330,650,670],"text":"a film by the harbour collective","desc":"Small lowercase cream sans-serif credit line, centred below the title, light weight.","color_palette":["#E9E2D0"]},{"type":"obj","bbox":[700,0,760,1000],"desc":"Thin horizontal band of distant grey sea along the horizon line."}]}}`

**T5 signage in a scene** (photo; neon as a `text` element whose box sits where the sign hangs; room number nested in the door box):
`{"high_level_description":"A night exterior of a roadside desert motel with a glowing red neon sign reading VACANCY above the office door and a lit room-number plaque on the nearest door.","style_description":{"aesthetics":"lonely, cinematic, quiet Americana","lighting":"red neon as the key light on the office wall, cool blue moonlight fill, a single warm porch bulb","photo":"35mm lens, eye level, deep focus","medium":"photograph","color_palette":["#0F1626","#2B3A55","#D8343A","#F2C46D","#5E4B3C"]},"compositional_deconstruction":{"background":"A gravel parking lot in front of a single-storey stucco motel, flat desert scrub and dark low hills under a clear starry night sky.","elements":[{"type":"obj","bbox":[330,80,820,640],"desc":"Single-storey motel office building with beige stucco walls, a glass door with blinds, and a small porch light."},{"type":"text","bbox":[180,170,320,540],"text":"VACANCY","desc":"Red neon tube letters in a bold script sign mounted on a steel frame above the office roof, glowing with a soft halo.","color_palette":["#D8343A"]},{"type":"obj","bbox":[420,640,820,900],"desc":"Turquoise motel room door with a brass handle, part of the row of rooms running toward the right edge."},{"type":"text","bbox":[480,740,530,790],"text":"7","desc":"Small brass room number on the turquoise door at eye level.","color_palette":["#C8A15A"]}]}}`

**T5 lower third** (16:9; the bar is an `obj`, name and role separate `text` blocks inside it):
`{"high_level_description":"A documentary lower-third graphic over a soft-focus market photograph, with a speaker name and role in a clean bar at the lower left of a 16:9 frame.","style_description":{"aesthetics":"clean broadcast design, understated","lighting":"even, soft daylight in the photograph","medium":"graphic_design","art_style":"broadcast lower third, flat semi-transparent bar, sans-serif typography","color_palette":["#101418","#F4F1EA","#E0A33A","#55606A"]},"compositional_deconstruction":{"background":"A softly blurred daytime photograph of a busy night-market street setting up stalls, warm awnings and steel carts out of focus.","elements":[{"type":"obj","bbox":[760,60,900,520],"desc":"A flat near-black bar with slight transparency and a thin amber accent line on its left edge, anchored at the lower left."},{"type":"text","bbox":[775,100,840,500],"text":"MARA OKAFOR","desc":"Off-white bold sans-serif capitals, the speaker name, on the upper line inside the bar.","color_palette":["#F4F1EA"]},{"type":"text","bbox":[845,100,885,500],"text":"Stallholder, Riverside Night Market","desc":"Smaller amber regular sans-serif role line under the name, inside the bar.","color_palette":["#E0A33A"]}]}}`

**T9 poster / key art** (2:3, 1.5-2.2 MP; billing hierarchy = tagline, image, title, release line):
`{"high_level_description":"A vertical theatrical key-art poster for a film called NIGHT FERRY, a lone figure at the rail of a lit ferry on black water under a huge moon, title at the bottom and a tagline at the top.","style_description":{"aesthetics":"moody, minimal, graphic key art, strong silhouette","lighting":"large pale moon as backlight, warm cabin windows as practical light","medium":"graphic_design","art_style":"photographic movie poster, high contrast, fine grain, classic billing-block layout","color_palette":["#05080D","#14202E","#E8E2D2","#E39A3B","#6E7B88"]},"compositional_deconstruction":{"background":"Black still water and a deep blue-black night sky with a very large pale moon low over the horizon.","elements":[{"type":"text","bbox":[40,150,110,850],"text":"SOME CROSSINGS DON'T END","desc":"Small widely spaced cream sans-serif tagline across the top.","color_palette":["#E8E2D2"]},{"type":"obj","bbox":[380,120,700,900],"desc":"A small passenger ferry seen side-on, its row of warm amber cabin windows reflected in the black water."},{"type":"obj","bbox":[420,560,560,640],"desc":"A lone silhouetted figure in a long coat standing at the ferry's stern rail, facing the moon."},{"type":"text","bbox":[740,100,860,900],"text":"NIGHT FERRY","desc":"Large bold cream condensed serif title across the lower part of the poster.","color_palette":["#E8E2D2"]},{"type":"text","bbox":[880,150,950,850],"text":"IN CINEMAS THIS WINTER","desc":"Small amber uppercase sans-serif release line under the title.","color_palette":["#E39A3B"]}]}}`

**T4 insert with printed matter** (macro; `\n` for the two print lines):
`{"high_level_description":"A close-up insert of a weathered paper ferry ticket held between two fingers, the printed route and time clearly readable against a blurred wooden deck bench.","style_description":{"aesthetics":"tactile, intimate, realistic detail","lighting":"soft overcast daylight from above left","photo":"macro 100mm lens, close-up, shallow depth of field","medium":"photograph","color_palette":["#E8DFC8","#2B2B2B","#8C2F2B","#6E5A44"]},"compositional_deconstruction":{"background":"An out-of-focus weathered wooden bench and grey deck boards.","elements":[{"type":"obj","bbox":[200,150,820,850],"desc":"A creased cream paper ticket with a red stripe along its top edge, held at the left by a thumb and index finger with short unpolished nails."},{"type":"text","bbox":[300,250,420,750],"text":"HARBOUR LINE","desc":"Bold black condensed sans-serif printed header on the ticket.","color_palette":["#2B2B2B"]},{"type":"text","bbox":[460,250,640,750],"text":"PIER 7 → ISLAND\n23:40","desc":"Two lines of smaller black monospace print under the header, slightly faded.","color_palette":["#2B2B2B"]}]}}`

**T1 keyframe / frame 0** (16:9). Ideogram is not the first choice for photographic frames, but works when a frame needs
exact placement or printed text. Make the action's onset readable in the subject's `desc` (hands already on the rope) and
leave room in the frame for the move:
`{"high_level_description":"A medium-wide 35mm film still of a young ferry deckhand in an orange rain jacket coiling a wet mooring rope on the open stern deck of a small car ferry at dusk, the harbour lights behind her.","style_description":{"aesthetics":"naturalistic cinematic film still, grounded, observational, muted colour","lighting":"overcast dusk sky as soft key from frame right, sodium harbour lamps as small amber points in the distance","photo":"35mm lens, eye level, deep focus, fine film grain, 16:9 frame","medium":"photograph","color_palette":["#26313B","#4F5E68","#D9792B","#C9A86A","#121820"]},"compositional_deconstruction":{"background":"The stern deck of a small car ferry: wet steel plating with painted yellow safety lines, a white railing along the right edge, grey choppy water beyond, and a low harbour quay with scattered amber lamps under a slate-blue dusk sky.","elements":[{"type":"obj","bbox":[300,330,1000,600],"desc":"A young woman deckhand, mid-twenties, light brown skin, dark hair tied back under a black knit cap, orange waterproof rain jacket and dark work trousers, bent forward with both hands pulling a wet rope into a coil, face in three-quarter profile looking down at the rope.","color_palette":["#D9792B","#1E2226","#6B4A3A"]},{"type":"obj","bbox":[720,560,960,820],"desc":"A thick coil of wet blue mooring rope lying on the deck at her feet, its loose end running up into her hands."},{"type":"obj","bbox":[180,780,620,1000],"desc":"A white steel bollard and railing post at the right edge of the deck, streaked with rust and water."}]}}`

**T8 storyboard frame** (non-photo, `illustration` + `art_style`):
`{"high_level_description":"A rough storyboard frame in pencil and grey marker showing a wide shot of a deckhand running along a ferry deck toward camera, with a hand-drawn arrow for her direction.","style_description":{"aesthetics":"loose, functional, clear staging","lighting":"implied flat light, simple grey tone blocks","medium":"illustration","art_style":"film storyboard sketch, graphite pencil lines with grey marker shading on white paper","color_palette":["#FFFFFF","#2A2A2A","#9A9A9A"]},"compositional_deconstruction":{"background":"White paper with a thin black rectangular frame line, a quickly sketched ferry deck receding to a vanishing point and a railing on the left.","elements":[{"type":"obj","bbox":[300,420,850,600],"desc":"A sketched woman in a rain jacket running toward camera, mid-stride, arms pumping, drawn with quick pencil lines."},{"type":"obj","bbox":[450,620,600,760],"desc":"A thick hand-drawn arrow pointing down and toward the viewer, showing her direction of travel."},{"type":"text","bbox":[880,40,950,300],"text":"SC 12 / SH 3","desc":"Small handwritten pencil label in the lower left corner of the frame."}]}}`

**T3 location plate:** same as T1 with no people; describe the shell in `background`, give each landmark object its box.
**T2 one character across shots:** no reference input. Copy the character's full `desc` verbatim into every caption and
keep the seed; expect drift. **T6/T7:** not possible here; re-generate with one element changed and the same seed only
as a last resort `[hypothesis]`.
**T10 (unique):** in-world graphic props with many exact text blocks (tickets, menus, newspapers, maps, UI screens) and an
exact brand palette.

## 7. Parameters

| Knob | Official `[official]` | Continuo default / house `[code]` | Effect |
|---|---|---|---|
| steps | presets 48 / 20 / 12 | 20 (catalog `standard`), 48 (`hq`) | more = finer detail; 48 is the quality preset |
| cfg | 7 for all but the last 3/2/1 polish steps at 3 | 7, override 3 on the last 30 % (fixed) | higher = adherence, saturation; KJNodes author: 6-7 is fine with the override starting 0.6-0.7 [maintainer 2026-06-10] |
| mu | 0 (48, 20), 0.5 (12) | 0 | shifts where steps are spent; raised automatically with resolution |
| std | 1.5 (48), 1.75 (20, 12) | 1.75 (`hq`: 1.5) | spread of the schedule |
| size | 256-2048 per side, multiple of 16, aspect up to 6:1; best quality 2048x2048 | megapixels default 1 | the server lowers megapixels to fit 2048 per side: 16:9 ≤2.2 MP (2032x1136), 2:3 ≤2.6, 21:9 ≤1.7, 1:1 ≤4 [code] |

Use `standard` for drafts, `hq` (48 / std 1.5) for finals. The sampler is Euler and fixed.

## 8. Failure -> cause -> fix

| Symptom | Cause | Fix |
|---|---|---|
| Refused before queueing: `prompt must be a JSON object` | prose or a JSON array | send one JSON object |
| Grey "Image blocked by safety filter" card | thin/off-format caption, no boxes, sparse big text, unlucky seed | section 4 |
| Blocked text painted over a real scene | `high_level_description` was fragments | one full 20-50-word sentence |
| Layout rotated or transposed | `[x,y,...]` order | y first |
| Everything piled top-left | 0-1 or pixel coordinates | 0-1000 |
| Round thing stretched / duplicated subject | square bbox on a non-square frame, or one huge box | scale the x-span by H/W; tight box per subject |
| Wrong or dropped letters | long one-line stylised title; text in `desc`; box too small | text in `text`, stack with `\n`, bigger box |
| Small text illegible | small type is a weak spot [community 2026-06-04] | fewer, larger text blocks; 2 MP |
| Text blends into the background | no palette contrast | text colour in the element palette, background colour in the style palette `[maintainer, KJNodes author, 2026-06-10]` |
| Feet sunk into the floor | floor emitted as an element | floor in `background` only |
| Checkerboard behind the subject | asked for transparency | solid flat background |
| Same seed, different picture after an edit | whitespace/indentation changed | always send compact |
| Last elements ignored | very long caption | most important first; shorten `desc`s |

## 9. Ideogram 4 or MOSS-Image?

| Need | Pick |
|---|---|
| Exact brand palette, 2-8 placed text blocks, poster/title design quality | Ideogram 4 |
| A paragraph or more of text, Chinese text, dense UI/infographic labels | MOSS-Image (LLTB: MOSS 96.3 vs Ideogram 63.5 Mean-6; Ideogram ZH 32-60 — MOSS's own paper) |
| No risk of a blocked card, NSFW-adjacent drama | MOSS-Image |
| Commercial use | MOSS-Image (Apache-2.0); Ideogram is non-commercial |
| Photographic frame without text | neither first: a photo model |

## 10. Sources (accessed 2026-11-12)

`[official]` github.com/ideogram-oss/ideogram4: README.md, docs/prompting.md, docs/inference.md, docs/pipeline.md,
docs/model_architecture.md, docs/safety.md, src/ideogram4/caption_verifier.py, sampler_configs.py, scheduler.py,
pipeline_ideogram4.py, magic_prompt.py, magic_prompt_system_prompts/v1.txt · ideogram.ai/blog/ideogram-4.0 ·
docs.ideogram.ai/prompting/json-prompting.
`[maintainer]` ComfyUI comfy/text_encoders/ideogram4.py, comfy/ldm/ideogram4/model.py, comfy_extras/nodes_ideogram4.py,
nodes_custom_sampler.py (DualModelGuider, CFGOverride) at commit 2f89433 · KJNodes nodes/ideogram4_nodes.py (17195fc) ·
blog.comfy.org/p/ideogram-4-day-0-support-in-comfyui · KJNodes author on Banodoco #ideogram 2026-06-03..14.
`[community]` github.com/ideogram-oss/ideogram4 issues #5, #13, #14, #21, #33, #35 (2026-06..08) · Banodoco #ideogram
2026-06-04..15 · MOSS-Image Technical Report arXiv 2610.23374 App. G.1 (third-party measurement).
`[code]` Continuo 9f7510c0: workflows/ideogram4-create-v1/*, model_catalog.v1.json, catalog_create_workflow_adapter.py,
image_workflow_run.py, routes/image/workflow_1.py, desktop caption-json.js.
