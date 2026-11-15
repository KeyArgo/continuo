# GPT Image (Create, Edit): prompting reference

Load this file when the target is `gpt-image-2-create-v1` or `gpt-image-2-edit-v1` (catalog family `gpt_image`,
grammar `gpt_image_prose`). Evidence tags: `[code]` Continuo source, `[official]` OpenAI docs and repos,
`[maintainer]` the Hermes image provider and its tracker, `[community]` named and dated third-party reports,
`[hypothesis]` not yet settled by a test render.

## 1. Scope

| Catalog variant | Target | Operations | Inputs |
|---|---|---|---|
| Create | `gpt-image-2-create-v1` | create | prompt only; references are refused |
| Edit | `gpt-image-2-edit-v1` | edit, multi_reference | Image 1 = picture to edit (exactly 1), plus 0 to 15 references |

The model is OpenAI's GPT Image 2 (`gpt-image-2`). The artist's ChatGPT (Codex) subscription pays for it, through
Hermes' `openai-codex` image provider. There is no API key and no ComfyUI graph `[code]`. It is a closed,
instruction-following model that reasons over the whole request, so it reads long natural language, layouts and
lists well.

Use it for:
- exact text in the picture: signage, title cards, period print, screens and labels (T5);
- dense layouts: storyboard sheets, a poster with copy, maps and diagrams (T8, T9);
- world knowledge and period accuracy: name a place and a date and it fills in the right detail `[official]`;
- extreme scale, crowds and world shots that local edit models under-deliver `[hypothesis]` (house practice);
- multi-reference composites with up to 16 pictures, and instruction edits that keep the rest of the frame (T6).

Do not use it for:
- transparency, masks, exact pixel-region edits or seed-reproducible variations (none of these is offered here);
- formats other than 3:2 landscape (section 2);
- full figures of an established character from anchor references: house tests came back doll-like, with the
  head too big and the face too young. Use a local edit model for those `[hypothesis]`;
- relighting or changing the camera height of an existing photo. Edits kept the original front light and eye
  level `[hypothesis]`;
- real people's likeness, gore and sexualised content: moderation blocks them, and false positives also hit
  ordinary action and swimwear scenes `[official]` `[community]`;
- cheap iteration. Every take is one request against the subscription's usage limits, with no retry
  `[code]` `[official]`.

## 2. What Continuo sends (do not duplicate it, and do not fight it)

- **Your prompt goes to the model exactly as written.** The server adds no wrapper, template, role suffix or
  enhancer, and returns no effective prompt (`capabilities.prompt_enhancer: false`, `effective_prompt: false`)
  `[code]`. Unlike the P-H3 and Qwen edits, the server does **not** add "Picture N is the X reference". You
  must name every input in your own words.
- Prompt limit: 1 to 16,384 characters, no NUL `[code]`.
- **Image order on Edit**: the picture to edit is sent first (`image_url`), then the references in the order you
  submitted them (`reference_image_urls`). Image 1 is always the target; references are Image 2 to Image 16
  `[code]` `[maintainer]`. The role tags you set in Continuo (`target`, `reference`) are **not** sent to the
  model, so only the prompt tells it what each picture is for.
- Each request body has `model gpt-image-2, n 1, quality <low|medium|high>, size 1536x1024, background opaque`, and
  for edits `images[]` as data URLs. No `mask`, `input_fidelity`, `output_format`, `moderation` or `seed` is
  sent `[maintainer]`.
- **Format: Landscape 1536×1024 (3:2) is the only option.** On this route the backend does not enforce size, and
  the provider has returned other sizes (1672×941, 1312×1199, 1370×1148, 1254×1254). If the picture does not
  come back at exactly 1536×1024, Continuo fails the take as `output_invalid`, and the request is still used up
  `[code]` `[maintainer]`. So never ask for a different aspect ratio in the prompt ("16:9", "vertical poster",
  "square"). Compose for 3:2 and crop in the cut. Whether the prompt's wording can move the returned size is open:
  untested `[hypothesis]`.
- **Quality** is low, medium (default) or high. On the Codex route it is a request, not a guarantee: a
  maintainer-side test asked for `high` and the server reported `medium` or `low` `[maintainer]`. The take's
  record shows the provider's `reported_quality`; read it before you blame the prompt.
