"""H3 Video inspector controls on the pinned conditioning graphs (lane w2-h3ctl).

Sampling (turbo on/off + strength, recipe, sigma shift video/audio, engine), user
LoRAs and performance (attention, sparse, cache) for ``minimax-h3-frames-v1`` and
``minimax-h3-references-v1``.  Source of every node and value: the artist's
``H3_CE_0.6_TEMPORAL_RC2.json`` (groups ENGINE, TURBO, SAMPLING RECIPE, USER LORAS,
ATTENTION BACKEND, SLA / NATIVE SPARSE, CACHE).

The controls are compiled structurally into the graph the pinned compile returns:
nodes are added, removed and rewired, never a second graph per combination.  A
request without any control key never reaches this module, so its submitted graph
is byte-identical to the one before (pinned in tests).

RC2 model order, kept here::

    UNET -> user LoRAs -> attention | sparse -> cache -> SigmaShift -> turbo LoRA
         -> AdaLN LoRA fix (only with user LoRAs) -> guider / scheduler

Sparse (SLA / native) replaces the attention patch as in RC2 (its own dense
fall-through backend follows the attention choice for SLA).  Pure: no network,
no files.  Loaded standalone (no package-relative imports).
"""

from __future__ import annotations

import copy
import math
import os
import re
from typing import Any, Iterable, Mapping

TARGET_IDS = ("minimax-h3-frames-v1", "minimax-h3-references-v1")
CONTROL_KEYS = frozenset({"turbo", "turbo_strength", "recipe", "passes", "sigmas", "sigma_shift_video", "sigma_shift_audio", "loras",
                          "attention", "sparse", "sparsity", "cache", "engine"})
COUNT_MIN, COUNT_MAX = 1, 8
BATCH_KEYS = frozenset({"count", "take_index"})  # take_index is set by the route's fan-out only
SEED_MODULUS = 4294967296
LORA_MAX = 8
LORA_STRENGTH = (0.0, 2.0)
TURBO_STRENGTH = (0.0, 2.0)
SIGMA_SHIFT = (0.01, 100.0)
RECIPES = ("native", "sandwich", "fast_0903", "custom")
ATTENTIONS = ("comfy_kitchen", "sage", "pytorch")  # the catalog stage options (model_catalog.v1.json)
SPARSES = ("off", "sla", "native")
CACHES = ("none", "t8", "spectrum")
ENGINES = ("native", "shark")
SLA_SPARSITY = (0.6, 0.95, 0.85)    # min, max, RC2 value (break-even 0.60 per the node's tooltip)
NATIVE_TAU = (0.0, 4.0, 1.3)        # sol-attn threshold (RC2 value 1.3)
RECIPE_A_STEPS, RECIPE_C_STEPS = 3, 3
FAST_0903_C_SIGMAS = "0.9035, 0.6316, 0.3158, 0.0000"
# Custom passes (w46-b, VID-182): the run's steps split into at most 4 passes, each with its own sampler and noise.
PASS_MAX = 4
PASS_STEPS = (1, 100)
PASS_NOISE = (0.0, 64.0, 1.0)   # s_noise min, max (SamplerLCM's 64 is the smallest maximum of the nodes below), default
PASS_KEYS = frozenset({"steps", "sampler", "noise", "s_noise", "s_noise_end"})
# A pass with its own noise value runs the sampler's own node instead of KSamplerSelect.  Every fixed input is the value
# KSamplerSelect runs with (ComfyUI 0.45.0 comfy_extras/nodes_custom_sampler.py:396-511,585-631 and
# nodes_advanced_samplers.py:89-117; k_diffusion/sampling.py defaults), so only s_noise (and s_noise_end) differ.
NOISE_NODES: dict[str, tuple[str, dict[str, Any]]] = {
    "er_sde": ("SamplerER_SDE", {"solver_type": "ER-SDE", "max_stage": 3, "eta": 1.0}),
    "lcm": ("SamplerLCM", {"noise_clip_std": 0.0}),
    "dpmpp_3m_sde": ("SamplerDPMPP_3M_SDE", {"eta": 1.0, "noise_device": "cpu"}),
    "dpmpp_3m_sde_gpu": ("SamplerDPMPP_3M_SDE", {"eta": 1.0, "noise_device": "gpu"}),
    "dpmpp_2m_sde": ("SamplerDPMPP_2M_SDE", {"solver_type": "midpoint", "eta": 1.0, "noise_device": "cpu"}),
    "dpmpp_2m_sde_gpu": ("SamplerDPMPP_2M_SDE", {"solver_type": "midpoint", "eta": 1.0, "noise_device": "gpu"}),
    "dpmpp_sde": ("SamplerDPMPP_SDE", {"eta": 1.0, "r": 0.5, "noise_device": "cpu"}),
    "dpmpp_sde_gpu": ("SamplerDPMPP_SDE", {"eta": 1.0, "r": 0.5, "noise_device": "gpu"}),
    "euler_ancestral": ("SamplerEulerAncestral", {"eta": 1.0}),
    "dpmpp_2s_ancestral": ("SamplerDPMPP_2S_Ancestral", {"eta": 1.0}),
}
NOISE_END_SAMPLERS = ("lcm",)  # SamplerLCM ramps s_noise to s_noise_end over its pass
# Drawn noise curve (w46-b, VID-181): steps + 1 falling values from at most 1 to 0, sent as one ManualSigmas.
CURVE_SCHEDULERS = ("simple", "beta")   # the H3 schedulers (h3_conditioning.SCHEDULERS) whose curve is computed here
CURVE_DECIMALS = 6
LATENT_UPSCALER = "minimax_h3_latent_upscaler_3d_fp16.safetensors"
PINNED_TURBO_LORAS = frozenset({"minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors"})
H3_FAMILY = "MiniMax H3"
DEFAULTS = {"turbo": True, "turbo_strength": 0.8, "recipe": "native", "passes": [], "sigmas": None, "sigma_shift_video": 12.0,
            "sigma_shift_audio": 3.0, "loras": [], "attention": None, "sparse": "off", "sparsity": None,
            "cache": "none", "engine": "native"}

# Pinned node ids (identical in both graphs).
_UNET, _SHIFT, _TURBO = "1", "5", "6"
_SEED, _NOISE, _SAMPLER, _SCHEDULER, _GUIDER, _RUN = "9", "10", "11", "12", "13", "14"
_GENERATOR, _VIDEO_VAE = "8", "3"
_NEW = 300  # every added node id is >= 300 (pinned graphs use ids < 100)

