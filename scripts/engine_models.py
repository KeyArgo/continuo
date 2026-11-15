"""Model files of the optional engines: where each one comes from, and the one way to fetch them.

Nothing here runs when the plugin is installed.  An engine installer (``install-song-engine.py``,
``install-scene-engine.py``, ``install-lama-engine.py``) calls ``ensure`` when the user runs that installer:

- a file that is already in the folder is checked by its sha256 and kept;
- a missing file is downloaded from the source pinned below (one revision per repository, never a branch),
  to ``<name>.part`` first, resumed after an interruption (three tries per source, and again on the next run),
  and accepted only with the pinned sha256;
- a file that is there with another sha256 is refused, never replaced.

``--no-download`` on an installer turns the download off: missing files are then listed with their addresses.
Continuo ships none of these files.  Sizes are the files' own byte counts.

Stdlib only; starts no process.
"""
from __future__ import annotations

import hashlib
import http.client
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Callable

USER_AGENT = "continuo-engine-installer"
SPARE_BYTES = 256 * 1024 * 1024  # free space kept beyond the download itself
TRIES = 3            # per source, each resuming the part file
RETRY_PAUSE_S = 3.0  # before the second and third try
PROGRESS_BYTES = 512 * 1024 * 1024  # a line this often while a large file comes in
# folder -> sources (tried in order; the sha256 decides, not the host), revision, licence, files {path: (bytes, sha256)}
MODELS = {
    "adtof-pytorch": {
        "sources": ["https://raw.githubusercontent.com/xavriley/ADTOF-pytorch/85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9/src/adtof_pytorch/data/"],
        "revision": "85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9",
        "licence": "CC-BY-NC-SA-4.0 (ADTOF weights)",
        "files": {
            "adtof_frame_rnn_pytorch_weights.pth": (3617805, "1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320"),
        },
    },
    "rmvpe": {
        "sources": ["https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/e6d0c1a17da07c33557852f9dfa2bd44cc75737d/"],
        "revision": "e6d0c1a17da07c33557852f9dfa2bd44cc75737d",
        "licence": "MIT",
        "files": {
            "rmvpe.onnx": (361688443, "5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd"),
        },
    },
    "qwen3-forcedaligner-0.6b": {
        "sources": ["https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B/resolve/c7cbfc2048c462b0d63a45797104fc9db3ad62b7/"],
        "revision": "c7cbfc2048c462b0d63a45797104fc9db3ad62b7",
        "licence": "Apache-2.0",
        "files": {
            "config.json": (5982, "d616c65d46c4b90bdc651b0a0963ea932732241140f337f9bb6b0335a9c8ef09"),
            "model.safetensors": (1835544544, "47831d0e82f96b20e9034dba01a075ee06436654719f6a68289e49f1b65ce0e7"),
            "preprocessor_config.json": (330, "45e120a4eda2c20c5d7f2ea9354e63536bf35e27aa573fb7cdf78017b378770d"),
            "tokenizer_config.json": (12666, "3ab80063f8511deb9566e6ad438d17b7a6277fcffd52d92854112f19d36bd81c"),
            "vocab.json": (2776833, "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910"),
            "merges.txt": (1671853, "8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5"),
            "chat_template.json": (1161, "75a8cfca24f00de72d796fbfed6858fc9614ef3dabd8696684cc3bc03a9c58ff"),
            "generation_config.json": (115, "948d089b23bca1d214e768d59c4438365665f52ec6d33678f4062206b3fbbb8c"),
        },
    },
    "songformer": {
        "sources": ["https://huggingface.co/ASLP-lab/SongFormer/resolve/a75880ed1b7375ac71860ec6c4fc9c899cf99515/"],
        "revision": "a75880ed1b7375ac71860ec6c4fc9c899cf99515",
        "licence": "code CC-BY-4.0; MuQ part CC-BY-NC-4.0",
        "files": {
            "model.safetensors": (2755035132, "8dcabf4ea19973edd51b9e5794004775fa7e8de3ecfa07eb1dbce00f516ce7f7"),
            "config.json": (655, "912c39afb6543fedfd47f27eb1596ed971bb4911e374e24e9ffe329bf6cb303d"),
            "configuration_songformer.py": (736, "8d4b5660645901c0a54ffb3a7b7e4667e35b572981c3b203fbdc04a614e210fa"),
            "model.py": (18578, "d0e32c179f044ccca553375bf31d71c3fc24ff2c723f0e2dbb3f77bc867bb28a"),
            "model_config.py": (2725, "3676ead26f900d664dc89d86a216482e778833a65f2279fb8e726b61290680f6"),
            "modeling_songformer.py": (12436, "904c8e650f753c918038ac24e776df94464df61de911bf5d35eb1a0f17e83cb3"),
            "msd_stats.json": (2531, "10a2ca43de6b94522bfb651fdfccc2336d89a8a746af0a597528f66f56e64586"),
            "muq_config2.json": (3719, "8de4a64926105f3377d715615e59f6798db60bcae94a9aa45d21edb18fc370fa"),
            "musicfm/model/__init__.py": (2, "75a11da44c802486bc6f65640aa48a730f0f684c5c07a42ba3cd1735eb3fb070"),
            "musicfm/model/musicfm_25hz.py": (8615, "33071676d19f953318ead3099bead5a44f40ec455fb4ff550d9d7d0616a215a1"),
            "musicfm/modules/__init__.py": (2, "75a11da44c802486bc6f65640aa48a730f0f684c5c07a42ba3cd1735eb3fb070"),
            "musicfm/modules/conv.py": (3154, "585705a6450db374e8c411034e846491f7f48d4ed0516fbf8d3b84855ef0d7d1"),
            "musicfm/modules/features.py": (1869, "aa8e99711f4a4eab522ff89fe86fc27e281e373ed0ae416743736da229f171da"),
            "musicfm/modules/flash_conformer.py": (95453, "c0bf5df817a9c50e4706b4414b75e5399bcbdf89cec3a03de05f5ad8d0b3abfb"),
            "musicfm/modules/random_quantizer.py": (3055, "2ffae390fbf7fefa8a62000ba0490af92ecc001d3b5715fb98f7a1e1578c2aa2"),
            "postprocessing/functional.py": (2567, "0bafe5406ee38fefabdf4537c5c0572331e717e950bf05c4ee3d9c6a5be6b898"),
            "postprocessing/helpers.py": (3732, "06f970fdcf42e02b4ae9395a69a5a902ec96ecc2aaa38a949ecc34517984ffbb"),
        },
    },
    "syncnet-v2": {
        "sources": ["https://huggingface.co/ByteDance/LatentSync-1.6/resolve/c42c7e6c8e9c213626389fa7d9a3c444b8536353/"],
        "revision": "c42c7e6c8e9c213626389fa7d9a3c444b8536353",
        "licence": "no licence stated (Oxford VGG weights via LatentSync mirror)",
        "files": {
            "auxiliary/syncnet_v2.model": (54573114, "961e8696f888fce4f3f3a6c3d5b3267cf5b343100b238e79b2659bff2c605442"),
        },
    },
    "omnishotcut": {
        "sources": ["https://huggingface.co/uva-cv-lab/OmniShotCut/resolve/7b59cc525168ea13d36dcf08db6885fd7edc2215/"],
        "revision": "7b59cc525168ea13d36dcf08db6885fd7edc2215",
        "licence": "MIT",
        "files": {
            "OmniShotCut_ckpt.pth": (164149963, "5948ea78e00626c0e6c5e742e64873ef872cf4a5071d2a0841aed51c3e686cfa"),
        },
    },
    "nemotron-3-diarization": {
        "sources": ["https://huggingface.co/nvidia/Nemotron-3-Diarization/resolve/f667ed73aee57d40cc39428eb768b4fd87a0a29e/"],
        "revision": "f667ed73aee57d40cc39428eb768b4fd87a0a29e",
        "licence": "OpenMDW-1.1",
        "files": {
            "model.safetensors": (396954592, "c074d86335b3b794f8fa5edc25594558f128bdb3914d27806a3a5a2e44963cb6"),
            "config.json": (1458, "dd795ec07ffa09acf18d231aa3fa8642aa5c521760953754e02559a7413b6873"),
            "processor_config.json": (623, "91726746788a024a2f0f2f699a6c3667f0d74e6a0e9288fc44fe3018e23af68e"),
        },
    },
    "mediapipe-face": {
        "sources": ["https://huggingface.co/Comfy-Org/mediapipe/resolve/f787efc1ad99492ec7d5b6564c0dd6c48d84ee49/detection/"],
        "revision": "f787efc1ad99492ec7d5b6564c0dd6c48d84ee49",
        "licence": "Apache-2.0",
        "files": {
            "mediapipe_face_fp32.safetensors": (5423900, "a98c4806081d40eba35102a0f6dc0000c2e1388b72cf24e691703d0605bd888a"),
        },
    },
    "big-lama": {
        "sources": [
            "https://github.com/Sanster/models/releases/download/add_big_lama/",
            "https://huggingface.co/signature-ai/big-lama/resolve/0c69ed801efa8bda408da0a9203da9800d0ea9e7/",
        ],
        "revision": "add_big_lama",
        "licence": "Apache-2.0",
        "files": {
            "big-lama.pt": (205669692, "344c77bbcb158f17dd143070d1e789f38a66c04202311ae3a258ef66667a9ea9"),
        },
    },
}