- **Engine identity is opaque.** The Codex backend echoes the alias `gpt-image-2-codex`, and which weights sit
  behind it cannot be verified from outside (it may be a newer GPT Image) `[maintainer]`. Write prompts that
  follow OpenAI's shared guidance for the GPT Image family, which is the same for 2 and 2.5 `[official]`.
- One picture per request: batch is 1, there is no seed, and repeating a prompt gives a different picture. There
  is no LoRA. The same `operation_id` never sends a second request `[code]`.
- Failure reasons: `not_connected` (no Codex sign-in), `limit_reached` (usage limit / HTTP 429),
  `execution_failed` (including a moderation block), `output_invalid` (wrong size or unreadable picture).
  None is retried automatically `[code]`.
- Box and Area edits are not offered for this model ("No mask: not offered in Box") `[code]`. For a local change
  you describe the region in words.

## 3. Grammar: the brief, not the tag list

OpenAI says any format works (prose, labeled sections, JSON-like, tags), as long as intent and constraints are
clear and easy to maintain `[official]`. What reliably works is a **production brief**:

1. **Name the deliverable first**: "A frame from a live-action film", "a storyboard sheet", "a landscape
   cinema quad poster", "a photographed shop sign". The model picks its defaults from this word `[official]`.
2. **Then follow this order: scene, subject, key details, constraints.** For anything complex, use short labeled
   lines or line breaks rather than one paragraph `[official]`.
3. **Use visible facts, not praise.** Name materials, light sources and where they land, colours, lens feel and
   framing. "Stunning, epic, cinematic, 8K, masterpiece" gives the model nothing to draw `[official]` `[community]`.
4. **Ask for realism explicitly.** For photographs write "photorealistic" or "a real photograph". Camera specs
   ("50 mm, f/2") set the look, not exact optics `[official]`.
5. **Mood scenes need concrete detail.** For wide, cinematic, low-light, rainy or neon scenes, state scale,
   atmosphere and colour, or the model trades mood for surface realism `[official]`.
6. **People need framing, gaze and hands**: "full body visible, feet included", "looking down at the ledger, not
   at the camera", "both hands gripping the rope" `[official]`.
7. **Constraints go on their own line, and negatives work here.** Unlike the local diffusion models, GPT Image
   reads exclusions as instructions. OpenAI's own prompts end with "No extra text, no watermarks, no unrelated
   logos" `[official]`. Keep them short and concrete. For an *absent* thing in the scene, still describe the
   positive state ("the empty platform") when you can.
8. **Text**: put the exact words in quotes (or ALL CAPS), say where they sit and give the typography (weight,
   style, colour, size), say how often they appear ("exactly once"), and close with "no other text". Spell rare
   words letter by letter. Use medium or high quality for small or dense text `[official]`.
9. **Length**: one to three clear sentences are enough for a simple frame `[official]`. Long, structured briefs
   (100 to 300 words) work well for layouts and edits. Do not pad: the model invents in the gaps of a vague
   brief, not in a long precise one. No weights, no `(word:1.3)`, no quality tags.

Annotated create example (T1):
```
A single frame from a live-action feature film, photorealistic, 35 mm film grain.   <- deliverable + medium
Scene: the car deck of a small ferry at dusk, wet steel plates, a pale grey sea      <- scene
beyond the open stern.
Subject: a deckhand in a yellow oilskin, about forty, kneels at frame left coiling   <- subject + action onset
a wet mooring rope, his breath visible, eyes on the rope.
Details: cold overcast light from the open sea behind him, one warm sodium lamp      <- light with sources
above the cabin door at frame right throwing amber on the wet deck; eye-level
camera, medium-wide, generous empty deck on the right for him to walk into.
Constraints: no text or signage anywhere, no other people, no watermark.             <- constraints
```

## 4. Per operation

### Create (`gpt-image-2-create-v1`)
Create takes no references (the server refuses them) `[code]`. Use it for first looks, locations, inserts, title
cards and posters that need no existing identity. To build a new frame *around* an existing person, prop or look,
use Edit (below), even when nothing of Image 1's composition should stay.