# RC2 widget values (H3_CE_0.6_TEMPORAL_RC2.json), read once and frozen here.
_SLA_INPUTS = {"block_size": "64", "min_seq_len": 4096, "dense_last_steps": 1, "protect_audio": True, "enabled": True,
               "dense_steps": "0", "disable_fp16_accum": True, "stabilize_motion": False, "reference_protection": "Off",
               "tail_correction": False, "use_int8_qk": True, "engine": "comfy_kitchen"}
_SLA_DENSE = {"comfy_kitchen": "comfy_kitchen", "pytorch": "pytorch", "sage": "sage:auto", None: "comfy_kitchen"}
_NATIVE_SPARSE_INPUTS = {"start_percent": 0.2, "end_percent": 1.0, "dense_blocks": "", "min_tokens": 12288,
                         "extra_tokens": 256, "sink_conditioning": "exact_kv_and_rows", "verbose": False}
_T8_INPUTS = {"residual_diff_threshold": 0.12, "start_percent": 0.08, "end_percent": 0.95, "max_consecutive_hits": 2,
              "cache_device": "cpu", "metric_stride": 8, "verbose": False}
_SPECTRUM_INPUTS = {
    "enabled": True, "blend_weight": 0.5, "degree": 4, "ridge_lambda": 0.1, "window_size": 2.0, "flex_window": 0.75,
    "warmup_steps": 5, "tail_actual_steps": 1, "max_history": 8, "debug": False, "history_storage": "system_ram",
    "bootstrap_first_forecast": False, "anchor_residual_feedback": False, "selective_rollback_correction": False,
    "offline_smoothing_replay": True, "audio_blend_weight": 0.0, "offline_archive_storage": "system_ram",
    "model_aware_mode": "off", "model_aware_risk_threshold": 0.65, "model_aware_trust_shrinkage": False,
    "model_aware_replay_generic_correction": False, "generic_correction_mode": "coordinate_rls",
    "generic_correction_limiter": "hard_clip", "generic_correction_limit": 0.4,
    "generic_correction_attenuation": "no_attenuation", "sa_pece_forecast_policy": "balanced"}
_SHARK_OPTIONS = ("default_dtype=float32\nmultistep_fallback_sampler=ddim\nmultistep_extra_initial_steps=0\n"
                  "skip_final_model_call\nno_batch_loop\nmute_EO")

# Live classes (and combo options) each control value needs; health answers ``unavailable`` without them.
NEEDS: dict[tuple[str, Any], tuple[tuple[str, str | None, str | None], ...]] = {
    ("recipe", "sandwich"): (("SplitSigmas", None, None), ("DisableNoise", None, None),
                             ("KSamplerSelect", "sampler_name", "dpmpp_3m_sde_gpu"), ("SamplerCustomAdvanced", None, None)),
    ("recipe", "custom"): (("SplitSigmas", None, None), ("DisableNoise", None, None), ("SamplerCustomAdvanced", None, None)),
    ("recipe", "fast_0903"): (("SplitSigmas", None, None), ("DisableNoise", None, None),
                              ("KSamplerSelect", "sampler_name", "dpmpp_3m_sde_gpu"), ("SamplerCustomAdvanced", None, None),
                              ("LTXVSeparateAVLatent", None, None), ("LTXVConcatAVLatent", None, None),
                              ("ManualSigmas", None, None), ("MinimaxH3LatentUpscaler3D", "model_name", LATENT_UPSCALER)),
    ("sigmas", True): (("ManualSigmas", None, None),),
    ("loras", True): (("LoraLoaderModelOnly", None, None), ("H3AdaLNLoRAFix", "mode", "port")),
    ("attention", "comfy_kitchen"): (("ModelAttentionBackend", "attention", "comfy kitchen attention"),),
    ("attention", "pytorch"): (("ModelAttentionBackend", "attention", "pytorch attention"),),
    ("attention", "sage"): (("PathchSageAttentionKJ", "sage_attention", "auto"), ("MiniMaxH3MemoryEfficientSageAttentionPatch", None, None)),
    ("sparse", "sla"): (("H3SLAAttention", "dense_backend", "comfy_kitchen"),),
    ("sparse", "native"): (("BlockSparseAttention", None, None),),
    ("cache", "t8"): (("MiniMaxH3BlockCacheT8", None, None),),
    ("cache", "spectrum"): (("SpectrumApplyMiniMaxH3", None, None),),
    ("engine", "shark"): (("ClownsharKSampler_Beta", "sampler_name", "exponential/etdrk2_2s"),
                          ("ClownsharkChainsampler_Beta", "sampler_name", "multistep/res_3m"),
                          ("ClownOptions_ExtraOptions_Beta", None, None), ("ConditioningZeroOut", None, None)),
}

