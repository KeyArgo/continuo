# Music models in Continuo: SA3 Small Music, YuE2 Song, Foundation-1 Loop

Load this page before you call `continuo_music_gen_generate`. It covers three local targets. Each one wants a different kind of prompt, and the server already writes part of each prompt. Generate only when the artist asks: every take uses the local GPU.

| Target id | Engine | Use it for | Prompt you write |
|---|---|---|---|
| `sa3-small-music-v1` | Stable Audio 3 Small Music | Instrumental score cues and beds of 1–120 s | One descriptive sentence |
| `yue2-song-v1` | YuE2-3B (int8) | Songs with sung lyrics, and source music with vocals | Style tags + lyrics with `[Section]` tags; the ABC score is editable |
| `foundation1-loop-v1` | Foundation-1.2 Samples / Keybeds | 4- or 8-bar loops that land exactly on the bar grid; six-note instrument chunks | Comma-separated tags in separate fields |

Evidence tags: `[code]` Continuo source, `[local]` ComfyUI node source, `[official]` model authors, `[maintainer]` tool author, `[community]` practitioner reports, `[hypothesis]` not yet tested. The sources are listed in §8.

---

## 1. Scope

**SA3 Small Music** (`stable_audio_3_small_music.safetensors` with the `t5gemma_b_b_ul2` encoder) is the adversarially post-trained 433M "small-music" model. It makes instrumental music only and can run up to 120 s `[official]`. It was trained on AudioSparx music metadata `[official]`. Small Music handles full mixes and stems; sound effects belong to a different checkpoint (small-sfx), which Continuo does not ship `[official]`. Do not use it for:
- intelligible vocals (at most it produces "non-lexical vocal-like textures") `[official]`;
- sound effects;
- an exact key [local measurement, hypothesis-grade].

**YuE2** (`yue2_3b_int8_convrot.safetensors`, the Comfy-Org int8 repack of m-a-p/YuE2-3B) generates complete songs with vocals and accompaniment from a style prompt and lyrics. It first writes an editable ABC score (melody, chords, tempo, key, form), then renders the audio from that score `[official]`. Do not use it for:
- reliable instrumentals (vocals leak; see §4.2);
- an exact length (the model decides; Continuo can only trim);
- voice cloning or a reference singer (YuE2 has no input for either) `[official]`.

**Foundation-1** is a fine-tune of Stable Audio Open (t5-base encoder) trained on hand-labelled production loops `[official]`. Continuo runs two of its checkpoints:
- `Foundation-1.2-Samples` for loops;
- `Foundation-1.2-Keybeds` for six-note pitched instrument chunks.

Do not use it for:
- full songs, drums or "genre" captions; the authors say it was "not designed as a full song generator, a drum generator, or a general-purpose music captioning model" `[official]`;
- tempos outside the trained grid (§6).

---

## 2. What Continuo sends (never duplicate it)

All three targets end in an `AudioAdjustVolume −6 dB` stage, so each file has 6 dB of headroom. Do not ask for it in the prompt. Takes go to a temporary location and are then copied into the project `[code]`. The settings are pinned per target: the agent cannot change steps, CFG or the sampler. Every control is listed in `continuo_music_gen_targets`.

### SA3: the server wraps your sentence

```
TrackType: Music, VocalType: Instrumental, <your prompt, trailing period removed>, <key if set>. BPM: <bpm>.
```
[code `music_gen/targets.py` `_slots`]

- **Controls:**
  - `prompt`: text, ≤600 characters, required;
  - `length`: whole seconds, 1–120, default 30. A fraction is refused (`length_whole_seconds`);
  - `bpm`: 40–220, default 100;
  - `key`: "" (default) or one of 24 major/minor keys; a hint the model does not always follow;
  - `track_type`: `Music` (default) or `Instrument`;
  - `seed`.
- **Pinned:** 8 steps, CFG 1.0, `lcm`/`simple`, empty negative. The latent is `length` seconds long and is trimmed to exactly `length` `[code]`. This is the ComfyUI template, not the author's own pingpong schedule. Same-seed listening tests found no gain from the author schedule `[local]`.
- **So never write:**
  - `TrackType`, `VocalType`, `BPM`, a key or a length in the sentence;
  - a negative prompt. At CFG 1 a negative prompt has no effect, and the authors state that `negative_prompt` and `cfg_scale` "have no effect on post-trained checkpoints" `[official]`.
