from __future__ import annotations


# --- Continuo's engine settings (lane w41-settings items 2-3, HER-091) ---------------------------------------------
# ONE read path and ONE write path for the machine-wide engine values declared in plugin.yaml config_schema
# (plugins.entries.film-suite.settings): Hermes Settings > Plugins > Continuo (the page), the automatic schema form
# ("Agent settings") and the agent tools continuo_settings_* all land here or in the same Hermes writer
# (ctx.set_config -> plugins_state.save_plugin_setting, the writer plugins.manage settings uses too). The environment variable
# stays the override and wins over the setting (generation/comfy_endpoint.py, the one place that names it).
# Agent rule (orchestrator decision): Hermes may set an address on this machine (loopback) or clear it, and test one
# on this machine. An address on another host sends the artist's prompts and pictures there: refused for the agent,
# the artist's own act on the page.
# Lane w41-folders item 2: the ComfyUI folder (comfy_root) and the models folder (comfy_models) take the same read and
# write path; their rule is generation/comfy_root.py (variable > setting > default; an unusable saved folder is a
# fact). The agent may read both and may write neither (orchestrator decision: a folder is always the artist's to
# approve, as for folder grants).
import importlib.util as _settings_util

_settings_root_spec = _settings_util.spec_from_file_location(
    "film_suite_settings_comfy_root", Path(__file__).resolve().parent / "generation" / "comfy_root.py")
_settings_root_module = _settings_util.module_from_spec(_settings_root_spec)
_settings_root_spec.loader.exec_module(_settings_root_module)
_SETTINGS_FOLDER_KEYS = (_settings_root_module.ROOT_SETTING, _settings_root_module.MODELS_SETTING)

_SETTINGS_MESSAGES = {
    "settings_invalid": "Not a valid address (scheme://host:port)",
    "settings_other_host": "An address on another machine is the artist's own setting: that machine receives the prompts and pictures",
    "settings_overridden": _comfy_endpoint_module.URL_ENV + " is set and overrides this setting",
    "settings_managed": "Plugin settings are managed by the administrator",
    "settings_unavailable": "Hermes' settings writer is not available in this process (the plugin is not registered here)",
    "settings_folder_artist": "A folder is the artist's own setting: Continuo reads the models and custom nodes there",
}