# Real renders through the Suite's own /submit on the local ComfyUI (lane w2-h3ctl, see the
# lane report: prompt id, seconds, ffprobe facts).  Only what is listed here is ``rendered``;
# every other control value is ``untested`` (offered, not proven).
EVIDENCE: dict[tuple[str, Any], dict[str, Any]] = {
    # Scalar controls are keyed (control, True): rendered with a value other than the pinned one.
    ("turbo", True): {'prompt_id': '698ca948-07e9-4809-a814-07f3e61ed2a9', 'date': '2026-10-22', 'seconds': 32.6, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'turbo off: node 6 removed; mean frame difference to the default take 15.8 (0-255)'},
    ("recipe", "sandwich"): {'prompt_id': '9c43db86-7078-40cc-9e3e-209c2bc92039', 'date': '2026-10-22', 'seconds': 32.6, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': '3 SamplerCustomAdvanced (A 3 | B 2 | C 3 of 8 steps); mean frame difference to the default 44.3'},
    ("loras", True): {'prompt_id': '95a142d6-d573-4b29-9ee0-6c1e48a7fb41', 'date': '2026-10-22', 'seconds': 32.5, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'H3_Motion_BoosterV2 at 0.8 + H3AdaLNLoRAFix port; mean frame difference to the default 8.9'},
    ("attention", "sage"): {'prompt_id': '60784c87-d95a-432e-822c-ffd071d974d1', 'date': '2026-10-22', 'seconds': 24.6, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'PathchSageAttentionKJ auto + MiniMaxH3MemoryEfficientSageAttentionPatch; 21.0 s engine time vs 21.1 s comfy_kitchen'},
    ("attention", "comfy_kitchen"): {'prompt_id': 'd3c73614-f902-4023-b1a2-715301c8c87f', 'date': '2026-10-22', 'seconds': 24.5, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'ModelAttentionBackend comfy kitchen attention; mean frame difference to sage 8.2'},
    ("cache", "t8"): {'prompt_id': '740b7d78-62b7-4236-a601-c8242deac6da', 'date': '2026-10-22', 'seconds': 32.6, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'ran, but the cache took 0 of 8 forwards (also 0 of 12 at 12 steps): the take is identical to the default; no speed-up measured at this size'},
    ("count", True): {'prompt_id': 'f2d206d8-14ae-4fe3-9637-237f6d126f98', 'date': '2026-10-22', 'seconds': 32.6, 'output': '960x544 107 frames 24/1 fps, aac 32000 Hz', 'note': 'count 2: two takes, seeds 4242 and 4243, one batch id; take 2 submitted when take 1 ended'},
}


def _control_diagnostic(detail: str) -> dict[str, Any]:
    """Turn finite validator details into a structured, safe artist message at the source."""
    match = re.search(r"passes\[(\d+)\](?:\.(steps|sampler|noise|s_noise_end|s_noise))?", detail)
    if match:
        index = int(match.group(1))
        field = match.group(2)
        position = "the first pass" if index == 0 else f"pass {index + 1}"
        label = {"steps": "Steps", "sampler": "Sampler", "noise": "Noise", "s_noise": "Noise amount",
                 "s_noise_end": "Noise amount at the end"}.get(field, "Settings")
        if field == "noise" and index == 0 and "must be true" in detail:
            message = "Noise of the first pass must be on"
        elif "number from" in detail:
            limits = re.search(r"number from ([0-9.]+) to ([0-9.]+)", detail)
            message = f"{label} of {position} must be from {limits.group(1)} to {limits.group(2)}" if limits else f"{label} of {position} is not valid"
        else:
            message = f"{label} of {position} is not valid"
        return {"control": "passes", "field": field, "index": index, "message": message, "detail": detail}
    if "sigmas" in detail:
        return {"control": "sigmas", "message": "Noise curve must fall from at most 1 to 0 with one value per step plus one", "detail": detail}
    total = re.fullmatch(r"the passes add up to (\d+) steps; steps is (\d+)", detail)
    if total:
        # w47-r2 item 4 (cold review M2): the artist's words, no parameter name; the page says the same.
        return {"control": "passes", "message": f"The passes add up to {total.group(1)} steps; the shot has {total.group(2)}", "detail": detail}
    if "passes" in detail or "pass" in detail:
        return {"control": "passes", "message": "The passes or their total steps are not valid", "detail": detail}
    # Engine facts (a node, sampler or LoRA the engine does not have) are already plain and name what to install or
    # choose; a generic sentence would hide the one fact the artist needs. Every other refusal keeps the generic text.
    if detail.startswith(("Unavailable: ", "The engine ")) or re.search(r" is not a \S.* LoRA", detail):
        return {"control": None, "message": detail, "detail": detail}
    # The remaining refusals are fixed sentences; with their control names in plain words they tell artist and Hermes
    # the one thing to change ("Turbo strength needs turbo on"). Only a sentence that still carries a field-shaped token
    # after that becomes the generic one (cold review w47 M2).
    plain = re.sub(r"\b(" + "|".join(_PLAIN_NAMES) + r")\b", lambda m: _PLAIN_NAMES[m.group(1)], detail)
    if not re.search(r"\w_\w|\[\d|[a-z]\.[a-z]", plain):
        return {"control": None, "message": plain[:1].upper() + plain[1:], "detail": detail}
    return {"control": None, "message": "The sampling controls are not valid", "detail": detail}


_PLAIN_NAMES = {"turbo_strength": "Turbo strength", "sigma_shift_video": "Video shift", "sigma_shift_audio": "Sound shift",
                "take_index": "Take", "sampler_name": "Sampler", "duration_seconds": "Duration", "aspect_ratio": "Aspect ratio"}


class H3ControlError(ValueError):
    """Finite refusal of a control request, raised before any side effect."""

    def __init__(self, message: str, reason_code: str = "invalid_request") -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.diagnostic = _control_diagnostic(message)


def _fail(message: str, reason_code: str = "invalid_request") -> H3ControlError:
    return H3ControlError(message, reason_code)


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise _fail(f"{name} must be a number from {low:g} to {high:g}")
    return round(float(value), 4)


def _choice(value: Any, name: str, options: Iterable[str]) -> str:
    options = tuple(options)
    if type(value) is not str or value not in options:
        raise _fail(f"{name} must be one of {', '.join(options)}")
    return value


def has_controls(args: Mapping[str, Any]) -> bool:
    return isinstance(args, Mapping) and any(key in args for key in CONTROL_KEYS)


def split_args(args: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(the pinned compile's args, the control args); the batch keys belong to neither."""
    base = {k: v for k, v in args.items() if k not in CONTROL_KEYS and k not in BATCH_KEYS}
    return base, {k: v for k, v in args.items() if k in CONTROL_KEYS}


def batch_args(args: Mapping[str, Any]) -> dict[str, int] | None:
    """``{count, index}`` of one take of a Generate x N request; None for a single take (count absent or 1)."""
    if "count" not in args:
        if "take_index" in args:
            raise _fail("take_index belongs to a count request")
        return None
    count = args["count"]
    if isinstance(count, bool) or type(count) is not int or not COUNT_MIN <= count <= COUNT_MAX:
        raise _fail(f"count must be a whole number from {COUNT_MIN} to {COUNT_MAX}")
    index = args.get("take_index", 0)
    if isinstance(index, bool) or type(index) is not int or not 0 <= index < count:
        raise _fail("take_index must be a take of this count")
    return None if count == 1 else {"count": count, "index": index}


def take_seed(seed: int, index: int) -> int:
    return (seed + index) % SEED_MODULUS


def take_client_request_id(client_request_id: str, index: int) -> str:
    """Take 0 keeps the request's id (count 1 is the request before); take i gets ``:take-i``."""
    return client_request_id if index == 0 else f"{client_request_id}:take-{index}"


def batch_id(client_request_id: str) -> str:
    import hashlib

    return "h3b_" + hashlib.sha256(client_request_id.encode("utf-8")).hexdigest()[:24]


def normalize_loras(value: Any) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > LORA_MAX:
        raise _fail(f"loras must be a list of at most {LORA_MAX}")
    out, seen = [], set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {"file", "strength"}:
            raise _fail(f"loras[{index}] must be {{file, strength}}")
        name = item["file"]
        if (type(name) is not str or not name.endswith(".safetensors") or len(name) > 240 or name.startswith(("/", "."))
                or "\\" in name or ".." in name.split("/") or any(c in name for c in ':*?"<>|') or name in seen):
            raise _fail(f"loras[{index}].file is not a LoRA file name or is listed twice")
        if name.rsplit("/", 1)[-1] in PINNED_TURBO_LORAS:
            raise _fail("the turbo LoRA is set with turbo and turbo_strength, not as a user LoRA")
        seen.add(name)
        strength = _number(item["strength"], f"loras[{index}].strength", *LORA_STRENGTH)
        out.append({"file": name, "strength": strength})
    return out


_PASS_FORM = "{steps, sampler, noise, s_noise?, s_noise_end?}"


def _sampler_name(value: Any) -> bool:
    return type(value) is str and 0 < len(value) <= 64 and all(c.isascii() and (c.isalnum() or c == "_") for c in value) \
        and value == value.lower()


def normalize_passes(value: Any, steps: int) -> list[dict[str, Any]]:
    """The pass list of recipe custom: at most PASS_MAX passes whose steps add up to the run's steps; the first adds noise."""
    if type(value) is not list or not 1 <= len(value) <= PASS_MAX:
        raise _fail(f"passes must be a list of at most {PASS_MAX} passes, each {_PASS_FORM}")
    out = []
    for index, item in enumerate(value):
        name = f"passes[{index}]"
        if not isinstance(item, Mapping):
            raise _fail(f"{name} must be {_PASS_FORM}")
        missing = [key for key in ("steps", "sampler", "noise") if key not in item]
        if missing:
            raise _fail(f"{name} lacks {', '.join(missing)}; a pass is {_PASS_FORM}")
        unknown = sorted(str(key) for key in item if key not in PASS_KEYS)
        if unknown:
            raise _fail(f"{name} has an unknown field ({len(unknown)}); a pass is {_PASS_FORM}")
        count = item["steps"]
        if isinstance(count, bool) or type(count) is not int or not PASS_STEPS[0] <= count <= PASS_STEPS[1]:
            raise _fail(f"{name}.steps must be a whole number from {PASS_STEPS[0]} to {PASS_STEPS[1]}")
        sampler = item["sampler"]
        if not _sampler_name(sampler):
            raise _fail(f"{name}.sampler must be a sampler name such as er_sde or lcm")
        if type(item["noise"]) is not bool:
            raise _fail(f"{name}.noise must be true or false")
        row: dict[str, Any] = {"steps": count, "sampler": sampler, "noise": item["noise"]}
        if "s_noise" in item:
            if sampler not in NOISE_NODES:
                raise _fail(f"{name}.s_noise is offered for {', '.join(NOISE_NODES)}; {sampler} runs with its own noise")
            row["s_noise"] = _number(item["s_noise"], f"{name}.s_noise", PASS_NOISE[0], PASS_NOISE[1])
        if "s_noise_end" in item:
            if sampler not in NOISE_END_SAMPLERS:
                raise _fail(f"{name}.s_noise_end is offered for {', '.join(NOISE_END_SAMPLERS)} only")
            row["s_noise_end"] = _number(item["s_noise_end"], f"{name}.s_noise_end", PASS_NOISE[0], PASS_NOISE[1])
        out.append(row)
    if not out[0]["noise"]:
        raise _fail("the first pass adds the noise: passes[0].noise must be true")
    total = sum(row["steps"] for row in out)
    if total != steps:
        raise _fail(f"the passes add up to {total} steps; steps is {steps}")
    return out


def normalize_sigmas(value: Any, steps: int) -> list[float]:
    """A drawn curve: steps + 1 numbers, the first at most 1, each smaller than the one before, the last 0."""
    if type(value) is not list:
        raise _fail(f"sigmas must be a list of numbers: {steps + 1} values (steps + 1) falling from at most 1 to 0")
    out: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or type(item) not in (int, float) or not math.isfinite(item) or item < 0:
            raise _fail(f"sigmas[{index}] must be a number from 0 to 1")
        out.append(round(float(item), CURVE_DECIMALS))
    if len(out) != steps + 1:
        raise _fail(f"sigmas must hold {steps + 1} values (steps + 1); it holds {len(out)}")
    if out[0] > 1.0:
        raise _fail("sigmas[0] must be at most 1")
    for index in range(1, len(out)):
        if out[index] >= out[index - 1]:
            raise _fail(f"sigmas must fall from one value to the next (sigmas[{index}] does not, at {CURVE_DECIMALS} decimals)")
    if out[-1] != 0.0:
        raise _fail("sigmas must end at 0")
    return out


def validate_controls(target_id: str, args: Mapping[str, Any], steps: int) -> dict[str, Any]:
    """The normalized control set (every key filled from DEFAULTS); shape rules only, no live check."""
    if target_id not in TARGET_IDS:
        raise _fail("controls are offered for MiniMax H3 Frames and References only")
    given = {k: v for k, v in args.items() if k in CONTROL_KEYS}
    c = copy.deepcopy(DEFAULTS)
    if "turbo" in given:
        if type(given["turbo"]) is not bool:
            raise _fail("turbo must be true or false")
        c["turbo"] = given["turbo"]
    if "turbo_strength" in given:
        if not c["turbo"]:
            raise _fail("turbo_strength needs turbo on")
        c["turbo_strength"] = _number(given["turbo_strength"], "turbo_strength", *TURBO_STRENGTH)
    for key in ("sigma_shift_video", "sigma_shift_audio"):
        if key in given:
            c[key] = _number(given[key], key, *SIGMA_SHIFT)
    if "engine" in given:
        c["engine"] = _choice(given["engine"], "engine", ENGINES)
    if "recipe" in given:
        c["recipe"] = _choice(given["recipe"], "recipe", RECIPES)
    if c["recipe"] != "native":
        if c["engine"] != "native":
            raise _fail("a sampling recipe runs on the Native engine only")
    if c["recipe"] == "custom":
        if "passes" not in given:
            raise _fail(f"recipe custom needs passes: a list of {_PASS_FORM}")
        c["passes"] = normalize_passes(given["passes"], steps)
    elif "passes" in given:
        raise _fail("passes need recipe custom")
    if c["recipe"] in ("sandwich", "fast_0903"):
        if steps < RECIPE_A_STEPS + RECIPE_C_STEPS + 1:
            raise _fail(f"the {c['recipe']} recipe needs at least {RECIPE_A_STEPS + RECIPE_C_STEPS + 1} steps")
    if "sigmas" in given:
        c["sigmas"] = normalize_sigmas(given["sigmas"], steps)
    if c["engine"] == "shark" and steps < 2:
        raise _fail("the Shark engine needs at least 2 steps")
    if "loras" in given:
        c["loras"] = normalize_loras(given["loras"])
    if "attention" in given:
        c["attention"] = _choice(given["attention"], "attention", ATTENTIONS)
    if "sparse" in given:
        c["sparse"] = _choice(given["sparse"], "sparse", SPARSES)
    if "sparsity" in given:
        if c["sparse"] == "off":
            raise _fail("sparsity needs sparse sla or native")
        low, high, _ = SLA_SPARSITY if c["sparse"] == "sla" else NATIVE_TAU
        c["sparsity"] = _number(given["sparsity"], "sparsity", low, high)
    elif c["sparse"] != "off":
        c["sparsity"] = (SLA_SPARSITY if c["sparse"] == "sla" else NATIVE_TAU)[2]
    if c["sparse"] == "native" and c["attention"] is not None:
        raise _fail("native sparse runs its own attention; leave attention unset")
    if "cache" in given:
        c["cache"] = _choice(given["cache"], "cache", CACHES)
    return c


def requested(controls: Mapping[str, Any]) -> dict[str, Any]:
    """The values that differ from the pinned graph (take facts, receipts)."""
    return {k: copy.deepcopy(v) for k, v in controls.items() if v != DEFAULTS[k]}


def needs(controls: Mapping[str, Any]) -> list[tuple[str, str | None, str | None]]:
    """Every live class/option the controls need (sparse replaces the attention patch, as in RC2)."""
    out: list[tuple[str, str | None, str | None]] = []
    keys = [(k, controls[k]) for k in ("recipe", "sparse", "cache", "engine")]
    if controls["sparse"] == "off":
        keys.append(("attention", controls["attention"]))
    if controls["loras"]:
        keys.append(("loras", True))
    if controls.get("sigmas") is not None:
        keys.append(("sigmas", True))
    for key in keys:
        for need in NEEDS.get(key, ()):
            if key == ("sparse", "sla"):
                need = ("H3SLAAttention", "dense_backend", _SLA_DENSE[controls["attention"]])
            if need not in out:
                out.append(need)
    if controls["recipe"] == "custom":
        for row in controls["passes"]:
            need = (NOISE_NODES[row["sampler"]][0], None, None) if "s_noise" in row or "s_noise_end" in row \
                else ("KSamplerSelect", "sampler_name", row["sampler"])
            if need not in out:
                out.append(need)
    return out


# --------------------------------------------------------------------------- compile


def _consumers(graph: Mapping[str, Any], node_id: str, slot: int = 0) -> list[tuple[str, str]]:
    return [(nid, key) for nid, node in graph.items() for key, value in node["inputs"].items()
            if isinstance(value, list) and len(value) == 2 and value[0] == node_id and value[1] == slot]


def _rewire(graph: dict[str, Any], old: list[Any], new: list[Any], skip: Iterable[str] = ()) -> None:
    skip = set(skip)
    for nid, key in _consumers(graph, old[0], old[1]):
        if nid not in skip:
            graph[nid]["inputs"][key] = list(new)


class _Ids:
    def __init__(self, graph: Mapping[str, Any]) -> None:
        self.next = _NEW
        if any(k.isdigit() and int(k) >= _NEW for k in graph):
            raise _fail("graph already carries control nodes")

    def __call__(self) -> str:
        self.next += 1
        return str(self.next - 1)


def apply_controls(graph: Mapping[str, Any], controls: Mapping[str, Any], *, steps: int) -> dict[str, Any]:
    """The compiled pinned graph with the controls applied structurally (a new graph)."""
    g = copy.deepcopy(dict(graph))
    for node_id in (_UNET, _SHIFT, _TURBO, _NOISE, _SAMPLER, _SCHEDULER, _GUIDER, _RUN):
        if node_id not in g:
            raise _fail("the pinned graph lacks a node the controls need")
    new = _Ids(g)
    # Model chain between UNET and SigmaShift: user LoRAs -> attention | sparse -> cache.
    tail: list[Any] = [_UNET, 0]
    for item in controls["loras"]:
        nid = new()
        g[nid] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"model": list(tail), "lora_name": item["file"].replace("/", os.sep), "strength_model": item["strength"]}}
        tail = [nid, 0]
    if controls["sparse"] == "sla":
        nid = new()
        g[nid] = {"class_type": "H3SLAAttention", "inputs": {"model": list(tail), "sparsity_ratio": controls["sparsity"],
                                                            **_SLA_INPUTS, "dense_backend": _SLA_DENSE[controls["attention"]]}}
        tail = [nid, 0]
    elif controls["sparse"] == "native":
        nid = new()
        g[nid] = {"class_type": "BlockSparseAttention", "inputs": {"model": list(tail), "selection": "sol-attn",
                                                                  "selection.tau": controls["sparsity"], **_NATIVE_SPARSE_INPUTS}}
        tail = [nid, 0]
    elif controls["attention"] in ("comfy_kitchen", "pytorch"):
        nid = new()
        g[nid] = {"class_type": "ModelAttentionBackend", "inputs": {
            "model": list(tail), "attention": "comfy kitchen attention" if controls["attention"] == "comfy_kitchen" else "pytorch attention"}}
        tail = [nid, 0]
    elif controls["attention"] == "sage":
        kj, h3 = new(), new()
        g[kj] = {"class_type": "PathchSageAttentionKJ", "inputs": {"model": list(tail), "sage_attention": "auto", "allow_compile": False}}
        g[h3] = {"class_type": "MiniMaxH3MemoryEfficientSageAttentionPatch", "inputs": {"model": [kj, 0]}}
        tail = [h3, 0]
    if controls["cache"] == "t8":
        nid = new()
        g[nid] = {"class_type": "MiniMaxH3BlockCacheT8", "inputs": {"model": list(tail), **_T8_INPUTS}}
        tail = [nid, 0]
    elif controls["cache"] == "spectrum":
        nid = new()
        g[nid] = {"class_type": "SpectrumApplyMiniMaxH3", "inputs": {"model": list(tail), **_SPECTRUM_INPUTS}}
        tail = [nid, 0]
    g[_SHIFT]["inputs"]["model"] = list(tail)
    g[_SHIFT]["inputs"]["shift_video"] = controls["sigma_shift_video"]
    g[_SHIFT]["inputs"]["shift_audio"] = controls["sigma_shift_audio"]

    # Turbo LoRA (pinned node 6): strength, or removed with its consumers moved to SigmaShift.
    model = [_TURBO, 0]
    if controls["turbo"]:
        g[_TURBO]["inputs"]["strength_model"] = controls["turbo_strength"]
    else:
        _rewire(g, [_TURBO, 0], [_SHIFT, 0])
        del g[_TURBO]
        model = [_SHIFT, 0]
    if controls["loras"]:
        fix = new()
        _rewire(g, model, [fix, 0])
        g[fix] = {"class_type": "H3AdaLNLoRAFix", "inputs": {"model": list(model), "mode": "port"}}

    # Engine / recipe: replace the single SamplerCustomAdvanced (node 14) structurally.
    if controls["engine"] == "shark":
        _shark(g, new, steps)
    elif controls["recipe"] in ("sandwich", "fast_0903"):
        _recipe(g, new, steps, controls["recipe"])
    elif controls["recipe"] == "custom":
        _passes(g, new, controls["passes"])
    if controls.get("sigmas") is not None:
        # The drawn curve replaces the pinned BasicScheduler (12) for whatever reads it (native, passes, sandwich, Shark);
        # fast_0903 keeps its own C tail.  Fixed decimals: ManualSigmas' regex cannot read exponent form.
        manual = new()
        g[manual] = {"class_type": "ManualSigmas", "inputs": {"sigmas": curve_text(controls["sigmas"])}}
        _rewire(g, [_SCHEDULER, 0], [manual, 0])
        del g[_SCHEDULER]
    _check_links(g)
    return g


def _ksampler(g: dict[str, Any], new: _Ids, name: str) -> str:
    nid = new()
    g[nid] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": name}}
    return nid


def _recipe(g: dict[str, Any], new: _Ids, steps: int, recipe: str) -> None:
    """RC2 SANDWICH / FAST 0903: A (3 steps, noise) -> B (no noise) -> C (3 steps).

    The curve is the pinned BasicScheduler (12) with the artist's steps and scheduler; B uses
    the artist's sampler (11), A and C dpmpp_3m_sde_gpu.  Sandwich: C finishes the curve's last
    3 steps without noise.  Fast 0903: B's denoised video is latent-upscaled 2x (audio passes
    around), C re-noises with the validated 0903 tail at full size, the audio of B is grafted back.
    """
    run = g[_RUN]["inputs"]
    guider, latent = list(run["guider"]), list(run["latent_image"])
    out = [_RUN, 0]
    split_ab, split_bc, quiet = new(), new(), new()
    g[split_ab] = {"class_type": "SplitSigmas", "inputs": {"sigmas": [_SCHEDULER, 0], "step": RECIPE_A_STEPS}}
    g[split_bc] = {"class_type": "SplitSigmas", "inputs": {"sigmas": [split_ab, 1], "step": steps - RECIPE_A_STEPS - RECIPE_C_STEPS}}
    g[quiet] = {"class_type": "DisableNoise", "inputs": {}}
    sampler_a, sampler_c = _ksampler(g, new, "dpmpp_3m_sde_gpu"), _ksampler(g, new, "dpmpp_3m_sde_gpu")
    a, b, c = new(), new(), new()
    g[a] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [_NOISE, 0], "guider": guider, "sampler": [sampler_a, 0],
                                                              "sigmas": [split_ab, 0], "latent_image": latent}}
    g[b] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [quiet, 0], "guider": list(guider), "sampler": [_SAMPLER, 0],
                                                              "sigmas": [split_bc, 0], "latent_image": [a, 0]}}
    if recipe == "sandwich":
        g[c] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [quiet, 0], "guider": list(guider), "sampler": [sampler_c, 0],
                                                                  "sigmas": [split_bc, 1], "latent_image": [b, 0]}}
        final = [c, 0]
    else:
        part, up, join, tail, part_c, graft = new(), new(), new(), new(), new(), new()
        g[part] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [b, 1]}}
        g[up] = {"class_type": "MinimaxH3LatentUpscaler3D", "inputs": {
            "latent": [part, 0], "model_name": LATENT_UPSCALER, "mode": "scale by multiplier", "mode.scale": 2.0, "align": 32,
            "enable_temporal_chunking": True, "force_unload": True, "device": "cuda", "precision": "fp16"}}
        g[join] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": [up, 0], "audio_latent": [part, 1]}}
        g[tail] = {"class_type": "ManualSigmas", "inputs": {"sigmas": FAST_0903_C_SIGMAS}}
        g[c] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [_NOISE, 0], "guider": list(guider), "sampler": [sampler_c, 0],
                                                                  "sigmas": [tail, 0], "latent_image": [join, 0]}}
        g[part_c] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [c, 0]}}
        g[graft] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": [part_c, 0], "audio_latent": [part, 1]}}
        final = [graft, 0]
    _rewire(g, out, final)
    del g[_RUN]


