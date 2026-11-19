"""One answer to "can this image target take a job on the engine that is running now" (lane w45-s1 item 2).

Before w45 three code paths answered it and disagreed: the model catalog said ``runnable`` from files on disk plus a
render on record, submit refused with ``image_target_not_ready``, and ``/generation/health`` answered
``invalid_request`` for every image target. Every caller now asks :func:`image_target_readiness`:
- the catalog (``/models/catalog`` and the agent's ``continuo_image_catalog``) for the picker's availability,
- ``/generation/health`` (``continuo_target_health``) and ``/projects/image-producer/workflow-health``,
- submit (``ImageWorkflowRuntime.health``, the last check before the ledger).

The answer (``studio.image-target-readiness/1``): ``state`` ``ready_static`` | ``missing`` | ``unreachable`` |
``unknown_target`` (the generation health vocabulary), ``ready`` (bool), ``reason`` (one stating sentence), the facts
``missing_classes``, ``missing_files``, ``schema_problems`` ({problem, class_type, input, pinned, live}),
``engine`` {reachable, address, version} and ``inference_tested`` False. A render on record is never part of it.

Cost: ``GET /object_info/<class>`` once per class per call (shared by every target of a catalog read), and kept per
engine (address + ComfyUI version) for ``CACHE_SECONDS`` unless ``fresh`` (health and submit always ask again).
"""
from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from typing import Any

from . import comfy_endpoint, comfyui_client, image_workflow_contract as workflow
from . import image_workflow_run as run

SCHEMA = "studio.image-target-readiness/1"
CACHE_SECONDS = 15.0
PROBE_REF = "filmsuite-ref-" + "0" * 32 + ".png [temp]"
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_LOCK = threading.Lock()


