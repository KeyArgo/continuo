---
name: image-prompts
description: "Use when writing or repairing a prompt for a Continuo image model (create or edit)."
---

# Image prompts (Continuo image models)

Every image model reads its own grammar, and the server sends almost every prompt **literally**: no local model has
an enhancer switched on unless the artist asks. Write what the model was trained on. This page picks the model and
gives each one's rule; the reference for that model has the grammar, worked prompts, parameters and failures.

1. Read `continuo_image_catalog` (or `continuo_targets_catalog`): only targets marked runnable can render; each names
   its `prompt_grammar`.
2. Pick the model for the film task (section 1), then load its reference (section 2) before writing a prompt.
3. Write in that model's grammar. Never carry one model's syntax (tags, JSON, `<Picture N>`, `<image1>`, H3 fields)
   into another.


## 1. Which model for which film task

| Task | First choice | Second choice | Why |
|---|---|---|---|
| T1 keyframe / frame 0 for a video take | P-H3-Image Create at the take's aspect | Krea 2 Turbo (2 MP); Qwen-Image 2.1 Create; MiniMax-H3-Image | P-H3 renders 8 MP film frames and shares H3's transformer (that frames transfer better is untested); Krea is fastest for staging tests |
| T2 one character across shots | Krea 2 Identity Edit V2 (one clean photo restaged) | P-H3-Image Edit (brief + `identity` reference); Qwen-Image 2.1 Edit with references | Only reference-based models hold a face; text-only models (Anima, Ideogram, MOSS) drift |
| T3 location / establishing plate | Krea 2 Turbo or P-H3-Image Create | Qwen-Image 2.1 Create; FLUX.3 Klein | Photographic range from words; Qwen and FLUX.3 for layouts spelled out element by element |
| T4 insert / prop close-up | Krea 2 Turbo (macro, texture) | P-H3-Image; Qwen-Image (a label on the prop) | Material detail; Qwen when the prop carries text |
| T5 title card / signage | Ideogram 4 (a few exact text blocks, placed) | MOSS-Image (long or dense text); Qwen-Image; GPT Image when connected | Ideogram places blocks by box; MOSS leads on long text; Ideogram refuses sparse big text more often |
| T6 continuity repair | Qwen-Image area edits (all seven operations measured) | FLUX.3 Klein box edit (several objects, Keep boxes); Krea 2 General Edit V2 on Raw (removals); FLUX.2 Klein (relight) | Read `continuo_image_edit_capabilities` first: some cells carry measured warnings |
| T7 look / style transfer | Qwen-Image 2.1 Edit with a `style` reference | P-H3-Image Edit (medium change); area Restyle | Name what the style consists of; style follows a reference more than words |
| T8 storyboard frame | FLUX.2 Klein (4 steps) or Krea 2 Turbo | Anima (anime boards); Qwen-Image (one panel per render); GPT Image (sheets) | Speed matters; one panel per render keeps staging |
| T9 poster / key art | Ideogram 4 (JSON layout) | MOSS-Image layout JSON; Qwen-Image; P-H3 (2:3, short title) | Exact hierarchy and placement |
| T10 unique strengths | see the "best at" column below | | |

## 2. Runnable models: grammar, the rule agents break, the reference