def _pass_sampler(g: dict[str, Any], new: _Ids, row: Mapping[str, Any]) -> str:
    if "s_noise" not in row and "s_noise_end" not in row:
        return _ksampler(g, new, row["sampler"])
    class_type, fixed = NOISE_NODES[row["sampler"]]
    s_noise = row.get("s_noise", PASS_NOISE[2])
    inputs = {**fixed, "s_noise": s_noise}
    if class_type == "SamplerLCM":
        inputs = {"s_noise": s_noise, "s_noise_end": row.get("s_noise_end", s_noise), **fixed}
    nid = new()
    g[nid] = {"class_type": class_type, "inputs": inputs}
    return nid


def _passes(g: dict[str, Any], new: _Ids, passes: list[Mapping[str, Any]]) -> None:
    """Custom passes: the curve (node 12) split by a SplitSigmas cascade, one SamplerCustomAdvanced per pass.

    Pass i runs its own sampler on its share of the curve and continues the latent of pass i-1; a pass with
    noise takes the seed's noise (node 10), one without DisableNoise.  The artist's single sampler (11) is unused.
    """
    run = g[_RUN]["inputs"]
    guider, latent = list(run["guider"]), list(run["latent_image"])
    quiet = None
    source: list[Any] = [_SCHEDULER, 0]
    for index, row in enumerate(passes):
        if index < len(passes) - 1:
            split = new()
            g[split] = {"class_type": "SplitSigmas", "inputs": {"sigmas": list(source), "step": row["steps"]}}
            sigmas, source = [split, 0], [split, 1]
        else:
            sigmas = list(source)
        if not row["noise"] and quiet is None:
            quiet = new()
            g[quiet] = {"class_type": "DisableNoise", "inputs": {}}
        sampler = _pass_sampler(g, new, row)
        nid = new()
        g[nid] = {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": [_NOISE, 0] if row["noise"] else [quiet, 0], "guider": list(guider), "sampler": [sampler, 0],
            "sigmas": sigmas, "latent_image": latent}}
        latent = [nid, 0]
    _rewire(g, [_RUN, 0], latent)
    del g[_RUN]
    if not _consumers(g, _SAMPLER):
        del g[_SAMPLER]


