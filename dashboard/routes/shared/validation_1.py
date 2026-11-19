from __future__ import annotations


router = APIRouter()


# Lane w11-backend M-2 / U-42: these routes are no project request; a bad body
# names its first wrong field (a field name of the request model, never a value).
_NAMED_FIELD_PATHS = frozenset({"/media/feed", "/media/marks/read", "/projects/timeline/export", "/projects/timeline/export/status"})  # p13b-cut: export wait_ms


def _named_field_error(exc: Any) -> JSONResponse | None:
    try:
        location = exc.errors()[0].get("loc") or ()
        field = next((str(part) for part in reversed(location) if isinstance(part, str) and part != "body"), None)
    except Exception:  # noqa: BLE001 - fall back to the finite project answer
        return None
    if not field or len(field) > 64 or not field.replace("_", "").isalnum():
        return None
    return JSONResponse(status_code=422, content={"error": {
        "code": "invalid_request", "field": field, "message": f"The field {field} is missing or invalid"}})


def _render_spec_error(exc: Any) -> JSONResponse | None:
    """w45-s1 item 4 (HER-100): a render_spec the submit model refuses is named (the validator's reason and the accepted
    schemas), never folded into invalid_project. A krea2-render-spec/1 makes one picture; /2 takes batch_size 1-8."""
    try:
        errors = exc.errors()
        first = next((e for e in errors if "render_spec" in str(e.get("msg", "")) or "render_spec" in (e.get("loc") or ())), None)
        if first is None:
            return None
        message = str(first.get("msg") or "").removeprefix("Value error, ").strip()
    except Exception:  # noqa: BLE001 - fall back to the finite project answer
        return None
    # w45-s11 item 3: the validator's text echoes the caller's keys; the one sanitiser keeps it one clean line.
    message = _refusal_text.one_line(message, 200)
    if not message.strip():
        message = "render_spec invalid"
    return JSONResponse(status_code=422, content={"error": {
        "code": "invalid_render_spec", "field": "render_spec", "message": message,
        "accepted": {"schemas": ["studio.krea2-render-spec/1", "studio.krea2-render-spec/2"],
                     "batch_size": {"studio.krea2-render-spec/1": [1, 1], "studio.krea2-render-spec/2": [1, 8]},
                     # w45-s10 item 2: where a valid spec is (the models catalog's Krea 2 rows).
                     "valid_spec": "continuo_models_catalog families[krea2].variants[turbo|raw].submit.render_spec"}}})


class FiniteValidationRoute(APIRoute):
    """Translate only request-model failures into a finite project response."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()
        # Lane p5b-bck (BCK-032): the desktop mounts this router under /api/plugins/<name>, so the
        # route's path carries that prefix; match the route's own path at the end, not the whole path.
        named = any(self.path == p or self.path.endswith(p) for p in _NAMED_FIELD_PATHS)

        async def finite_handler(request):
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                answer = _named_field_error(exc) if named else _render_spec_error(exc)
                if answer is not None:
                    return answer
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "invalid_project",
                            "message": "Project request is invalid",
                        }
                    },
                )

        return finite_handler


class ImageCatalogValidationRoute(APIRoute):
    """Translate catalog request-model failures to its finite public error."""

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
                            "code": "invalid_image_catalog_request",
                            "message": "Image catalog request is invalid",
                        }
                    },
                )

        return finite_handler
