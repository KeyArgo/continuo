"""Install the Film Suite LaMa inpaint engine (lane p13-img): the pre-fill of Image Remove.

    python scripts/install-lama-engine.py [--reuse-venv VENV] [--model BIG_LAMA_PT] [--models-dir DIR]
                                          [--no-download] [--engine-dir DIR]

Writes ``%LOCALAPPDATA%/hermes/film-suite/engines/lama-inpaint/`` (or ``--engine-dir``):
    runner.py      copy of backend/film-suite/dashboard/inpaint_core/lama_runner.py
    engine.json    record the backend reads (inpaint_core/lama_engine.locate), schema studio.inpaint-engine/1

No Python environment of its own: it runs in an EXISTING venv with torch, numpy and Pillow.  Without
``--reuse-venv`` that is the scene engine's (``engines/scene-analysis/venv``; run ``install-scene-engine.py`` first);
the installer imports the three once with that python to prove it and records the versions.

The model is the big-lama TorchScript (206 MB, sha256 344c77bb..., refused otherwise).  Without ``--model`` it is
read in place from ComfyUI's ``models/inpaint/big-lama.pt`` when that is the pinned file, else fetched into
``engines/models/big-lama/`` (``--models-dir``) from its pinned source (``scripts/engine_models.py``);
``--no-download`` fetches nothing and names the missing file.  It is loaded with ``torch.jit.load`` (spandrel breaks
its colours).  Idempotent.  Remove the directory to uninstall: Remove then refuses with ``inpaint_engine_missing``.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER_SOURCE = (REPO / "backend" / "film-suite" / "dashboard" if (REPO / "backend" / "film-suite" / "dashboard").is_dir() else REPO / "dashboard") / "inpaint_core" / "lama_runner.py"
ENGINE_SCHEMA = "studio.inpaint-engine/1"
MODEL_SHA256 = "344c77bbcb158f17dd143070d1e789f38a66c04202311ae3a258ef66667a9ea9"


def _load_engine_process():
    """The plugin's own child-process helper (``dashboard/engine_process``), loaded by path: ``backend/film-suite/``
    in the repository, the tree root in the catalog copy.  Every child of this script gets its minimal environment."""
    here = Path(__file__).resolve().parent
    for dashboard in (here.parent / "backend" / "film-suite" / "dashboard", here.parent / "dashboard"):
        path = dashboard / "engine_process" / "__init__.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location("film_suite_engine_process", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise SystemExit("dashboard/engine_process is missing next to this script; reinstall the plugin")


engine_process = _load_engine_process()
_models_spec = importlib.util.spec_from_file_location("film_suite_engine_models", Path(__file__).resolve().parent / "engine_models.py")
engine_models = importlib.util.module_from_spec(_models_spec)
_models_spec.loader.exec_module(engine_models)


def _comfy_root() -> Path:
    """The Suite's one ComfyUI folder (``generation/comfy_root.py``); an unusable saved setting falls back to the usual install."""
    spec = importlib.util.spec_from_file_location("film_suite_comfy_root", RUNNER_SOURCE.parents[1] / "generation" / "comfy_root.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.comfy_root()
    except ValueError:
        return module.default_comfy_root()


COMFY_ROOT = _comfy_root()
MODEL_FILE = "big-lama.pt"


def _machine_local() -> str:
    """LOCALAPPDATA, else ~/Library/Application Support on macOS, else ~/AppData/Local (dashboard/local_data
    engines_base, inline: this script stands alone; PR #2 by @ShawnCRMer)."""
    if os.environ.get("LOCALAPPDATA"):
        return os.environ["LOCALAPPDATA"]
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    return str(Path.home() / "AppData" / "Local")


def default_engine_dir() -> Path:
    base = _machine_local()
    return Path(base) / "hermes" / "film-suite" / "engines" / "lama-inpaint"


def default_models_dir() -> Path:
    """``engines/models``; an install from before this folder had a name keeps its ``engines/candidates``."""
    engines = Path(_machine_local()) / "hermes" / "film-suite" / "engines"
    return engines / "candidates" if (engines / "candidates").is_dir() else engines / "models"


def venv_path(explicit: Path | None, engine_dir: Path) -> Path:
    """``--reuse-venv``, else the scene engine's venv beside this engine's folder."""
    if explicit is not None:
        return Path(explicit)
    scene = Path(engine_dir).parent / "scene-analysis" / "venv"
    if not scene.is_dir():
        raise SystemExit(f"no Python environment to run in: {scene} does not exist. Run "
                         "`python scripts/install-scene-engine.py` first, or name a venv with torch, numpy and Pillow: --reuse-venv VENV")
    return scene


def model_path(explicit: Path | None, models_dir: Path, *, download: bool = True, opener=None, models: dict | None = None) -> Path:
    """``--model``, else ComfyUI's copy when it is the pinned file (read in place), else the installer's own,
    downloaded when missing (``engine_models.ensure``).  ``models`` replaces the pinned table (tests)."""
    if explicit is not None:
        return Path(explicit)
    in_comfy = COMFY_ROOT / "models" / "inpaint" / MODEL_FILE
    if in_comfy.is_file() and sha256(in_comfy) == MODEL_SHA256:
        return in_comfy
    found = engine_models.ensure(models_dir, engine_models.SETS["lama"], download=download, opener=opener,
                                 log=lambda line: print(line, flush=True), models=models)
    return Path(found["big-lama"][MODEL_FILE]["path"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def venv_python(venv: Path) -> Path:
    for candidate in (venv / "Scripts" / "python.exe", venv / "bin" / "python"):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"no python in the venv {venv}")


def probe(py: Path) -> dict:
    code = "import json, torch, numpy, PIL; print(json.dumps({'torch': torch.__version__, 'numpy': numpy.__version__, 'pillow': PIL.__version__, 'cuda': torch.cuda.is_available(), 'mps': bool(getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available())}))"
    out = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=300, env=engine_process.engine_env())
    if out.returncode != 0:
        raise SystemExit(f"the venv python cannot import torch/numpy/PIL: {out.stderr.strip()[-300:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def install(engine_dir: Path, venv: Path, model: Path, *, check_venv: bool = True) -> dict:
    if not model.is_file():
        raise SystemExit(f"model not found: {model}")
    model_sha = sha256(model)
    if model_sha != MODEL_SHA256:
        raise SystemExit(f"model sha256 {model_sha} is not big-lama.pt ({MODEL_SHA256})")
    py = venv_python(venv)
    versions = probe(py) if check_venv else {}
    engine_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUNNER_SOURCE, engine_dir / "runner.py")
    record = {
        "schema": ENGINE_SCHEMA,
        "python": str(py),
        "runner": str(engine_dir / "runner.py"),
        "runner_sha256": sha256(engine_dir / "runner.py"),
        "model": str(model),
        "model_sha256": model_sha,
        "mode": "reuse_venv",
        "venv": str(venv),
        "versions": versions,
        "loader": "torch.jit.load",
    }
    temp = engine_dir / "engine.json.tmp"
    temp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(temp, engine_dir / "engine.json")
    return record


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine-dir", type=Path, default=default_engine_dir())
    ap.add_argument("--reuse-venv", type=Path, default=None,
                    help="an existing venv with torch, numpy and Pillow (default: the scene engine's)")
    ap.add_argument("--model", type=Path, default=None,
                    help="big-lama.pt (TorchScript), read in place (default: ComfyUI's copy, else downloaded)")
    ap.add_argument("--models-dir", type=Path, default=default_models_dir(),
                    help=f"where a downloaded model goes ({engine_models.gigabytes(engine_models.total_bytes('lama'))})")
    ap.add_argument("--no-download", action="store_true", help="fetch no model file: name the missing one and stop")
    args = ap.parse_args(argv)
    venv = venv_path(args.reuse_venv, args.engine_dir)
    record = install(args.engine_dir, venv, model_path(args.model, args.models_dir, download=not args.no_download))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
