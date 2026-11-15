---
name: Platform report
about: A run of Continuo on macOS or Linux
labels: platform
---

**System**
- Operating system and version:
- CPU, GPU and memory:
- Hermes (`hermes --version`):
- Continuo build (`source_commit` in `BUILD-INFO.json` of the plugin folder):
- ffmpeg (`ffmpeg -version`, first line):
- ComfyUI version, if used:

**Which issue this run answers**
#

**Steps run**
For each: the command or click, the result (worked or failed), and for a failure the last 20 lines of output.

**Files**
The `ffprobe` line of an exported file, screenshots, and for a backend error the lines from `logs/agent.log`.

**Run by**
Hand, or an agent (which one).