def _shark(g: dict[str, Any], new: _Ids, steps: int) -> None:
    """RC2 SHARK: ClownsharKSampler (etdrk2_2s, all but the last step) -> Chainsampler (res_3m).

    Same patched model and conditioning as Native, zeroed negative, the artist's curve (node 12).
    """
    guider = g[_GUIDER]["inputs"]
    model, positive = list(guider["model"]), list(guider["conditioning"])
    latent = list(g[_RUN]["inputs"]["latent_image"])
    negative, options, first, second = new(), new(), new(), new()
    g[negative] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": list(positive)}}
    g[options] = {"class_type": "ClownOptions_ExtraOptions_Beta", "inputs": {"extra_options": _SHARK_OPTIONS}}
    g[first] = {"class_type": "ClownsharKSampler_Beta", "inputs": {
        "eta": 0.5, "sampler_name": "exponential/etdrk2_2s", "scheduler": "simple", "steps": 1, "steps_to_run": steps - 1,
        "denoise": 1.0, "cfg": 1.0, "seed": [_SEED, 0], "sampler_mode": "standard", "bongmath": True, "model": model,
        "positive": positive, "negative": [negative, 0], "latent_image": latent, "sigmas": [_SCHEDULER, 0],
        "options_group.options0": [options, 0]}}
    g[second] = {"class_type": "ClownsharkChainsampler_Beta", "inputs": {
        "eta": 0.15, "sampler_name": "multistep/res_3m", "steps_to_run": -1, "cfg": 1.0, "sampler_mode": "resample",
        "bongmath": True, "latent_image": [first, 0], "options_group.options0": [options, 0]}}
    _rewire(g, [_RUN, 0], [second, 0])
    for node_id in (_RUN, _GUIDER, _NOISE, _SAMPLER):
        del g[node_id]