- `track_type: Instrument` sends the official stem tag (`TrackType: Instrument`) for a solo stem; `Music` sends the line above (§4.1) `[code]`.

### YuE2: two graphs, with the score passed between them as text

The native node builds the prompt like this [local `comfy/text_encoders/yue2.py`]:
```
<instruction for mode>\n[Tags]\n<your style>\n[Lyrics]\n<your lyrics>\n
```

- **Mode is always `full`** (melody and chord planning) `[code]`. Continuo does not expose `melody` or `off`.
- **Stages** (`stages`, default `both`):
  - `notes` runs only `YuE2GenerateABC` and returns the ABC score as editable text on the take;
  - `song` renders from `values.notes`, or from `notes_from: <take id>`;
  - `both` runs `notes` and then `song` `[code]`.
- **Controls:**
  - `prompt` (Style, ≤600 characters, required);
  - `lyrics` (≤8000 characters; empty = instrumental, and the take carries a warning);
  - `notes` (ABC, ≤40000 characters);
  - `length`: whole seconds, 0 = the model's own length. A non-zero value trims the song with a hard cut and no fade;
  - `max_length`: generation budget in seconds, default 360, up to 900;
  - `seed`: drives both the score and the semantic tokens; the diffusion sampler seed is pinned to 42 `[code]`.
- **Pinned to the authors' preset** [code, official `yue2_generation_config.json`]:
  - score: temperature 0.7, top-p 0.9, top-k 30, repetition penalty 1.005, `max_abc_tokens 4096`;
  - semantic tokens: 1.0 / 0.95 / 100 / 1.2;
  - 32 steps `dpm_2`/`sgm_uniform`, CFG 1 (no text guidance).

### Foundation-1: the server assembles the tag string

The loop graph sends `[code]`:
```
<instrument>, <timbre>, <Wet|Dry>, <fx>, <key>, <bars> Bars, <bpm> BPM
```

The keybed graph (when `keybed: true`) sends `[code]`:
```
Keybed, Sequence, Timbre Profile, <instrument>, <timbre>, <Wet|Dry>, <fx>, Chromatic Chunk, Note Sequence, <note+1 octave>, …
```

- **Controls:**
  - `instrument`: ≤120 characters, required;
  - `timbre`: ≤200 characters;
  - `fx`: ≤200 characters;
  - `wet`: Wet (default) or Dry;
  - `key`: 24 keys, default C minor;
  - `bpm`: 40–200, default 100; outside the trained 100–150 the take carries a warning, nothing is clamped;
  - `bars`: 4 or 8;
  - `keybed`: boolean;
  - `notes`: 1–16 names such as `C4 F#3`;
  - `seed`.
- **Loop length:** exactly `bars × 4 × 60 / bpm` seconds. The trim is sample-exact; the latent is 0.05 s longer `[code]`.
- **Loop sampler:** 250 steps, CFG 7, `dpmpp_3m_sde`/`exponential`.
- **Keybed:** 80 steps, CFG 6. The length follows the notes: 3.0 s per note plus 0.25 s gaps, so six notes give 19.25 s, the author's chunk `[code, maintainer]`. `Chromatic Chunk` is sent only for six rising semitones; any other selection goes out as `Note Sequence` alone and the take carries the warning `keybed_untrained` `[code]`.
- **Keybed octave:** the server writes each keybed note one octave higher, because Keybeds sounds an octave low `[code, measured]`. Write the pitch you want to hear.
- **On Dry the server drops `fx`** from the prompt, as the author's tool does [code, maintainer].
- **The server does not:**
  - give musical-behaviour tags (Arp, Melody, Chord Progression…) a field of their own. Put them in `timbre` (§3.3).

---

## 3. Grammar

### 3.1 SA3: one natural sentence, written the way the authors' Prompt Assistant writes it

The Prompt Assistant is the authors' own rewriter, which ships in the SA3 Gradio UI [official `reprompt.py`]. Its "Music" template is:

> Genre/Style with main instruments, supporting instruments/layers, and rhythm/percussion creating mood/energy. BPM: X.

