from __future__ import annotations


def _model_catalog_client() -> Any:
    return _comfy_client_module.ComfyUIClient()


def _image_readiness_module() -> Any:
    """w45-s1 item 2: the one image readiness answer (generation/image_readiness.py), inside the generation package.
    w45-s4 item 5: the package is loaded when it is not (a reload dropped it): never ModuleNotFoundError."""
    if _GENERATION_PACKAGE_NAME not in sys.modules:
        _load_generation_package()
    return importlib.import_module(_image_contract_module().__package__ + ".image_readiness")


class ModelCatalogValidationRoute(APIRoute):
    """Translate model catalog request-model failures to a finite error."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def finite_handler(request):
            try:
                return await original_route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "invalid_model_catalog_request",
                            "message": "Model catalog request is invalid",
                        }
                    },
                )

        return finite_handler


model_catalog_router = APIRouter(route_class=ModelCatalogValidationRoute)


class ModelCatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    check_classes: bool = True
    # Lane fs-voice: voice families are listed only when asked ("voice"), so the
    # Image/Shoot pickers keep their answer; omitted = image and video.
    kinds: list[Literal["image", "video", "voice"]] | None = Field(default=None, min_length=1, max_length=3)


@model_catalog_router.post("/models/catalog")
async def models_catalog(request: ModelCatalogRequest) -> Any:
    """Families, variants, operations, inputs, presets, file names and health.

    Read-only: scans model folders off the event loop (bounded, names only)
    and, when asked, probes ``GET /object_info/{class}``; never queues work.
    """
    try:
        classes = None
        engine_files: frozenset[str] = frozenset()
        engine = None
        if request.check_classes:
            catalog = await asyncio.to_thread(_model_catalog_module.load_catalog)
            # w39-p2-tester item 4: the engine's own loader lists count as present (a ComfyUI on another port keeps
            # its models in its own folder), and the answer says whether an engine answered and where.
            classes, engine_files = await _model_catalog_module.probe_engine(
                _model_catalog_client(), _model_catalog_module.required_classes(catalog)
            )
            engine = await asyncio.to_thread(_comfy_endpoint_module.engine_state, answered=classes is not None)
        # w45-s1 item 2: the picker's availability of every catalog image target is the one readiness answer
        # (generation/image_readiness.image_target_readiness, the same health and submit use); None without a check.
        readiness = await _image_readiness_module().catalog_readiness(client=_model_catalog_client()) if request.check_classes else None
        out = await asyncio.wait_for(
            asyncio.to_thread(
                _model_catalog_module.build_public_catalog,
                classes,
                comfy_root=_MODEL_CATALOG_COMFY_ROOT,
                engine_files=engine_files,
                readiness=readiness,
                **({"kinds": tuple(request.kinds)} if request.kinds else {}),
            ),
            _MODEL_CATALOG_TIMEOUT_SECONDS,
        )
        _catalog_submit_rows(out)
        return {**out, "engine": engine} if engine is not None else out
    except ValueError as exc:
        if getattr(exc, "comfy_folder_setting", False):  # w41-folders: a saved folder that cannot be used, the fact
            return JSONResponse(status_code=409, content={"error": {"code": "comfy_folder_invalid", "message": str(exc)}})
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "model_catalog_unavailable", "message": "Model catalog is unavailable"}},
        )
    except Exception:  # noqa: BLE001 - finite, path-free plugin boundary
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "model_catalog_unavailable", "message": "Model catalog is unavailable"}},
        )


# Lane w45-s10 item 2: every image row names the tool that submits it, and the Krea 2 rows (Turbo, Raw: the render-spec
# route, not a workflow target) carry the whole studio.krea2-render-spec/2 the submit takes. The 1.1.2 agent probe was
# told "Use the catalog render_spec" while no catalog held one, and continuo_image_workflow_health refused the Krea 2
# target it found here; one catalog read now gives a spec continuo_image_submit takes as it is (seed 0, 1024 x 1024).
_KREA2_SUBMIT_PROFILES = ("turbo", "raw")


_KREA2_SPEC_FOR_CATALOG: list[Any] = []


def _krea2_spec_for_catalog() -> Any:
    """generation/krea2_render_spec.py loaded by file as a top-level module (it then reads the catalog file itself), so
    this route never registers film_suite_generation.model_catalog (test_models_catalog_route); one source of the spec."""
    if not _KREA2_SPEC_FOR_CATALOG:
        path = Path(_model_catalog_module.__file__).with_name("krea2_render_spec.py")
        spec = importlib.util.spec_from_file_location("film_suite_catalog_krea2_render_spec", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _KREA2_SPEC_FOR_CATALOG.append(module)
    return _KREA2_SPEC_FOR_CATALOG[0]


def _catalog_submit_rows(out: Any) -> None:
    spec_module = _krea2_spec_for_catalog()
    for family in out.get("families") or ():
        if family.get("kind") != "image":
            continue
        for variant in family.get("variants") or ():
            workflow = variant.get("workflow")
            if isinstance(workflow, dict) and workflow.get("target_id"):
                variant["submit"] = {"tool": "continuo_image_workflow_submit", "target_id": workflow["target_id"]}
            elif family.get("id") == "krea2" and variant.get("id") in _KREA2_SUBMIT_PROFILES:
                variant["submit"] = {"tool": "continuo_image_submit",
                                     "render_spec": spec_module.default_spec_v2(0, 1024, 1024, variant["id"])}
