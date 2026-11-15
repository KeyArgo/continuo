---
name: voice-prompts
description: "Use when writing a spoken line, direction or voice description for a Continuo voice take."
---

# Voice prompts (OmniVoice and Drama 3 in Continuo)

Three local targets speak one line per take. The server rewrites only the neutral cues and the direction; everything
else in the text reaches the engine as written. The clip decides most of the performance, the words second.

Load the reference before the first line: `skill_view('film-suite:voice-prompts', 'references/ref-voice.md')`
(both engines, cue tables, clip rules, description vocabulary, film recipes V1-V6, failures).

## 1. Pick the target

| Target | Voice from | Use it for | Text it reads |
|---|---|---|---|
| `omnivoice-clone-v1` | a clip (+ its words, optional) | fast, stable cloning in 600+ languages; many short neutral lines | the line; `{cue:laugh}` and `{cue:sigh}` only; direction is dropped |
| `omnivoice-design-v1` | a description from a closed word list | a new voice when no clip exists (audition, then clone from the kept take) | the line; same cues; direction is dropped |
| `drama3-clone-v1` | a clip **and its exact words** (required) | acted lines: tears, held anger, a laugh through words, a whisper on three words, a mid-line turn | the line with `[direction]` in front and all four cues |

A clip voice runs only on the clip targets and a description voice only on design (`voice_mismatch` otherwise).
`omnivoice-clone-v1` takes six optional traits in `values`: `trait_gender`, `trait_age`, `trait_pitch`, `trait_style`
(`whisper`), `trait_accent` (English lines) or `trait_dialect` (Chinese lines, never with an accent). Leave them out
for the clip's own voice.
`continuo_voice_targets` lists readiness, cues and the controls each target really has.

## 2. Write the line

- Plain spoken words, one sentence per thought. Punctuation is the pause control on OmniVoice.
- Spell out numbers, dates, units and abbreviations (`twenty to nine`, `Doctor Hale`): OmniVoice runs without text
  normalisation here.
- No quotation marks around the line, no speaker name, no screenplay parentheticals (Drama 3 speaks text in round
  parentheses), no line breaks (OmniVoice deletes them and joins the words), no `<|...|>` tokens.
- Cues in `text` are the four neutral ones: `{cue:laugh}`, `{cue:sigh}`, `{cue:whisper}`, `{cue:pause}`. OmniVoice
  keeps only laugh and sigh; the others are dropped with a warning.
- Performance goes in the line's `direction` field, without brackets (`weary, patient, to a new hand`). Drama 3 reads
  it as a `[style]` prefix; OmniVoice drops it. Keep directions short (a long one may be read aloud or chunked:
  untested).

## 3. The clip (the biggest lever)

- 3-10 s of one speaker, clean, dry, cut between sentences, in the register the line needs (a shouted line wants a
  raised-energy clip; a calm clip plus "shouting" gives little).
- Same language as the line, or the line inherits the clip's accent.
- The words must match IN/OUT exactly: after every IN/OUT change run `continuo_voice_transcribe`; never type words you
  did not hear (`continuo_voice_state_write`). A transcript that misses the clip's last words is the most common
  reason a Drama 3 take falls silent.

## 4. Describe a new voice (`omnivoice-design-v1`)

Comma-separated items from a closed list, at most one per category: gender (`male`, `female`), age (`child`,
`teenager`, `young adult`, `middle-aged`, `elderly`), pitch (`very low pitch` ... `very high pitch`, `moderate pitch`),
style (`whisper`), an English accent (`british accent`, `american accent`, ...). Example:
`female, middle-aged, low pitch, british accent`. Any adjective (`gravelly`, `warm`, `deep`) or a near-miss (`young`,
`medium pitch`) fails the take. A description gives a different speaker per seed: keep the best take and clone from
it for the rest of the film.

## 5. Takes and repair

- Ask for 3-4 seeds per line (`count`), because Drama 3 takes can go silent mid-line; check length and words with
  `continuo_voice_take_words` before calling a take done.
- One fixed clip and one engine per character per scene; the two engines differ in timbre and sample rate.
- Lines do not hear each other: state the reaction in the direction (`cutting him off`) and make overlaps in the Cut.
- Level with `continuo_voice_match`; place with `continuo_voice_take_to_cut`; re-time pauses without re-speaking
  with `continuo_voice_take_recut` (needs word timings first).
- Neither engine can replace one word: re-speak the whole line with the fix and cut the word in at a pause.
- Generation runs on the artist's GPU: submit only when the artist asked.

## 6. Failures

| Symptom | Cause | Fix |
|---|---|---|
| Take stops or goes silent mid-line (Drama 3) | model trait; clip words do not match IN/OUT | transcribe again; 3-4 seeds; pick a complete take |
| "Voice description not understood" | a word outside the closed list | only the listed items, one per category |
| Direction ignored | OmniVoice drops directions | pick a clip in that register, or use Drama 3 |
| Flat delivery | flat clip | a clip already in the wanted emotion and energy |
| Digits misread or rushed | no text normalisation | spell numbers out |
| Words run together | a line break in the text | a space or punctuation |
| Wrong accent | clip in another language | a same-language clip |