def curve_text(sigmas: Iterable[float]) -> str:
    return ", ".join(f"{float(v):.{CURVE_DECIMALS}f}" for v in sigmas)


# --------------------------------------------------------------------------- sigma curve
# The scheduler's own curve to start a drawing from, in plain Python (scipy is not a declared dependency).  ComfyUI 0.45.0:
# the H3 model sampling is ModelSamplingAV(shift = sigma shift video), a ModelSamplingDiscreteFlow with 1000 steps and
# multiplier 1000 (comfy/model_sampling.py:294-317,338-351, nodes_minimax_h3.py:408-416): sigmas[i] = time_snr_shift(shift,
# (i + 1) / 1000) (:289-292).  simple_scheduler: comfy/samplers.py:645-652; beta_scheduler (alpha = beta = 0.6): :696-709.


def _flow_sigmas(shift: float) -> list[float]:
    out = []
    for i in range(1, 1001):
        t = i / 1000
        out.append(t if shift == 1.0 else shift * t / (1 + (shift - 1) * t))
    return out


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) (continued fraction, Lentz)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1.0 - x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    f = d
    for m in range(1, 400):
        m2 = 2 * m
        for num in (m * (b - m) * x / ((a + m2 - 1) * (a + m2)), -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))):
            d = 1.0 + num * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + num / c
            c = c if abs(c) > tiny else tiny
            f *= c * d
        if abs(c * d - 1.0) < 1e-16:
            break
    return front * f / a


