# Continuo

**A film studio inside Hermes.** You write the script, make pictures and video takes on your own GPU, cut them to
music and render the film. Hermes works in the same project, on the page you have open.

![Continuo in Hermes Desktop](docs/media/hero.png)

**Start without any model.** Open the Sample film, change the cut and render an MP4. Only ffmpeg is needed for that.
Script, Cut, beat analysis and Deliver run on the CPU.

**You and Hermes work on the same film.** Hermes gets 212 tools that cover every page, and the open page shows
what Hermes did. On Script and Cut you can undo each of its changes. Only you can approve a folder for Continuo.

```
hermes plugins install https://github.com/realartsbro/continuo
hermes plugins enable film-suite
```

Then restart Hermes, open **Capabilities > Plugins** and turn the **Continuo** switch on. Continuo appears in the
sidebar at once. Details are under [Install](#install).

Continuo is a plugin for [Hermes Agent](https://hermes-agent.nousresearch.com), the open-source AI agent by Nous
Research. It needs Hermes Agent `>=0.22.7` with the desktop app. MIT licence.

[Pages](#cut-and-deliver) ·
[Install](#install) ·
[Models](#models-optional) ·
[Talk to Hermes](#talk-to-hermes) ·
[What it does on your machine](#what-this-plugin-does-on-your-machine)

## Cut and deliver

![The Cut page](docs/media/01-cut.png)

One timeline with picture tracks, sound tracks and a music lane. Continuo finds the beats of the song, and
**Fit to beats** moves the cuts onto them. With the optional speech detector (Silero VAD), the music drops under
dialogue by itself.

**Deliver** renders an MP4 or a film master (Apple ProRes in a MOV), with SRT and VTT subtitles. It also writes the
timeline as FCPXML 1.9, FCP 7 XML, OpenTimelineIO and EDL, the exchange formats of Premiere, Resolve and Final Cut.
**Check before render** stops a render while a clip is offline. The render queue keeps its jobs across a restart.

## Image

![The Image page](docs/media/02-image.png)

**Create** pictures from a prompt with a local model through ComfyUI, then **Edit** a selection or a mask. Each picture
keeps the prompt, seed and settings that made it; **Use these settings** puts them back into the controls.

## Video

![The Video page](docs/media/03-video.png)

Make video takes with MiniMax H3 on your own GPU, from a prompt, from keyframes or from reference pictures. Continue
a take from a frame you choose, compare two takes A/B, upscale the one you keep and send it to Cut.

## Script

![The Script page](docs/media/04-script.png)

Write in screenplay format with a scene list. Enter and Tab pick the next element; `int.` or `ext.` starts a scene
heading. Hermes writes in the same script, and you can undo what it changed.

## Audio

![The Audio page](docs/media/05-audio.png)

Play a song, set IN and OUT and analyse it. The built-in analysis finds beats, bars and the song's sections; the
optional song engine names them (Intro, Verse, Chorus). **Use in Cut** places the song or the IN-OUT range under the
cut.

## Hermes works beside you

![A change Hermes made, shown on the page with Undo](docs/media/06-hermes.png)

Hermes uses the same project and the same job list as you. When it rewrites a scene or moves a clip, the open page
shows the change with before and after, and Undo takes it back. Each edit from Hermes names the revision it read. If
you changed the scene or the cut since then, the edit is refused and nothing is saved.

## Install

### Requirements

| Part | Requirement | Notes |
|:---|:---|:---|
| Platform | Windows 11, macOS (Apple Silicon) | Tested on Windows 11. A contributor ran it on macOS 26.5 on an Apple M4 Pro; see [macOS](#macos) for what ran there and what did not. The code is written to run on Linux too, not yet tested; reports are welcome, see [Feedback](#feedback). |
| Hermes&nbsp;Agent | `>=0.22.7` | With the Hermes desktop app. |
| ffmpeg | Required | For Cut, Deliver and Audio; tested with 7.1.1. Looked up in `FFMPEG_PATH`, then `PATH`, then `C:\ffmpeg\bin`. macOS: `brew install ffmpeg`. |
| ComfyUI | For generation | Generates pictures, video, music and voice. Without a setting Continuo asks this machine: `http://127.0.0.1:8188`, then `http://127.0.0.1:8000` (the ComfyUI desktop app). Another address: Hermes Settings › Plugins › Continuo › ComfyUI address (Test, then Save; it applies to the next request, no restart). The environment variable `FILM_SUITE_COMFY_URL` overrides the setting. An address on another machine sends your prompts and pictures to that machine. |
| ComfyUI&nbsp;folders | For generation | Where ComfyUI is installed (its models and custom nodes) and, if you keep them elsewhere, your models: Hermes Settings › Plugins › Continuo › ComfyUI folder and Models folder (Choose… or type the path, then Save; it applies to the next request, no restart). Empty: the usual install, `Documents\ComfyUI-Easy-Install\ComfyUI` on Windows (macOS: see [macOS](#macos)), and that folder's `models`. A folder that is missing, relative or on the network is refused with the reason. The environment variables `FILM_SUITE_COMFY_ROOT` and `FILM_SUITE_COMFY_MODELS` override the settings. Only you set these folders; Hermes may read them. |
| GPU | For generation | Script, Cut, Audio analysis and Deliver run on the CPU, so a GPU is optional for them. Generation uses your GPU. When Continuo has used ComfyUI and nothing has run there for 10 minutes, Continuo asks ComfyUI to free its graphics memory; change the minutes in Hermes Settings › Plugins › Continuo › Free graphics memory after (0 = never). |
| Disk | 24&nbsp;MB&nbsp;+&nbsp;511&nbsp;MB | Measured: the plugin 24 MB; its Python packages 511 MB, set up by Hermes. Models need extra space, see [Models](#models-optional). |

### macOS

A contributor ran Continuo on macOS 26.5 on an Apple M4 Pro: the Sample film from Script to Deliver, beat tracking, object
removal, speech detection and one image model through ComfyUI; the song and scene engines installed. Not run on a Mac so far:
the Continuo pane inside Hermes Desktop, video, the larger image models, and song or scene analysis on real material. Reports
are welcome, see [Feedback](#feedback).

- **ffmpeg:** `brew install ffmpeg`.
- **Machine-local records** (approved folders, analysis caches, job records) live in
  `~/Library/Application Support/hermes/film-suite/` unless `LOCALAPPDATA` is set, not in the temp folder macOS empties.
- **Engines** install from their own macOS hash locks (`scripts/engine-locks/ENGINE.macos.txt`: the same package
  versions, torch without the CUDA tag). `--cpu-only` is ignored on macOS. The engines use the GPU (`mps`) when
  ComfyUI's queue is empty, except Beat This!, which stays on the CPU (the contributor measured it no faster on Metal,
  with identical beats); `FILM_SUITE_BEAT_DEVICE`, `FILM_SUITE_SONG_DEVICE`, `FILM_SUITE_SCENE_DEVICE` or
  `FILM_SUITE_INPAINT_DEVICE` set to `mps` or `cpu` overrides.
- **ComfyUI folder** (models and custom nodes): Hermes Settings › Plugins › Continuo › ComfyUI folder names it; empty,
  it is looked for at ComfyUI Desktop's install folder, then `~/Documents/ComfyUI`, `~/ComfyUI` and `~/comfy/ComfyUI`.
  `FILM_SUITE_COMFY_ROOT` overrides the setting.
- **GPU line** in Jobs shows the Apple GPU and the unified memory in use.
- **Shortcuts:** labels show ⌘ where Windows shows Ctrl, and the Script page's own keys (focus, undo a scene move,
  save a synopsis, paste Fountain) answer to ⌘. Find stays Ctrl+H. Not tried inside Hermes Desktop on a Mac.

### Steps

```
hermes plugins install https://github.com/realartsbro/continuo
hermes plugins enable film-suite
```

No GitHub login is needed. The plugin's id in Hermes is `film-suite`; Continuo is its name in the app.

> **The install scan says "caution".** Hermes scans every plugin before it installs it. Continuo runs ffmpeg and talks
> to your local ComfyUI (`127.0.0.1`), so the scan asks you to confirm. Answer `y`. The reasons are listed under
> [Install scan](#install-scan). The installer then asks whether to enable the plugin and whether to set up its Python
> packages (numpy, librosa, soundfile, httpx, Pillow; 511 MB). Answer `y` to both.

1. Restart Hermes.
2. Open **Capabilities > Plugins**, find **Continuo** and turn its switch on. Continuo appears in the sidebar at once.
   Hermes installs a plugin's window switched off, and `hermes plugins enable` turns on only the agent's tools. A
   restart does not turn the window on.
3. Open **Continuo** from the sidebar. Hermes also gets five skills: `film-suite:continuo` (which tool does what),
   `film-suite:video-prompts`, `film-suite:image-prompts`, `film-suite:voice-prompts` and `film-suite:music-prompts`
   (how to prompt the video, image, voice and music models).

### Your first film, no models needed

The Sample film needs only ffmpeg. It holds three scenes, six pictures, music with a steady beat and a cut. The six
pictures are AI-generated with Krea 2 Turbo; the script and the music are CC0 (free to reuse).

1. On **Start**, choose **Sample film**. Continuo copies it into a new project folder,
   `Documents\Continuo\Sample film`, and opens it on **Cut**.
2. Play the cut. Move or trim a clip.
3. Open **Deliver**, choose the format **MP4** and click **Add to render queue**.
4. The file is saved to the project's output folder: `output/` inside the project folder, unless you chose another
   folder in the project settings.

Or ask Hermes in one sentence:

```text
Open the sample film in Continuo, swap the first two shots and export an MP4.
```

## All pages

The bar at the bottom of Continuo holds the pages in working order.

| Page | What you can do |
|:---|:---|
| **Script** | Write in screenplay format with a scene list; Hermes writes in the same script, and you can undo its changes. |
| **Audio** | Play a song, set IN and OUT, analyse beats and song parts, and **Use in Cut**. |
| **Image** | **Create** pictures from a prompt and **Edit** a selection or mask; **Use these settings** restores any result. |
| **Video** | Make MiniMax H3 takes locally, continue a take, compare A/B, upscale and send to **Cut**. |
| **Cut** | Edit one timeline with music, song parts and beats; **Fit to beats**, and music lowered under dialogue with the speech detector. |
| **Deliver** | Render MP4 or Film master, export FCPXML, FCP 7 XML, OTIO, EDL and subtitles, after **Check before render**. |
| **Media** | Browse the project's media on every page, with bins, filters, ratings and compare. |
| **Jobs** | See and stop every running job in one list, the same list Hermes works with. |

**More on each page**

<details>
<summary>Show</summary>

- **Script**: Enter and Tab pick the next element, `int.` or `ext.` starts a scene heading, Fountain bold and italic
  show while you type. Hermes' changes are marked.
- **Audio**: waveform, playback, IN and OUT, markers. Analysis runs only when you ask: beats, bars and sections with
  the built-in engine, named song parts (Intro, Verse, Chorus) with the optional song engine. Lyrics are transcribed from the vocals
  or taken from text you paste. **Use in Cut** places the whole song or the IN-OUT range.
- **Image**: several pictures in one run with a local model. Edit with selection tools, numbered boxes and **Remove**.
  Every picture keeps the prompt and settings that made it.
- **Video**: takes from keyframes or reference pictures, run on your machine. Continue a take from a chosen frame, keep
  the best one.
- **Cut**: a large viewer (Timeline and Source), tracks V1, V2, A1 to A3 and Music. Clips come from your folders
  through Source IN/OUT. Each cut of the project is its own item in **Media**.
- **Deliver**: MP4, Film master (MOV, Apple ProRes), FCPXML 1.9, FCP 7 XML, OpenTimelineIO, EDL (CMX 3600), SRT and
  VTT. **Check before render** refuses offline clips; the render queue can stop and re-render, and it survives a
  restart.
- **Jobs**: all jobs from every page that run in the background, with stop. Hermes can also repeat them.

</details>

## Models (optional)

No model ships with Continuo, and the Sample film needs none.

- **Without any model**: Script, Cut, Deliver, Media and Jobs, plus Audio playback, IN and OUT, markers, beat analysis
  with the built-in librosa engine, and **Use in Cut**.
- **With ComfyUI and models**: Image **Create** and **Edit**, Video takes and upscaling, stems and music generation.
  Voice and song generation are in progress.

Each generation feature runs a ComfyUI workflow. Install only the models of the workflows you want to use:

| Page | Workflows | Size per workflow |
|:---|---:|---:|
| **Image › Create** | 10 | 5.6–37.8 GB |
| **Image › Edit** | 9 | 11.0–31.2 GB |
| **Video** | 8 | 4.5–45.6 GB |
| **Audio** (5 in progress) | 7 | 0.5–40.1 GB |

**All workflows and model sizes**

<details>
<summary>Show the table</summary>

Sizes come from the plugin's own source list (`dashboard/workflows/model-sources.json`); files shared between
workflows count once per row. Rows marked "in progress" are wired but not yet proven in the app. Repos are on Hugging
Face, custom nodes on GitHub.

| Workflow | For | Size | Files | Hugging Face repos, custom nodes |
|:---|:---|:---|:---|:---|
| yue2-song-v1 | Audio: a song with lyrics (in progress) | 3.96 GB | 1 | Comfy-Org/YuE2 |
| omnivoice-design-v1 | Audio: a voice from a description (in progress) | 2.45 GB | 1 | Bgeorge/OmniVoice; Nodes: Saganaki22/ComfyUI-OmniVoice-TTS |
| drama3-clone-v1 | Audio: a voice from a reference recording (in progress) | 40.14 GB | 2 | PedroMarinhoDev/Drama-3-ComfyUI; Nodes: PedroMarinhoDev/ComfyUI-Drama3 |
| omnivoice-clone-v1 | Audio: a voice from a reference recording (in progress) | 2.45 GB | 1 | Bgeorge/OmniVoice; Nodes: Saganaki22/ComfyUI-OmniVoice-TTS |
| foundation1-loop-v1 | Audio: loops and keybeds (in progress) | 5.75 GB | 3 | RoyalCities/Foundation-1; google-t5/t5-base |
| sa3-small-music-v1 | Audio: music from a prompt (Stable Audio 3 Small) | 3.46 GB | 2 | Comfy-Org/stable-audio-3 |
| audio-stems-v1 | Audio: split a song into stems | 0.46 GB | 1 | Kijai/MelBandRoFormer_comfy |
| flux3-klein-sd-create-v1 | Image › Create | 20.77 GB | 4 | Comfy-Org/Flux-2-Dev; Comfy-Org/Krea-2; KoalaNation/FLUX-3-KLEIN-MODELS; black-forest-labs/flux-3-image-klein-comfy |
| anima-turbo-create-v1 | Image › Create (Anima Turbo) | 5.63 GB | 3 | Comfy-Org/Qwen-Image; circlestone-labs/Anima |
| flux2-klein-9b-t2i-v1 | Image › Create (FLUX.2 Klein 9B) | 18.82 GB | 3 | Comfy-Org/Flux-2-Dev; Comfy-Org/Flux-2-Klein-9B; black-forest-labs/FLUX.2-klein-9b-kv-fp8 |
| ideogram4-create-v1 | Image › Create (Ideogram 4) | 30.09 GB | 4 | Comfy-Org/Flux-2-Dev; Comfy-Org/Ideogram-4; Comfy-Org/Qwen3-VL |
| krea2-raw-t2i-create | Image › Create (Krea 2 Raw) | 18.99 GB | 3 | Comfy-Org/Krea-2; Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL |
| krea2-turbo-t2i-create | Image › Create (Krea 2 Turbo) | 18.99 GB | 3 | Comfy-Org/Krea-2; Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL |
| moss-image-sft-create-v1 | Image › Create (MOSS-Image) | 20.25 GB | 3 | Comfy-Org/Flux-2-Dev; Comfy-Org/MOSS-Image |
| minimax-h3-image-create-v1 | Image › Create (MiniMax-H3-Image) | 37.83 GB | 3 | Comfy-Org/MiniMax-H3; Comfy-Org/MiniMax-H3-Image |
| p-h3-image-lora-t2i-v1 | Image › Create (P-H3-Image) | 31.19 GB | 4 | Comfy-Org/MiniMax-H3; PrunaAI/P-H3-Image-Comfy |
| qwen-image-2.1-create-pe-v3-v2 | Image › Create (Qwen-Image 2.1) | 27.09 GB | 7 | Comfy-Org/Qwen-Image-2.1; Comfy-Org/Qwen3-VL; PrunaAI/Pruna-Q-Image-2.1; Qwen/Qwen-Image-2.1-PE-I2I; Qwen/Qwen-Image-2.1-PE-T2I |
| flux3-klein-sd-edit-v1 | Image › Edit | 20.77 GB | 4 | Comfy-Org/Flux-2-Dev; Comfy-Org/Krea-2; KoalaNation/FLUX-3-KLEIN-MODELS; black-forest-labs/flux-3-image-klein-comfy |
| flux2-klein-9b-kv-edit-v1 | Image › Edit (FLUX.2 Klein 9B) | 18.82 GB | 3 | Comfy-Org/Flux-2-Dev; Comfy-Org/Flux-2-Klein-9B; black-forest-labs/FLUX.2-klein-9b-kv-fp8 |
| krea2-edit-turbo-v1 | Image › Edit (Krea 2 Turbo) | 20.82 GB | 4 | Comfy-Org/Krea-2; Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL; conradlocke/krea2-identity-edit |
| krea2-general-edit-v2 | Image › Edit (Krea 2 with the general edit LoRA) | 20.82 GB | 4 | Comfy-Org/Krea-2; Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL; conradlocke/krea2-identity-edit |
| krea2-edit-kroma-v1 | Image › Edit (Krea 2, Kroma) | 21.46 GB | 4 | Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL; conradlocke/krea2-identity-edit; silveroxides/Kroma-Quant |
| p-h3-image-lora-edit-v1 | Image › Edit (P-H3-Image) | 31.19 GB | 4 | Comfy-Org/MiniMax-H3; PrunaAI/P-H3-Image-Comfy |
| qwen-image-2.1-edit-pe-v3-v2 | Image › Edit (Qwen-Image 2.1) | 27.09 GB | 7 | Comfy-Org/Qwen-Image-2.1; Comfy-Org/Qwen3-VL; PrunaAI/Pruna-Q-Image-2.1; Qwen/Qwen-Image-2.1-PE-I2I; Qwen/Qwen-Image-2.1-PE-T2I |
| qwen-image-2.1-edit-pe-v3 | Image › Edit (Qwen-Image 2.1, earlier pin) | 27.09 GB | 5 | Comfy-Org/Qwen-Image-2.1; Comfy-Org/Qwen3-VL; PrunaAI/Pruna-Q-Image-2.1 |
| krea2-identity-edit-v2 | Image › Edit that keeps a person's identity (Krea 2 with the identity edit LoRA) | 20.82 GB | 4 | Comfy-Org/Krea-2; Comfy-Org/Qwen-Image; Comfy-Org/Qwen3-VL; conradlocke/krea2-identity-edit |
| flux3-klein-box-edit-v1 | Image › Edit: the Box tool | 11.02 GB | 3 | Comfy-Org/Flux-2-Dev; Comfy-Org/Krea-2; KoalaNation/FLUX-3-KLEIN-MODELS |
| minimax-h3-t2v | Video: a take from a prompt | 42.47 GB | 4 | Comfy-Org/MiniMax-H3; Nodes: chanon/comfyui-obvpm-timeline, kijai/ComfyUI-KJNodes, ComfyUI core ResolutionSelector (ComfyUI >= 0.25.0) |
| minimax-h3-frames-v1 | Video: a take from keyframes | 41.05 GB | 5 | Comfy-Org/MiniMax-H3; Kijai/MiniMax-H3-experimental; Momoking/MiniMax-H3-Turbo-Lora-ComfyUI; Nodes: chanon/comfyui-obvpm-timeline |
| minimax-h3-references-v1 | Video: a take from reference pictures, clips and sound | 45.59 GB | 6 | Comfy-Org/MiniMax-H3; Kijai/MiniMax-H3-experimental; Momoking/MiniMax-H3-Turbo-Lora-ComfyUI; Nodes: chanon/comfyui-obvpm-timeline |
| minimax-h3-extend-mctx-v1 | Video: continue a take | 40.43 GB | 4 | Comfy-Org/MiniMax-H3; Kijai/MiniMax-H3-experimental; Nodes: chanon/comfyui-obvpm-timeline |
| minimax-h3-bridge-mctx-v1 | Video: fill the gap between two takes | 40.43 GB | 4 | Comfy-Org/MiniMax-H3; Kijai/MiniMax-H3-experimental; Nodes: chanon/comfyui-obvpm-timeline |
| minimax-h3-finish-v1 | Video: finishing pass (latent upscale, frame interpolation) | 4.49 GB | 4 | Comfy-Org/Frame-Interpolation; Comfy-Org/MiniMax-H3; KENIC-1/minimax_h3_latent_upscaler_3d_fp16_V2; Kijai/MiniMax-H3-experimental; Nodes: chanon/comfyui-obvpm-timeline, LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler |
| minimax-h3-prepend-mctx-v1 | Video: lead into a take | 40.43 GB | 4 | Comfy-Org/MiniMax-H3; Kijai/MiniMax-H3-experimental; Nodes: chanon/comfyui-obvpm-timeline |
| relayvsr-video-upscale-v1 | Video: upscale ×2 or ×4 (RelayVSR) | 10.58 GB | 4 | Comfy-Org/RelayVSR |

</details>

To see what a workflow needs, ask Hermes: "Which model files am I missing for &lt;workflow&gt;?" The tool
`continuo_models_missing` compares the list with your ComfyUI folders and names each missing file with its folder,
size, sha256, license and pinned download link. It never downloads anything.

### Other external parts

Not installed by this plugin.

| Part | Needed for, where, measured size |
|:---|:---|
| ffmpeg | required for Cut, Deliver and Audio; found through FFMPEG_PATH, then PATH, then C:\ffmpeg\bin. Tested with ffmpeg 7.1.1 (gyan.dev full build, 0.44 GB measured). |
| ComfyUI | optional; only for generating images, video, music and voice. Root: FILM_SUITE_COMFY_ROOT when set, else the plugin setting comfy_root (Hermes Settings > Plugins > Continuo; an existing absolute local folder), otherwise the usual install (Documents\ComfyUI-Easy-Install\ComfyUI on Windows); models elsewhere: FILM_SUITE_COMFY_MODELS when set, else the plugin setting comfy_models; both folders are set by the artist only. Server: FILM_SUITE_COMFY_URL when set, else the plugin setting comfy_url (Hermes Settings > Plugins > Continuo; origin only: no credentials, path or query; another machine receives the prompts and pictures), otherwise this machine only, http://127.0.0.1:8188 then http://127.0.0.1:8000 (the first that answers). The ComfyUI folder without models, custom nodes and outputs measured 0.27 GB; its Python environment, custom nodes and models need extra space (model sizes above). |
| optional engines | beat tracking, song map, scene analysis, object removal (LaMa) and speech detection. Not installed with this plugin: each has its own installer, which downloads its Python environment and model files when you run it (sizes under Optional analysis engines). Features that need one show it as not installed. |

### Optional analysis engines

Better beat tracking, song maps, scene analysis, object removal and dialogue detection. Nothing below is installed with
Continuo: each engine has its own installer, which downloads what it needs when you run it.

**Engines and how to install them**

<details>
<summary>Show</summary>

Run these from the plugin directory; they need `uv` and `git` on the PATH. Beat, song and scene create their own Python environments and never modify the Hermes environment. Environment sizes are measured on Windows with the CUDA build of torch; with `--cpu-only` the song environment measured 1.0 GB and the scene environment 1.2 GB. macOS is not measured. Model sizes are the files' own.

| Engine | Adds | Installer | Models | Environment |
|:---|:---|:---|---:|---:|
| Beat | Better beat tracking | `python scripts/install-beat-engine.py` | 81 MB | 4.5 GB |
| Song | Named song parts, drums, melody and words on the song map | `python scripts/install-song-engine.py` | 5.0 GB | 5.0 GB |
| Scene | Measure sync on a take, cuts, speakers, camera move | `python scripts/install-scene-engine.py` | 0.6 GB | 5.1 GB |
| LaMa | Remove in Image | `python scripts/install-lama-engine.py` | 0.2 GB | the scene engine's |
| Silero VAD | Music lowered under dialogue | `python scripts/install-speech-engine.py` | 2.3 MB | none |

Model files come from their publishers at one pinned revision each ([sources](scripts/engine_models.py)) and are accepted only with their pinned sha256. They go to `engines/models/` beside the engines. A file that is already there is checked and kept, an interrupted download resumes on the next run, and `--no-download` fetches nothing and lists what is missing. Beat, song and scene take `--cpu-only`.

- **Scene:** Measure sync also uses ComfyUI's own face landmarker code, so it needs a ComfyUI install in the [ComfyUI folder](#requirements); cuts, speakers and camera move do not.
- **LaMa:** install the scene engine first, it runs in that environment (or name another one with torch, numpy and Pillow: `--reuse-venv`). It reads `models/inpaint/big-lama.pt` in your ComfyUI folder when that file is there.

Silero installs the model only; dialogue ducking also needs `onnxruntime` importable by the Continuo backend Python process. It does not use a separate engine venv.

**Transcription:** `faster-whisper` is provided by Hermes' local speech-to-text (voice) option. Continuo uses `large-v3` offline only: cache `Systran/faster-whisper-large-v3` beforehand, for example by running `python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-large-v3')"` in the same user/cache environment. Without the package or cached model, transcription shows as unavailable.

On macOS the default engine location is `~/Library/Application Support/hermes/film-suite/engines/`; on Linux it is `~/AppData/Local/hermes/film-suite/engines/`, unless `LOCALAPPDATA` or the engine lookup override `FILM_SUITE_BEAT_ENGINE_DIR`, `FILM_SUITE_SONG_ENGINE_DIR`, `FILM_SUITE_SCENE_ENGINE_DIR`, or `FILM_SUITE_INPAINT_ENGINE_DIR` is set; the installers do not read these engine-specific overrides, so use their `--engine-dir` flag to match one.

Thanks to @ShawnCRMer for reporting the missing installer (#1) and for the macOS port (#2).

</details>

## Talk to Hermes

Continuo gives Hermes 212 `continuo_*` tools that cover all pages. Hermes picks the right ones from a plain
sentence, and the page you have open shows the result live.

| You say | Hermes uses |
|:---|:---|
| "Open the sample film in Continuo, swap the first two shots and export an MP4." | `continuo_project_sample`, `continuo_timeline_apply`, `continuo_timeline_export_check`, `continuo_timeline_export` |
| "Rewrite scene 2 so the ferryman speaks first." | `continuo_script_read`, `continuo_script_scene_write` |
| "Analyse the song and put it under the cut." | `continuo_music_analyse_start`, `continuo_use_in_cut` |
| "What is running in Jobs? Stop the render." | `continuo_jobs_list`, `continuo_timeline_export_cancel` |
| "Which model files am I missing for minimax-h3-frames-v1?" | `continuo_models_missing` |
| "Is Continuo ready, or still preparing?" | `continuo_dependencies` |

## What this plugin does on your machine

Everything Continuo does outside its own window is listed here: the install scan, the network, the programs it starts, background work and where it keeps data.

### Install scan

Hermes' install scan rates Continuo as **caution** because Continuo starts programs (ffmpeg, ffprobe and the optional
local engines listed under [Programs it starts](#programs-it-starts)), talks to `127.0.0.1` (ComfyUI and those
engines), reads `/proc/self/fd` on Linux to re-open a file it already holds, and ships a large bundled
`desktop/plugin.js` (encoded data and `../` import paths inside it).

From the Hermes plugin catalog it installs by name: `hermes plugins install film-suite`. The catalog points at a reviewed
version and can be behind this repository.

### Network

Continuo calls only these hosts:

| Host | Why |
|:---|:---|
| `127.0.0.1` | local ComfyUI (HTTP + websocket) and the plugin's own loopback routes |
| `civitai.com` | LoRA lookup by file sha256, on the user's request |
| `image.civitai.com` | LoRA preview images of that lookup |
| `imagecache.civitai.com` | LoRA preview images of that lookup |
| `optim-images.krea.ai` | style-browser thumbnails of an uncached board |
| `cloud.cp.jku.at` | Beat This! checkpoint download when the optional beat installer is run |
| `huggingface.co` | model files of an optional engine when you run its installer (song, scene, LaMa: each file at one pinned revision, accepted only with its pinned sha256), and the Beat This! checkpoint's second source when cloud.cp.jku.at fails. Downloads are redirected to Hugging Face's own file hosts (*.hf.co) |
| `download.pytorch.org` | PyTorch wheels when optional hash-locked engine installers are run (the files come from download-r2.pytorch.org) |
| `pypi.org` | Python packages when optional hash-locked engine installers are run (the files come from files.pythonhosted.org) |
| `releases.astral.sh` | Python 3.10 (22 MB) for an engine's own environment, fetched by uv when an optional beat, song or scene installer is run and uv finds no Python 3.10.20 on the machine |
| `raw.githubusercontent.com` | pinned Silero VAD model and the ADTOF drum model (3.6 MB) when their optional installers are run |
| `github.com` | the LaMa model (206 MB, a release file, redirected to release-assets.githubusercontent.com) and pinned model code of the song and scene engines (git) when their optional installers are run |

Never fetched:

- Links in documentation and metadata only: `hermes-agent.nousresearch.com`, `fountain.io`, `www.w3.org`, `ns.adobe.com`, `docs.comfy.org`, `www.minimax.io`, `ffmpeg.org`.
- Source citations in the bundled music reference list: `blogs.loc.gov`, `downloads.bbc.co.uk`, `imslp.org`, `mtosmt.org`, `songdata.io`, `www.musicnotes.com`.
- Source citations in the bundled prompt skills (`skills/*/references/`): links to model cards, vendor documentation and community posts.

The language model Hermes uses is your Hermes setting, not part of this plugin; it may be remote.

### Programs it starts

| Program | Why |
|:---|:---|
| `ffmpeg` | decode, render and export pictures, clips and sound (Cut, Deliver, Audio) |
| `ffprobe` | read the length, size and streams of media you add |
| `engine venv pythons` | optional analysis engines (beat tracking, song map, scene analysis, speech detection, inpainting), each in its own Python environment, only when you start that analysis and only if the engine is installed |
| `explorer/open/xdg-open` | "Show in folder" for a file you asked to reveal |

### Background work

Only while something you started runs:

- export jobs (one thread per Deliver export; cancellable from Deliver)
- control-map extraction jobs (Video controls)
- voice-take jobs (Audio voice)
- music-take jobs (Audio music)
- ComfyUI job watchers (websocket to 127.0.0.1 while a generation you submitted runs)
- picture-mask jobs (asyncio tasks for a mask you asked for)
- style-board thumbnail downloads (a small thread pool while a style board you opened has no cached thumbnails)
- image readiness check (one short thread while the model list is read: it asks ComfyUI which nodes and files it has and waits at most 60 seconds)
- graphics memory release (one thread, started when Continuo sends work to ComfyUI: every 30 seconds it reads ComfyUI's queue and its newest history entry at the ComfyUI address in use; when nothing has run there for the minutes set under Free graphics memory after, default 10, it asks ComfyUI once to unload its models and free graphics memory, then ends; 0 minutes turns it off)
- The Hermes mark follows the exact operations Hermes asked for; the page is trusted to use them only for that action, and when the record cannot be read the work is shown as the artist's.
- picture bring-home: there is no background service. A Jobs list or status call that finds a finished picture fetches it from ComfyUI and publishes it into Media, and normally waits for it. At most 4 fetches or publications run at once in the whole process, and one Jobs call selects at most 4 pictures, oldest eligible owned job first, at most 2 runs per call; jobs already publishing or waiting to retry are skipped, and work over the limit is left for a later look. A run of 200 or more older pending jobs that cannot be read or checked can still hold back later ones. A Jobs list fetch still waiting after 20 seconds is stopped and reported on its Jobs API row as TimeoutError with code collect-deadline; the page shows "Slow to arrive; tried again on the next look" on that job. A status fetch has no deadline. Publication runs on a thread of its own: closing or cancelling the request does not stop a publication already running, it continues and finishes unless it gets stuck. A publication still running after 20 seconds is reported as TimeoutError with code publication-overdue on its Jobs API row when that job is in the listed rows, and the page shows "Still saving into Media" on that job; a stuck publication keeps its slot until Hermes is closed. If Hermes stops after the picture is recorded as ingested, a later Jobs look can finish it without fetching again. If it stops before the ingested ledger record, it may need to be fetched again; if provider output is missing by then, the job is marked failed and the picture is not recovered from the stage; the artist can submit a new run with the same settings
- video-take line (one thread while video takes wait, a waiting take's predecessor runs or a take's cancel is not yet carried out: starts the next take when ComfyUI is free and follows it until it ends; a thread silent past the deadline is replaced by the next request, and every poll, cancel or Jobs list also recovers stalled takes; ends when nothing is left). Timers only decide when Hermes looks: what happened to a take is decided by what ComfyUI lists under the take's marker. Cleaning up late copies is best effort. A submit whose engine ID was lost is checked while Hermes is running and ComfyUI answers; that can take longer than five minutes. A late submission may start before Hermes sees it; Hermes then tries to stop it. A copy that already finished cannot be undone, and its output stays in ComfyUI. Hermes remembers a given-up take for 24 hours and looks in ComfyUI's queue and its last 100 history entries; a copy outside that can be missed. A later take can reach ComfyUI before an earlier delayed one. While a given-up take is remembered, one more thread looks every 15 seconds, also with no page open, and ends when none is left. Media already uploaded to ComfyUI are not deleted. A synchronous operation that hangs cannot be forcibly stopped in Python; its helper thread can remain until it returns or the process exits, and a cancel it was carrying out is taken over by the next recovery check after one minute. A Stop that got no answer may or may not have been kept: check the take and press Stop again if it still runs. A Hermes process that stops responding entirely needs a restart; the line then continues from where it was.

To tell whether a music or voice take left running belongs to a Hermes that has stopped, Continuo asks the system
whether that process still runs. It only reads; it never signals or ends a process.

### Where it keeps data

- your project folders: project.json, script/, state/, pictures/, clips/, sound/, output/ (Deliver) and exports/ (script, picture and previz exports) inside the folder you chose
- <HERMES_HOME>/plugin-data/film-suite/: recent projects, job databases with a small owner note per running music or voice take, image edits, LoRA cache, style thumbnails
- <HERMES_HOME>/cache/film-suite/: staging copies of results before they are published to a project
- %LOCALAPPDATA%\hermes\film-suite\: this machine's own records (approved folders, who started a job, review decisions, analysis caches, posters); without LOCALAPPDATA on macOS ~/Library/Application Support/hermes/film-suite/, on Linux the temp folder
- %LOCALAPPDATA%\hermes\film-suite\engines\ (without LOCALAPPDATA on macOS ~/Library/Application Support/hermes/film-suite/engines/, on Linux ~/AppData/Local/hermes/film-suite/engines/): optional analysis engines, only if you install them
- a per-profile receipt key inside the Hermes home, protected with a user+SYSTEM-only ACL on Windows (0600 on POSIX)

### Private Hermes access

Continuo uses no private Hermes interface. Hermes signs in every request to Continuo's routes before Continuo sees it.

## Troubleshooting

| You see | Do this |
|:---|:---|
| The install asks about a **caution** rating | Expected for this plugin (see [Install](#install)). Answer `y`, or run the install again with `--force`. |
| Continuo is not in the sidebar | Open **Capabilities > Plugins**, find **Continuo** and turn its switch on. A restart does not do this. |
| "Preparing the Audio engine, or restart Hermes" or "Preparing picture import, or restart Hermes" | A Python package is unavailable in this process. Hermes may still be setting it up, or may need a restart after setup. Hermes can check with `continuo_dependencies`. |
| The Sample film tile says "ffmpeg not found" | Install ffmpeg and put it on `PATH`, set `FFMPEG_PATH`, or place it in `C:\ffmpeg\bin`; then choose **Sample film** again. No half-made sample is left behind. |
| A recent project is unavailable or its project file is missing | Restore `project.json` and the project folder from the original or a backup, or open another project folder. If the missing project was a Sample film, choose the Sample film tile to create a new copy. |
| "ComfyUI is not running." | Start ComfyUI on this machine. Continuo asks `http://127.0.0.1:8188`, then `http://127.0.0.1:8000`; another address goes in Hermes Settings › Plugins › Continuo (Test shows whether ComfyUI answers there), or in `FILM_SUITE_COMFY_URL`, which overrides the setting. |
| A model is missing | Ask Hermes "Which model files am I missing for &lt;workflow&gt;?" (`continuo_models_missing`), which names each file with its folder, size, sha256 and pinned download link; put the file into that ComfyUI folder. |
| An analysis shows as unavailable | It may need an optional engine. See [Optional analysis engines](#optional-analysis-engines). |

## Roadmap

What comes next is listed in `ROADMAP.md`.

## Feedback

Issues are welcome at [github.com/realartsbro/continuo/issues](https://github.com/realartsbro/continuo/issues). Please include:

- the page (Script, Audio, Image, Video, Cut, Deliver, Media, Jobs) and the steps that led there
- a screenshot
- your Hermes version (`hermes --version`)
- the Continuo build: `source_commit` from `BUILD-INFO.json` in the plugin folder

Pull requests are welcome through a fork. This repository is a built tree: the maintainer carries an accepted change
over into the source, and it comes back here with the next build.

### Testing on macOS and Linux

Continuo is built and tested on Windows. Runs on macOS and Linux are the most useful help right now, by hand or by your
agent. Open issues labelled `help wanted` name what to run, and each states what it downloads.

| Step | Downloads |
|:---|:---|
| Install, enable, export the Sample film | the plugin (24 MB) and its Python packages (511 MB), plus ffmpeg |
| Open Continuo in Hermes Desktop | nothing more |
| An optional engine | up to 5 GB of model files and 1 to 5 GB for its Python environment; each size is under [Optional analysis engines](#optional-analysis-engines) |
| A model through ComfyUI | 5 to 46 GB per workflow; each size is under [Models](#models-optional) |

Report with the **Platform report** issue form. If an agent runs the steps for you, give it this section and the issue:
it runs the commands as written, changes no plugin file, and pastes commands, exit codes and the last lines of output.
A step that fails is a useful report and needs no fix.

## License and credits

MIT License, Copyright (c) 2026 Arts Bro. See `LICENSE`. Continuo is made and maintained by Arts Bro.

Third-party code and assets are listed in `THIRD_PARTY_NOTICES.md`: CodeMirror and three.js (bundled), Lucide icons,
the timeline edit and interchange logic ported from FilmCraft, ComfyUI workflow templates by Comfy Org, and the Krea
moodboard style prompts from [ComfyUI-Krea-Moodboards](https://github.com/Andro-Meta/ComfyUI-Krea-Moodboards) (MIT, unofficial, not affiliated with Krea AI). Models you
install keep their own licenses. The license named on each model card is recorded in
`dashboard/workflows/model-sources.json`.
Hermes Agent is by Nous Research.

Continuo is an entry to the Nous Research Hermes Agent Plugin Hackathon.