### Edit, one picture
The core rule is **change only X, keep Y** `[official]`:
```
Edit Image 1. Change only <the thing, named precisely, with its location>.
<The new state, described as the finished result.>
Keep <identity / pose / framing / camera angle / light / background / props / text> exactly as they are.
No new objects, no text, no watermark.
```
- Name the object exactly: "the red thermos on the dashboard", not "the cup".
- For surgical edits, also lock saturation, contrast, camera angle and surrounding objects `[official]`.
- Expect a full redraw. A GPT Image edit is a new picture that resembles the input, so fine texture can soften
  even where nothing was asked to change `[community]`. OpenAI's advice: "If a region must remain pixel-identical,
  composite the approved edit into the original image instead of relying on prompting alone" `[official]`.
- Do not chain edits. Every edit of an edit softens texture further `[community]`. Once the revision list is
  known, apply all of it in **one** edit of the cleanest approved source.

### Edit as "new frame from references"
The edits endpoint also makes new pictures from references `[official]`. Put the most important reference (the
identity anchor, or the location plate the shot must live in) as Image 1, the others after it, and say plainly
that this is a new frame:
```
Image 1: the deckhand, identity reference (face, hair, build).
Image 2: the ferry car deck at dusk, location reference.
Create a new frame: the man from Image 1 stands at the stern rail of the deck from Image 2 ...
```

### Multi-reference (up to 16 pictures)
- **Number every image and give it one job**, in the order Continuo sends them: "Image 1: ... Image 2: ..."
  `[official]`. An unnamed image is copied loosely or ignored.
- Say how they combine, using spatial words: "Put the jacket from Image 2 on the man in Image 1"; "place the dog
  from Image 3 at frame left, beside the woman" `[official]`.
- Limit a reference to its job: "Image 3: boots reference, use only for the boots" `[community]`.
- Use fewer references where you can: each extra image is another thing for the model to blend `[community]`.
  The input limit is 25 MB per picture `[maintainer]`.
- A style reference is described by its parts, not by "same style": palette, grain, edge treatment, light
  quality `[community]`.

### Masks, inpainting, transparency
Not available here. The Image API has a prompt-guided mask on Image 1, and OpenAI says it "may not follow its
exact shape" `[official]`. Continuo sends none. For a hard region, use a local model with Box/Area edits. For
cut-outs, use a matting tool. The provider fixes `background: opaque` `[maintainer]`.

## 5. Film tasks

### T1 Keyframe / frame 0 for a video take
Recipe: deliverable "a single frame from a live-action film", one subject caught at the **onset** of the action,
the direction of travel left open in frame, and light with named sources. Leave anything that arrives later in
the take **out** of frame. A body part in mid-motion is drawn badly; the video model brings it in better
`[hypothesis]`. Keep all surfaces that will grow in the shot blank, or they turn into gibberish lettering
in motion `[hypothesis]`.
```
A single unselected frame from a live-action film, photorealistic, 35 mm grain, natural colour, 3:2 landscape
composition. A desert motel parking lot at 5 a.m., the sky pale blue-grey at the horizon, sodium lamps still on.
A woman in a faded denim jacket stands at frame left beside an open car door, one hand on the roof, looking down
the empty highway toward frame right, about to get in. Wide shot from eye level across the lot, about 40 mm,
long empty asphalt between her and the road. Light: cold dawn from the right, warm sodium spill on the car roof
and her shoulders from a lamp behind her. The motel sign is out of frame. No readable text anywhere, no other
people, no lens flare, no watermark.
```

### T2 One character across shots
GPT Image has no identity LoRA, so identity comes only from reference pictures plus a repeated description.
1. Create one clean identity frame: neutral light, plain background, face and full outfit described concretely
   (age, face shape, hair cut and colour, marks, garments with colours).
2. For each shot use Edit: Image 1 = identity frame (or the approved previous shot), plus a face crop as Image 2
   if it helps. **Repeat the defining details in every prompt**, and lock them: "same face, same hair, same
   green hooded jacket; do not redesign the character" `[official]`.
3. Check the hairline, hair length and proportions on every take; hair drifting longer and fuller is a known
   failure `[hypothesis]`.