def _beta_ppf(q: float, a: float, b: float) -> float:
    """Inverse of _betainc by bisection to machine precision."""
    if q <= 0.0:
        return 0.0
    if q >= 1.0:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2
        if mid in (low, high):
            break
        if _betainc(a, b, mid) < q:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def sigma_curve(scheduler: str, steps: int, shift: float) -> list[float]:
    """The curve the pinned BasicScheduler gives for (scheduler, steps, sigma shift video): steps + 1 values ending at 0."""
    if scheduler not in CURVE_SCHEDULERS:
        raise _fail(f"scheduler must be one of {', '.join(CURVE_SCHEDULERS)}")
    if isinstance(steps, bool) or type(steps) is not int or not 1 <= steps <= 100:
        raise _fail("steps must be a whole number from 1 to 100")
    sig = _flow_sigmas(_number(shift, "sigma_shift_video", *SIGMA_SHIFT))
    out: list[float] = []
    if scheduler == "simple":
        ss = len(sig) / steps
        out = [sig[-(1 + int(x * ss))] for x in range(steps)]
    else:
        last = -1
        for x in range(steps):
            t = round(_beta_ppf(1 - x / steps, 0.6, 0.6) * (len(sig) - 1))  # numpy.rint: half to even, as round()
            if t != last:
                out.append(sig[int(t)])
            last = t
    return [round(v, CURVE_DECIMALS) for v in out] + [0.0]


def _check_links(g: Mapping[str, Any]) -> None:
    for node_id, node in g.items():
        for name, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int \
                    and value[0] not in g:
                raise _fail(f"node {node_id} input {name} points at a removed node")


def canvas_after(controls: Mapping[str, Any], canvas: Mapping[str, int]) -> dict[str, int]:
    """Fast 0903 delivers twice the canvas (its C pass runs on the 2x latent)."""
    if controls.get("recipe") == "fast_0903" and controls.get("engine", "native") == "native":
        return {"width": canvas["width"] * 2, "height": canvas["height"] * 2}
    return dict(canvas)


# --------------------------------------------------------------------------- live admission / descriptor


def _options(spec: Any) -> list[Any]:
    if not isinstance(spec, list) or not spec:
        return []
    if isinstance(spec[0], list):
        return list(spec[0])
    if len(spec) > 1 and isinstance(spec[1], Mapping) and isinstance(spec[1].get("options"), list):
        return [o.get("key") if isinstance(o, Mapping) else o for o in spec[1]["options"]]
    return []


def class_problem(need: tuple[str, str | None, str | None], info: Mapping[str, Any] | None) -> str | None:
    """None when the live ``/object_info`` of the class carries what the control needs."""
    class_type, field, option = need
    node = info.get(class_type) if isinstance(info, Mapping) else None
    if not isinstance(node, Mapping):
        return f"the engine has no {class_type} node"
    if field is None:
        return None
    inputs = node.get("input") or {}
    spec = (inputs.get("required") or {}).get(field) or (inputs.get("optional") or {}).get(field)
    if option not in _options(spec):
        return f"{class_type} does not offer {option}"
    return None


def lora_family(base_model: str, name: str, base_family: Any) -> str:
    """The family of a LoRA: its metadata base model, else a strong family word in its file name."""
    family = base_family(base_model) if base_model else ""
    return family or base_family(name.rsplit("/", 1)[-1])


