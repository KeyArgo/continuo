# Voice reference: OmniVoice (clip, description) and Drama 3 (clip)

Load this before you write a voice, a line, a direction or a description for `continuo_voice_*`.
Part A covers both engines, Part B is OmniVoice and Part C is Drama 3. Part D has the film recipes.
Evidence tags: `[code]` Continuo server, `[local]` installed node or package source, `[official]` vendor docs or papers,
`[maintainer]` node author, `[community]` named and dated practitioner reports, `[hypothesis]` not yet tested.

---

## A. Both engines

### A1. Scope

| Target | Engine / variant | Voice from | Words of the clip | Rate | Use it for |
|---|---|---|---|---|---|
| `omnivoice-clone-v1` | OmniVoice, upstream full checkpoint | clip (≥1 s, 3–10 s best) | optional (empty = local Whisper) | 24 kHz | fast, stable cloning, 600+ languages, short barks, a neutral-to-moderate read that copies the clip |
| `omnivoice-design-v1` | OmniVoice, same checkpoint | description from a **closed word list** | none | 24 kHz | a scratch or temp voice when no clip exists; casting auditions |
| `drama3-clone-v1` | Fish Audio Drama 3, FP8 experts (Fish's own expert weights) | clip | **required, word for word** | 44.1 kHz | performance: free-language direction, sighs, laughs, whispers, held anger, tears |

Neither engine does singing on these targets, infilling (fixing one word inside a take), relative notes against an earlier take, or multi-speaker scenes in one pass. Continuo speaks **one line per take** with one voice. `[code]` `workflows/*/manifest.json`; `[local]` ComfyUI-Drama3 `nodes.py` (`speakers` fixed to "one take per line").

### A2. What Continuo sends (do not duplicate it)

- A **voice** is either a clip (Media sound + IN/OUT + words) or a description. A **character** maps to one voice. A **line** is `{character, text, direction}`. `continuo_voice_generate` speaks one line N times (1–8 seeds: seed, seed+1, …). `[code]` `voice/store.py`, `agent_tools.py:152-157`
- The voice source must match the target: a clip voice runs only on the two clip targets, a description voice only on `omnivoice-design-v1`. Otherwise the request is refused with `voice_mismatch`. `[code]` `routes/voice/voice_1.py:_voice_plan`
- The server cuts the clip to IN/OUT as 16-bit WAV and uploads it. The words go in unchanged. **Neutral cues** in the line text are rewritten per engine. `[code]` `voice/targets.py:49-52, 189-214`:

| You write | OmniVoice gets | Drama 3 gets |
|---|---|---|
| `{cue:laugh}` | `[laughter]` | `[laughs]` |
| `{cue:sigh}` | `[sigh]` | `[sighs]` |
| `{cue:whisper}` | *dropped, warning* | `[whispers]` |
| `{cue:pause}` | *dropped, warning* | `[pause]` |
| any other `{cue:x}` | dropped, warning | dropped, warning |

- **Direction** (the line's `direction` field, e.g. `softer, to himself`) is put in front of the line as `[softer, to himself] <line>` on Drama 3. On OmniVoice it is **dropped** with a warning. `[code]` `targets.py:206-211`
- Anything else in the text, raw engine tags included, reaches the model unchanged. The server never adds a speaker tag, a language or a style.
- Fixed in the graph, and not something you can change: OmniVoice `t_shift 0.1`, `position_temperature 5`, `class_temperature 0`, `layer_penalty 5`, `denoise on`, `preprocess_prompt on`, `postprocess_output on`, clone `instruct ""` (no accent or whisper on clone). Drama 3: `max_frames 600`, `split_long_text on`, `speakers: one take per line`, experts in RAM. `[code]` `workflows/*/workflow-api.json`
- Afterwards the server measures each take's integrated LUFS and true peak. `continuo_voice_match` levels a line's takes against each other. `continuo_voice_take_words` and `continuo_voice_take_recut` re-time pauses without re-speaking (0–10 s per pause). `[code]` `voice/runner.py`, `voice/takecut.py`

**Rule: write performance in the `direction` field and use only the four neutral cues in `text`.** Then the same line works on both engines. Write raw engine syntax only once the target is settled (B3, C3).

### A3. Writing the line itself (both engines)

- Write a line the way it is **spoken**. Use one sentence per thought. Punctuation is your pause control: a comma for a short pause, a period for a full stop, `?` for a rising question, `—` or `…` for a hesitation `[hypothesis: dash/ellipsis effect varies by engine; untested]`.
- **Spell out numbers, dates, units and abbreviations** as they should be said: `twenty to nine`, `three hundred metres`, `Doctor Hale`. OmniVoice reads digits poorly unless text normalisation is on, and the Continuo graph never turns it on. Every digit also inflates its length estimate (weight 3.5 per digit versus 1 per letter). `[official]` OmniVoice README tips; `[local]` `omnivoice/utils/duration.py:39-62`. Drama 3 is better with digits (93.2 % on a pronunciation-robustness benchmark, vendor claim) `[official]` Fish blog, 2026-10-13. Spelled-out words are still the deterministic choice.
- **No quotation marks around the whole line, no screenplay parentheticals, no speaker name prefix.** On Drama 3, text in round parentheses **is spoken**. `[official]` Drama 3 report App. C
- Line breaks: OmniVoice deletes them, so `A\nB` reads as `AB` with no space. Use a space or punctuation instead. `[local]` `omnivoice.py:_combine_text`
- Length: keep one take to one line of dialogue, about 2–20 s. OmniVoice cannot reliably make 1–2 s clips **without a reference** (design mode). `[official]` docs/tips.md, issue #118. Drama 3 cuts text over ~300 UTF-8 bytes into chunks, and each chunk is capped at 600 frames (~28 s). `[local]` `drama3/chunking.py`
- Never write `<|speaker:N|>`, `<|im_start|>` or other `<|…|>` structure tokens. Drama 3 refuses structural ones outright. A speaker tag on this single-voice graph gives a voice that has no reference. `[local]` `drama3/prompt.py:check_text`

### A4. Choosing the clip (the biggest lever on both engines)

Both models **copy the clip's delivery**: timbre, room, pace, energy and emotion. A flat clip gives a flat take. `[maintainer]` ComfyUI-Drama3 README "Settings"; `[community]` Banodoco #ltx_chatter, 2026-05-09 (OmniVoice "can exactly copy the emotion"); `[official]` OmniVoice tips.

1. **3–10 s of one speaker**, clean, dry, no music or effects, no overlap, cut **between sentences**. OmniVoice: over 20 s is trimmed to ≤15 s only when the words are empty. With words given, the full clip is kept and is slower and worse. `[official]` OmniVoice README; `[local]` `omnivoice.py:778-806`
2. **Choose the clip in the register you want.** For a shouted line, use a clip of the actor at raised energy. For a whisper, use a quiet, close clip. A calm clip plus `[shouting]` gives less than an angry clip. `[maintainer]` Drama3 README; `[community]` Morphic guide ("a soft, breathy voice struggles with a shouted command").
3. **Same language as the line.** Otherwise the line carries the clip's accent. `[official]` OmniVoice README
4. **Words must match IN/OUT exactly** (Drama 3 requires them). A transcript that misses the clip's last words is "the most common reason a take falls silent". After every IN/OUT change run `continuo_voice_transcribe`, and never type words you did not hear. `[maintainer]` Drama3 README Quick start tip; `[code]` `agent_tools.py:153`
5. Room noise is less fatal on OmniVoice (its `denoise` token is trained on noisy, reverberant prompts) than on Drama 3, which normalises the clip but does not denoise it. `[official]` OmniVoice paper §2.3.1; `[local]` `drama3/audio.py:tidy_clip`
6. Loudness: OmniVoice scales its output to the clip's RMS when the clip is quiet. Run `continuo_voice_match` before cutting, and do not chase level with re-rolls. `[local]` `omnivoice.py:_post_process_audio`

### A5. Pick the engine per task

| Need | Use |
|---|---|
| Clone, neutral to moderate read, fast, any of 600+ languages, many short lines | OmniVoice clip |
| Acted moment: tears, held anger, laugh through words, whisper on three words, a mid-line turn | Drama 3 clip |
| A voice with no clip yet | OmniVoice description → keep the best take → clone from it (B5) |
| Language outside ~80 major ones | OmniVoice (Drama 3 covers ~80 languages, S2 coverage) `[official]` Drama 3 report §3.1 |
| Exact length to picture | OmniVoice `duration` (C has no length control) |
| Same actor across a scene | either. Use one clip per character, kept fixed (D, V4) |

---

## B. OmniVoice (`omnivoice-clone-v1`, `omnivoice-design-v1`)

### B1. What the model reads

A masked-diffusion LM over audio tokens. Its input is a style prefix (`<|denoise|>`, language `None`, instruct), then `<|text_start|>` + **clip words + " " + your line** + `<|text_end|>`, then the clip's audio tokens and a masked block whose length is **estimated from the clip's words-per-second** divided by `speed`, or fixed by `duration`. `[local]` `omnivoice.py:1220-1258, 1168-1180`. In practice:
- the take's **tempo follows the clip's tempo**, and `speed` scales from there.
- wrong words for the clip give a wrong length estimate and garbled starts. If you are unsure, leave the words empty and Whisper fills them.
- no language is passed (language-agnostic mode). Upstream says a stated language is "slightly better", but Continuo cannot set it. `[official]` `generate()` docstring

### B2. Line grammar

Plain sentences plus inline tags. Only these 13 tags are tokenised as events. `[local]` `omnivoice.py:_NONVERBAL_PATTERN`; `[official]` README:

`[laughter]` `[sigh]` `[confirmation-en]` `[question-en]` `[question-ah]` `[question-oh]` `[question-ei]` `[question-yi]` `[surprise-ah]` `[surprise-oh]` `[surprise-wa]` `[surprise-yo]` `[dissatisfaction-hnn]`

- The suffix names the **sound** (`-ah`, `-oh`, `-hnn`), not a language. `[community]` voicecreator.pro guide, 2026
- `[sniff]` appears in the ComfyUI node README but **not** in the upstream tag list. Do not use it `[local]`.
- Put a tag where the sound belongs: `[sigh] Fine. Take the late ferry.` or `You did what? [laughter] Of course you did.`
- There is **no emotion control** on OmniVoice: no emotion tags and no free directions (the `direction` field is dropped). Emotion comes from the clip and the wording. `[official]` README; `[code]` `targets.py`
- Pronunciation: wrap uppercase CMU ARPAbet in brackets inside the sentence, `the [B EY1 S] guitar`, or pinyin with a tone digit for Chinese (`ZHE2`). Use it for names the model misreads. `[official]` README
- No `<whisper>`, `<emphasis>` or `[anything else]`. Unknown bracket text is plain text and may be **read aloud** `[hypothesis]`.

### B3. Description grammar (`omnivoice-design-v1`)

A **closed vocabulary**, comma-separated, case-insensitive, **at most one item per category**, any order. Anything else fails the take with "Voice description not understood". `[local]` `omnivoice.py:_resolve_instruct`; `[code]` `runner.py:110-161`

| Category | English items |
|---|---|
| gender | `male`, `female` |
| age | `child`, `teenager`, `young adult`, `middle-aged`, `elderly` |
| pitch | `very low pitch`, `low pitch`, `moderate pitch`, `high pitch`, `very high pitch` |
| style | `whisper` |
| accent (English text only) | `american accent`, `british accent`, `australian accent`, `canadian accent`, `indian accent`, `chinese accent`, `korean accent`, `japanese accent`, `portuguese accent`, `russian accent` |
| Chinese dialect (Chinese text only) | 四川话 陕西话 河南话 贵州话 云南话 桂林话 济南话 石家庄话 甘肃话 宁夏话 青岛话 东北话 |

Chinese equivalents exist for gender, age, pitch and style (男/女, 儿童…老年, 极低音调…极高音调, 耳语). Do not mix an accent with a dialect. `[official]` docs/voice-design.md

Traps: `young`, `old`, `medium pitch`, `deep`, `raspy`, `warm`, `gravelly`, `husky`, `sichuan accent`, `german accent` and every adjective are **invalid**. The node's own tooltip lists `young`, `medium` and `sichuan`, and those are wrong too. `[local]` live `/object_info` tooltip vs `_resolve_instruct`. Timbre adjectives cannot be expressed: get them from a clip.

Good: `male, elderly, low pitch, british accent` · `female, young adult, moderate pitch` · `male, middle-aged, very low pitch, american accent` · `female, teenager, high pitch, whisper`
Bad: `gruff old sailor, smoky voice` (fails) · `male, female` (conflict, fails) · `male, german accent` (fails)

Fewer items are more stable. The model may ignore a rare combination, so simplify if the output does not match. `[official]` voice-design.md. Design is trained on Chinese and English only. In other languages it can produce garbage (~10 % in one Bengali report), and clone is more stable. `[official]` README note; `[community]` GitHub issue #186, 2026-06-14

### B4. Clone operation

- Voice = clip + optional words. Leave the words empty unless you have the exact transcript. Whisper (large-v3-turbo, local) then fills them and trims a long clip. `[local]` node `voice_clone_node.py`
- Gender, age, pitch, whisper style, an English accent or a Chinese dialect can be added on top of a clone through the optional values `trait_gender`, `trait_age`, `trait_pitch`, `trait_style`, `trait_accent` and `trait_dialect` (the closed vocabulary of B3; accent and dialect cannot be combined; all empty = the clip's own voice) `[code]`. Upstream: when instruct and clip conflict, the model follows the clip anyway. `[official]` docs/tips.md

### B5. Design → stable cast voice

A description gives a **different speaker per seed**. A fixed seed with a different line is not guaranteed to keep the voice `[hypothesis]`. Upstream does the same for long text: it generates chunk 0 and then **clones every later chunk from chunk 0**. `[local]` `omnivoice.py:999-1019`. So:
1. Design a 6–10 s neutral sentence (`Most nights the last ferry leaves on time, and nobody waits for it.`) with 4–8 seeds.
2. The artist keeps one take.
3. Make that take a clip voice (artist-approved import) and speak every line from it on `omnivoice-clone-v1` or `drama3-clone-v1` (words: transcribe).

### B6. Parameters (Continuo controls)

| Control | Range | House default | Upstream default | Effect |
|---|---|---|---|---|
| seed | 1–2³¹ | 4711 | 0 = random | new take; 0 is excluded so takes are repeatable |
| speed | 0.5–2.0 | **0.9** (house) | 1.0 | scales the **estimated length**, so the model fills more or less time. It is not a time-stretch |
| duration | 0–60 s (0 = free) | 0 | none | fixes the length and overrides speed. Post-processing may trim trailing silence, so the take can come out slightly short `[official]` generation-parameters.md |
| guidance_scale | 0–10 | 2.0 | 2.0 (paper) | higher = tighter to text and voice, eventually harsher `[hypothesis]`. Keep 1.5–3 |
| steps | 4–64 | **64** (house) | 32 | 16 fast, 32 balanced, 64 best per node docs. Costs time, gives small gains |

Fixed `postprocess_output` removes inner silences longer than 0.5 s (keeping ~0.5 s on each side), so **written pauses top out around 1 s**. Make longer pauses with `continuo_voice_take_recut` (needs `continuo_voice_take_words` first). `[local]` `omnivoice.py:_post_process_audio`, `utils/audio.py:remove_silence`

---

## C. Drama 3 (`drama3-clone-v1`)

### C1. What the model reads

A 35B MoE (3B active) speech LM. The system turn holds `[Reference 1] Text: <|speaker:0|> <words> Speech: <clip codes>`, the user turn holds `<|speaker:0|> <your line>`, and the assistant answers in audio. The node adds the speaker tag. `[local]` `drama3/prompt.py`; `[official]` report App. B Fig. 11–12. Trained by RL against a learned human-preference reward that **rewards following the written direction**, so whispered and laughing reads are not pulled back to neutral. `[official]` report §3.3, §5.2

### C2. Direction syntax (free language, not a fixed list)

All of these are plain text. Any wording works, and words close to Fish's examples work best. `[official]` report App. C Table 10; `[maintainer]` vLLM-Omni recipe

| Control | Form | Example |
|---|---|---|
| Style prefix (whole line) | `[note] line`, which is what Continuo's `direction` field produces | `[icy calm, as if she already accepted it] So this is goodbye.` |
| Mid-line turn | a new `[note]` where the mood changes | `[bright, showing off] And this is the galley. [stopping short, alarmed] Is that water?` |
| Point tag (event) | `[event]` at the spot | `[sighs]` `[laughs]` `[pause]` `[gasps]` `[clears throat]` `[hesitates]` `[shaky breath]` `[small laugh]` |
| Scoped tag (only these words) | `<tag>words</tag>` | `Promise me <whisper>you won't tell her</whisper>.` |
| Director's note | `Direction: …` new line `Line: …` | `Direction: tired, kind, he has said this a hundred times.`<br>`Line: Tickets are at the window.` |
| Language hint (not spoken) | `[language: xx]` after the line | `Welcome aboard. [language: en]` |

Scoped tags documented by Fish: `<whisper>` `<emphasis>` `<soft>` `<fast>` `<slow>` `<stress>` `<forceful>`. `[official]` Fish docs drama-3.mdx. Those docs describe the hosted API, so local support for `<soft>`, `<fast>`, `<stress>` and `<forceful>` is assumed, not measured `[hypothesis]`.

How to write a direction (Fish's own advice): brief it like an actor. Name the **feeling and what is under it**, the **situation or listener**, and the pacing: `[cheerful, but hiding that she is worried]`, `[quietly, so the kids next door don't hear]`. Put a sound **after its cause**: `That's the third time. [sighs] Fine.` A direction may be in another language than the line. `[official]` Fish docs; `[community]` Morphic guide, 2026

Do not use these here:
- **Relative notes** (`[softer than before]`, `Direction: less angry than the last take`) need the earlier take in the prompt, and Continuo does not send it. `[maintainer]` Drama3 README
- **Scene dubbing from text descriptions, multi-speaker tags, infill.** These are not wired.
- **Phoneme tags** `<|phoneme_start|>EH1 N JH AH0 N IH0 R<|phoneme_end|>` are documented for the hosted API. The tokens exist in the local tokenizer, but local behaviour is untested `[hypothesis]`.

### C3. Continuo specifics

- Your `direction` field becomes the style prefix `[direction]` at line start. Write it **without brackets** (the server strips them) and do not repeat it in the text.
- The neutral cue `{cue:whisper}` becomes the point tag `[whispers]`. To whisper only a few words, write `<whisper>…</whisper>` in the text on Drama 3. That is non-portable, so do it only once the target is fixed.
- **Risk at line start.** A tag, filler or pause as the very first thing in a line more often gives the first word and then silence. `[maintainer]` vLLM-Omni recipe "Known limitations"; `[maintainer]` Drama3 README (a line that opens with `[long pause]` can stay silent). Prefer the tag after the first words (`Fine. [sighs] …`). Keep style prefixes short. Re-roll seeds rather than piling tags.
- `shorten_long_pauses` (on by default) cuts every pause over 0.75 s to 0.75 s, so a written `[pause]` or `[long pause]` is clamped. Turn it **off** for a held beat, or re-time afterwards with `continuo_voice_take_recut`. `[local]` `nodes.py:43, 374-387`
- The clip is edge-trimmed and peak-normalised before encoding. `[local]` `drama3/audio.py`

### C4. Parameters (Continuo controls)

| Control | Range | Default | Effect |
|---|---|---|---|
| seed | 0–2³¹ | 4711 | new take. Chunk *i* uses seed+i |
| temperature | 0–2 | 1.0 | lower = slower, flatter, **more silent takes** |
| top_p | 0.05–1 | 0.9 | keep ≥0.9 |
| top_k | 0–4096 | 0 (no cap) | **keep 0.** top_k 30 left 11 of 40 takes silent in Fish's test |
| shorten_long_pauses | on/off | on | see C3 |

Sources: `[maintainer]` Drama3 README "Settings", `nodes.py:212-218`. Conflict: Fish's paper evaluated at temperature 0.7 / top-p 0.7 / top-k 30 and its servers default to top_k 30 `[official]` report §5.1, model card. The node maintainer and Fish's own Space use 1.0 / 0.9 / 0. Stay on the Continuo defaults. The paper's numbers also re-generated failed takes.

### C5. Failure behaviour you must plan for

Drama 3 sometimes **falls silent mid-take** or drops a sentence. That is a model trait, not a Continuo bug. `[maintainer]` ComfyUI-Drama3 author, Banodoco #fishaudio-drama-3, 2026-10-14/16: "this generated 50 seconds and stayed silent after 12", "the silence is an inherent issue with the model". The node retries once if the first 2.5 s never come. Always ask for **3–4 seeds per line**, and check each take's length and words (`continuo_voice_take_words`) before you call it done.

---

## D. Film tasks

**V1 — a line in a cast voice (clone).**
Clip: 5–8 s of the actor in the scene's register, words transcribed. OmniVoice for neutral lines, Drama 3 for acted ones. Example (Drama 3), voice "Deckhand" from a tired, low clip:
- text: `We tie off at the second post, not the first. {cue:sigh} Every night I say it.`
- direction: `weary, patient, talking to a new hand who isn't listening`
- count 4, defaults. Sent: `[weary, patient, talking to a new hand who isn't listening] We tie off at the second post, not the first. [sighs] Every night I say it.`

**V2 — a new voice from a description.**
`omnivoice-design-v1`, description `female, middle-aged, low pitch, british accent`, text `The rooms are cash only, and checkout is at ten.`, count 6. The artist keeps one take, then promote it to a clip voice (B5). Never send adjectives.

**V3 — performance control.**
- *Emotion*: Drama 3 direction (`[choked up, trying not to cry]`). On OmniVoice choose a clip that already carries it.
- *Pace*: OmniVoice `speed` (0.85 slow, 1.1 brisk) or `duration`. On Drama 3 use direction words (`[slow, deliberate]`, `<fast>…</fast>`).
- *Pauses*: punctuation first. Then `{cue:pause}` (Drama 3), then `continuo_voice_take_recut` for exact lengths in the cut.
- *Whisper / shout*: Drama 3 `<whisper>…</whisper>` or a `[shouting over the engine]` direction. On OmniVoice, use a whisper-register clip, `trait_style: whisper` on a clone, or a `whisper` description on design voices.
- *Non-verbal*: OmniVoice only its 13 tags. On Drama 3 any short event (`[clears throat]`, `[sharp inhale]`).
Worked example (Drama 3): text `I checked the manifest twice. <emphasis>Twice.</emphasis> {cue:pause} And there's still a crate nobody signed for.`, direction `controlled, quietly furious, keeping her voice down so the passengers don't hear`.

**V4 — multi-speaker dialogue continuity.**
Every line is its own take, and lines do not hear each other. Continuity comes from:
1. one fixed clip per character for the whole scene (do not change IN/OUT mid-scene).
2. one engine per character per scene. OmniVoice and Drama 3 renditions of the same clip differ in timbre and band (24 vs 44.1 kHz).
3. directions that state the reaction (`[cutting him off]`, `[answering too fast]`), because the model cannot hear the previous line.
4. `continuo_voice_match`, then place takes with `continuo_voice_take_to_cut`. Make overlaps and gaps in the cut, not in the text.
For a character who must sound different in a later scene (shouting on deck), make a second clip voice of the same actor in that register. Do not stack directions on a calm clip.

**V5 — language / accent.**
OmniVoice: write the line in its language. A same-language clip gives native pronunciation, and a foreign clip gives an accent (useful for a tourist character). Design accents apply to English text only. Min Nan needs Tai-lo romanisation. `[official]` tips.md. Drama 3: ~80 languages, a direction may be in English over a line in another language, `[language: xx]` is a hint, and `<french>…</french>`-style mid-line switches are experimental API features `[hypothesis locally]`.
Example (OmniVoice clone, Spanish clip): `El último ferry sale a las nueve y media, ni un minuto más tarde.`

**V6 — repair a single word or breath.**
Neither target can infill. Re-speak the **whole line** with the corrected text and 4 seeds, pick the take whose rhythm matches, and cut the word or phrase in the Cut at a pause. For a misread name, use CMU brackets on OmniVoice (`[K AE1 S P ER0]`) or spell it phonetically (`Cass-per`) on Drama 3. Remove or lengthen breaths and gaps with `continuo_voice_take_recut`. It cuts only inside pauses and never touches a word.

---

## E. Failure → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| "Voice description not understood" | adjective or unlisted item in the description | use only B3 words, one per category |
| Warning "has no whisper/pause cue" or "does not read directions" | OmniVoice target | change the clip/wording, or move the line to Drama 3 |
| Drama 3 take goes silent after a few seconds / drops a sentence | model trait; words not matching the clip; tag at line start; top_k > 0; low temperature | re-roll seeds; re-transcribe the clip; move the tag after the first words; top_k 0, temp 1.0 |
| Drama 3 take speaks the direction aloud | malformed brackets, round parentheses, a direction split from its line by chunking (>300 bytes) | square brackets only; keep the line under ~300 bytes |
| Flat, lifeless read | flat clip (both); Drama 3 with low temperature | choose a livelier clip stretch; temperature 1.0 |
| OmniVoice garbled first words / wrong pace | wrong clip words; clip over 20 s with words given | empty the words (Whisper) or fix them; trim the clip to 3–10 s |
| OmniVoice reads `2045` digit by digit | no text normalisation | write `twenty forty-five` |
| OmniVoice design gives noise on a short line | design mode cannot do 1–2 s | lengthen the line, or clone from a designed take |
| Designed voice changes between lines | design samples a speaker per take | B5: promote one take to a clip voice |
| Long pause collapses to ~1 s / 0.75 s | silence post-processing | `continuo_voice_take_recut`; on Drama 3 turn `shorten_long_pauses` off |
| Wrong accent | foreign-language clip (OmniVoice) | same-language clip |
| Tag read as words (`sniff`) | tag not in OmniVoice's list | use only the 13 tags |

---

## F. Sources (accessed 2026-11-12)

- `[code]` Continuo 9f7510c0: `backend/film-suite/dashboard/voice/{targets,runner,store,takecut,asr}.py`, `routes/voice/voice_1.py`, `agent_tools.py:152-180`, `dashboard/generation/model_catalog.v1.json` (families omnivoice, drama3), `workflows/{omnivoice-clone-v1,omnivoice-design-v1,drama3-clone-v1}/`.
- `[local]` omnivoice 0.2.1 package (`models/omnivoice.py`, `utils/{voice_design,text,audio,duration}.py`). ComfyUI-OmniVoice-TTS 0.4.7 (commit 3fe8e42, 2026-06-11) README and nodes, live `/object_info`. ComfyUI-Drama3 (commit d74b74f, 2026-10-20) README, `nodes.py`, `drama3/{prompt,chunking,audio,generate}.py`.
- `[official]` github.com/k2-fsa/OmniVoice README; docs/tips.md, voice-design.md, generation-parameters.md, languages.md; arXiv 2604.00688; HF k2-fsa/OmniVoice; issues #118, #186.
- `[official]` Fish Audio Drama 3 Technical Report (fish-speech repo, docs/assets PDF; App. B–C, §3.2–3.3, §5.1–5.2); HF fishaudio/drama-3; docs.fish.audio Drama 3 page (fishaudio/docs drama-3.mdx); fish.audio blog 2026-10-13.
- `[maintainer]` SGLang-Omni Drama 3 cookbook; vLLM-Omni recipe fishaudio/drama-3 (serving-framework maintainers).
- `[maintainer]` ComfyUI-Drama3 README (github.com/PedroMarinhoDev/ComfyUI-Drama3); the node author in Banodoco #fishaudio-drama-3, 2026-10-14 and 2026-10-16.
- `[community]` Banodoco #ltx_chatter 2026-05-09; voicecreator.pro OmniVoice voice-design guide; morphic.com Drama 3 prompt guide; k2-fsa/OmniVoice issue #186 (2026-06-14); r/LocalLLaMA Drama 3 local-app thread (~2026-10-24, Whisper-checked takes).