```
Image 1: identity reference of the deckhand (face, beard, hair, yellow oilskin). Image 2: close-up of his face.
Create a new frame from a live-action film, photorealistic: the same man from Image 1 sits alone in the ferry's
passenger cabin at night, holding a paper cup of tea in both hands, looking out of a rain-streaked window at frame
right. Medium close-up, eye level, about 50 mm. Light: cold blue from the window on his face, one warm overhead
fluorescent behind him. Keep his face, beard, hairline, short grey hair and build exactly as in Images 1 and 2;
same yellow oilskin, unzipped. Do not make him younger or slimmer. No text, no other passengers, no watermark.
```

### T3 Location / establishing plate
State the period and place; the model adds the right detail from world knowledge, but check that detail for
accuracy `[official]`. Give the scale (people for size), the atmosphere and the light. Leave no people in frame
when the plate is a background for later composites.
```
A wide establishing frame from a live-action film, photorealistic: a covered night market in a Southeast Asian
port town in the 1970s, seen from a raised walkway at the entrance. Rows of stalls under bare incandescent bulbs
on wires, steam from noodle carts, wet concrete, crates of fruit; a dozen shoppers small in the middle distance
for scale. Haze in the air catching the bulbs, deep shadow under the tin roof. Hand-painted stall signs only as
unreadable colour shapes. No modern objects, no plastic signage, no watermark.
```

### T4 Insert / prop close-up
Name the material, its wear and the light raking across it, and give the exact text on the prop if there is any.
```
A macro insert shot from a live-action film, photorealistic: a brass ship's compass on a scratched teak chart
table, needle pointing toward frame right, a pencil and a folded paper chart beside it. Low raking lamplight from
the left shows fingerprints and green tarnish in the engraved ring. Very shallow depth of field. The compass card
shows only the letters "N", "E", "S", "W" in black serif capitals; no other text.
```

### T5 Title card / typography / signage
This is GPT Image's strongest task. Write text like a designer: the exact words, their placement, the typeface
style, weight, colour, how many times each appears, and "no other text" `[official]`. Use medium or high quality.
Spell unusual names letter by letter.
```
A title card for a feature film, 3:2 landscape. Background: a photographed night sky over a dark sea, a faint
lighthouse beam at frame right. Centered in the upper third, the title "THE LAST FERRY" in large white condensed
sans-serif capitals, generous letter spacing, on one line. Directly below it, smaller, in light grey italic serif:
"a film in three crossings". Text appears exactly once each, perfectly legible, no other text, no logos,
no watermark.
```
Signage inside a scene: "a hand-painted wooden sign above the motel office door reading "VACANCY" in red block
letters, the paint chipped; no other text".

### T6 Continuity repair (remove, replace, recolour, relight, extend)
Edit one picture with the change/keep form. Do the whole revision list in one pass from the approved frame, and
composite the result back over the original if the rest must stay pixel-identical `[official]`.
```
Edit Image 1. Remove only the modern plastic water bottle from the dashboard at frame right; where it stood, show
the same cracked brown dashboard vinyl continuing. Keep the driver, his face, his hands on the wheel, the
windscreen reflections, the road outside, the framing and the light exactly as they are. No new objects,
no text.
```
- Recolour: "Change only the colour of the woman's scarf from red to mustard yellow, same fabric folds and
  shadows."
- Weather/time: "Make it the same street ten minutes into heavy rain: wet asphalt reflections, rain streaks in
  the lamp light; keep every building, car and person in place" `[official]` (the lighting-weather pattern).
- Relighting a person's face and changing the camera height edit poorly `[hypothesis]`. Do these in the grade, or
  regenerate the frame.
- Extend/outpaint: not available; the format is fixed. Use a local model with outpaint.

### T7 Look / style transfer
Give the style picture one job and spell out what the style consists of `[official]` `[community]`:
```
Image 1: the approved frame to restyle. Image 2: look reference only.
Redraw Image 1 in the look of Image 2: bleach-bypass colour with muted greens, crushed blacks, hard top light,
heavy 35 mm grain. Keep the composition, the people, their poses and every object of Image 1. Do not copy any
object or person from Image 2.
```
For a period look, name live-action references and the medium. Anime or manga titles pull the result into
illustration `[hypothesis]`.