def admit_loras(loras: list[dict[str, Any]], live: list[str] | None, family_of: Any) -> None:
    """Only files the engine lists and only MiniMax H3 LoRAs."""
    for item in loras:
        if live is not None and item["file"] not in live:
            raise _fail(f"The engine does not list {item['file']}", "invalid_request")
        family = family_of(item["file"])
        if family != H3_FAMILY:
            raise _fail(f"{item['file']} is not a {H3_FAMILY} LoRA" + (f" ({family})" if family else ""), "invalid_request")


def evidence(key: str, value: Any) -> dict[str, Any]:
    proof = EVIDENCE.get((key, value))
    if proof is None:
        return {"state": "untested"}
    return {"state": "rendered", **copy.deepcopy(proof)}


_CONTROLS = (
    # id, section, kind, label, options or range, values that have an evidence entry
    ("turbo", "sampling", "boolean", "Turbo", None),
    ("turbo_strength", "sampling", "number", "Turbo LoRA strength", {"min": TURBO_STRENGTH[0], "max": TURBO_STRENGTH[1], "step": 0.05}),
    ("recipe", "sampling", "select", "Recipe", list(RECIPES)),
    ("sigmas", "sampling", "sigma_curve", "Noise schedule", {"min": 0.0, "max": 1.0, "decimals": CURVE_DECIMALS, "schedulers": list(CURVE_SCHEDULERS)}),
    ("passes", "sampling", "pass_list", "Passes", {"max": PASS_MAX, "noise": {"min": PASS_NOISE[0], "max": PASS_NOISE[1], "default": PASS_NOISE[2]},
                                                     "noise_samplers": list(NOISE_NODES), "noise_end_samplers": list(NOISE_END_SAMPLERS)}),
    ("sigma_shift_video", "sampling", "number", "Sigma shift video", {"min": SIGMA_SHIFT[0], "max": SIGMA_SHIFT[1], "step": 0.5}),
    ("sigma_shift_audio", "sampling", "number", "Sigma shift audio", {"min": SIGMA_SHIFT[0], "max": SIGMA_SHIFT[1], "step": 0.5}),
    ("engine", "sampling", "select", "Engine", list(ENGINES)),
    ("loras", "loras", "lora_list", "LoRAs", {"max": LORA_MAX, "strength": {"min": LORA_STRENGTH[0], "max": LORA_STRENGTH[1]}}),
    ("attention", "performance", "select", "Attention", list(ATTENTIONS)),
    ("sparse", "performance", "select", "Sparse", list(SPARSES)),
    ("sparsity", "performance", "number", "Sparsity", {"sla": {"min": SLA_SPARSITY[0], "max": SLA_SPARSITY[1], "default": SLA_SPARSITY[2]},
                                                       "native": {"min": NATIVE_TAU[0], "max": NATIVE_TAU[1], "default": NATIVE_TAU[2], "meaning": "sol-attn tau"}}),
    ("cache", "performance", "select", "Cache", list(CACHES)),
)


def live_samplers(info: Mapping[str, Any] | None) -> list[str] | None:
    """The sampler names the live KSamplerSelect offers (None when the engine was not read)."""
    node = info.get("KSamplerSelect") if isinstance(info, Mapping) else None
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("input") or {}
    return [str(o) for o in _options((inputs.get("required") or {}).get("sampler_name"))]


def descriptor(problems: Mapping[tuple[str, Any], str | None] | None, *, lora_names: list[str] | None = None,
               samplers: list[str] | None = None) -> dict[str, Any]:
    """Per control: options, default, live availability (``problems`` None = engine not checked) and evidence.

    ``problems`` maps (control, value) to the first live problem (None = available).
    """
    controls = []
    for cid, section, kind, label, spec in _CONTROLS:
        row: dict[str, Any] = {"id": cid, "section": section, "kind": kind, "label": label, "default": DEFAULTS[cid]}
        if isinstance(spec, list):
            options = []
            for value in spec:
                problem = None if problems is None else problems.get((cid, value))
                state = "unchecked" if problems is None else ("unavailable" if problem else "available")
                options.append({"value": value, "state": state, **({"reason": problem} if problem else {}),
                                "evidence": evidence(cid, value)})
            row["options"] = options
        elif spec is not None:
            row.update(spec)
        if cid == "loras":
            problem = None if problems is None else problems.get(("loras", True))
            row["state"] = "unchecked" if problems is None else ("unavailable" if problem else "available")
            if problem:
                row["reason"] = problem
            if lora_names is not None:
                row["files"] = list(lora_names)
            row["evidence"] = evidence("loras", True)
        elif cid == "sigmas":
            problem = None if problems is None else problems.get(("sigmas", True))
            row["state"] = "unchecked" if problems is None else ("unavailable" if problem else "available")
            if problem:
                row["reason"] = problem
            row["evidence"] = evidence("sigmas", True)
        elif cid == "passes":
            row["state"] = "available" if problems is not None else "unchecked"
            if samplers is not None:
                row["samplers"] = list(samplers)
            row["evidence"] = evidence("passes", True)
        elif cid in ("turbo", "turbo_strength", "sigma_shift_video", "sigma_shift_audio", "sparsity"):
            row["state"] = "available" if problems is not None else "unchecked"
            row["evidence"] = evidence(cid, True)
        rendered = [o for o in row.get("options", ()) if o["evidence"]["state"] == "rendered" and o["value"] != DEFAULTS[cid]]
        row["proof"] = "rendered" if rendered or row.get("evidence", {}).get("state") == "rendered" else "untested"
        controls.append(row)
    return {"schema": "studio.h3-controls/1", "targets": list(TARGET_IDS), "controls": controls,
            "count": {"min": COUNT_MIN, "max": COUNT_MAX, "seed": "seed + index", "proof": evidence("count", True)["state"],
                      "evidence": evidence("count", True)}}


def option_needs() -> dict[tuple[str, Any], tuple[tuple[str, str | None, str | None], ...]]:
    return dict(NEEDS)


__all__ = ["BATCH_KEYS", "batch_args", "batch_id", "take_client_request_id", "take_seed", "ATTENTIONS", "CACHES", "CONTROL_KEYS", "COUNT_MAX", "COUNT_MIN", "DEFAULTS", "ENGINES", "EVIDENCE", "H3ControlError",
           "H3_FAMILY", "NEEDS", "RECIPES", "SPARSES", "TARGET_IDS", "admit_loras", "apply_controls", "canvas_after", "live_samplers", "normalize_passes", "normalize_sigmas", "sigma_curve", "curve_text", "NOISE_NODES", "PASS_MAX",
           "class_problem", "descriptor", "evidence", "has_controls", "lora_family", "needs", "normalize_loras",
           "option_needs", "requested", "split_args", "validate_controls"]
