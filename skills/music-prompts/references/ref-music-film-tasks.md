# Music models in Continuo: film tasks, parameters, failures

Load this with `skill_view('film-suite:music-prompts', 'references/ref-music.md')` (what the server sends and the grammar of each target). Evidence tags as in that file.

## 5. Film tasks

### M1 Score cue to picture (mood, tempo, length)

**SA3** is the default.
- Set `length` to the cue length in whole seconds (the server trims exactly).
- Set `bpm` to match the edit pace.
- Leave `key` empty unless the cue must sit against other music (key adherence is weak).
- Describe the scene context in the sentence.

```json
{"target_id":"sa3-small-music-v1","count":3,"values":{
 "prompt":"Sparse ambient underscore for a lonely night ferry crossing, with low bowed cello drones, distant felt piano notes, soft granular textures and a slow heartbeat-like pulse creating quiet, uneasy tension",
 "length":48,"bpm":64}}
```

- Long cues: past about 119 s the end may drift into silence `[local, hypothesis-grade]`. Generate 2–3 shorter cues instead and join them on the cut.
- For a rising cue, say so in the sentence ("building from a single cello to full strings and timpani by the end"). Duration conditioning lets the model plan an arc over the given length `[official: "choose a duration that fits what you're describing"; arc control is a hypothesis]`.

### M2 Song with lyrics (source music, a radio in the scene, end credits)

**YuE2**, in two stages:

```json
{"target_id":"yue2-song-v1","values":{"stages":"notes",
 "prompt":"English, 1970s roadside country ballad, weathered male vocal, pedal steel guitar, acoustic guitar, upright bass, brushed drums, warm tape sound, 76 BPM",
 "lyrics":"[Intro]\n\n[Verse]\nNeon sign is humming at the desert motel\nOne light left burning where the highway fell\nI paid for the night with a borrowed name\nThe ice machine is singing it all the same\n\n[Chorus]\nRoom number nine, the door won't lock\nI keep on staring at a stopped clock\nYou said you'd come before the morning sun\nI'm still awake and the night's not done\n\n[Outro]\nI'm still awake and the night's not done"}}
```
Read the notes, check `Q:1/4=76` and the section order, then render with `{"stages":"song","notes_from":"<take>"}`, with style and lyrics unchanged and `count` 2.

### M3 Loop / stem for the cut

- **Foundation-1 loop** for a pitched musical layer (bass line, arp, pad, plucked motif):

```json
{"target_id":"foundation1-loop-v1","count":3,"values":{
 "instrument":"Sub Bass","timbre":"Deep, Warm, Round, Bassline, Simple, Rolling",
 "wet":"Dry","fx":"","key":"D minor","bars":8,"bpm":120}}
```
That gives exactly 16.0 s. Stack two or three loops in the same key and tempo: the author notes that single layers sound thin until they are layered `[community, via author]`.
- **SA3** for a stem that is not pitched (percussion bed, textures):

```
Solo cinematic percussion loop with deep taiko hits on the downbeat, rolling low toms and dry shaker sixteenths, steady and driving
```
Set `length` to whole bars: 8 bars at 120 BPM is 16 s (§5 M5).

### M4 Matching an existing track's feel

None of the three targets accepts reference audio in Continuo `[code]`. Measure the reference first, then write:
1. Run `continuo_music_open` and `continuo_music_analyse_start` (beats, key, sections) on the reference, or read `continuo_song_map_read`.
2. Copy its BPM, key and section lengths into the controls (SA3 `bpm`/`length`; Foundation-1 `bpm`/`key`; YuE2 `Q:`/`K:` in the notes).
3. Name its genre, era, instruments and production in the target's grammar. Name sounds, not the artist: the authors' grammars carry no artist field, and practitioners say artist names do not transfer without a LoRA `[community]`.
4. For YuE2, the closest route is a hand-written or edited ABC with the reference's melody contour. The official guidance allows agent-written scores only when the artist explicitly asks for a written melody `[official]`. YuE2 audio-to-ABC transcription (SheetSage2) is not wired into Continuo `[code]`.