### T8 Storyboard frame or sheet
A single frame: write the shot like a director (camera position, lens, what is in frame, the one action) and add
"storyboard frame, grey-wash pencil drawing" or "photographic previz". A sheet: one beat per panel, concrete
actions, an explicit panel count and layout `[official]`.
```
A storyboard sheet, 3:2 landscape, six equal panels in two rows of three, thin black borders, white gutters,
loose grey-wash pencil style. Same deckhand in a yellow oilskin in every panel.
Panel 1: wide, ferry pulling away from a dark pier at night.
Panel 2: medium, the deckhand coils rope at the stern, looks up.
Panel 3: his point of view, a small figure waving on the pier.
Panel 4: close-up, his face, recognition.
Panel 5: wide, he runs along the rail toward the bow.
Panel 6: insert, his hand on the cold rail.
Under each panel its number "1" to "6" in small black sans-serif; no other text.
```

### T9 Poster / key art
In 3:2 landscape, design a landscape quad or banner poster, not a one-sheet. Write it as a creative brief: the
hero image, the hierarchy, the exact copy and its placement, and the negative space `[official]`.
```
A landscape cinema quad poster for a drama, 3:2. Left two-thirds: a photographed woman in a denim jacket seen from
behind, standing in a desert motel parking lot at dawn, her long shadow reaching toward the camera. Right third:
dark empty sky for type. Title "VACANCY" in tall white condensed capitals, vertically centered in the right third;
below it the line "Some roads only go one way." in small light-grey serif; at the bottom right a credit block in
tiny grey condensed type, unreadable as words. Title and tagline exactly once each, spelled exactly, no other
readable text, no studio logos, no watermark.
```

### T10 What it does better than the local models
- Exact copy in many scripts and dense layouts (menus, timetables, newspaper front pages, screens) `[official]`.
- Period and place accuracy from one line ("a crowd scene in Bethel, New York on August 16, 1969") `[official]`.
- Translating signage while keeping the layout: "Translate the text on the shop signs to Portuguese. Do not change
  any other aspect of the image" `[official]`.
- Extreme scale and witness framing: a camera where a person could stand, normal lens, the giant thing partly
  hidden, haze, reacting people `[hypothesis]`.

## 6. Parameters

| Knob | Offered in Continuo | OpenAI API (gpt-image-2) | Effect / advice |
|---|---|---|---|
| quality | low / **medium** (house default) / high | low, medium, high, auto `[official]` | Low for drafts and ideas; medium for most frames; high for small text, dense layouts, close faces and identity edits `[official]`. Not enforced on this route: check `reported_quality` `[maintainer]`. |
| size | **1536×1024 only** | any multiple of 16, ratio ≤ 3:1, 655,360–8,294,400 px; >2560×1440 experimental `[official]` | Compose for 3:2; crop for 16:9 or scope in the cut. |
| background | fixed opaque | transparent (preview) / opaque / auto | No transparency here. |
| input_fidelity | not sent | must be omitted; inputs are always high fidelity `[official]` | Nothing to set. |
| mask | none | prompt-guided, on the first image `[official]` | Describe the region in words. |
| moderation | not sent (service default) | auto / low `[official]` | No way to relax it from Continuo. |
| n / seed | 1 / none | n 1–10, no seed | Every rerun is a new picture and a new request. |
| prompt | ≤ 16,384 chars, verbatim | — | Nothing is added by the server. |