| Model (targets) | Grammar in one line | Rule agents break most | Best at | Reference |
|---|---|---|---|---|
| Krea 2 Turbo / Raw (`krea2-turbo-t2i-create`; Raw is a profile) | one English prose paragraph, **medium first**, then subject + one action, place, light with source and direction; 60-150 words; no weights, no quality tags | Nothing expands the prompt here: write the full caption, and type a style LoRA's trigger into the text (LoRAs are model-only) | look development from words alone, fast seeds | `skill_view('film-suite:image-prompts', 'references/ref-krea2-create.md')` |
| Krea 2 Identity Edit V2 (`krea2-identity-edit-v2`) | one sentence "This person ...": how much is visible (full body, boots), action, place, every garment, light by where it lands | A short instruction copies the photo's crop and coat back: state the framing and the new outfit and what is gone | a person from one casual photo, restaged anywhere | `skill_view('film-suite:image-prompts', 'references/ref-krea2-edit.md')` |
| Krea 2 General Edit V2 (`krea2-general-edit-v2`; area edits with model krea2) | one imperative sentence, 6-15 words, `, keep ...` optional | Removals: apply the `removal_raw` preset ("Removals (Raw)": the Raw model, 20 steps / CFG 3); Turbo re-renders the subject instead of removing it | recolour, relight, background, outfit, sign text | `skill_view('film-suite:image-prompts', 'references/ref-krea2-edit.md')` |
| Qwen-Image 2.1 Create / Edit (`qwen-image-2.1-create-pe-v3-v2`, `qwen-image-2.1-edit-pe-v3-v2`; area `qwen-image-2.1-edit-pe-v3`) | create: an observer paragraph, medium first, positional phrases, a lighting sentence, 150-300 words; edit: operation first, change at full strength, then "Keep <named things> unchanged" | `<image1>` is the target, `<image2>` ... references; the server's "Reference roles" list only names roles, so say what each picture gives and where it goes; the negative is live (CFG 1.5) | exact quoted text, copy swaps in a plate, transparent (RGBA) elements, up to 10 references | `skill_view('film-suite:image-prompts', 'references/ref-qwen-image.md')` |
| P-H3-Image Create / Edit (`p-h3-image-lora-t2i-v1`, `p-h3-image-lora-edit-v1`; area edits) | create: 80-200 words opening with one sentence that says what the picture is ("A frame from a feature film: ..."); edit: one paragraph `Edit <Picture 1>. <result>. Keep <...> exactly as it is.`, or with references the six-section brief | No upsampler is installed: a bare request redraws the whole picture; no hype words ("cinematic" makes it glossy) | 8 MP film and editorial frames, 1-7 references composed into one scene | `skill_view('film-suite:image-prompts', 'references/ref-p-h3-image.md')` |
| MiniMax-H3-Image (`minimax-h3-image-create-v1`) | detailed English paragraph of the finished picture ("The target image is ..."); references add `<Subject N>` definitions and preservation clauses, one paragraph | Not P-H3-Image: no "Edit <Picture 1>." prefix or brief; no expander | 16 MP, 6 steps, up to 9 references | `skill_view('film-suite:image-prompts', 'references/ref-h3-image.md')` |
| FLUX.2 Klein 9B (`flux2-klein-9b-t2i-v1`; area edit `flux2-klein-9b-kv-edit-v1`) | subject-first narrative prose, 40-70 words, light described heavily, short quoted text | Writing it like FLUX.3's long caption; hex colours work but drift by seed | 4-step drafts, the strongest area relight | `skill_view('film-suite:image-prompts', 'references/ref-flux2-klein.md')` |
| FLUX.3 Klein (`flux3-klein-sd-create-v1`; area `flux3-klein-sd-edit-v1`, box `flux3-klein-box-edit-v1`) | upsampler off (default): one 100-350-word caption opening with the medium ("Full-color outdoor photograph, ..."), layout in frame words, people profiled, text quoted; box edits: `In <ref_image_0>, ...` citing every `<id>` | A short prompt with the upsampler off: the model was trained only on upsampled captions | box edits (add, change, move, keep, remove in one job) | `skill_view('film-suite:image-prompts', 'references/ref-flux3-klein.md')` |
| Anima Turbo (`anima-turbo-create-v1`) | lowercase Danbooru tags with spaces (quality/safety, count, character/series, `@artist`, traits, camera, place), then 2-4 plain sentences | Leave Guidance at 1.0 (Turbo is distilled for it; above 1 the fixed quality negative switches on and each take is twice as slow); always include `safe` | anime frames and boards, anime look-dev in seconds | `skill_view('film-suite:image-prompts', 'references/ref-anima.md')` |
| Ideogram 4 (`ideogram4-create-v1`) | one **compact** JSON object: `high_level_description` (one 20-50-word sentence), `style_description` (`photo` xor `art_style`), `compositional_deconstruction` with `bbox` `[top, left, bottom, right]` on 0-1000 | Pretty or indented JSON, or a thin caption with no boxed subject, draws the grey "blocked" card; no negative exists | a few exact text blocks with exact placement and palette | `skill_view('film-suite:image-prompts', 'references/ref-ideogram4.md')` |
| MOSS-Image SFT (`moss-image-sft-create-v1`) | English prose describing the finished picture, 80-250+ words, every visible string quoted with real line breaks; defects in the negative; optional layout JSON | A short request instead of a full description: seed drift and broken text; backgrounds come out soft | long or dense in-image text (menus, boards, screens), many-constraint scenes | `skill_view('film-suite:image-prompts', 'references/ref-moss-image.md')` |
| GPT Image Create / Edit (`gpt-image-2-create-v1`, `gpt-image-2-edit-v1`; subscription, listed only when connected) | a plain-English production brief: deliverable first, scene, subject, details, constraints on their own line; edit = `Image 1: ... Image 2: ...` + "change only X, keep Y exactly" | Only 1536x1024 exists: never ask for another ratio (a wrong returned size fails the take); the server adds no role text, so name every picture | exact copy and layouts, period-accurate places, up to 16 references | `skill_view('film-suite:image-prompts', 'references/ref-gpt-image.md')` |