### M5 Hitting a beat grid / exact length

- **Foundation-1:** exact by construction. Pick `bpm` and `bars`; the length is `bars × 240 / bpm`, sample-exact `[code]`. Local tests found the length and key held to the bar `[local]`.
- **SA3:** the length is exact in whole seconds `[code]`; the tempo comes out close but not locked (95.7 BPM measured for 96) `[local]`. Choose a BPM where whole bars fill whole seconds, so the file can be cut on bar lines:

  | BPM | Seconds per bar (4/4) | Clean lengths |
  |---|---|---|
  | 60 | 4.0 | any multiple of 4 s |
  | 75 | 3.2 | 16 s (5 bars), 32 s (10 bars) |
  | 80 | 3.0 | multiples of 3 s |
  | 90 | 2.667 | 8 s (3 bars), 32 s (12 bars) |
  | 96 | 2.5 | multiples of 5 s (2 bars) |
  | 100 | 2.4 | 12 s, 24 s, 48 s |
  | 120 | 2.0 | any even number |

  Then beat-analyse the take before you cut on it. Beat trackers halve or double tempo on sparse material `[local]`.
- **YuE2:** set `Q:` and the bar count in the notes. The nominal score length is `bars × beats per bar × 60 / Q`, but the audio length "is not guaranteed to equal the score length" `[official]`. Then use `length` to trim at a phrase end. The trim is a hard cut with no fade, so place it on a rest or add a fade on the cut.

---

## 6. Parameters

| Knob | SA3 | YuE2 | Foundation-1 |
|---|---|---|---|
| Steps / sampler | 8, `lcm`/`simple` (official card: 8 steps `pingpong`; that ComfyUI `lcm` matches pingpong is a hypothesis) `[code, official]` | 32 `dpm_2`/`sgm_uniform` (official: 32 midpoint) `[code, official]` | Loop 250 / Keybed 80, `dpmpp_3m_sde`/`exponential` (author UI default 75 for loops, 250 in his generate function) `[code, maintainer]` |
| CFG | 1.0, no effect on post-trained small-music `[official]` | 1.0, guidance off (authors: try 1.2 as an experiment) `[official]`; not exposed | Loop 7 (author default 7), Keybed 6 (author 6) `[maintainer]` |
| Negative | empty, inert | none | zeroed conditioning (author uses none) |
| Length | 1–120 whole s; the model is conditioned on the duration `[local]` | budget `max_length` × 25 tokens/s; the prompt eats context `[local]` | from bars and BPM |
| Tempo | `bpm` → "BPM: N." in the text | `Q:` in the ABC | `<N> BPM` tag |
| Key | optional text, weak | `K:` in the ABC | tag, held `[local]` |

**YuE2 budget:**
- The song can run at most about 360 s by default. The official semantic cap is 9,000 tokens = 360 s, and Continuo allows up to 900 s [official config, code].
- A long style, long lyrics and a long score all take context (24,576 tokens). ComfyUI then shortens the song budget with the log line "music budget reduced…" `[local]`.
- Do not set `max_length` below the song's natural length: the song gets cut without warning `[local]`.
- Leave `length` at 0 unless you need a cut.

