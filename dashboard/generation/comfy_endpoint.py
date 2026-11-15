"""The one ComfyUI address every Continuo client reads (lane w39-p2-tester item 4).

Order (lane w41-settings item 1, BCK-231): ``FILM_SUITE_COMFY_URL`` when set (the artist's own environment, the
override; it may name another host); else the plugin setting ``plugins.entries.film-suite.settings.comfy_url`` when
set (Hermes Settings > Plugins > Continuo, the Desktop form or the agent; one writer, Hermes' own); otherwise this
machine only - ``127.0.0.1:8188`` (ComfyUI's default), then ``127.0.0.1:8000`` (the Windows desktop ComfyUI). The
first that answers ``GET /system_stats`` wins and is kept for the process; when neither answers the default is used
and asked again after ``RETRY_SECONDS``.

The setting is read at every call through Hermes' config cache (keyed by the file's signature), so a saved change
reaches the next request of every client in every process that loads this file, without a restart. An invalid
variable or setting raises ValueError (a stated fact), never a silent fallback to another address.

Trust rule: an origin is scheme + host + port only - no credentials, no path, no query, no fragment; redirects are
never followed. Without the variable or the setting no other host is ever reached.

Standalone (stdlib only, no package-relative imports): modules that are loaded by path import it by path.
"""
from __future__ import annotations

import ipaddress
import json
import os
import sys
import threading
import time
import types
import socket
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit, urlunsplit

URL_ENV = "FILM_SUITE_COMFY_URL"
ENV = URL_ENV
PLUGIN_ID = "film-suite"
SETTING_KEY = "comfy_url"  # plugin.yaml config_schema: plugins.entries.film-suite.settings.comfy_url
SOURCE_VARIABLE, SOURCE_SETTING, SOURCE_LOCAL = "variable", "setting", "local"
NO_PROBE_ENV = "FILM_SUITE_COMFY_NO_PROBE"  # set by the test session (inherited by its children): never ask 8188 / 8000
NO_PROBE_WITH_SETTINGS = "settings"  # value of NO_PROBE_ENV in a test that reads the setting from its own Hermes home
DEFAULT_ORIGIN = "http://127.0.0.1:8188"
DESKTOP_ORIGIN = "http://127.0.0.1:8000"
LOCAL_CANDIDATES = (DEFAULT_ORIGIN, DESKTOP_ORIGIN)
PROBE_TIMEOUT_SECONDS = 0.6
RETRY_SECONDS = 10.0

# Modules loaded by path get their own copy of this file; the probe result lives in ONE process-wide holder so every
# copy agrees on the address. ``candidates`` is the local probe order (tests point it at a closed port).
_STATE = sys.modules.setdefault("film_suite_comfy_endpoint_state", types.ModuleType("film_suite_comfy_endpoint_state"))
if not hasattr(_STATE, "lock"):
    _STATE.lock = threading.Lock()
    _STATE.found = None  # an answering local origin, kept for the process
    _STATE.missed_at = None  # monotonic time of the last probe in which nothing answered
    _STATE.candidates = LOCAL_CANDIDATES
    _STATE.blocked = frozenset()  # origins never asked (the test session blocks the artist's 8188 and 8000)