# What each installer needs.
SETS = {
    "song": ("adtof-pytorch", "rmvpe", "qwen3-forcedaligner-0.6b", "songformer"),
    "scene": ("syncnet-v2", "omnishotcut", "nemotron-3-diarization"),
    "face": ("mediapipe-face",),
    "lama": ("big-lama",),
}


def total_bytes(*sets: str) -> int:
    return sum(size for name in sets for folder in SETS[name] for size, _sha in MODELS[folder]["files"].values())


def gigabytes(count: int) -> str:
    if count >= 1e8:
        return f"{count / 1e9:.1f} GB"
    return f"{count / 1e6:.1f} MB" if count >= 1e5 else f"{max(1, round(count / 1e3))} KB"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receive(url: str, part: Path, size: int, opener: Callable, log: Callable) -> None:
    """One try: append to ``part`` from where it stops (or start over when the server sends the whole file)."""
    have = part.stat().st_size if part.is_file() else 0
    if have > size:
        part.unlink()
        have = 0
    if have >= size:
        return
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    with opener(urllib.request.Request(url, headers=headers), timeout=120) as response:
        resumed = bool(have) and getattr(response, "status", 200) == 206
        done = have if resumed else 0
        said = done // PROGRESS_BYTES
        with part.open("ab" if resumed else "wb") as out:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                out.write(chunk)
                done += len(chunk)
                if done // PROGRESS_BYTES > said and done < size:
                    said = done // PROGRESS_BYTES
                    log(f"    {gigabytes(done)} of {gigabytes(size)}")