def probe_request(target_id: str, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The request readiness compiles: the caller's own, else the target's defaults with a neutral prompt (a JSON
    caption for a caption model) and one placeholder picture per required edit target."""
    if request is not None:
        return dict(request)
    family, entry = workflow.entries()[target_id]
    desc = entry["descriptor"]
    try:
        manifest = workflow.compiler(target_id).load_assets(target_id)[0]
    except Exception:  # noqa: BLE001 - an adapter without manifest assets takes the plain probe
        manifest = {}
    prompt = '{"caption": "Static check"}' if (manifest.get("prompt") or {}).get("format") == "json_object" else "Static check"
    refs = [{"image": PROBE_REF, "role": "target"}] if desc["capabilities"].get("edit") and not desc["capabilities"].get("create") else []
    return {"schema": desc["request_schema"], "target_id": target_id, "prompt": prompt, "controls": {}, "references": refs}


def _sentence(answer: Mapping[str, Any], shared: Any) -> str:
    version = (answer.get("engine") or {}).get("version")
    engine = f"ComfyUI {version}" if version else "The image engine"
    parts = []
    if answer["missing_classes"]:
        parts.append(f"{engine} has no node " + ", ".join(answer["missing_classes"]))
    if answer["missing_files"]:
        parts.append(f"{engine} does not list " + ", ".join(answer["missing_files"]))
    for problem in answer["schema_problems"]:
        parts.append(shared.schema_sentence(problem))
    others = [m for m in answer.get("schema_mismatches", []) if m not in {f"{p['class_type']}.{p['input']}" for p in answer["schema_problems"]}]
    if others:
        parts.append(f"{engine} lists no files for " + ", ".join(others))
    if not parts:
        return f"Ready on {engine}" if version else "Ready on the image engine"
    return "; ".join(parts)


async def _engine(client: Any) -> dict[str, Any]:
    """Address and ComfyUI version; the version is a fact when /system_stats answers (an older stand-in or a proxy
    without it leaves it unknown; whether the engine answers at all is decided by /object_info)."""
    version = None
    try:
        stats = await client.system_stats()
        system = stats.get("system") if isinstance(stats, Mapping) else None
        version = system.get("comfyui_version") if isinstance(system, Mapping) else None
    except Exception:  # noqa: BLE001 - see docstring
        version = None
    try:
        address = comfy_endpoint.comfy_label()
    except ValueError:
        address = None
    return {"reachable": True, "address": address, "version": version if isinstance(version, str) else None}


async def _infos(client: Any, engine: Mapping[str, Any], classes: list[str], cache: dict[str, Any] | None, fresh: bool) -> dict[str, Any]:
    key = (str(engine.get("address")), str(engine.get("version")))
    now = time.monotonic()
    kept: dict[str, Any] = {}
    if not fresh:
        with _LOCK:
            hit = _CACHE.get(key)
            if hit and now - hit[0] < CACHE_SECONDS:
                kept = hit[1]
    shared = cache if cache is not None else {}
    out: dict[str, Any] = {}
    for name in classes:
        if name in shared:
            body = shared[name]
        elif name in kept:
            body = kept[name]
        else:
            body = await client.object_info(name)
            shared[name] = body
        if isinstance(body, Mapping):
            out.update(body)
    if shared:
        with _LOCK:
            previous = _CACHE.get(key)
            merged = {**(previous[1] if previous and now - previous[0] < CACHE_SECONDS else {}), **shared}
            _CACHE[key] = (now, merged)
    return out


def _unreachable(target_id: str, provider_id: str) -> dict[str, Any]:
    engine = comfy_endpoint.engine_state(answered=False)
    return {"schema": SCHEMA, "target_id": target_id, "provider_id": provider_id, "state": "unreachable", "ready": False,
            "reason": engine.get("reason") or "The image engine does not answer", "missing_classes": [], "missing_files": [],
            "schema_mismatches": [], "schema_problems": [], "inference_tested": False,
            "engine": {"reachable": False, "address": engine.get("address"), "version": None}}


async def image_target_readiness(target_id: str, *, client: Any = None, request: Mapping[str, Any] | None = None,
                                 cache: dict[str, Any] | None = None, fresh: bool = True) -> dict[str, Any]:
    """Whether the image target can take a job on the engine running now (see the module docstring).

    ``request``: the job's own workflow request (submit, workflow-health); None checks the target's defaults.
    ``cache``: a dict shared by the calls of one catalog read (one ``/object_info`` per class). ``fresh=False`` may
    reuse an answer of the same engine younger than ``CACHE_SECONDS``. A request the target refuses raises the
    adapter's own ValueError (the caller answers it as an invalid request). Never queues work.
    """
    if target_id in EDIT_ADAPTERS:  # w45-s4 item 3: the area-edit targets (/image/edit) answer here too
        return await _edit_readiness(target_id, client=client, cache=cache, fresh=fresh)
    if target_id == KREA2_TARGET:  # w45-s4 item 4: the Krea 2 render-spec route (Turbo and Raw)
        return await _krea2_readiness(target_id, client=client, request=request, cache=cache, fresh=fresh)
    entries = workflow.entries()
    if target_id not in entries:
        return {"schema": SCHEMA, "target_id": target_id, "provider_id": None, "state": "unknown_target", "ready": False,
                "reason": f"{target_id} is not an image target of the catalog", "missing_classes": [], "missing_files": [],
                "schema_mismatches": [], "schema_problems": [], "inference_tested": False, "engine": None}
    adapter = workflow.compiler(target_id)
    req = probe_request(target_id, request)
    graph = run.compile_request(adapter, req)
    provider_id = getattr(adapter, "provider_id", None) or _provider_of(adapter)
    if not graph:  # a subscription target (no local graph): its own static health is the whole answer
        own = adapter.static_health(run.strip(req)[0], {})
        ready = own.get("state") == "ready_static"
        return {"schema": SCHEMA, "target_id": target_id, "provider_id": own.get("provider_id", provider_id),
                "state": own.get("state"), "ready": ready, "reason": own.get("reason") or ("Ready" if ready else "Not connected"),
                "missing_classes": [], "missing_files": [], "schema_mismatches": [], "schema_problems": [],
                "inference_tested": False, "engine": None}
    client = client if client is not None else comfyui_client.ComfyUIClient()
    try:
        engine = await _engine(client)
        info = await _infos(client, engine, sorted({n["class_type"] for n in graph.values()}), cache, fresh)
    except Exception:  # noqa: BLE001 - the engine does not answer: that is the answer
        return _unreachable(target_id, provider_id)
    health = adapter.static_health(run.strip(req)[0], info)
    missing_loras = run.lora_health(graph, info)
    missing_files = sorted(set(health.get("missing_files", [])) | set(missing_loras))
    answer = {"schema": SCHEMA, "target_id": target_id, "provider_id": provider_id,
              "missing_classes": list(health.get("missing_classes", [])), "missing_files": missing_files,
              "schema_mismatches": list(health.get("schema_mismatches", [])),
              "schema_problems": list(health.get("schema_problems", [])), "inference_tested": False, "engine": engine}
    ready = not (answer["missing_classes"] or answer["missing_files"] or answer["schema_mismatches"])
    answer.update(state="ready_static" if ready else "missing", ready=ready,
                  reason=_sentence(answer, _shared_rule()), availability=health.get("availability"))
    return answer


def _provider_of(adapter: Any) -> str:
    from . import image_contract
    return image_contract.PROVIDER_ID


def _shared_rule() -> Any:
    from . import qwen_image_workflow_adapter
    return qwen_image_workflow_adapter


async def catalog_readiness(target_ids: Any = None, *, client: Any = None) -> dict[str, dict[str, Any]]:
    """target_id -> readiness for every catalog image target (or ``target_ids``), one ``/object_info`` per class."""
    shared: dict[str, Any] = {}
    out = {}
    # w45-s4 item 4: the Krea 2 render-spec route is a catalog target too (families krea2 turbo and raw)
    target_ids = target_ids if target_ids is not None else sorted(workflow.entries()) + [KREA2_TARGET]
    for target_id in target_ids:
        try:
            out[target_id] = await image_target_readiness(target_id, client=client, cache=shared, fresh=False)
        except Exception as exc:  # noqa: BLE001 - a target whose defaults do not compile says so; others go on
            out[target_id] = {"schema": SCHEMA, "target_id": target_id, "state": "missing", "ready": False,
                              "reason": f"The workflow does not compile with its defaults: {str(exc)[:160]}",
                              "missing_classes": [], "missing_files": [], "schema_mismatches": [], "schema_problems": [],
                              "inference_tested": False, "engine": None}
        if out[target_id]["state"] == "unreachable":
            # One engine for every target: the rest share the same fact without asking again.
            for rest in target_ids:
                out.setdefault(rest, {**out[target_id], "target_id": rest})
            break
    return out


# --------------------------------------------------------------------------------------------- area-edit targets
# w45-s4 item 3 (release run finding 3): the seven area-edit targets of /image/edit (Fill, Replace, Remove, Restyle,
# Relight, Outpaint, Box) answered readiness from image_edit_capabilities.v1.json and never asked the engine. They
# answer here now, with the same facts and the same slot rule (qwen_image_workflow_adapter.slot_problem): every class
# of the pinned graph plus the classes the adapter inserts (latent mask, strength), every model file the graph loads in
# the live loader's list, every value the graph sends valid on the live node (the seed over its whole range). The
# picture's upload name and the instruction are the job's own and never checked. Callers: /image/edit/capabilities,
# /generation/health, and the edit submit's engine check (routes/image/edit_1.py _edit_engine_check).
EDIT_ADAPTERS = {
    "qwen-image-2.1-edit-pe-v3": ("qwen_image_edit_adapter", "QwenImageEditAdapter"),
    "flux3-klein-sd-edit-v1": ("flux3_klein_edit_adapter", "Flux3KleinEditAdapter"),
    "flux2-klein-9b-kv-edit-v1": ("flux2_klein_edit_adapter", "Flux2KleinEditAdapter"),
    "flux3-klein-box-edit-v1": ("flux3_klein_box_adapter", "Flux3KleinBoxEditAdapter"),
    "p-h3-image-lora-crop-edit-v1": ("p_h3_image_edit_adapter", "PH3ImageEditAdapter"),
    "krea2-edit-kroma-v1": ("krea2_edit_adapter", "Krea2EditAdapter"),
    "krea2-edit-turbo-v1": ("krea2_edit_adapter", "Krea2EditTurboAdapter"),
}
_FILE_INPUTS = ("unet_name", "clip_name", "vae_name", "lora_name", "ckpt_name", "model_name")
_SCALAR_KINDS = {"COMBO", "STRING", "INT", "FLOAT", "BOOLEAN"}


def edit_adapter(target_id: str) -> tuple[Any, Any]:
    """(module, adapter class) of one area-edit target."""
    import importlib
    module_name, class_name = EDIT_ADAPTERS[target_id]
    module = importlib.import_module(f"{__package__}.{module_name}")
    return module, getattr(module, class_name)


def _norm(name: Any) -> str:
    return str(name).replace("\\", "/")


def _pinned_kind(value: Any, live_kind: str | None) -> str:
    """The kind the graph's VALUE has (w45-s19 item 1: read from the value first, never taken from the live input):
    a string is a choice when the live input is a choice list, else STRING; an int fits an INT or a FLOAT input; any
    other value is named by its own type, so a live input of another kind is a changed type."""
    if type(value) is str:
        return "COMBO" if live_kind == "COMBO" else "STRING"
    if type(value) is bool:
        return "BOOLEAN"
    if type(value) is int:
        return "FLOAT" if live_kind == "FLOAT" else "INT"
    if type(value) is float:
        return "FLOAT"
    return type(value).__name__.upper()


def graph_problems(graph: Mapping[str, Any], info: Mapping[str, Any], *, required: Any = (),
                   skip: Any = (), controls: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, list]:
    """Classes, files and slot problems of a pinned graph without manifest slots against the live ``object_info``.

    ``required``: classes the adapter inserts at compile time. ``skip``: pointers whose value is the job's own (the
    upload name, the instruction). ``controls``: pointer -> the control whose whole range is sent (the seed).

    w45-s19 item 1 (cold review s1-s4 High 3): every input the graph sends must be an input of the live node
    (``missing_input``, links included), a value must have the live input's type (``type_changed``, the kind read from
    the graph's value), and every REQUIRED live input must be sent (``input_required``). The one narrow exception is
    ComfyUI's dynamic inputs: a dotted name (``images.image1``) is not compared, and a required live input ``images``
    counts as sent when the graph sends ``images.<n>``. A skipped pointer's value is the job's own, its input still
    has to exist."""
    rule = _shared_rule()
    missing_classes = sorted(({n["class_type"] for n in graph.values()} | set(required)) - set(info))
    missing_files: set[str] = set()
    problems: list[dict] = []
    for node_id, node in graph.items():
        schema = info.get(node["class_type"])
        if not isinstance(schema, Mapping):
            continue
        inputs = schema.get("input") or {}
        sent = node.get("inputs") or {}
        where = {"class_type": node["class_type"]}
        for name, value in sent.items():
            pointer = f"/{node_id}/inputs/{name}"
            if "." in name:  # a dynamic input (images.image1): the live node declares its group, not each member
                continue
            group = "required" if name in (inputs.get("required") or {}) else "optional"
            live = (inputs.get(group) or {}).get(name)
            if live is None:  # the graph sends an input the engine no longer declares: the engine refuses the job
                problems.append({"problem": "missing_input", **where, "input": name, "pinned": None, "live": None})
                continue
            if pointer in skip or isinstance(value, list):  # the job's own value, or a link: the input exists
                continue
            if name in _FILE_INPUTS:
                options = rule._spec_options(live)
                if not isinstance(options, list) or _norm(value) not in {_norm(o) for o in options}:
                    missing_files.add(str(value))
                continue
            kind = rule._spec_kind(live)
            pinned = _pinned_kind(value, kind)
            slot = {"class_type": node["class_type"], "input_name": name, "schema_group": group, "pointer": pointer,
                    "schema": [[value], {}] if pinned == "COMBO" else [pinned, {}]}
            problem = rule.slot_problem(graph, slot, live, (controls or {}).get(pointer))
            if problem is not None:
                problems.append(problem)
        for name in (inputs.get("required") or {}):
            if name not in sent and not any(key.startswith(f"{name}.") for key in sent):
                problems.append({"problem": "input_required", **where, "input": name, "pinned": None,
                                 "live": rule._spec_kind((inputs.get("required") or {}).get(name))})
    return {"missing_classes": missing_classes, "missing_files": sorted(missing_files), "schema_problems": problems}


async def _edit_readiness(target_id: str, *, client: Any = None, cache: dict[str, Any] | None = None,
                          fresh: bool = True) -> dict[str, Any]:
    from . import image_contract, image_edit_contract
    module, adapter_type = edit_adapter(target_id)
    base = {"schema": SCHEMA, "target_id": target_id, "provider_id": image_contract.PROVIDER_ID, "inference_tested": False,
            "missing_classes": [], "missing_files": [], "schema_mismatches": [], "schema_problems": []}
    try:
        _manifest, graph = adapter_type(None).load_assets()
    except Exception:  # noqa: BLE001 - the pinned workflow is absent or changed: the install lacks it, no engine asked
        return {**base, "state": "missing", "ready": False, "workflow_missing": True, "engine": None,
                "reason": f"The edit workflow {target_id} is not installed with Continuo"}
    pointers = getattr(module, "MUTABLE_POINTERS", {})
    skip = {pointers.get(k) for k in ("image", "instruction", "negative")} - {None}
    seed = pointers.get("seed")
    controls = {seed: {"kind": "integer", "min": 0, "max": image_edit_contract.SEED_MAX}} if seed else {}
    required = set(getattr(module, "REQUIRED_CLASSES", ()))
    client = client if client is not None else comfyui_client.ComfyUIClient()
    try:
        engine = await _engine(client)
        info = await _infos(client, engine, sorted({n["class_type"] for n in graph.values()} | required), cache, fresh)
    except Exception:  # noqa: BLE001 - the engine does not answer: that is the answer
        return _unreachable(target_id, image_contract.PROVIDER_ID)
    facts = graph_problems(graph, info, required=required, skip=skip, controls=controls)
    answer = {**base, **facts, "engine": engine,
              "schema_mismatches": sorted({f"{p['class_type']}.{p['input']}" for p in facts["schema_problems"]})}
    ready = not (answer["missing_classes"] or answer["missing_files"] or answer["schema_mismatches"])
    answer.update(state="ready_static" if ready else "missing", ready=ready, reason=_sentence(answer, _shared_rule()))
    return answer


async def edit_capabilities_readiness(caps: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """``caps`` (studio.image-edit-capabilities/1) with each offered operation's engine fact ``readiness``
    {state, ready, reason}. An engine that answers and cannot take the target's job makes the operation unavailable
    with that reason; an engine that does not answer leaves every wired operation offered and says so (``engine``,
    ``readiness.state`` unreachable); a wired operation is never hidden. One ``/object_info`` per class for all."""
    shared: dict[str, Any] = {}
    answers: dict[str, dict[str, Any]] = {}
    for family in caps.get("families") or []:
        for declared in (family.get("operations") or {}).values():
            target_id = declared.get("target_id") if isinstance(declared, dict) else None
            if target_id not in EDIT_ADAPTERS or not declared.get("available"):
                continue
            if target_id not in answers:
                answers[target_id] = await image_target_readiness(target_id, client=client, cache=shared, fresh=False)
            answer = answers[target_id]
            declared["readiness"] = {"state": answer["state"], "ready": answer["ready"], "reason": answer["reason"]}
            if answer["state"] != "unreachable" and not answer["ready"]:
                declared.update(available=False, reason=answer["reason"])
    engines = [a["engine"] for a in answers.values() if a.get("engine")]
    caps["engine"] = engines[0] if engines else None
    return caps


# ----------------------------------------------------------------------------------------- Krea 2 render-spec route
# w45-s4 item 4 (s1 report item 2 "Gap"): krea2-turbo-t2i-create (families Krea 2 Turbo and Raw, the default image
# model, submitted through continuo_image_submit with a render_spec) is not a catalog workflow target; its availability
# was "files present plus a render on record". It answers here now: the graph krea2_create_adapter compiles for the
# spec (the job's own, else each profile's default) against the live engine, with the same facts and slot rule.
# ``profiles`` {turbo, raw} carries each family's own answer (the catalog's turbo and raw variants read their own).
KREA2_TARGET = "krea2-turbo-t2i-create"
_KREA2_SKIP = ("/35/inputs/text", "/300/inputs/text")  # the prompt and Raw's negative: the job's own words


def _krea2_controls(spec_module: Any) -> dict[str, dict[str, Any]]:
    return {"/38/inputs/seed": {"kind": "integer", "min": 0, "max": 18_446_744_073_709_551_615},
            "/38/inputs/steps": {"kind": "integer", "min": 1, "max": 100},
            "/38/inputs/cfg": {"kind": "number", "min": 0.1, "max": 20.0},
            "/37/inputs/width": {"kind": "integer", "min": spec_module.V2_SIZE_MIN, "max": spec_module.V2_SIZE_MAX, "step": 8},
            "/37/inputs/height": {"kind": "integer", "min": spec_module.V2_SIZE_MIN, "max": spec_module.V2_SIZE_MAX, "step": 8}}


async def _krea2_readiness(target_id: str, *, client: Any = None, request: Mapping[str, Any] | None = None,
                           cache: dict[str, Any] | None = None, fresh: bool = True) -> dict[str, Any]:
    from . import image_contract, krea2_create_adapter, krea2_render_spec as spec_module
    base = {"schema": SCHEMA, "target_id": target_id, "provider_id": image_contract.PROVIDER_ID, "inference_tested": False,
            "missing_classes": [], "missing_files": [], "schema_mismatches": [], "schema_problems": []}
    spec = (request.get("render_spec") if isinstance(request, Mapping) and "render_spec" in request else request)
    specs = {str(spec.get("profile")): dict(spec)} if isinstance(spec, Mapping) else {
        profile: spec_module.default_spec_v2(0, 1024, 1024, profile) for profile in ("turbo", "raw")}
    adapter = krea2_create_adapter.Krea2CreateAdapter(None)
    graphs: dict[str, dict[str, Any]] = {}
    for profile, one in specs.items():
        try:
            graphs[profile] = adapter.compile_render_spec(one, "Static check", check_files=False)
        except krea2_create_adapter.Krea2AdapterError:
            graphs[profile] = {}  # the pinned graph is absent or changed: said below, no engine needed for that
    client = client if client is not None else comfyui_client.ComfyUIClient()
    classes = sorted({n["class_type"] for g in graphs.values() for n in g.values()})
    try:
        engine = await _engine(client)
        info = await _infos(client, engine, classes, cache, fresh)
    except Exception:  # noqa: BLE001 - the engine does not answer: that is the answer
        return _unreachable(target_id, image_contract.PROVIDER_ID)
    profiles: dict[str, dict[str, Any]] = {}
    for profile, graph in graphs.items():
        if not graph:
            profiles[profile] = {**base, "state": "missing", "ready": False, "workflow_missing": True, "engine": engine,
                                 "reason": f"The Krea 2 {profile} workflow is not installed with Continuo"}
            continue
        facts = graph_problems(graph, info, skip=_KREA2_SKIP, controls=_krea2_controls(spec_module))
        answer = {**base, **facts, "engine": engine,
                  "schema_mismatches": sorted({f"{p['class_type']}.{p['input']}" for p in facts["schema_problems"]})}
        ready = not (answer["missing_classes"] or answer["missing_files"] or answer["schema_mismatches"])
        answer.update(state="ready_static" if ready else "missing", ready=ready, reason=_sentence(answer, _shared_rule()))
        profiles[profile] = answer
    first = profiles.get("turbo") or next(iter(profiles.values()))
    keep = ("state", "ready", "reason", "missing_classes", "missing_files", "schema_mismatches", "schema_problems")
    return {**first, "profiles": {p: {k: a.get(k) for k in keep} for p, a in profiles.items()}}


__all__ = ["CACHE_SECONDS", "EDIT_ADAPTERS", "KREA2_TARGET", "SCHEMA", "catalog_readiness", "edit_adapter", "edit_capabilities_readiness",
           "graph_problems", "image_target_readiness", "probe_request"]
