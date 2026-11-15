# Anima (CircleStone Labs) — prompting reference for Continuo

Load this when the catalog names family `anima` / grammar `anima_booru_hybrid`. Evidence tags: `[code]` Continuo source,
`[local]` installed ComfyUI / workflow files, `[official]` model card or vendor/maintainer repo, `[maintainer]` named
node/tool author, `[community]` dated practitioner report, `[hypothesis]` reasoned, untested. Sources and dates in §8.

## 1. Scope

| Catalog variant | Target | Model file | State in Continuo |
|---|---|---|---|
| `create` | `anima-turbo-create-v1` | `anima-turbo-v1.1` (distilled) | **runnable** (rendered 2026-10-21) `[code]` |
| `control` | none | Base v1.0 + `anima-lllite-any-test-like-v2` | declared only: no workflow, no target `[code]` |
| `inpaint` | none | Base v1.0 + `anima-lllite-inpainting-v2` | declared only `[code]` |
| `i2i` | none | Base v1.0 | declared only `[code]` |

`continuo_image_edit_capabilities` reports every Anima edit (fill, remove, restyle, outpaint, control) as
`available: false`, "the adapter comes later" `[code]`. Do not offer Anima control, inpaint or image-to-image to the
artist as a Continuo action until the catalog shows a target for it. §4 still covers them, because the artist may
run them in ComfyUI directly and because the presets already exist.

What Anima is: a 2B text-to-image DiT (from Cosmos-Predict2-2B) with a Qwen3-0.6B text encoder and the Qwen-Image
VAE, trained on several million anime images plus ~800k non-photographic art images, anime knowledge cut-off
September 2025 `[official]`. Use it for: anime / cel-shaded / illustrated frames, storyboards and animatic panels in an
anime look, anime key art, painterly concept art, fast look-development (Turbo renders in seconds).
Not for: photographs or photoreal frames ("will not work well at realism") `[official]`; text beyond a single word or
a short phrase `[official]`; instruction edits ("make her coat red"): there is no Anima edit model [official card
lists none; code note "Not an edit model."]; multi-reference identity transfer (no reference input at all).

## 2. What Continuo sends (do not duplicate it)

- **Your prompt goes in byte-for-byte** as the positive text. No prefix, no quality tags, no enhancer, no
  rewriting [code: catalog_create_workflow_adapter.py "nothing is rewritten"; descriptor `prompt_enhancer: false`].
  So you write the quality/safety prefix yourself.
- **The negative is fixed and you cannot edit it** `[code: workflow node 14]`. It is the official template
  negative: `worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia`. It names only
  quality defects: no hair style, no `text`.
- **At the default Guidance 1.0 the negative does nothing.** ComfyUI skips the unconditional pass when CFG is
  exactly 1 `[local: comfy/samplers.py]`. Turbo is distilled for CFG 1 `[official]`. Consequence: everything is decided by
  the positive prompt. Fight an unwanted trait by naming the wanted one (`short hair`, `clear sky`), never by
  "no ...".
- **If you raise Guidance above 1 the fixed negative switches on.** It pushes only away from low quality, blur,
  JPEG artifacts and sepia; long hair, ponytails and lettering stay possible. Each step then runs twice (slower), and
  Turbo is distilled for 1.0: keep Guidance at 1.0 unless the artist asks.
- Exposed controls `[code: descriptor]`: Seed; Steps 1-10000 (default 10); Guidance 0-100 (default 1.0); Sampler
  (default `euler_ancestral`); Schedule (default `beta`); Format (1:1, 2:3, 3:2, 3:4, 4:3, 9:16, 16:9, 21:9); Megapixels
  0.1-4.0 (default 1.0), sides rounded to 16. Batch 1-8 (seed + index). LoRAs: a chain after the model, strength 0-2,
  Anima LoRAs only; one Anima LoRA render is on record `[code: image_workflow_run.py]`.
- The model file is pinned to Turbo v1.1. The catalog also lists Base and a community merge as accepted file names,
  but the create graph loads Turbo only `[code]`; Base-only advice (30-50 steps, CFG 4-5) does not apply here.
- Output sizes at 1 MP: 16:9 = 1360x768, 21:9 = 1568x672, 2:3 = 832x1248, 1:1 = 1024x1024 `[code: size formula]`.
  Anima works between 512² and 1536² pixels of area `[official]`; 2 MP at 16:9 gives 1936x1088, past the trained range
  `[hypothesis: expect duplicated subjects / broken anatomy]`. Stay at 1.0-1.5 MP.