def normalize(value: str) -> str:
    """``scheme://host:port`` or ValueError: never credentials, a path, a query or a fragment."""
    if not isinstance(value, str) or value != value.strip() or any(ord(c) < 33 for c in value):
        raise ValueError("Invalid ComfyUI address")
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid ComfyUI port") from exc
    if (parts.scheme not in ("http", "https", "ws", "wss") or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or port is None or port == 0 or "\\" in parts.netloc):
        raise ValueError("Invalid ComfyUI address")
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return urlunsplit((scheme, parts.netloc.lower(), "", "", ""))


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def reachable(origin: str, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """Whether a ComfyUI answers ``GET <origin>/system_stats`` (a read; never queues work)."""
    try:
        if normalize(origin) in _STATE.blocked or (os.environ.get(NO_PROBE_ENV, "") and normalize(origin) in LOCAL_CANDIDATES):
            return False
        with _opener.open(normalize(origin) + "/system_stats", timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read(1024 * 1024))
            return isinstance(data, dict) and isinstance(data.get("system"), dict)
    except (OSError, ValueError, TypeError):
        return False


def plugin_setting(key: str) -> object:
    """``plugins.entries.film-suite.settings.<key>`` of the active Hermes profile, or None.

    Read through Hermes' own config reader (cached on the file's signature: a saved change is seen at the next call).
    Without Hermes (a standalone load) there is no setting. The test session (``NO_PROBE_ENV``) reads no setting,
    so the artist's config stays unread; a test that made its own Hermes home says so with the value
    ``NO_PROBE_WITH_SETTINGS``. The Hermes home itself is never taken from the environment here (a gateway serving
    several profiles keeps the launch profile there): Hermes' reader resolves the active profile.
    """
    if os.environ.get(NO_PROBE_ENV, "") not in ("", NO_PROBE_WITH_SETTINGS):
        return None
    try:
        from hermes_cli.config import load_config_readonly
        node = load_config_readonly()
    except Exception:  # noqa: BLE001 - no Hermes in this process, or an unreadable config: no setting
        return None
    for part in ("plugins", "entries", PLUGIN_ID, "settings", key):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def setting_text() -> str:
    """The saved address setting as text ('' = not set); a value that is no text reads as invalid."""
    value = plugin_setting(SETTING_KEY)
    if value is None:
        return ""
    if not isinstance(value, str):
        return "\x00"  # normalize refuses control characters: a stated fact, never another host
    return value.strip()


def origin_source() -> str:
    """Where the address in use comes from: ``variable``, ``setting`` or ``local`` (the probe on this machine)."""
    if os.environ.get(URL_ENV, ""):
        return SOURCE_VARIABLE
    return SOURCE_SETTING if setting_text() else SOURCE_LOCAL


TEST_TIMEOUT_SECONDS = 3.0


def ask(origin: str, timeout: float = TEST_TIMEOUT_SECONDS) -> dict[str, object]:
    """``GET <origin>/system_stats`` under the trust rule (no redirect, a timeout, 1 MB at most):
    ``{ok, address, version, reason}``; the reason is one fact. Never queues work."""
    try:
        normalized = normalize(origin)
    except ValueError:
        return {"ok": False, "address": None, "version": None, "reason": "Not a valid address (scheme://host:port)"}
    label = label_of(normalized)
    answer = {"ok": False, "address": label, "version": None, "reason": f"No ComfyUI answers at {label}"}
    if normalized in _STATE.blocked or (os.environ.get(NO_PROBE_ENV, "") and normalized in LOCAL_CANDIDATES):
        return answer
    try:
        with _opener.open(normalized + "/system_stats", timeout=timeout) as response:  # noqa: S310 - trust rule above
            data = json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            return {**answer, "reason": f"{label} answers with a redirect; redirects are not followed"}
        return {**answer, "reason": f"{label} answers HTTP {exc.code}, not ComfyUI"}
    except (TimeoutError, socket.timeout):
        return {**answer, "reason": f"No answer from {label} within {timeout:g} s"}
    except (OSError, ValueError, TypeError):
        return answer
    system = data.get("system") if isinstance(data, dict) else None
    if not isinstance(system, dict):
        return {**answer, "reason": f"{label} answers, but not as ComfyUI"}
    version = system.get("comfyui_version")
    return {"ok": True, "address": label, "version": version if isinstance(version, str) and len(version) <= 64 else None,
            "reason": None}


def configured_origin() -> str | None:
    """The variable's address, else the setting's, normalized; None when neither is set. Invalid raises ValueError."""
    value = os.environ.get(URL_ENV, "")
    if value:
        return normalize(value)
    value = setting_text()
    return normalize(value) if value else None


def invalid_reason() -> str:
    """The fact when the address in use is invalid (the variable's or the setting's)."""
    return f"{ENV} is not a valid address" if os.environ.get(URL_ENV, "") else "The ComfyUI address setting is not a valid address"


def comfy_origin() -> str:
    """The address every client uses now."""
    configured = configured_origin()
    if configured:
        return configured
    candidates = tuple(_STATE.candidates)
    with _STATE.lock:
        if _STATE.found:
            return _STATE.found
        if _STATE.missed_at is not None and time.monotonic() - _STATE.missed_at < RETRY_SECONDS:
            return candidates[0]
        for candidate in candidates:
            if reachable(candidate):
                _STATE.found = candidate
                return candidate
        _STATE.missed_at = time.monotonic()
        return candidates[0]


def current_label() -> str:
    """``host:port`` in use WITHOUT asking any engine (registration at import time must not reach the network)."""
    configured = configured_origin()
    return label_of(configured or _STATE.found or tuple(_STATE.candidates)[0])


def label_of(origin: str) -> str:
    return urlsplit(normalize(origin)).netloc


def comfy_label() -> str:
    """``host:port`` of the address in use (public text: never a path or credentials)."""
    return label_of(comfy_origin())


def comfy_ws_url(client_id: str) -> str:
    parts = urlsplit(comfy_origin())
    return urlunsplit(("wss" if parts.scheme == "https" else "ws", parts.netloc, "/ws", urlencode({"clientId": client_id}), ""))


def is_engine_label(text: str) -> bool:
    """A provider ``endpoint_label`` the registry accepts: the configured address, or this machine on any port."""
    if not isinstance(text, str):
        return False
    try:
        if text == current_label():
            return True
    except ValueError:
        pass
    try:
        return is_loopback_host(urlsplit(normalize("http://" + text)).hostname)
    except ValueError:
        return False


def tried_labels() -> list[str]:
    """The addresses Continuo asks, in order (the variable's or the setting's alone, else the two local ports)."""
    configured = configured_origin()
    return [label_of(configured)] if configured else [label_of(origin) for origin in _STATE.candidates]


def unreachable_reason() -> str:
    """One fact: which address(es) did not answer."""
    return "No ComfyUI answers at " + " or ".join(tried_labels())


def engine_state(*, answered: bool | None = None) -> dict[str, object]:
    """``{reachable, address, tried, reason}``; ``answered`` = a probe the caller already made (skips asking again)."""
    try:
        origin = comfy_origin()
        ok = reachable(origin) if answered is None else bool(answered)
        address = label_of(origin)
        tried = tried_labels()
    except ValueError:
        return {"reachable": False, "address": None, "tried": [], "reason": invalid_reason()}
    return {"reachable": ok, "address": address, "tried": tried, "reason": None if ok else unreachable_reason()}


def block(origins) -> None:
    """Never ask these origins (test sessions: the shared engine at 8188 / 8000 stays untouched)."""
    _STATE.blocked = frozenset(normalize(origin) for origin in origins)


def forget() -> None:
    """Drop the kept probe result (the next client asks the local ports again)."""
    with _STATE.lock:
        _STATE.found, _STATE.missed_at = None, None


__all__ = [
    "DEFAULT_ORIGIN", "DESKTOP_ORIGIN", "ENV", "LOCAL_CANDIDATES", "ask", "comfy_label", "comfy_origin", "comfy_ws_url",
    "block", "configured_origin", "current_label", "engine_state", "forget", "invalid_reason", "is_engine_label", "is_loopback_host", "label_of", "normalize", "origin_source",
    "plugin_setting", "reachable", "setting_text", "tried_labels", "unreachable_reason",
]