## 7. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Take failed `output_invalid`, "returned 1672x941" | backend chose another size; the prompt may have asked for a ratio | remove ratio words, compose for 3:2, resubmit (it is a new request) |
| `limit_reached` | subscription usage limit (image turns use limits 3–5× faster) `[official]` | wait; switch to a local model; do not loop |
| `not_connected` | no Codex sign-in in Hermes | the artist signs in; never fall back silently |
| `execution_failed` with a moderation message | input or output blocked (violence, sexual, real person, minors) `[official]`; false positives on mild action and swimwear `[community]` | reduce graphic detail, describe the aftermath instead of injury, use no real names; or use a local model |
| Wrong text, extra words, text repeated | no quotes or placement, no "exactly once", low quality | quote, place, "no other text", spell it out, quality high |
| Unwanted signage, labels or logos invented | the model fills empty surfaces | "no readable text anywhere", "blank pale wall" |
| Edit changed things you did not ask for | no keep-list | change/keep form; list identity, pose, framing, light, background |
| Edit is softer or plastic-looking, especially skin | each edit redraws; repeated edits compound `[community]` | one edit from the cleanest source; composite back; local skin pass |
| Identity drifts (hair longer, younger face, doll proportions) | references unnamed, details not repeated, full figure from a face ref | name each image's job, repeat the description, keep full figures on a local model `[hypothesis]` |
| Warm, yellow cast | known default warm bias `[community]` | "neutral white balance, cool daylight 6500 K"; fix in the grade |
| Glossy, staged look | hype words, "cinematic" alone | "a single unselected frame", real-texture details, "no glamorization" `[official]` |
| Illustration instead of photo | anime/art words, "miniature", "on a stage" `[hypothesis]` | "photorealistic, live-action, 35 mm grain"; name live-action references only |
| Quality looks like low although high was picked | the route did not honour quality `[maintainer]` | read `reported_quality`; rerun later |

## 8. Sources (accessed 2026-11-12)

- `[code]` Continuo `9f7510c0`: `dashboard/generation/paid/subscription_image_provider.py` (lines 50–76 targets,
  sizes, controls; 79–89 descriptor; 161–175 request checks; 243–265 provider call; 432–451 size check);
  `dashboard/generation/model_catalog.v1.json` family `gpt_image`; `dashboard/generation/image_workflow_run.py:64-69,111`.
- `[maintainer]` Hermes Agent `plugins/image_gen/openai-codex/__init__.py` and `plugins/image_gen/_common.py`
  (installed copy; last change to the provider 2026-10-08): native `images/generations` / `images/edits`, body
  fields, 16 inputs, 25 MB, PNG/JPEG/GIF/WebP; https://github.com/NousResearch/hermes-agent/issues/107233
  (2026-09-10/11: the backend echoes `gpt-image-2-codex quality=auto size=auto`; requested high reported as
  medium/low).
- `[official]` OpenAI, Image generation guide https://developers.openai.com/api/docs/guides/image-generation ;
  Image prompting guide incl. the "GPT Image 2 reference" tab
  https://developers.openai.com/api/docs/guides/image-prompting ; GPT Image prompting cookbook (gpt-image-2,
  2026-04-21, now archived)
  https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide ; model page
  https://developers.openai.com/api/docs/models/gpt-image-2 ; Codex image generation
  https://developers.openai.com/codex/image-generation ; Codex `imagegen` skill and references
  https://github.com/openai/codex/tree/main/codex-rs/skills/src/assets/samples/imagegen ; ChatGPT Images 2.0 and
  2.5 system cards https://deploymentsafety.openai.com/chatgpt-images-2-0/introduction ,
  https://deploymentsafety.openai.com/chatgpt-images-2-5 ; https://github.com/openai/codex/issues/28723
  (2026-06-17, the Codex route ignores size/quality).
- `[community]` fal, "GPT Image 2 Prompting Guide" https://fal.ai/learn/tools/prompting-gpt-image-2 ; 1LittleCoder,
  "ChatGPT Images 2.0 Prompting Guide" (X article, 2026-04) ; r/ChatGPT "GPT Image 2.5 prompt guide (1/3): 8 rules"
  (~2026-09) ; Replicate readme https://replicate.com/openai/gpt-image-2 ; OpenAI forum threads "Bug: Edited Images
  significantly degrade in quality" (1395704), "GPT Image 2 produces plastic-looking faces in product edit"
  (1394653), "Image moderation regression ... false positives" (1403516), "Collection of GPT-image-generator 2.0
  issues" (1379535) ; Astorie "GPT Image 2.5 Editing Drift" https://astorie.ai/blog/gpt-image-2-5-editing-drift ;
  Popular AI "ChatGPT's piss filter" ; Flick "GPT Image 2.0: The Complete Guide" (2026-07).