def _settings_fact(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _settings_refusal(code: str, status: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": _SETTINGS_MESSAGES[code]}})


def _settings_comfy_url_read() -> dict[str, Any]:
    """The address field as saved and as used, with where the used one comes from (blocking: probes)."""
    endpoint = _comfy_endpoint_module
    variable = os.environ.get(endpoint.URL_ENV, "")
    saved = endpoint.plugin_setting(endpoint.SETTING_KEY)
    field = {"key": "comfy_url", "value": saved if isinstance(saved, str) else ("" if saved is None else str(saved)),
             "variable": endpoint.URL_ENV, "variable_set": bool(variable),
             "variable_value": endpoint.label_of(variable) if variable and _settings_valid(variable) else None}
    try:
        origin = endpoint.comfy_origin()
    except ValueError:
        return {**field, "source": endpoint.origin_source(), "address": None, "reachable": False, "version": None,
                "tried": [], "reason": endpoint.invalid_reason()}
    source = endpoint.origin_source()
    answer = endpoint.ask(origin, timeout=endpoint.PROBE_TIMEOUT_SECONDS)
    if source == endpoint.SOURCE_LOCAL:
        source = "local" if answer["ok"] else "none"
    return {**field, "source": source, "address": endpoint.label_of(origin), "reachable": bool(answer["ok"]),
            "version": answer["version"], "tried": endpoint.tried_labels(),
            "reason": None if answer["ok"] else (endpoint.unreachable_reason() if source == "none" else answer["reason"])}


def _settings_valid(value: str) -> bool:
    try:
        _comfy_endpoint_module.normalize(value)
        return True
    except ValueError:
        return False


def _settings_is_loopback(origin: str) -> bool:
    return _comfy_endpoint_module.is_loopback_host(urlparse(origin).hostname)


def _settings_read_sync() -> dict[str, Any]:
    return {"plugin": "film-suite", "settings": {"comfy_url": _settings_comfy_url_read(),
                                                 **{key: _settings_root_module.describe(key) for key in _SETTINGS_FOLDER_KEYS}}}


@router.get("/settings")
async def film_suite_settings_read() -> dict[str, Any]:
    """Every engine setting: the saved value, the value in use and its source (variable | setting | local | none),
    and the ComfyUI version when it answers."""
    return await asyncio.to_thread(_settings_read_sync)


class SettingsWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    comfy_url: str | None = Field(default=None, max_length=512)
    comfy_root: str | None = Field(default=None, max_length=1024)
    comfy_models: str | None = Field(default=None, max_length=1024)


def _settings_save_sync(values: dict[str, Any]) -> list[str]:
    # Hermes' writer through its public door: ctx.set_config, left by the plugin's register() (__init__.py
    # _publish_settings_door). Without it this process has no writer: a stated fact, nothing written elsewhere.
    door = sys.modules.get("film_suite_settings_door")
    set_config = getattr(door, "set_config", None)
    if not callable(set_config):
        raise ImportError("no settings writer")
    written = []
    for key, value in values.items():
        set_config(key, value)
        written.append(key)
    # The Desktop form and the page re-read at once (the same event Hermes' own form save sends). Only where the
    # gateway already runs in this process: importing it elsewhere starts Hermes' own bootstrap (a relaunch).
    if "tui_gateway.server" in sys.modules:
        try:
            from hermes_cli.plugin_events import broadcast_plugin_event
            broadcast_plugin_event("film-suite", "settings.changed", {"written": list(written)})
        except Exception:  # noqa: BLE001 - nobody to tell
            pass
    _comfy_endpoint_module.forget()  # the next client asks again (the local probe result may be stale)
    return written


@router.put("/settings")
async def film_suite_settings_write(request: SettingsWriteRequest) -> Any:
    """Save engine settings through Hermes' own writer; an empty value clears the setting (this machine is asked)."""
    values: dict[str, Any] = {}
    if request.comfy_url is not None:
        value = request.comfy_url.strip()
        if value:
            if not _settings_valid(value):
                return _settings_refusal("settings_invalid")
            value = _comfy_endpoint_module.normalize(value)
            if _film_caller() == "hermes" and not _settings_is_loopback(value):
                return _settings_refusal("settings_other_host", 403)
        if os.environ.get(_comfy_endpoint_module.URL_ENV, ""):
            return _settings_refusal("settings_overridden", 409)
        values["comfy_url"] = value
    for key in _SETTINGS_FOLDER_KEYS:
        folder = getattr(request, key)
        if folder is None:
            continue
        if _film_caller() == "hermes":
            return _settings_refusal("settings_folder_artist", 403)
        folder = folder.strip()
        if folder:
            reason = await asyncio.to_thread(_settings_root_module.folder_reason, key, folder)
            if reason is not None:
                return _settings_fact("settings_invalid", reason, 422)
        if _settings_root_module.variable_value(key):
            return _settings_fact("settings_overridden", _settings_root_module.VARIABLES[key] + " is set and overrides this setting", 409)
        values[key] = folder
    try:
        written = await asyncio.to_thread(_settings_save_sync, values) if values else []
    except PermissionError:
        return _settings_refusal("settings_managed", 403)
    except ImportError:
        return _settings_refusal("settings_unavailable", 503)
    except ValueError:
        return _settings_refusal("settings_invalid")
    return {"written": written, **(await asyncio.to_thread(_settings_read_sync))}


# --- Test the connection (lane w41-settings item 3) ----------------------------------------------------------------
# Asks a given address (not saved) for GET /system_stats under the trust rule: origin only, no redirect, a timeout.
# Answers the ComfyUI version or the reason as a fact. Another host is asked only for the page, never for the agent.

class SettingsTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    comfy_url: str = Field(min_length=1, max_length=512)


@router.post("/settings/test")
async def film_suite_settings_test(request: SettingsTestRequest) -> Any:
    value = request.comfy_url.strip()
    if not _settings_valid(value):
        return _settings_refusal("settings_invalid")
    if _film_caller() == "hermes" and not _settings_is_loopback(_comfy_endpoint_module.normalize(value)):
        return _settings_refusal("settings_other_host", 403)
    return await asyncio.to_thread(_comfy_endpoint_module.ask, value)