---

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| SA3 cue has vocal-like mumbling | vocal or "chorus"/"voice"/"choir-like" words, or a genre that implies singing | Remove them; name instruments only; reroll the seed |
| SA3 ignores the key | key adherence is weak in Small Music `[local]` | Leave `key` empty and transpose in post, or use Foundation-1 for pitched layers |
| SA3 output thin or generic | too short a prompt | 20–45 words: genre, 3–5 instruments, layers, rhythm, mood, context `[official]` |
| SA3 cue ends in silence | very long `length` (≈≥119 s) `[local]` | Shorter cues, joined on the cut |
| YuE2 sings stage directions | text in parentheses or notes in the lyrics | Only `[Section]` tags and sung words `[official]` |
| YuE2 ignores the tempo/key in the style | the score set its own `Q:`/`K:` `[local, official]` | Edit `Q:`/`K:` in the notes and render the song stage |
| YuE2 song stops abruptly | `max_length` too short, or the prompt reduced the budget `[local]` | Raise `max_length`; shorten the style or lyrics |
| YuE2 garbled words after a lyric change | syllable count no longer fits the score notes `[community]` | Keep the counts per line, or replan the notes |
| YuE2 vocals in an "instrumental" | the model always plans a Vocal line `[official, community]` | §4.2 edit; check with stems; else SA3 |
| YuE2 wrong language or accent | the style's language tag differs from the lyrics | Match them; prefer English/Mandarin `[community]` |
| Foundation loop incoherent phrase (the take warns) | BPM outside 100–150, or a loop longer than about 20 s | Use 100–150 from the list; 8 bars ≥ 96 BPM `[official, maintainer]` |
| Foundation loop reverberant or smeared | Wet with reverb/delay `fx` (on Dry the server drops `fx` `[code]`) | Dry, or one lighter `fx` tag |
| Foundation wrong instrument family | genre or prose words, or too many families | One or two instrument tags from §3.3 |
| Foundation distortion or harsh peaks | loud synth prompts | Fewer distortion/FX tags; reroll; the −6 dB headroom is already applied |
| Keybed notes out of tune or a note missing | non-chromatic or more than six notes | Exactly six consecutive semitones; same seed across chunks |

---

## 8. Sources (accessed 2026-11-12)

- `[code]` Continuo release candidate 9f7510c0: `dashboard/music_gen/targets.py`, `workflows/{sa3-small-music-v1,yue2-song-v1,foundation1-loop-v1}/`, `agent_tools.py` (continuo_music_gen_*), `dashboard/routes/music/generate_1.py`.
- `[local]` ComfyUI core (commit of 2026-11-05): `comfy_extras/nodes_yue2.py`, `comfy/text_encoders/yue2.py`, `comfy/model_base.py` (StableAudio3), templates `audio_yue2_text2music`, `audio_yue2_music_cover`, `audio_stable_audio_3_medium`.
- `[official]` Stable Audio 3: HF card stabilityai/stable-audio-3-small-music; github.com/Stability-AI/stable-audio-3 README, `docs/guides/prompting.md`, `docs/workflows/inference.md`, `stable_audio_3/interface/reprompt.py`; tech report arXiv 2605.17991 (§3 prompt preparation, §5 prefix); stability.ai/guides/stable-audio-3-prompt-guide.
- `[official]` YuE2: HF card m-a-p/YuE2-3B, `yue2_generation_config.json`, `examples/tonight-awake.json`, `assets/audio/examples.json`; github.com/multimodal-art-projection/YuE `docs/generation.md`, `examples/song.json`, `skills/yue2-music/` (SKILL.md, references/abc-editing.md, generation-and-covers.md, editing-workflows.md, instrumental/); paper arXiv 2609.33757; docs.comfy.org/tutorials/audio/yue2/yue2.
- `[official]` Foundation-1: HF card RoyalCities/Foundation-1, `Master_Tag_Reference.md`, `training_dataset_info.md`.
- `[maintainer]` github.com/RoyalCities/RC-stable-audio-tools: `interface/gradio.py` (`amend_prompt`, BPM list, defaults), `interface/keybed_tab.py`, `interface/prompts/{keybed_prompts,foundation_prompts,prompt_common}.py`; github.com/Saganaki22/ComfyUI-Foundation-1 `PROMPT_GUIDE.md`.
- `[community]` Banodoco Discord #yue2 (2026-09-11 … 2026-09-28: instrumental leaks, section-only lyrics, syllable matching, seed changes melody, narrow voice set) and #music (2026-03-20 Foundation-1 quality); HF discussion Comfy-Org/YuE2 #3 (2026-09, instrumental vocals, Vocal `Z` rests); songcreator.pro "YuE2 Prompting Guide" (2026-09-17).