def _fetch(sources: list[str], label: str, rel: str, dest: Path, size: int, want: str, opener: Callable,
           log: Callable = print) -> None:
    """Download ``rel`` to ``dest`` from the first source that delivers the pinned sha256."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    problems = []
    for base in sources:
        url = base + rel
        failed = None
        for attempt in range(TRIES):
            if attempt:
                time.sleep(RETRY_PAUSE_S)
            try:
                _receive(url, part, size, opener, log)
                failed = None
                break
            except (OSError, http.client.HTTPException) as exc:  # the part stays: the next try resumes it
                failed = exc
        if failed is not None:
            problems.append(f"{url}: {failed}")
            continue
        got = sha256(part)
        if got == want:
            part.replace(dest)
            return
        part.unlink()
        problems.append(f"{url}: sha256 {got}, expected {want}")
    raise SystemExit(f"could not get {label}/{rel}:\n  " + "\n  ".join(problems)
                     + "\nRun the installer again to resume, or place the file yourself and use --no-download.")


def ensure(root: Path, folders: tuple[str, ...], *, download: bool = True, opener: Callable | None = None,
           log: Callable = print, models: dict | None = None) -> dict:
    """Every file of ``folders`` under ``root`` with its pinned sha256: {folder: {path: {"path", "sha256"}}}.

    ``models`` replaces the pinned table (tests).  Stops with the fact (SystemExit) on a file with another sha256, on
    missing files with ``download=False``, on too little disk space and on a failed download.
    """
    table = MODELS if models is None else models
    root = Path(root)
    out: dict = {}
    missing = []
    for folder in folders:
        out[folder] = {}
        for rel, (size, want) in table[folder]["files"].items():
            path = root / folder / rel
            if not path.is_file():
                missing.append((folder, rel, path, size, want))
                continue
            got = sha256(path)
            if got != want:
                raise SystemExit(f"sha256 mismatch {path}: {got} != {want} (not replaced; remove the file to fetch it again)")
            out[folder][rel] = {"path": str(path), "sha256": got}
            log(f"model ok: {folder}/{rel}")
    if not missing:
        return out
    need = sum(size for _folder, _rel, _path, size, _want in missing)
    if not download:
        lines = [f"  {path}  <-  {table[folder]['sources'][0] + rel}" for folder, rel, path, _size, _want in missing]
        raise SystemExit(f"{len(missing)} model files are missing ({gigabytes(need)}) and --no-download is set:\n" + "\n".join(lines))
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    if free < need + SPARE_BYTES:
        raise SystemExit(f"not enough disk space in {root}: {gigabytes(need)} to download, {gigabytes(free)} free")
    log(f"downloading {len(missing)} model files, {gigabytes(need)}, to {root}")
    for folder, rel, path, size, want in missing:
        log(f"  {folder}/{rel} ({gigabytes(size)})")
        _fetch(table[folder]["sources"], folder, rel, path, size, want, opener or urllib.request.urlopen, log)
        out[folder][rel] = {"path": str(path), "sha256": want}
    return out