Its rules: start with the genre and optional adjectives, then list the main instruments, supporting layers, then rhythm and percussion, and fold mood and energy into the sentence. Use "one natural, fluid sentence. Avoid semicolons." The assistant rejects its own output if it has more than **45 words**, contains brackets, `*` or `#`, or matches its vocal-word filter `[official]`.

Write the sentence without the BPM (the server adds it). Copy-ready examples:

```
Melancholic piano piece with soft felt piano lead, sustained string pads, subtle atmospheric synth drones and minimal brushed percussion evoking a quiet rainy-night reflection
```
```
Suspenseful electronic thriller cue with pulsing analog bass synth, arpeggiated lead, low cinematic pads, glitchy percussion and high string stabs creating dark, tense energy
```

- **Order:** genre/style → instruments → layers → rhythm → mood. The official guide also suggests that "you can describe the context in which you'd hear the music", for example "for the final scene of a slow-burning sci-fi film" `[official]`. That suits film cues.
- **Era, place and recording style help:** "90s garage rock…", "Detroit-influenced techno…", "live-recorded in a vintage studio", "warm analogue tape" `[official]`.
- **Training captions** were AudioSparx metadata fields joined with commas, with field names such as `Instruments: Guitar, Drums` or `Genre: Funk` prepended half the time, and lowercased half the time [official tech report]. That makes `Genre: X` and `Instruments: A, B, C` valid in-distribution fragments inside your text. The authors list them as "Helpful AudioSparx Tags" `[official]`.
- **Forbidden words:** the assistant's filter rejects `vocal(s)`, `singing`, `singer`, `female`, `male`, `voice(s)`, `chorus`, `rap`, `rapper`, `chant(ing)`, `lyric(s)` [official `_VOCAL_RE`]. The prefix already says `VocalType: Instrumental`. "Chorus" counts too: for the effect write "chorused guitar" [hypothesis that this escapes the problem], and for the song section describe "the lift" or "the main theme".
- **Length:** 15–45 words. Past about 256 text tokens (roughly 1,000 characters) the model saw only truncated text in training `[official]`. Continuo's 600-character cap keeps you inside that.
- **Text rendering, weights, negatives:** none apply. Parentheses and `:1.3` weights are not part of this grammar.

### 3.2 YuE2: style tags plus clean sectioned lyrics

**Style.** Write a comma-separated tag line in this order: language → genre → vocal character → tempo → instruments → arrangement/mood/production [official ComfyUI guide and repo examples]. The authors' own examples:

```
English, warm piano pop, expressive female voice, acoustic piano, rounded bass and light drums, lyrical memorable melody, unhurried phrasing, 88 BPM
```
```
Jazz, expressive lead vocal, piano, tenor saxophone, upright bass, brushed drums, no guitar, spacious modern harmony
```

- Prose styles also occur in the official examples (a 70-word synthwave paragraph) `[official]`. Tags are the documented default.
- `no <instrument>` appears in the authors' examples `[official]`, but it is a request, not a guarantee `[official]`.
- **Always name the vocal.** Community reports say the model "has a bias for only using a small set of voices", so you cannot steer far from its standard female and male voices `[community]`.
- **The tempo and key in the style are hints.** The score decides them (§4.2).

**Lyrics.** Put only section tags and sung words in this field `[official]`:
- a single section tag per line: `[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Interlude]`, `[Outro]` [official examples];
- a blank line between sections;
- an empty `[Intro]`/`[Interlude]` asks for an instrumental passage [official example `tonight-awake.json`];
- write every repeated chorus out in full; shorthand like "x2" gets sung `[community, consistent with official "only the words intended to be sung"]`;
- use 4–6 lines per section `[community]`; each section takes roughly 10–30 s `[community]`;
- keep the language of the lyrics the same as the language tag in the style. English and Mandarin are the core languages; Japanese and others are reported weaker `[community]`;
- no titles, no `(repeat)` and no stage directions in parentheses.

Bracketed performance notes (`[Soft breath; intimate]`) are a **community** trick that some users report works. The authors say to keep implementation notes out of the lyrics `[official]`. Use them sparingly and test.

**Notes (ABC).** The model's native score dialect [official `abc-editing.md`]:

```abc
X:1
T:
M:4/4
L:1/32
Q:1/4=88
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:G
% verse
V: Vocal
"Gmaj7"B8d8"Am7"c8A8|"D7"F16"G"G16|
V: Ins
Z2|
```