## 3. Grammar

Anima was trained on Danbooru-style tags, natural-language captions, and mixtures of both `[official]`. The house
form (`anima_booru_hybrid`) is: **one tag block, then 2-4 plain sentences**.

```
<quality> <safety>, <count>, [<character>, <series>,] [@<artist>,] <appearance tags>, <framing/camera tags>,
<place/light tags>.
<Sentence: who is where in the frame, doing what.> <Sentence: setting, depth, light source and direction.>
```

Rules, all `[official]` unless tagged:
1. **Tags lowercase, spaces not underscores** (`blunt bangs`, `upper body`). Only score tags keep underscores
   (`score_7`). Where Danbooru and Gelbooru spell a tag differently, use the Gelbooru form.
2. **Tag order:** `[quality/meta/year/safety] [1girl/1boy/1other/no humans] [character] [series] [artist] [general]`.
   Order inside a group does not matter.
3. **Prefix:** `masterpiece, best quality, score_7, safe,` is the official recommendation (written for Base). Quality
   tags come in two independent families (masterpiece ... worst quality; score_9 ... score_1); any combination works.
   On Turbo the score tag's value is unverified (§ open questions); the card warns score tags push the Aesthetic build
   "into slop", and practitioners report `score_7` flattening variety `[community]`. Default: keep
   `masterpiece, best quality, safe,`; add `score_7` only if renders look unfinished.
4. **Safety tag always.** Short or vague prompts "may generate undesired content"; the fix is a safety tag in the
   positive plus a sufficiently detailed prompt. With the negative inert, `safe` in the positive is the only guard.
5. **Artists need `@`:** `@artist name`. Without `@` the effect is "very weak". On Turbo, artist styles bite less than
   on Base (distillation adds a strong default style) `[official; community]`; Turbo v1.1 improved this "a bit"
   [official CivitAI release note]. Use artist names only if the artist asks; describe the look otherwise (§5 T7).
6. **Meta and period tags:** `highres`, `absurdres`, `anime screenshot`, `official art`; `year 2025` ... or
   `newest, recent, mid, early, old`. `anime screenshot` pulls toward TV-anime framing and flat cel colour
   `[community: weight 1.5-2 against a glossy "waifu" look]`.
7. **Prose:** at least two descriptive sentences; extremely short prompts "give unexpected results". Normal English
   capitalisation for names. Name a character, then describe them; essential with two or more characters.
8. **Weights work but need ~2:** `(chibi:2)`. In ComfyUI the weight scales the text-adapter output for those tokens;
   the Qwen encoder never sees the brackets `[local: comfy/text_encoders/anima.py, comfy/ldm/anima/model.py]`. Use
   weights only for a trait that keeps disappearing, 1.5 first, then 2.
9. **Brackets are syntax.** Any `( )` in the prompt is read as a weight (bare brackets = x1.1) and removed [local:
   comfy/sd1_clip.py]. Tags with a qualifier must be escaped: `watercolor \(medium\)`. Never put a parenthetical
   aside in prose.
10. **`BREAK` is not a separator in ComfyUI**; it is just a word `[local: no BREAK handling in the core tokenizer]`.
    Separate the tag block from the prose with a full stop or a blank line.
11. **Tag dropout in training:** you do not need every tag. A focused set beats a long list.
12. **Dataset tags (non-anime art):** first line `deviantart` or `ye-pop`, optional second line a title, then the
    description. This routes to the painterly / poster distributions.
13. **Length:** no hard limit in ComfyUI's Anima tokenizer `[local]`. Practitioners report degradation past ~200-300
    tokens `[community]`; keep prompts to ~60-150 words.

Annotated example (create, 16:9):
```
masterpiece, best quality, safe, 1boy, solo, anime screenshot, cowboy shot, from side, short black hair,
yellow raincoat, rope, ferry, harbor, dusk, overcast, rim lighting.
A young deckhand stands on the left of the frame on the wet deck of a small ferry, coiling a thick rope over his
forearm. Behind him a grey harbor and a lighthouse fade into drizzle; cold light from the overcast sky, one warm
cabin window glowing on the right.
```
Count (`1boy, solo`) early stops extra people; `cowboy shot` (thighs up) and `from side` set the camera; tags fix
colours and props; prose places them (left/right, behind) and sets the light.

## 4. Per operation

