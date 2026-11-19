"""The one ComfyUI root and the one models folder of the Film Suite (lane w7-rest item 3; lane w41-folders item 1).

ComfyUI folder, in this order: ``FILM_SUITE_COMFY_ROOT`` when set (the override); else the plugin setting
``plugins.entries.film-suite.settings.comfy_root`` (Hermes Settings > Plugins > Continuo); else the root recorded at
install time (``fallback``); else ComfyUI-Easy-Install's folder in the user's Documents (on Windows always; elsewhere
the first existing usual install, see ``default_comfy_root``).  Every reader goes through ``comfy_root()``: the model
catalog (``model_catalog.py``), ``GET /models/missing`` (``routes/generation/model_sources_1.py``), the Krea2 render
spec's models folder, the scene engine's MediaPipe import and its installer.

Models folder elsewhere: ``FILM_SUITE_COMFY_MODELS`` when set, else the setting ``comfy_models``, else none (ComfyUI's
own ``<root>/models``).  Every reader goes through ``comfy_models()``.

A setting is read at every call through Hermes' own config reader (``comfy_endpoint.plugin_setting``, cached on the
file's signature), so a saved change reaches the next call without a restart.  A saved folder that is not text, not
absolute, a network (UNC) or device path, or not an existing folder raises ``FolderSettingError`` (a ValueError
carrying the fact): never a silent fallback to another folder.  A network path is refused on its text alone, before
any filesystem call.  The variables keep today's meaning (taken as written).

Stdlib only, no package imports: it is loaded by relative import and by file path alike.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV = "FILM_SUITE_COMFY_ROOT"
MODELS_ENV = "FILM_SUITE_COMFY_MODELS"
ROOT_SETTING = "comfy_root"  # plugin.yaml config_schema: plugins.entries.film-suite.settings.comfy_root
MODELS_SETTING = "comfy_models"  # plugin.yaml config_schema: plugins.entries.film-suite.settings.comfy_models
VARIABLES = {ROOT_SETTING: ENV, MODELS_SETTING: MODELS_ENV}
LABELS = {ROOT_SETTING: "ComfyUI folder", MODELS_SETTING: "models folder"}
SOURCE_VARIABLE, SOURCE_SETTING = "variable", "setting"
_HERE = Path(__file__).resolve().parent
_LOADED: dict[str, object] = {}


class FolderSettingError(ValueError):
    """A saved folder setting that cannot be used, with the fact; ``setting_key`` names the setting."""

    comfy_folder_setting = True

    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.setting_key = key


def _sibling(name: str, path: Path):
    module = _LOADED.get(name)
    if module is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED[name] = module
    return module


def plugin_setting(key: str) -> object:
    """The saved setting through the address module's reader (Hermes' own, the same test guard), or None."""
    try:
        endpoint = _sibling("film_suite_comfy_root_endpoint", _HERE / "comfy_endpoint.py")
    except (OSError, ImportError):  # a copy of this file without its siblings: no setting
        return None
    return endpoint.plugin_setting(key)


def variable_value(key: str) -> str:
    """The override variable of a folder setting as text ('' = not set)."""
    return (os.environ.get(VARIABLES[key]) or "").strip()


def setting_text(key: str) -> str | None:
    """The saved folder setting as text ('' = not set), None when the saved value is not text."""
    value = plugin_setting(key)
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else None


def folder_reason(key: str, text: object) -> str | None:
    """None when ``text`` names an existing absolute local folder; else the fact. A network or device path is refused
    on its text, before any filesystem call."""
    label = LABELS[key]
    if not isinstance(text, str):
        return f"The {label} setting is not text"
    try:
        local_path = _sibling("film_suite_comfy_root_local_path", _HERE.parent / "studio_core" / "local_path.py")
        remote = local_path.remote_path_reason(text)
    except (OSError, ImportError):
        remote = "unchecked" if text.strip().replace("/", "\\").startswith("\\\\") else None
    if remote is not None:
        return f"The {label} setting is a network (UNC) or device path"
    path = Path(text)
    if not path.is_absolute():
        return f"The {label} setting is not an absolute path"
    try:
        exists = path.is_dir()
    except OSError:
        exists = False
    return None if exists else f"The {label} setting names a folder that does not exist"


def _saved_folder(key: str) -> Path | None:
    """The saved folder setting, None when not set; an unusable one raises FolderSettingError."""
    text = setting_text(key)
    if text == "":
        return None
    reason = folder_reason(key, text)
    if reason is not None:
        raise FolderSettingError(key, reason)
    return Path(text)


def folder_source(key: str) -> str | None:
    """Where a folder comes from: ``variable``, ``setting`` or None (today's fallback for that folder)."""
    if variable_value(key):
        return SOURCE_VARIABLE
    return SOURCE_SETTING if setting_text(key) != "" else None


def _desktop_app_base_path() -> Path | None:
    """macOS ComfyUI Desktop: its chosen install folder (``basePath`` in its config.json), absolute only, or None."""
    import json

    config = Path.home() / "Library" / "Application Support" / "ComfyUI" / "config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    base = data.get("basePath") if isinstance(data, dict) else None
    if not isinstance(base, str) or not base.strip():
        return None
    path = Path(base.strip())
    return path if path.is_absolute() else None


def default_comfy_root() -> Path:
    """ComfyUI-Easy-Install's folder in Documents: always on Windows, and elsewhere when it exists.

    On macOS and Linux (PR #2 by @ShawnCRMer, 8c6ba33) the first of the usual installs that holds a ``models``
    folder: ComfyUI Desktop's base path, ``~/Documents/ComfyUI``, ``~/ComfyUI``, ``~/comfy/ComfyUI`` (comfy-cli).
    None found: the Easy-Install folder, so a missing ComfyUI is reported against the same path as before.
    """
    easy_install = Path.home() / "Documents" / "ComfyUI-Easy-Install" / "ComfyUI"
    if os.name == "nt" or easy_install.is_dir():
        return easy_install
    home = Path.home()
    for candidate in (_desktop_app_base_path(), home / "Documents" / "ComfyUI", home / "ComfyUI",
                      home / "comfy" / "ComfyUI"):
        if candidate is not None and (candidate / "models").is_dir():
            return candidate
    return easy_install


# ComfyUI's own folders under models/ (folder_paths.py), and the ones the Suite reads (model_catalog.FOLDER_KINDS):
# a folder holding one of them looks like a models folder.
MODEL_SUBFOLDERS = ("checkpoints", "diffusion_models", "unet", "text_encoders", "clip", "vae", "loras", "controlnet",
                    "clip_vision", "upscale_models", "embeddings", "model_patches", "latent_upscale_models",
                    "frame_interpolation", "omnivoice", "audio_encoders")


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


MAX_LISTED_FOLDERS = 64


def model_folders(models: Path | None, root: Path) -> list[dict[str, object]]:
    """Lane w46-eg G-a (FRM-047): every folder ComfyUI reads models from, as ``[{path, kinds}]``: the models folder
    elsewhere first (when set), then ``<root>/models`` and each ``extra_model_paths.yaml`` folder. One rule, read
    from ``model_catalog.model_roots`` (the rule ``GET /models/missing`` reads files by); no ComfyUI call."""
    try:
        catalog = _sibling("film_suite_comfy_root_model_catalog", _HERE / "model_catalog.py")
        roots, kinds_of = catalog.model_roots(root), catalog.FOLDER_KINDS
    except Exception:  # noqa: BLE001 - a copy of this file without its siblings: the folders it knows
        return [{"path": str(models), "kinds": []}] if models is not None else []
    out: dict[str, list[str]] = {}
    if models is not None:
        out[str(models)] = list(kinds_of)
    for kind, paths in roots.items():
        for path in paths:
            listed = out.setdefault(str(Path(path).parent), [])
            if kind not in listed:
                listed.append(kind)
    return [{"path": path, "kinds": kinds} for path, kinds in list(out.items())[:MAX_LISTED_FOLDERS]]


def describe(key: str) -> dict[str, object]:
    """One folder as the settings page shows it: the saved value, the variable, the folder in use and where it comes
    from (``variable`` | ``setting`` | ``default``), whether it exists and looks like what it should be, and the fact
    when it cannot be used. A network or device path is never touched."""
    label = LABELS[key]
    raw = plugin_setting(key)
    variable = variable_value(key)
    field: dict[str, object] = {
        "key": key, "value": raw if isinstance(raw, str) else ("" if raw is None else str(raw)),
        "variable": VARIABLES[key], "variable_set": bool(variable), "variable_value": variable or None,
        "source": "default", "folder": None, "exists": False, "looks_like": False, "reason": None}
    if key == MODELS_SETTING:
        field["folders"] = []
    try:
        folder = comfy_root() if key == ROOT_SETTING else comfy_models()
    except FolderSettingError as exc:
        own = exc.setting_key == key
        return {**field, "source": SOURCE_SETTING if own else "default",
                "folder": (raw.strip() if isinstance(raw, str) else None) if own else None, "reason": str(exc)}
    source = folder_source(key) or "default"
    if key == MODELS_SETTING:
        try:
            field["folders"] = model_folders(folder, comfy_root())
        except FolderSettingError:
            field["folders"] = [{"path": str(folder), "kinds": []}] if folder is not None else []
    if folder is None:  # no models folder of its own: the ComfyUI folder's models
        try:
            folder = comfy_root() / "models"
        except FolderSettingError as exc:
            return {**field, "reason": str(exc)}
    text = str(folder)
    remote = folder_reason(key, text)
    if remote is not None and "network" in remote:
        where = f"{VARIABLES[key]} is" if source == SOURCE_VARIABLE else f"The {label} in use is"
        return {**field, "source": source, "folder": text, "reason": f"{where} a network (UNC) or device path"}
    exists = _is_dir(folder)
    if key == ROOT_SETTING:
        looks = exists and _is_dir(folder / "models")
        miss = "The ComfyUI folder holds no models folder"
    else:
        looks = exists and any(_is_dir(folder / sub) for sub in MODEL_SUBFOLDERS)
        miss = "The models folder holds none of ComfyUI's model folders (checkpoints, diffusion_models, loras, vae, ...)"
    reason = None if looks else (miss if exists else f"No folder at {text}")
    return {**field, "source": source, "folder": text, "exists": exists, "looks_like": looks, "reason": reason}


def comfy_root(fallback: str | os.PathLike[str] | None = None) -> Path:
    """``FILM_SUITE_COMFY_ROOT``, else the ``comfy_root`` setting, else ``fallback`` (a root recorded at install
    time), else the default. An unusable saved setting raises FolderSettingError."""
    configured = (os.environ.get(ENV) or "").strip()
    if configured:
        return Path(configured)
    saved = _saved_folder(ROOT_SETTING)
    if saved is not None:
        return saved
    if fallback:
        return Path(fallback)
    return default_comfy_root()


def comfy_models() -> Path | None:
    """``FILM_SUITE_COMFY_MODELS``, else the ``comfy_models`` setting, else None (ComfyUI's ``<root>/models``).
    An unusable saved setting raises FolderSettingError."""
    configured = os.environ.get(MODELS_ENV)
    if configured:
        return Path(configured)
    return _saved_folder(MODELS_SETTING)


__all__ = ["ENV", "FolderSettingError", "LABELS", "MODELS_ENV", "MODELS_SETTING", "ROOT_SETTING", "VARIABLES",
           "MODEL_SUBFOLDERS", "comfy_models", "model_folders", "comfy_root", "default_comfy_root", "describe", "folder_reason",
           "folder_source", "setting_text", "variable_value"]