- The header sets:
  - `Q:` the tempo (quarter-note BPM);
  - `K:` the key;
  - `M:` the meter;
  - `L:` the unit. With `L:1/32`, `C8` is a quarter note.
- Two voices only: `Vocal` carries the sung melody and the chord symbols; `Ins` carries an instrumental melody line.
- `Z`/`Z2` are whole-bar rests, `z8` is a quarter-note rest, and `% chorus` comments mark the form.
- Native chord suffixes: none (major), `m`, `dim`, `aug`, `7`, `maj7`, `m7`, `dim7`, `m7b5`, `sus4`, `sus2`, `6`, `m6`, `7sus4`, `m(maj7)`. Slash basses are allowed (`F#m7/C#`).
- Not native: tuplets, grace notes, repeats, `w:` lyric lines, `Cmaj9`.
- Keep the exported `L:` value, and tie notes across chord changes (`"C"E16-"Am7"E16`) `[official]`.

### 3.3 Foundation-1: tags from the trained vocabulary

The model card's layered order `[official]`:

```
[Instrument Family / Sub-Family], [Timbre], [Musical Behavior / Notation], [FX], [Key], [Bars], [BPM]
```

Fill Continuo's fields so that the assembled string matches this order:

| Field | Put here | Vocabulary [official tag sheet, maintainer prompt code] |
|---|---|---|
| `instrument` | 1–2 instrument tags, family first if you like | Synth Lead, Pad, Pluck, Supersaw, FM Synth, Wavetable Bass, Reese Bass, Sub Bass, Grand Piano, Rhodes Piano, Felt Piano, Digital Piano, Church Organ, Violin, Cello, Digital Strings, Marimba, Vibraphone, Kalimba, Bell, Flute, Pan Flute, Clarinet, Trumpet, French Horn, Brass, Acoustic Guitar, Nylon Guitar, Electric Guitar, Harp, Koto, Choir, Music Box… |
| `timbre` | timbre, then space, then **musical behaviour** | Warm, Dark, Bright, Airy, Thick, Gritty, Clean, Soft, Silky, Woody, Glassy, Metallic, Hollow, Breathy, Wide, Near, Intimate, Spacey, Analog, Vintage, Retro… then behaviour: Melody, Arp, Chord Progression, Bassline (bass only), Sustained, Rolling, Rising, Falling, Simple, Complex, Catchy, Epic, Triplets, Off Beat, Strummed, Slow Speed, Fast Speed |
| `wet` | Wet when you want FX tags, Dry for a clean source | Wet / Dry |
| `fx` | Only with Wet; one or two | Low/Medium/High Reverb, Plate Reverb, Low/Medium/High Delay, Ping Pong Delay, Stereo Delay, Cross Delay, Low/Medium/High Distortion, Phaser, Low/Medium/High Phaser, Bitcrush |
| `key`, `bars`, `bpm` | controls | — |

- **Author guidance:** "Use FX and timbre tags sparingly at first, then layer more" `[official]`. Wet prompts in the author's generator get one FX tag, and a second only 25 % of the time `[maintainer]`. In his examples Dry loops carry no FX tags [maintainer `amend_prompt`].
- **Only tags.** Write no sentences, genre names or mood prose: the training captions were tags only `[official]`.
- A worked loop, as the model receives it:

```
Rhodes Piano, Warm, Soft, Intimate, Vintage, Chord Progression, Simple, Wet, Low Reverb, A minor, 8 Bars, 100 BPM
```

---

## 4. Per operation

### 4.1 SA3: text to music (the only mode)

Continuo exposes text-to-audio only. SA3's inpainting, continuation and audio-to-audio modes are not wired in `[code]`. For a solo stem, describe one instrument and its playing and recording, and avoid ensemble words:

```
Solo nylon-string guitar playing a slow fingerpicked motif with natural room resonance, close-miked and intimate, sparse and unhurried
```

Set `track_type: Instrument` so the prefix asks for a stem. Accompaniment can still appear now and then `[hypothesis]`. Run two or three seeds (`count` up to 4).

### 4.2 YuE2: notes → edit → song

This loop is the precision tool:

1. **Plan.** Call `stages: "notes"` with style and lyrics, and read the ABC from `continuo_music_gen_takes`. Check:
   - `Q:` (tempo) and `K:` (key);
   - the `% section` comments against your lyric sections;
   - the bar count.
2. **Edit**, keeping the dialect (§3.2). The score controls:
   - tempo and key: tested by the authors, the rendered audio matches the score's key in 93 % of cases and its tempo within 8 % in 98.7 % [official paper];
   - form and melody;
   - harmony.

   The style text does not reliably set tempo or key: in one local test a plan picked E♭ major at 92 BPM for a "D minor, 96 BPM" style [local measurement].
3. **Render.** Call `stages: "song"` with `notes_from: <the notes take id>` (or `values.notes`), using the same style and lyrics. Keep the seed when you want to change only what you edited `[official: "keeps the lyrics and seed"]`.
4. **Iterate on the seed, not the settings.** A new seed changes the melody and timing `[community]`. The authors' benchmark lead comes from best-of-2 and best-of-8 selection `[official]`, so use `count` 2–4 and keep the best.

**Changing words without a new melody:** keep the score and change the lyrics. Matching syllable counts per line keeps them aligned. "If the syllables don't match, the lyrics get mangled" `[community]`. When you change language, adapt the lines for singing (stress, vowels on long notes) rather than translating word for word `[official]`.

**Instrumental (no voice) – best effort:**
- **Official route:** keep the YuE2 plan, move every Vocal note into `Ins`, and leave the lyrics empty or as section names [official instrumental skill]. In Continuo the lyrics must not be empty, so send section tags only.
- **Edit:** in every `V: Vocal` block replace the notes with rests and keep the chord symbols on the rests, for example `"Am7"z32|`. Copy the melody into `V: Ins` where `Ins` is resting `[official]`.
- **Style:** list instruments only, with no vocal words. A community recipe that some users report works: start with `instrumental`, end with `no singing, no spoken voice, no vocal samples` `[community]`. Others report that "the vocals come through in some tracks" `[community]`.
- **Check:** listen to every take, or split stems with `continuo_audio_stems_start` (vocals_rest) and check the vocal stem level. For a guaranteed instrumental, use SA3 instead.

### 4.3 Foundation-1: loop

One request makes one loop of exactly 4 or 8 bars.
- **Tempo:** stay on the author's trained grid **100, 110, 120, 128, 130, 140, 150 BPM** [maintainer UI list, community guide].
- **Length:** keep `bars × 240 / bpm` ≤ 20 s, which is the training sample length of about 20 s `[official]`. 8 bars needs ≥ 96 BPM; 4 bars works down to 48 BPM, but tempos under 100 are outside the trained grid.

The authors warn that when the duration does not match the implied musical structure, "the model may produce less coherent musical phrases" `[official]`.

**Same sound, new phrase:** the same prompt with a new seed keeps the timbre and varies the notes [official "One Prompt → Multiple Outputs"]. Use `count` 2–4.

### 4.4 Foundation-1: keybed (pitched chunk)

`keybed: true` with six `notes` produces one 19.25 s file: six notes of 3.0 s each, starting at 0, 3.25, 6.5, 9.75, 13.0 and 16.25 s `[code, maintainer]`.
- Prefer **six rising semitones** (e.g. `C4 C#4 D4 D#4 E4 F4`): that is the trained `Chromatic Chunk`. Any other 1-16 notes are sent as a plain note sequence with a length to match (3.0 s per note plus 0.25 s gaps), and the take carries `keybed_untrained`: how well the model holds such a sequence is untested `[code]`.
- Use sharps, within C2–B5 [maintainer default range].
- `key`, `bpm` and `bars` are ignored.
- **The descriptor is the instrument.** Use the author's short form `[official]`, for example:
  - `instrument: Grand Piano`, `timbre: Warm, Gritty`, `wet: Wet`, `fx: Low Reverb`;
  - waveforms: `instrument: Pure Tone`, `timbre: Triangle`, `wet: Dry`.
- Reuse one seed across chunks so the instrument stays the same across its range `[maintainer: the tool "reuses the same resolved seed across generation chunks"]`.

---

---
Film-task recipes (M1-M5), parameters, failure modes and sources: `skill_view('film-suite:music-prompts', 'references/ref-music-film-tasks.md')`.