## 3. Listed but not runnable (say so plainly)

- FLUX.2 Klein **compose** (multi-reference): catalogued, no workflow, no target. Use Qwen-Image Edit or P-H3-Image
  Edit for compositions from references.
- Anima **control, inpaint, image-to-image** and every Anima edit: declared, adapter not built. Anima is create only.
- Krea 2 **Identity Edit (v1)** row: legacy values, no target. Use Identity Edit V2.
- References on area edits (`continuo_image_edit`) for Qwen, FLUX.2 and FLUX.3 are accepted and ignored. For
  references use the catalog edit (`continuo_image_workflow_submit`).
- No mask, no inpaint and no transparency on GPT Image; no image-to-image on Ideogram 4; no edit on MOSS.
- Offered with a measured warning (tell the artist, do not hide it): P-H3 area Outpaint (grey margin), Krea area
  Fill / Remove / Outpaint / Box (grey stays grey on flat pictures), FLUX.3 area Replace (old object recoloured),
  FLUX.2 area Fill / Outpaint.

## 4. Rules that really are shared

- Load the model's reference before the first prompt for it; read back the effective prompt when the job returns
  one (Qwen, FLUX.3, P-H3) to see what the model got.
- Name things concretely: materials, colours, counts as numbers, where in the frame ("frame-left", "in the upper
  third"). Light gets a source, a direction and what it hits.
- Visible text: quote the exact string, say where it sits and how it looks. Check spelling on every seed and re-roll
  the seed before rewording.
- Weights: `(word:1.3)` reaches every model except Anima as literal characters (their text encoders disable weights).
  Anima reads weights and needs about 2 for an effect.
- Quality tags ("masterpiece, 8k, hyper-detailed") help no prose model; Anima's tag prefix is the exception.
- Edits: say the change as the finished result and list what stays (faces, poses, background, light, framing). An
  unnamed reference is copied loosely or ignored; one clean view per identity, never a character sheet.
- A keyframe for a video take: render at the take's aspect (H3 crops keyframes from the centre), show the onset of
  the action, keep surfaces that will come close to the lens plain, no motion blur. Then load
  `film-suite:video-prompts` for the take.
- Generation runs on the artist's local GPU (GPT Image on their subscription): submit only when the artist asked.

## 5. Corrected cross-model rules (differ per model)

**Negatives.** There is no global rule; check the model.

| Model | Negative |
|---|---|
| Krea 2 Turbo, FLUX.2, FLUX.3, P-H3-Image, Krea 2 Edit V2 | none reaches the model: describe the wanted state ("the empty platform", not "no people") |
| Krea 2 Raw | real negative field (Raw only); keep it empty unless one defect needs it |
| Qwen-Image 2.1 | live at the house CFG 1.5: keep it short and about defects; describe scene content positively |
| MOSS-Image | real, prefilled with defect tags: keep them; add `heavy blur, bokeh` to fight soft backgrounds |
| Anima | fixed official quality negative, inert at Guidance 1.0: never write "no X", name the wanted trait |
| Ideogram 4 | none exists; JSON describes only what is there |
| GPT Image | exclusion lines work ("No other text, no watermark"); still describe scene content positively |
| Closures | "no other text" after quoted strings is vendor practice on P-H3, Qwen, GPT Image, MOSS |

**Ordering.** Medium first on Krea 2, FLUX.3, P-H3-Image, Qwen-Image Create and MOSS ("A 35 mm film still, ...").
Subject first on FLUX.2 Klein. Edits: operation first (Qwen, Krea General, P-H3 `Edit <Picture 1>.`). Anima: tag
order quality/safety, count, character/series, artist, traits, then sentences. Ideogram: the JSON key order is fixed.
GPT Image: deliverable first.

**Length.** FLUX.2 40-70 words · Krea 2 60-150 · P-H3 80-200 · MOSS 80-250+ · Qwen 150-300 (the official rewriter
targets 400-500; the 8-step path is untested that long) · FLUX.3 100-350 · Krea Identity Edit 25-45 · Krea General
Edit 6-15 · Ideogram `high_level_description` 20-50 · GPT Image 1-3 sentences for simple frames, a labelled brief for
complex ones.

**"Cinematic" and hype words.** Avoid them on P-H3-Image (glossy, oversaturated) and Krea 2 (3D-render look); name
the medium instead ("a frame from a feature film", "a 35 mm film still"). H3 video is different: its guide opens
`[Shot 1] Live-action, cinematic, ...`.

## 6. Area edits (`continuo_image_edit`)

In template mode (default) your prompt is the THING; the server wraps it in the operation's sentence. Send
`options.instruction_mode: raw` to write the whole instruction yourself, in that model's edit grammar. Read
`continuo_image_edit_capabilities` first; box edits: read `continuo_image_box_prompt` before running.

| Operation | Server sends (most models) | Your prompt |
|---|---|---|
| fill | "Fill the grey area with {prompt}. Keep everything else ..." | `a wooden rowing boat with a red hull` |
| replace | "Replace {target} completely with {prompt}, ..." | the new object; `options.target` names the old one |
| remove | background-only fill after a pre-fill | ignored on most models: nothing to write |
| restyle | "Redraw the whole picture as {prompt}. ..." | `a loose ink-and-wash drawing` |
| relight | "Relight the photo with {prompt}. ..." | `low warm sunset light from the left` |
| outpaint | "Extend the picture into the grey area ..., with {prompt}" | optional |

Per-model differences: FLUX.2 and P-H3 Fill send "Add {prompt}{where}. Keep everything else ..."; FLUX.3 Fill adds
"the whole of it small enough to fit inside the area" itself (do not repeat it); Krea Relight (`krea2-edit-turbo-v1`)
sends "Change the lighting to {prompt}. ..."; P-H3 area edits get `Edit <Picture 1>. ` in front. The enhancer
(`options.prompt_enhancer`) is opt-in and forced off for Relight.

Catalog edits (`continuo_image_workflow_submit` with role-tagged references): P-H3 Edit appends
"<Picture N> is the <role> reference." after one space, in the same paragraph as your text; Qwen Edit appends a "Reference roles" list where
`<image1>` is the target; Krea Edit V2 and GPT Image add no role text. The output takes the first picture's aspect
(Krea, Qwen, P-H3).

## 7. Failures common to many models

| Symptom | Cause | Fix |
|---|---|---|
| Wrong subject leads | it is not where the model looks first | put the medium, then the subject, at the start (subject first on FLUX.2) |
| Unwanted thing appears | you named it to forbid it | describe the wanted state; use the negative only where it exists (section 5) |
| Garbled or invented text | long, unquoted or unplaced strings; small print the design usually carries | quote and place every string, close with "no other text", check corners; Ideogram, MOSS or GPT Image for real layouts |
| Edit redrew the whole picture | no keep list, or a bare request on P-H3 | name what stays; on P-H3 use the edit form |
| Identity drifts | reference unnamed, a sheet as identity, or a text-only model | name each picture's job; one clean view; a reference-based model |
| Sentence reads twice ("Fill the grey area with fill ...") | a sentence in template mode | send the thing only, or `instruction_mode: raw` |
| Ideogram grey card | prose, pretty JSON, or a thin caption without a boxed subject | compact JSON, a rich sentence, box the main subjects |

Model-specific failure tables are in each reference, section 7.

## References

| File | Load for |
|---|---|
| `skill_view('film-suite:image-prompts', 'references/ref-krea2-create.md')` | Krea 2 Turbo / Raw create |
| `skill_view('film-suite:image-prompts', 'references/ref-krea2-edit.md')` | Krea 2 Identity Edit V2, General Edit V2, Krea area edits |
| `skill_view('film-suite:image-prompts', 'references/ref-qwen-image.md')` | Qwen-Image 2.1 create, edit, area edits, enhancer |
| `skill_view('film-suite:image-prompts', 'references/ref-p-h3-image.md')` | P-H3-Image create, edit (instruct and brief), area edits |
| `skill_view('film-suite:image-prompts', 'references/ref-h3-image.md')` | MiniMax-H3-Image |
| `skill_view('film-suite:image-prompts', 'references/ref-flux2-klein.md')` | FLUX.2 Klein create and area edits |
| `skill_view('film-suite:image-prompts', 'references/ref-flux3-klein.md')` | FLUX.3 Klein create, area and box edits, upsampler |
| `skill_view('film-suite:image-prompts', 'references/ref-anima.md')` | Anima Turbo |
| `skill_view('film-suite:image-prompts', 'references/ref-ideogram4.md')` | Ideogram 4 JSON captions |
| `skill_view('film-suite:image-prompts', 'references/ref-moss-image.md')` | MOSS-Image prose, negative, layout JSON |
| `skill_view('film-suite:image-prompts', 'references/ref-gpt-image.md')` | GPT Image create and edit |
