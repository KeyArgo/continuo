---
name: music-prompts
description: "Use when writing a prompt, lyrics or loop tags for a Continuo music take."
---

# Music prompts (SA3, YuE2, Foundation-1 in Continuo)

Three local music targets, each with its own prompt form. The server writes part of every prompt itself: write only
your part, never the part it adds. Generate only when the artist asked: every take uses the local GPU.

Load before the first take: `skill_view('film-suite:music-prompts', 'references/ref-music.md')` (what the server
sends, the grammar of each target, the YuE2 notes-edit-song loop, keybeds). Film recipes M1-M5, parameters and
failures: `skill_view('film-suite:music-prompts', 'references/ref-music-film-tasks.md')`.

## 1. Pick the target

| Film task | Target | Why |
|---|---|---|
| M1 score cue to picture (mood, tempo, length) | `sa3-small-music-v1` | instrumental cues and beds, 1-120 s, exact length in whole seconds |
| M2 song with lyrics (source music, end credits) | `yue2-song-v1` | sung lyrics; an editable ABC score sets tempo, key and form |
| M3 loop / stem for the cut | `foundation1-loop-v1` (pitched, 4 or 8 bars) or SA3 (beds, non-pitched textures) | Foundation-1 loops have exact bar length |
| M4 match an existing track's feel | SA3 with genre, era, instruments and recording style of that track; measure the track first with `continuo_music_analyse_start` | no audio reference input exists on any target |
| M5 beat grid / exact length | Foundation-1 (bars x 4 x 60 / BPM) or SA3 `length` | both trims are sample-exact; YuE2 only trims with a hard cut |

`continuo_music_gen_targets` lists the controls each target really takes and its readiness.

## 2. What you write per target

**SA3 (`sa3-small-music-v1`).** The server sends
`TrackType: Music, VocalType: Instrumental, <your sentence>, <key>. BPM: <bpm>.`
- Write one natural sentence of 15-45 words: genre/style, main instruments, supporting layers, rhythm, then mood or
  the scene it plays under ("for the final scene of a slow-burning thriller").
- Never write TrackType, VocalType, BPM, a key or a length in the sentence, and no vocal words (`vocals`, `voice`,
  `choir`, `singing`, `chorus`): the model is instrumental. No negative exists; brackets and weights are not grammar.
- `length` is whole seconds (a fraction is refused). `key` is a hint the model does not always follow: leave it empty
  unless needed.
- `track_type: Instrument` asks for a solo stem (the prefix then reads `TrackType: Instrument`); `Music`, the
  default, is a full mix.

**YuE2 (`yue2-song-v1`).** Style tags + lyrics; the score decides tempo and key.
- `prompt` (style): comma tags in this order: language, genre, vocal character, tempo, instruments, mood/production.
  Always name the vocal.
- `lyrics`: one `[Section]` tag per line (`[Verse]`, `[Chorus]`, ...), a blank line between sections, every repeat
  written out in full, only words meant to be sung (no "x2", no stage directions).
- Plan with `stages: "notes"`, read the ABC on the take, edit `Q:` (tempo) and `K:` (key) or the melody, then render
  with `stages: "song"` and the edited `notes` (or `notes_from` the take). Tempo written only in the style is a hint.
- Empty `lyrics` ask for an instrumental (a style is still required; the take carries a warning). Voices can still
  appear: move the Vocal notes to `Ins` in the notes stage and check the take.

**Foundation-1 (`foundation1-loop-v1`).** The server joins
`<instrument>, <timbre>, <Wet|Dry>, <fx>, <key>, <bars> Bars, <bpm> BPM`.
- Fill the fields with tags from the trained vocabulary (instrument names, timbre words, behaviour tags such as
  `Arp`, `Chord Progression`, `Melody` go in `timbre`).
- Keep BPM in the trained range (100-150); the control allows 40-200, and a take outside 100-150 carries a warning
  (nothing is clamped). Keep 8 bars at 96 BPM or faster (about 20 s of training clip).
- On Dry the server leaves the fx words out of the prompt; write `fx` only for Wet.
- Keybed (`keybed: true`): six rising semitones (`C4 C#4 D4 D#4 E4 F4`) at the pitch you want to hear are the
  trained "Chromatic Chunk" (19.25 s). Any other 1-16 notes are sent as a plain note sequence, 3.0 s per note plus
  0.25 s gaps, and the take carries a warning.

## 3. Checks after a take

`continuo_music_gen_takes` gives measured seconds, peak, clipped samples and loudness; every file has -6 dB headroom.
Measure tempo and key with the analysis tools before placing a cue on a grid. One change per retake; keep the seed
when the prompt changes.

## 4. Failures

| Symptom | Cause | Fix |
|---|---|---|
| Voices or "ah" pads in an SA3 cue | vocal words (incl. "chorus", "choir") | instruments only |
| SA3 cue ignores the BPM in the text | BPM belongs in the control | set `bpm`, remove it from the sentence |
| YuE2 tempo or key wrong | the score's `Q:` / `K:` win over the style | notes stage, edit `Q:` / `K:`, render the song stage |
| YuE2 sings "repeat" or section names | shorthand or notes in the lyrics | write every line out; only `[Section]` tags |
| Foundation-1 loop smeared or reverberant | Wet with reverb or delay fx | Dry, or fewer fx tags |
| Foundation-1 loop loses shape (the take warns) | BPM outside 100-150, or 8 bars too slow | 100-150 BPM; 4 bars below 96 BPM |
| Keybed notes in the wrong octave or out of order | a selection other than six rising semitones (the take warns) | six rising semitones at the heard pitch |