### Create (Turbo, the only runnable path)
- Keep Steps 10, Guidance 1.0 (official Turbo: CFG 1, 8-12 steps). Sampler/schedule `euler_ancestral`/`beta` is a
  house choice, not official; the maintainer names `euler` as good on Turbo and `er_sde` as a neutral default `[official]`.
- Turbo is stable but less diverse: different seeds give similar pictures `[official]`. For variety change the prompt
  (framing, angle, light), not only the seed. Use batch 4 for picking.
- Iterate here; it is the maintainer's recommended starting version.

### Control (declared; Base + any-test-like-v2 LLLite)
- One weight accepts several map kinds: HED scribble, PiDiNet scribble, two greyscale variants and line art, heavily
  augmented [official kohya card]. Pose and depth weights exist only for the older Preview3 base ("somewhat reduced
  quality" on v1.0; pose "noticeably weaker") `[official]`. The house default preprocessor is LineArt `[code]`.
- The map owns layout and silhouette; the prompt owns colour, materials, identity, light and style. Describe the
  picture you want, consistent with the map: do not contradict its pose or framing. Where a rough map is ambiguous
  (what is in front), say it in a sentence: "the shield is in front of her and the sword behind" `[community]`.
- Knobs: strength (default 1, node range -10 to 10), start/end percent (default 0-1) `[local]`. "If the cond is too
  dominant, lower the strength or restrict the active range with start/end percent" [official kohya]. Practitioners
  end control at ~0.45 to free details `[community]`. Strength 0.5 visibly loosens the pose `[community]`.
- Control image is resized (bicubic, centre-crop) to the output size `[local]`: give it the output's aspect ratio or it
  gets cropped.
- Presets: Base, 30 steps, CFG 4, euler_ancestral/beta `[code, house]`. Comfy's official template uses Base, 30 steps,
  CFG 4, euler/simple, with an optional Turbo LoRA at 8 steps / CFG 1 `[local]`. At CFG 4 the negative is active.

### Inpaint (declared; Base + inpainting-v2 LLLite)
- Mask: white = repaint, black = keep; binarised at 0.5, so feathering does nothing `[local; code note]`. Grow the mask a
  few pixels past the defect (house graph grows 6 px) `[local]`.
- Run it as image-to-image with the mask, not from an empty latent: "otherwise the colors may shift slightly"
  [official kohya usage note]. (Comfy's own template starts from an empty latent; the maintainer note wins.)
- Prompt the whole finished picture, in the same tag+prose form, with the repaired part described as it should be.
  The patch sees the unmasked image, so name what fills the hole and match the surroundings' style and light
  `[hypothesis, consistent with 4-channel RGB+mask conditioning]`. For a removal, describe what is behind the object
  ("an empty wooden bench, the harbor behind it"); never "remove ...".
- Size 512-1536 px [code note]. Presets Base 30 / CFG 4.

### Image-to-image (declared; Base, VAE-encode + denoise)
- Denoise is the only dial: house start 0.55 `[code]`. 0.25-0.35 = clean-up / detail pass (community hires-fix after a
  1.25x latent upscale `[community]`); ~0.4-0.6 = restyle keeping composition; above ~0.7 the source is only a colour
  and layout hint `[hypothesis]`. The higher the denoise, the more the prompt must state (identity, palette, setting).
- Anima will not keep a photographic look; photo-to-anime restyle is a natural use [official limitation; hypothesis
  on denoise band].

## 5. Film tasks

**T1 keyframe / frame 0 for a video take.** Anima frames feed anime-style video. Use 16:9 at 1 MP (1360x768). Choose
the moment just before the action, readable pose, one subject, clear background depth; name framing and angle tags.
Keep `anime screenshot` for a TV-frame look the video model can continue.
```
masterpiece, best quality, safe, 1girl, solo, anime screenshot, full body, from behind, night market, paper lanterns,
crowd, steam, bokeh.
A courier in a green bomber jacket and a red cap stands at the near end of a crowded night market, about to step
forward, her right foot lifted. Stalls with paper lanterns recede down the center of the frame; warm lantern light
from both sides, steam rising from a noodle stall on the left.
```
**T2 one character across shots.** No reference input exists, so identity is text (plus LoRA). Build an
"identity packet" of 6-10 tags and reuse it unchanged in every prompt: hair colour + length + cut, eye colour, one
garment with colour, one signature prop `[community]`. Change only framing, pose, place and light. Name the character
once in prose. For true identity lock, an Anima LoRA trained on Base is the only reliable route [official: train on
Base; community]; apply it via the LoRA list. Expect drift in small accessories first.
```
masterpiece, best quality, safe, 1boy, solo, upper body, three-quarter view, short black hair, undercut, brown eyes,
yellow raincoat, orange life vest, rope, ferry, morning, fog.
The deckhand leans on the ferry railing at the right of the frame and looks across the water toward the left.
Thick morning fog hides the far shore; soft grey light from the front, droplets on his raincoat.
```
**T3 location / establishing plate.** Lead with `no humans, scenery`, then `wide shot` and the place; describe depth
layers (foreground, middle, far) and time/weather in prose [Danbooru wiki: scenery, wide shot].
```
masterpiece, best quality, safe, no humans, scenery, wide shot, desert, motel, neon sign, dusk, power lines,
purple sky.
A one-storey roadside motel sits alone in the middle distance of a flat desert, its row of doors facing the camera.
A dirt parking lot fills the foreground; power lines run diagonally to the horizon under a purple dusk sky, and the
motel sign glows pink.
```
**T4 insert / prop close-up.** `no humans, object focus, close-up, still life`, the object first, then material and
light. Hands: use `hand focus` and expect anatomy errors (negative is inert); keep fingers simple (holding, gripping).
**T5 title card / signage.** Weak: single words, sometimes short phrases `[official]`. Quote one word and place it:
`a wooden sign above the door reading "MOTEL"`. Anything longer: Ideogram, or add text in the edit. Raising
Guidance does not help text on Turbo; keep 1.0.
**T6 continuity repair.** Not available in Continuo for Anima (all edit ops off) `[code]`. Re-generate with the same
packet and seed, or repair in another family. In ComfyUI directly: Inpaint (§4).
**T7 look / style.** Steer the look with tags the model knows: `anime screenshot` (TV cel), `official art`,
`year 2018`-style period tags, `flat color`, `monochrome`, `greyscale`, `sketch`, `watercolor \(medium\)`, or the
`deviantart` dataset line for painterly. Practitioners measured that phrases tied to concrete colours and motifs move
the style; studio names are weak; "cel shading" does nothing because it is already the default `[community]`.
**T8 storyboard frame.** Single panel per render (the `storyboard` tag means a multi-panel sheet [Danbooru wiki]):
```
masterpiece, best quality, safe, monochrome, greyscale, sketch, lineart, 2boys, wide shot, from above, dock,
ferry, rain.
Rough storyboard sketch: two deckhands on a rainy dock pull a mooring line toward the ferry moored on the right.
Seen from high above the dock, the boat in the right third of the frame, the men small in the lower left.
```
Use 16:9 or `letterboxed` for a cinema frame [Danbooru wiki]. Keep shapes simple; Turbo's strong default style
tends to colour; weight `(monochrome:1.5)` if it does `[hypothesis]`.
**T9 poster / key art.** Portrait 2:3, one hero subject, strong angle (`from below`, `dutch angle`), dramatic light
(`backlighting`, `rim lighting`), `official art`. Keep any title out of the render (T5).
**T10 unique strengths.** Fast anime look-dev (seconds per frame), deep anime/booru vocabulary for poses, framing
and costumes, and known anime characters by name + series (clear rights before using a real franchise).

## 6. Parameters

| Knob | Official | House / Continuo default | What it does |
|---|---|---|---|
| Steps | Turbo 8-12; Base 30-50 `[official]` | 10 `[code]` | fewer than 8 on Turbo: soft, unfinished `[hypothesis]` |
| Guidance | Turbo 1; Base 4-5 (CivitAI page 4-6) `[official]` | 1.0 `[code]` | >1 on Turbo: stronger prompt following but doubles time, activates the fixed quality negative; community reports CFG 2 helps adherence `[community]` |
| Sampler / schedule | er_sde neutral default; euler good on Turbo; euler_a softer, thinner lines, can drift 2.5D; beta57 for painterly texture `[official]` | euler_ancestral / beta `[code, house]` | change only on the artist's request |
| Megapixels | 512²-1536² area `[official]` | 1.0 `[code]` | >1.5 MP risks doubled subjects `[hypothesis]` |
| LoRA strength | card: train rank-32 LoRAs on Base at LR 2e-5, never train the LLM adapter `[official]` | 0-2 `[code]` | style LoRAs at 0.6-1.0 is common practice `[community]` |

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Unwanted content / random subject | prompt short, no safety tag | add `safe`, count tag, two full sentences `[official]` |
| "No X" brought X | negation in positive; negative inert at CFG 1 | name the wanted state |
| Long hair / ponytail missing | not named, or a short-hair tag elsewhere in the prompt | name `long hair` / `ponytail` among the traits |
| Sign text missing | text too long for Anima | one quoted word, placed; longer text: Ideogram or an edit |
| Bland, flat, same-looking renders | Turbo's reduced diversity, no style direction | vary framing/angle/light; add look tags or one `@artist` |
| Artist style barely shows | missing `@`; Turbo weakens artist tags | `@name`; weight 1.5; accept Turbo's limit |
| Weight did nothing / tag vanished | weight too low; or brackets mis-parsed | use 1.5-2; escape literal brackets `\( \)` |
| Two characters swap clothes or merge | names listed without per-character description | one sentence per character with position (left/right) `[official; community]` |
| Photoreal request comes out 2.5D/odd | out of scope | use a photographic model |
| Doubled people, stretched bodies | size over ~1536² area, very wide 21:9 | 1.0-1.5 MP |
| Character's outfit falls back to a default | outfit under-described | write the outfit out in tags + one sentence `[community]` |

## 8. Sources (accessed 2026-11-12 unless noted)
- `[official]` Anima model card, circlestone-labs/Anima README, revision f973fc41 (2026-08-24): https://huggingface.co/circlestone-labs/Anima
- `[official]` Anima CivitAI page, Turbo v1.1 notes (2026-08-24): https://civitai.com/models/2458426/anima
- `[official]` kohya-ss/Anima-LLLite README and PREVIEW3.md: https://huggingface.co/kohya-ss/Anima-LLLite
- `[maintainer]` kohya-ss/ComfyUI-Anima-LLLite README (rename to AnimaLLLiteApply_sdscripts; mask convention): https://github.com/kohya-ss/ComfyUI-Anima-LLLite
- `[official]` kohya sd-scripts docs anima_train_network.md, anima_train_control_net_lllite.md: https://github.com/kohya-ss/sd-scripts/tree/main/docs
- `[official]` ComfyUI Anima tutorial: https://docs.comfy.org/tutorials/image/anima/anima ; Comfy workflow templates image_anima_base_v1 / image_anima_lllite_* (comfyui_workflow_templates_json 0.1.128)
- `[official]` circlestone-labs/Anima-Official-LoRAs (Turbo LoRA v0.2): https://huggingface.co/circlestone-labs/Anima-Official-LoRAs
- `[local]` ComfyUI core: comfy/samplers.py (CFG 1 skips uncond), comfy/text_encoders/anima.py, comfy/ldm/anima/model.py, comfy/ldm/anima/lllite.py, comfy_extras/nodes_model_patch.py, comfy/sd1_clip.py (ComfyUI commit 2f8943324, 2026-11-05)
- `[code]` Continuo 9f7510c0: model_catalog.v1.json (family anima), image_edit_capabilities.v1.json, workflows/anima-turbo-create-v1, catalog_create_workflow_adapter.py, image_workflow_run.py
- `[community]` HF discussion #236 "Artificial looking" (2026-09): https://huggingface.co/circlestone-labs/Anima/discussions/236
- `[community]` HF discussion #165 samplers (2026): https://huggingface.co/circlestone-labs/Anima/discussions/165 ; #206 default outfits (2026-06-30)
- `[community]` CivitAI "Ultimate Anima Prompting Guidebook" (2026-09-15): https://civitai.com/articles/35368
- `[community]` CivitAI "How your prompt breaks Anima" (2026-06-13; contradicted on weights and BREAK by ComfyUI code): https://civitai.com/articles/31399
- `[community]` Reddit r/StableDiffusion "Anima 1.0 tips" (~2026-06): https://www.reddit.com/r/StableDiffusion/comments/1u4t2lx/
- `[community]` note.com, LLLite any-test trial (2026-04-30, upd. 05-24): https://note.com/yumenojmd/n/n096867334b93
- `[community]` note.com style-phrase sweep on one seed: https://note.com/ai_0049/n/n74ccab5370e0
- `[community]` Danbooru wiki: storyboard, letterboxed, cowboy shot, wide shot, scenery, object focus, dutch angle, multiple views: https://danbooru.donmai.us/wiki_pages/
