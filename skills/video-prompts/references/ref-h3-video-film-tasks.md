# MiniMax H3 video — film-task recipes

Worked recipes for common shots. Each gives the route, the decisions to make first and a full prompt. Load with
`skill_view('film-suite:video-prompts', 'references/ref-h3-video.md')`. Lengths use the snapped table (5 s = 5.17, 6 s = 6.58, 8 s = 8.00). Tags as in the core file.

Task ids: V-DLG dialogue line · V-REACT reaction/look · V-INSERT insert · V-ACTION action beat · V-EST establishing
move · V-MONTAGE montage beat · V-CHANGE weather/light change · V-BEAT cut on a music beat · V-HOLD held silent look.

---

## V-DLG — one line of dialogue

Route: Frames (frame 0 = the speaker, mouth closed) or References (identity + `voice_of`).
Decide first: the exact words; their spoken length (read aloud, add 30 %); where the line starts (leave 0.5-1 s
of held face before it); what the face does after the last word; whether anyone else is in frame (silent).
Rules: one `<d>` block per continuous line, no ellipsis or dash inside, delivery written outside the tag, the end
anchored by a visible action, clip just long enough (line + lead-in + 1-1.5 s after) `[house]` `[community]`.

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, the woman in the rain-dark trench coat shown in <Picture 1> stands under the bus-shelter light at night, facing frame left. The camera holds a static shot. She keeps her eyes on the road for a breath. At 00:01.00 the woman with a low, steady voice (S1) says in one breath, without pausing: <d>[English] The last bus left an hour ago.</d> At 00:03.20 she stops talking, closes her mouth and pulls her collar up with her right hand. She holds her look down the road until the end of the shot; the shelter light stays steady.

overall_soundscape:
Steady rain drums on the shelter roof and runs off its edge onto the pavement. A car hisses past on the wet road behind her.

non_diegetic_music:
N/A
```
Length: 5 s (5.17). If the take pauses mid-line: shorten the clip, keep the line one block, move the end anchor
earlier; never add an ellipsis or "pauses" to fix it.

## V-REACT — reaction or look

Route: Frames, frame 0 = the face before the reaction.
Decide: the trigger (off-screen, in sound only), the reaction as one visible change (eyes, jaw, breath, head), its
timing, and the held state after. Keep the cause off-screen and in `overall_soundscape` `[house]`.

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a close-up of the night-market cook shown in <Picture 1>, lit orange by the stall's bulbs, steam drifting past his face. The camera holds a static shot. For the first second he watches the wok, breathing steadily. At 00:01.20, at the sound of breaking glass off-screen, his eyes snap up toward frame right in one quick move and his jaw tightens; his hands stop on the wok handle. He holds that look, breathing through his nose, until the end of the shot. No one speaks.

overall_soundscape:
Market crowd murmur and sizzling oil fill the space. A glass bottle shatters on stone off-screen to the right, and the crowd noise drops for a moment.

non_diegetic_music:
N/A
```
Length: 4 s (4.46) or 5 s.

## V-INSERT — insert / prop close-up

Route: Frames from a picture that shows ONLY the insert's subject, or Text to Video.
Decide: what the insert must prove for the story (one action, not filler); what stays out of frame; whether the
hand and prop are already in their grip in frame 0. "The hand and the cup stay still; only the steam moves" is a
valid action `[house]`. Never describe an off-screen cause by its visible effects (the cause enters the frame)
`[house]`.

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, an extreme close-up of a brass motel key on a scratched wooden counter, as shown in <Picture 1>, under warm tungsten light. The camera holds a static shot. At 00:00.80 a man's hand enters from frame right, its fingertips press on the key and slide it out of frame left in one smooth move. The empty counter, its scratches and a faint ring of water remain until the end of the shot. No one speaks.

overall_soundscape:
Low fluorescent buzz. The key scrapes across the wood and taps once against the counter edge.

non_diegetic_music:
N/A
```
Length: 4 s; cut the slot from the middle.

## V-ACTION — action beat

Route: Frames (start one moment BEFORE the action) or Text to Video.
Decide: start state → path → impact → settle; the natural duration (fast beats short); the exact physical event
and its sound size (a dry-fire click is "the hammer snaps on an empty chamber: one dry metallic click", never
"fires" or "pulls the trigger" `[house lesson]`); the camera (locked, or one listed move with a destination).
Against slow motion: timestamps, "in one quick snap lasting a quarter of a second", brisk verbs, a cause that keeps
running until the trigger `[house]`.

```
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a wide shot frames a desert motel parking lot at noon under hard white sun, a dusty pickup parked at frame left and a vending machine by the office door at frame right. The camera holds a static shot. At 00:00.40 a teenage boy in a red cap sprints in from frame right, keeps accelerating across the lot and at 00:01.30 vaults the pickup's tailgate in one quick leap, landing in the truck bed on both feet. At 00:01.90 the truck rocks once on its springs and settles. He crouches low behind the cab and stays there, breathing hard, until the end of the shot. No one speaks.

overall_soundscape:
Dry wind and the vending machine's hum. Fast sneaker steps slap the asphalt, the truck bed booms once under his landing and the springs creak.

non_diegetic_music:
N/A
```
Length: 4 s (4.46). For a faster read, render on a shorter custom graph or speed it in the Cut (`fit_to_fill`).

## V-EST — establishing move

Route: Text to Video (or Frames from an approved location plate).
Decide: one listed move, its destination in frame terms, its end time; restate time of day and light; keep
people small and incidental; name text surfaces or keep them plain.

```
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a wide shot at blue hour frames a small ferry terminal across black harbour water, its single ticket booth lit warm yellow and a moored car ferry beside the pier. The camera pulls out with large amplitude at slow speed, rising over the harbour wall until the whole pier, the ferry and the dark hills behind the town are in frame, and stops at 00:05.50. Two tiny figures walk along the pier toward the ferry. The ferry's bow is a plain, unmarked white steel panel. No one speaks.

overall_soundscape:
Water laps against the harbour wall and a rope creaks on a bollard. A ferry engine idles low across the water and a gull calls once.

non_diegetic_music:
A low sustained cello note at a slow tempo, joined by soft piano notes, fading out in the final second.
```
Length: 7 s (7.29).

## V-MONTAGE — montage beat (several cuts in one take)

Route: Text to Video or Frames (only the first shot can have a fixed picture).
Decide: per shot its framing, subject, light side and ONE action; cut times; one sound per shot. Keep the shared
medium/look clause at the start of `[Shot 1]` (official form; a look line before `[Shot 1]` also worked in house
tests) and restate the light per shot. In-take cuts landed within about 2 frames of their timestamps `[house]`; about one shot per second
is the practical floor `[community]`.

```
integrated_multimodal_description:
[Shot 1] Live-action, cinematic, night-market look under string lights, an extreme close-up of a cleaver dropping onto a chopping board and splitting a scallion in one hard chop. [Shot 2] At 00:01.700, the camera cuts to a close-up of a wok tossing noodles over a roaring blue flame, lit orange from below by the same string lights. [Shot 3] At 00:03.400, the camera cuts to a medium close-up of a customer's hand taking a steaming paper plate across the counter, the string lights blurred behind. No one speaks.

overall_soundscape:
Crowd murmur under everything. The cleaver bangs on wood, the wok's flame roars and the oil hisses, and paper rustles as the plate changes hands.

non_diegetic_music:
N/A
```
Length: 5 s (5.17); cut each slot from the middle of its shot.

## V-CHANGE — weather or light change inside a shot

Route: Frames, frame 0 = the BEFORE picture; the change is written; never before + after pictures (two
near-identical anchors freeze) `[house, measured]`.
Decide: the change as one instant or a stated duration; everything that changes "at the same moment"; a hard
sound for a switch; life before and after (rain, breath, smoke, a small gesture); cut the slot to start a few
frames before the change `[house]`.

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, the night clerk shown in <Picture 1> sits behind the motel counter under one warm desk lamp, rain streaking the glass door behind him. The camera holds a static shot. He turns a page of his newspaper. At 00:01.80, in one single instant with no fade, the desk lamp and the ceiling light go dark at the same moment and the lobby drops to the cold blue light from the parking lot. He freezes with the page half turned, then at 00:02.80 slowly lowers the newspaper and looks toward the dark lamp. Rain keeps running down the glass. No one speaks.

overall_soundscape:
Rain patters on the glass door. A sharp electrical clunk cuts the fluorescent buzz to silence; afterwards only the rain remains.

non_diegetic_music:
N/A
```
Length: 5 s. Weather turning gradually ("the drizzle thickens into heavy rain over three seconds") follows the same
pattern with a duration instead of an instant `[hypothesis]`.

## V-BEAT — a cut that must land on a music beat

H3 cannot read your song. Route the beat in the edit:
1. Get the beat frame from the music map (`continuo_music_map`), e.g. beat at 12.40 s in the cut.
2. Render the take so the action's event happens early and cleanly: put the event at a timestamp with room
   before it (≥ 0.8 s), so the Cut can choose the in-point; render the take without score (`N/A`) so the song
   carries the music `[house]`.
3. In the Cut, measure the event frame in the take (largest frame change or loudest sound), then align with
   `fit_to_beats`, `snap_speed_key` or a trim so the event frame sits on the beat frame `[code]` timeline verbs.
4. Need picture to follow an exact audio file? `sound_track` on Frames/References plays a file from frame 0 and
   the picture follows it `[code]`; use it for lip-sync or dance to a known bed, not for score.

Prompt for the take: the event once, hard and short, at e.g. `At 00:01.00 ... in one single instant`, with a hard
sound; nothing else loud in the take.

## V-HOLD — a held silent look

Route: Frames, frame 0 = the face.
Decide: what is still (named parts) and what still moves (breath, eyes, hair in wind, steam); a boundary and an
exit; "No one speaks."; a quiet soundscape. Pure stillness reads as a freeze or invites invented motion; give it
one small residual motion `[community]` `[house]`. If the world must stop dead, do the freeze in the Cut
(`freeze_frame`) `[house]`.

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description:
[Shot 1] Live-action, cinematic, a close-up of the deckhand shown in <Picture 1> at the ferry rail at dusk, grey cloud behind her. The camera holds a static shot. Her face and shoulders stay still; only her eyes move once, from the water to the distant pier, and a few strands of hair lift in the wind. She breathes slowly through her nose. She keeps that look on the pier until the end of the shot; the dusk light stays even. No one speaks.

overall_soundscape:
Low engine throb and steady wind. Water slaps softly against the hull.

non_diegetic_music:
N/A
```
Length: 5 s. The freeze check may call this take frozen while it is right: let the artist judge `[code]` `[house]`.
