from __future__ import annotations


def _v4_request_identity(
    request: SubmitRequest,
    project_id: str | None,
    identity_args: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Use the single Task-5 serializer for the durable V4 identity."""
    del project_id  # Project scope is an independent immutable ledger field.
    boundary = _v4_path_boundary()
    args = dict(request.args if identity_args is None else identity_args)
    canonical_roots = [boundary.canonical_handle_identity(root) for root in _request_roots(request.approved_roots, request.project_ref)]
    payload = {
        "schema": request.schema or "studio.generation-request/1",
        "client_request_id": request.client_request_id,
        "provider_id": request.provider_id,
        "target_id": request.target_id,
        "args": args,
        "approved_roots": canonical_roots,
    }
    key = boundary.profile_identity_key()
    if request.provider_id == "comfyui-local":
        identity = _request_identity_module.build_comfy_request_identity(payload, key=key)
    elif request.provider_id == GMI_PROVIDER_ID:
        return _gmi_module.build_request_identity(payload, key=key)
    else:
        mode = request.mode or (request.target_id or "").replace("-", "_")
        identity = _request_identity_module.build_durable_request_identity(
            payload, key=key, mode=mode
        )
    return identity.request_json, identity.request_hash


def _v4_status_reason(outcome: Any, fallback: str) -> str:
    reason = getattr(outcome, "reason_code", None)
    if reason in generation.contract.REASON_CODES:
        return reason
    return fallback


def _v4_outcome_kind(outcome: Any) -> str:
    kind = getattr(outcome, "kind", None)
    return kind if isinstance(kind, str) else "malformed"


def _v4_finish_without_job(row: Any, expected_project_id: str | None, reason: str) -> Any:
    updated = _comfy_store().finish_submit_without_job(
        studio_job_id=row.studio_job_id,
        expected_project_id=expected_project_id,
        terminal_status="failed",
        reason_code=reason,
    )
    try:
        _private_ops().release_terminal_without_output(
            _private_ops().load_for_job(updated), "failed"
        )
    except (PrivateOperationError, OSError, ValueError):
        pass
    return updated


async def _v4_submit_route(request: SubmitRequest) -> dict[str, Any]:
    # Lane p5-vid (VID-020): every caller of this path (Generate x N, chain shoot) refuses a paid target first.
    if _generation_registry.is_paid_video_provider(request.provider_id):
        return _generation_registry.paid_target_refusal()
    # Resolve the provider/target pair before any destination, ledger,
    # admission, private-state, or provider operation.  A target ID is not a
    # provider-independent capability: registry membership is the authority.
    try:
        resolved_target = _generation_registry.resolve(request.provider_id, request.target_id)
    except (_generation_registry.InvalidRequestError, TypeError, ValueError):
        return _v4_named("unknown_target", None)
    if (
        resolved_target.provider_id != request.provider_id
        or resolved_target.target_id != request.target_id
    ):
        return _v4_named("unknown_target", None)
    if not request.client_request_id or not request.target_id:
        return _v4_named("request_id_missing", None)
    if request.provider_id == GMI_PROVIDER_ID:
        return await _gmi_submit_route(request)
    if _h3k_fans_out(request):  # lane w2-h3ctl: Generate x N, one durable request per take
        return await _h3k_submit_batch(request)
    media_boundary: Any | None = None
    pinned_media: list[tuple[str, int, Any]] = []
    try:
        try:
            directory, basename, project_id = _v4_destination(request)
        except ValueError as exc:
            # Lane p12-shl (BCK-023, P3 f3 wrong cause): a project take with a folder but no file name is
            # "Output file name missing", never "No output folder"; the destination literal alone cannot tell.
            if type(exc) is ValueError and str(exc) == "project output destination is invalid" and request.save_to and not request.requested_basename:
                return _v4_named("output_name_missing", "Generation submission failed")
            if type(exc) is ValueError and str(exc) == "save_to is not a folder":  # lane p13-prj item 1
                return _v4_named("save_to_not_folder", "Generation submission failed")
            raise
        store = _comfy_store()
        existing = _read_client_row(request.client_request_id)
        if existing is not None:
            identity_args = _v4_identity_args(request)
            request_json, request_hash = _v4_request_identity(
                request, project_id, identity_args
            )
            if getattr(existing, "row_contract", None) != 4:
                return _v4_named("request_id_conflict", None)
            if (
                existing.provider_id != request.provider_id
                or existing.target_id != request.target_id
                or existing.request_hash != request_hash
                or existing.project_id != project_id
            ):
                return _v4_named("request_id_conflict", None)
            _private_ops().validate_exact_retry(
                existing,
                destination=directory,
                requested_basename=basename,
            )
            if existing.provider_job_id is not None or existing.is_terminal:
                return _receipt_from_job(existing)
            # An accepted request without a durable provider id is never
            # submitted again.  Comfy may only attempt marker correlation.
            if request.provider_id == "comfyui-local":
                client = _comfy_client_module.ComfyUIClient()
                recovered = await _comfy_provider_module.comfy_recover_submit_v4(
                    client=client, client_request_id=request.client_request_id
                )
                if _v4_outcome_kind(recovered) == "accepted" and getattr(recovered, "provider_job_id", None):
                    # w47-u1 item 1a: one conditional bind; a row given up meanwhile has this copy stopped on the engine.
                    row = await _v4_bind_or_stop(existing, project_id, recovered.provider_job_id, client)
                    return _receipt_from_job(row)
                return _receipt_from_job(existing)
            row = _v4_finish_without_job(existing, project_id, "submission_unknown")
            return _receipt_from_job(row)

        h3_prepared: dict[str, Any] | None = None
        if request.provider_id == "flux3-managed":
            (
                identity_args,
                operational_args,
                media_boundary,
                pinned_media,
            ) = _v4_prepare_managed_media(request)
        elif _h3_is_conditioning(request):
            try:
                h3_prepared = await _h3_prepare_fresh(request)
            except _h3k_module.H3ControlError as exc:
                import logging
                logging.getLogger(__name__).debug("H3 control refusal: %s", exc.diagnostic.get("detail"))
                return {"error": exc.diagnostic["message"], "reason_code": exc.reason_code if exc.reason_code in generation.contract.REASON_CODES else "invalid_request"}
            identity_args = h3_prepared["identity"]
            operational_args = dict(request.args)
        elif _h3x_is_continuation(request):
            try:
                h3_prepared = await _h3x_prepare_fresh(request)
            except _h3x_module.H3ContinuationError as exc:
                # lane p10-vid (VID-116): a refused OUT names its bound (path-free, built from frame numbers), before
                # the ledger: no job row, nothing staged, nothing sent.
                if exc.reason_code != "source_frame_out_of_range":
                    raise
                return {"error": f"Generation submission failed: {exc}", "reason_code": exc.reason_code}
            identity_args = h3_prepared["identity"]
            operational_args = dict(request.args)
        elif _h3f_is_finish(request):
            h3_prepared = await _h3f_prepare_fresh(request)
            identity_args = h3_prepared["identity"]
            operational_args = dict(request.args)
        elif _vsr_is_upscale(request):  # lane w23-vsr: source, settings and the memory guard before the ledger
            try:
                h3_prepared = await _vsr_prepare_fresh(request)
            except _vsr_module.VideoUpscaleError as exc:
                return {"error": f"Generation submission failed: {exc}", "reason_code": exc.reason_code}
            identity_args = h3_prepared["identity"]
            operational_args = dict(request.args)
        else:
            identity_args = _v4_validate_media(request)
            operational_args = dict(request.args)
        request_json, request_hash = _v4_request_identity(
            request, project_id, identity_args
        )

        studio_job_id = _vq_reserved_for(request.client_request_id) or ("studio:" + uuid.uuid4().hex)  # w46-a: a line take keeps its id
        ops = _private_ops()
        prepared = ops.prepare(
            studio_job_id=studio_job_id,
            client_request_id=request.client_request_id,
            provider_id=request.provider_id,
            target_id=request.target_id,
            project_id=project_id,
            destination=directory,
            requested_basename=basename,
            request_hash=request_hash,
        )
        ledgered = False
        try:
            # w47-s1 invariant 2: a line take's ledger row is written only while its claim holds (video_line_order_1).
            row = _vq_fenced_insert(request.client_request_id, lambda: store.create_or_get_v4(
                studio_job_id=studio_job_id,
                client_request_id=request.client_request_id,
                provider_id=request.provider_id,
                target_id=request.target_id,
                project_id=project_id,
                request_json=request_json,
                request_hash=request_hash,
                destination_identity=prepared.destination_identity,
                requested_basename=basename,
            ))
            operation = ops.mark_ledgered(prepared, row)
            ledgered = True
            ops.mark_submit_started(operation)
        except _VQFenced as fence:
            ops.abort_prepared(prepared)
            if fence.busy:  # the line store was busy: nothing written or sent; the starter gives the take back
                return _vq_busy_answer()
            return {"fenced": True, "details": None, "reason_code": None}  # nothing written, nothing sent
        except BaseException:
            if not ledgered:
                ops.abort_prepared(prepared)
            raise

        if request.provider_id == "comfyui-local":
            profile, graph = _comfy_assets(request.target_id)
            manifest = profile.manifest if hasattr(profile, "manifest") else profile
            if manifest.get("id") != request.target_id:
                return _v4_failed_receipt(row, project_id, "invalid_request", operation,
                                          f"The workflow loaded for {request.target_id} is {manifest.get('id')}")
            client = _comfy_client_module.ComfyUIClient()
            health = await _comfy_static_health(client=client, manifest=manifest, graph=graph)
            if health.provider_id != request.provider_id or health.target_id != request.target_id:
                return _v4_failed_receipt(row, project_id, "invalid_request", operation,
                                          f"The engine check answered for {health.target_id}, not {request.target_id}")
            if health.state != "ready_static":
                if health.state == "unverified_runtime":
                    # w45-s7 item 2: the same facts and sentence as /generation/health (comfy_catalog_1.py), from one
                    # GET /system_stats on this refusal only; an engine that does not answer keeps the plain reason.
                    try:
                        facts, sentence = _comfy_provider_module.runtime_policy.unverified_facts(manifest, await client.system_stats())
                    except Exception:  # noqa: BLE001 - the refusal stands without its detail
                        facts = sentence = None
                    if sentence:
                        refused = _v4_failed_receipt(row, project_id, "unverified_runtime", operation, sentence)
                        refused.update(reason_text=sentence, runtime_facts=facts)
                        return refused
                return _v4_failed_receipt(row, project_id, health.reason_code or "unverified_runtime", operation,
                                          _v4_health_sentence(health))
            _h3_note_runtime(row, health)
            compiled_graph = None
            if h3_prepared is not None:
                continuation = _h3x_is_continuation(request)
                finish = _h3f_is_finish(request)
                upscale = _vsr_is_upscale(request)
                try:
                    if upscale:
                        compiled = await _vsr_upload_and_compile(manifest, graph, h3_prepared)
                    elif continuation:
                        compiled = await _h3x_stage_and_compile(manifest, graph, row.studio_job_id, h3_prepared)
                    elif finish:
                        compiled = await _h3f_stage_and_compile(manifest, graph, row.studio_job_id, h3_prepared)
                    else:
                        compiled = await _h3_upload_and_compile(manifest, graph, request, h3_prepared)
                except (_h3m_module.H3MediaError, _h3c_module.H3ConditioningError) as exc:
                    _job_cause_note(row.studio_job_id, str(exc))  # lane w11-backend M-35: the failed job keeps why
                    return _v4_failed_receipt(row, project_id, "invalid_request", operation, str(exc))
                except (_h3x_module.H3ContinuationError, _h3f_module.H3FinishError, _vsr_module.VideoUpscaleError) as exc:
                    _job_cause_note(row.studio_job_id, str(exc))
                    reason = exc.reason_code if exc.reason_code in generation.contract.REASON_CODES else "invalid_request"
                    return _receipt_from_job(_v4_finish_receipt_failure(row, project_id, reason, operation))
                except Exception:  # noqa: BLE001 - the temp upload did not reach ComfyUI
                    return _v4_failed_receipt(row, project_id, "unreachable", operation, _v4_upload_sentence())
                compiled_graph = compiled["graph"]
                facts_update = {
                    "effective_frames": compiled["effective_frames"],
                    "canvas": compiled["canvas"],
                    "media": compiled["media"],
                    "prompt_sent": compiled.get("prompt_sent", request.args.get("prompt")),
                }
                if upscale:
                    facts_update.update(upscale=compiled["upscale"])
                elif not (finish or continuation):
                    facts_update.update(_h3k_take_facts(request, h3_prepared.get("plan")))
                if finish:
                    facts_update.update(finish=compiled["finish"], staged=compiled["staged"])
                if continuation:
                    facts_update.update(continuation=compiled["continuation"], staged=compiled["staged"],
                                        **({"source_motion_activity": h3_prepared["source_motion"]}
                                           if h3_prepared.get("source_motion") is not None else {}))
                _h3m_module.merge_take_facts(_h3_facts_root(), row.studio_job_id, facts_update)
            # w47-t1 item 1 (cr50 H7): send and give-up are exclusive on the ledger row. One compare-and-set moves it
            # submitting -> sending (queued, no prompt id yet); a row a cancel or the lost-submit rule already ended
            # is not sent: its private operation is released and its own state answers.
            sending, current = _v4_cas_unsent(row, project_id, "sending")
            if not sending:
                return _receipt_from_job(current)
            row = current
            outcome = await _comfy_provider_module.comfy_submit_v4(
                client=client,
                manifest=manifest,
                graph=graph,
                args=dict(request.args),
                studio_job_id=row.studio_job_id,
                client_request_id=request.client_request_id,
                workflow_hash=manifest["workflow"]["api_sha256"],
                **({"compiled_graph": compiled_graph} if compiled_graph is not None else {}),
            )
        else:
            mode = request.mode or request.target_id.replace("-", "_")
            try:
                prepared_args = await _v4_upload_pinned_managed_media(
                    request, operational_args, media_boundary, pinned_media
                )
                problem = flux3_provider.validate(mode, prepared_args)
                if problem:
                    return _v4_failed_receipt(row, project_id, "invalid_request", operation, str(problem))
                outcome = await flux3_provider.submit_managed(
                    mode=mode,
                    args=prepared_args,
                    client_request_id=request.client_request_id,
                )
            finally:
                if media_boundary is not None:
                    for _field, _index, lease in pinned_media:
                        try:
                            media_boundary.abort_pinned_media(lease)
                        except BaseException:
                            pass

        if _v4_outcome_kind(outcome) == "accepted" and getattr(outcome, "provider_job_id", None):
            if request.provider_id == "comfyui-local":
                # w47-u1 item 1a (cr51 H11): the prompt id is bound by ONE conditional move (only a row still sending);
                # a row given up or cancelled while this sender was held has its late prompt cancelled here, at once.
                row = await _v4_uncancellable(_v4_bind_or_stop(row, project_id, outcome.provider_job_id, client))
                if row.provider_job_id != outcome.provider_job_id:
                    return _receipt_from_job(row)
            else:
                row = store.bind_provider_job(
                    studio_job_id=row.studio_job_id,
                    provider_job_id=outcome.provider_job_id,
                    expected_project_id=project_id,
                )
            ops.mark_submit_result(operation, row)
            return _receipt_from_job(row)
        if request.provider_id == "comfyui-local" and _v4_outcome_kind(outcome) == "transport_error":
            return _receipt_from_job(row)
        if request.provider_id == "comfyui-local":
            # w47-u1 item 1b: a row past its CAS (sending) ends only through its tombstone: an answer that could not be
            # read may still hide an accepted prompt, which a later look by marker stops.
            refused = _v4_outcome_kind(outcome) == "refused"
            reason = _v4_status_reason(outcome, "provider_refused" if refused else "submission_unknown")
            return _receipt_from_job(_v4_give_up_sending(row, reason, None, tomb=not refused))
        reason = _v4_status_reason(
            outcome,
            "provider_refused" if _v4_outcome_kind(outcome) == "refused" else "submission_unknown",
        )
        row = _v4_finish_receipt_failure(row, project_id, reason, operation)
        return _receipt_from_job(row)
    except BaseException as exc:
        if media_boundary is not None:
            for _field, _index, lease in pinned_media:
                try:
                    media_boundary.abort_pinned_media(lease)
                except BaseException:
                    pass
        if isinstance(exc, asyncio.CancelledError):
            raise
        return _v4_exception(exc, prefix="Generation submission failed")


def _v4_finish_receipt_failure(row: Any, project_id: str | None, reason: str, operation: Any) -> Any:
    updated = _comfy_store().finish_submit_without_job(
        studio_job_id=row.studio_job_id,
        expected_project_id=project_id,
        terminal_status="failed",
        reason_code=reason,
    )
    try:
        _private_ops().release_terminal_without_output(operation, "failed")
    except (PrivateOperationError, OSError, ValueError):
        pass
    return updated


async def _stream_managed_v4(
    url: str,
    sink: Any,
    *,
    client_factory: Any | None = None,
) -> Any:
    """Bounded, no-auth sample download used only by Contract 4."""
    parsed = urlparse(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme.lower() != "https" or not parsed.hostname:
        sink.request_abort()
        sink.worker_finished()
        sink.abort_owned()
        raise ValueError("generation sample URL must use HTTPS")
    factory = client_factory or create_ssrf_safe_async_client

    async def stream() -> Any:
        digest = hashlib.sha256()
        total = 0
        async with factory(
            timeout=60,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            async with client.stream("GET", url) as response:
                status_code = getattr(response, "status_code", None)
                if isinstance(status_code, int) and status_code >= 400:
                    raise ValueError("managed sample download failed")
                headers = getattr(response, "headers", {})
                declared = headers.get("Content-Length") if hasattr(headers, "get") else None
                if declared is None:
                    expected = None
                elif not isinstance(declared, str) or not declared.isdigit():
                    raise ValueError("generation output length is invalid")
                else:
                    expected = int(declared)
                if expected is not None and (expected < 65536 or expected > 1 << 30):
                    raise ValueError("generation output is outside the size bound")
                async for chunk in response.aiter_bytes(1024 * 1024):
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise ValueError("managed sample download returned invalid bytes")
                    chunk = bytes(chunk)
                    if total + len(chunk) > 1 << 30 or (
                        expected is not None and total + len(chunk) > expected
                    ):
                        raise ValueError("generation output exceeds the size bound")
                    sink.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
                if expected is not None and total != expected:
                    raise ValueError("generation output is truncated")
                if total < 65536:
                    raise ValueError("generation output is too small")
                sink.flush_and_close()
        return _private_operations_module.DownloadDigest(digest.hexdigest(), total)

    def blocking() -> Any:
        try:
            return asyncio.run(stream())
        except (ValueError, TypeError):
            raise
        except Exception as exc:
            raise ValueError("managed sample download failed") from exc

    worker = asyncio.create_task(asyncio.to_thread(blocking))
    try:
        result = await asyncio.shield(worker)
    except asyncio.CancelledError:
        sink.request_abort()
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            worker.result()
        except BaseException:
            pass
        sink.worker_finished()
        sink.abort_owned()
        raise
    except BaseException:
        sink.request_abort()
        sink.worker_finished()
        sink.abort_owned()
        raise
    sink.worker_finished()
    return result


# Lane p13-prjc finding 1: a write at a pending re-base's old place is its own named refusal on every V4 route
# (/submit, the GMI submit, finish); the text names the offline folder. Wrapped append-only like the other route units.
_v4_exception_before_rebase = _v4_exception


def _v4_exception(exc: BaseException, *, prefix: str | None = None) -> dict[str, Any]:  # noqa: F811
    if getattr(exc, "reason_code", None) == "project_rebase_pending" and isinstance(exc, (studio_core.ProjectError, _RebasePending)):
        return _v4_named("project_rebase_pending", prefix, str(exc))
    return _v4_exception_before_rebase(exc, prefix=prefix)


# Lane w33-rel2 item 2 (VID-169): the client_request_ids whose /submit is still running in this process. /poll never
# looks up or settles such a row (its submit still owns it); a row whose submit is gone is settled by /poll.
_V4_SUBMITS_IN_FLIGHT: set[str] = set()
_v4_submit_route_before_flight = _v4_submit_route


async def _v4_submit_route(request: SubmitRequest) -> dict[str, Any]:  # noqa: F811
    crid = getattr(request, "client_request_id", None)
    owned = isinstance(crid, str) and crid not in _V4_SUBMITS_IN_FLIGHT
    if owned:
        _V4_SUBMITS_IN_FLIGHT.add(crid)
    try:
        if getattr(request, "provider_id", None) != "comfyui-local":
            return await _v4_submit_route_before_flight(request)
        # w47-t1 item 1 (cr50 H7): a local submit runs from its ledger insert to its POST under a hard bound, far
        # below the lost-submit limit; past it the row is given up by the same compare-and-set as every give-up.
        try:
            return await asyncio.wait_for(_v4_submit_route_before_flight(request), float(V4_LOCAL_SUBMIT_TIMEOUT_SECONDS))
        except asyncio.TimeoutError:
            return _v4_submit_timed_out(request)
    finally:
        if owned:
            _V4_SUBMITS_IN_FLIGHT.discard(crid)


V4_LOCAL_SUBMIT_TIMEOUT_SECONDS = 120.0
V4_SUBMIT_TIMEOUT_CAUSE = "ComfyUI did not take the take within two minutes, so it was not sent."
V4_SUBMIT_UNREAD_CAUSE = ("The submit gave no answer within two minutes, and Hermes could not read whether ComfyUI took it."
                          " Poll the take or retry with the same request id; it is never sent twice.")


def _v4_cas_unsent(row: Any, project_id: str | None, to: str, reason: str | None = None) -> tuple[bool, Any]:
    """w47-t1 item 1: the ledger's compare-and-set of a submit not yet handed to ComfyUI (job_store.cas_unsent_v4);
    a give-up that won releases the row's private operation."""
    moved, current = _comfy_store().cas_unsent_v4(studio_job_id=row.studio_job_id, expected_project_id=project_id,
                                                  to=to, reason_code=reason)
    if current.is_terminal:  # ended (by this give-up or an earlier one): its private operation is released
        try:
            _private_ops().release_terminal_without_output(_private_ops().load_for_job(current), current.state)
        except Exception:  # noqa: BLE001 - the ledger row decides; a private record left behind names an ended row
            pass
    return moved, current


async def _v4_uncancellable(awaitable: Any) -> Any:
    """w47-u1: run ``awaitable`` to its end even when the request is cancelled meanwhile (the cancellation is raised
    after it). Used where a step must not be separated from its effect: the bind-or-stop after a POST."""
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.done():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError()
    return result


def _v4_give_up_sending(row: Any, reason: str, cause: str | None, to: str = "failed", tomb: bool = True) -> Any:
    """w47-u1 item 1b (cr51 H11): the one way a sending row (handed to ComfyUI, no prompt id) ends: its durable
    tombstone (marker, job id, time) is written FIRST, then one conditional ledger move ends it only while it is still
    sending. No tombstone (a busy store): nothing ends. Best effort (w47-v1): Hermes tries to stop a late copy of the
    take on the engine by the tombstone pass (video_line_engine_1) or by its own sender (_v4_bind_or_stop); a copy that
    already finished cannot be undone. Answers the row as it is now."""
    try:
        if tomb:  # tomb=False only for ComfyUI's own refusal of this POST (nothing was accepted: nothing to look for)
            _vq_tomb_write(row.client_request_id, row.studio_job_id)
    except Exception:  # noqa: BLE001 - without its tombstone the row is not ended; the next pass tries again
        return row
    moved, current = _comfy_store().give_up_sending_v4(studio_job_id=row.studio_job_id, expected_project_id=row.project_id,
                                                       to=to, reason_code=reason)
    if moved:
        try:
            _private_ops().release_terminal_without_output(_private_ops().load_for_job(current), current.state)
        except Exception:  # noqa: BLE001 - the ledger row decides
            pass
        if cause:
            _job_cause_note(row.studio_job_id, cause)
    elif current.provider_job_id is not None:
        _vq_tomb_drop(row.client_request_id)  # it was bound meanwhile: its own prompt, nothing to look for
    return current


def _v4_submit_timed_out(request: SubmitRequest) -> dict[str, Any]:
    """The bound passed: a row still submitting ends failed (never sent); a row already sending is the lost-submit
    rule's (its prompt is looked up by its marker); no row: nothing was written or sent. w47-v1 (cr61 H14): a ledger
    that cannot be read is not "no row": the answer says the outcome is not known and claims nothing was sent."""
    try:
        row = _read_client_row(request.client_request_id)
    except Exception:  # noqa: BLE001 - unreadable is not missing: nothing is decided or claimed
        return {"error": f"Generation submission failed: {V4_SUBMIT_UNREAD_CAUSE}", "reason_code": "unreachable",
                "reason_text": V4_SUBMIT_UNREAD_CAUSE, "details": None}
    if row is None:
        return {"error": f"Generation submission failed: {V4_SUBMIT_TIMEOUT_CAUSE}", "reason_code": "unreachable",
                "reason_text": V4_SUBMIT_TIMEOUT_CAUSE, "details": None}
    moved, current = _v4_cas_unsent(row, row.project_id, "failed", "unreachable")
    if moved:
        _job_cause_note(row.studio_job_id, V4_SUBMIT_TIMEOUT_CAUSE)
        return {**_receipt_from_job(current), "reason_text": V4_SUBMIT_TIMEOUT_CAUSE}
    return _receipt_from_job(current)


# Lane w35-ui-3 (critic run 3 #19): a refused path names itself and its side. A Frames take whose keyframe lay outside the
# project's folders said "The output folder is not an approved media folder": the input check (h3_media.resolve_media,
# PathBoundary.validate_input) raises the output folder's literal "path is outside approved roots". The input now carries
# refused_side/refused_path/refused_key (h3_media.py) and the output folder check its path (_v4_destination below); the
# answer names the input ("Keyframe 1 “still.png” is not inside an approved media folder", path_refused) or the output
# folder ("The output folder “takes” is not an approved media folder"), with refused_side and refused_path as fields and
# the full path in the error (Details / Copy error); reason_text, the line the page shows, carries the name only.
_REFUSED_INPUT_ROLES = MappingProxyType({"keyframes": "Keyframe", "reference_images": "Reference picture", "reference_videos": "Reference video",
                                         "control_video": "Motion guide", "reference_audios": "Reference sound", "sound_track": "Sound track",
                                         "source": "Source take", "target": "Fill-gap take"})
_v4_destination_before_refused_path = _v4_destination


def _v4_destination(request: SubmitRequest) -> tuple[Path, str, str | None]:  # noqa: F811
    try:
        return _v4_destination_before_refused_path(request)
    except studio_core.ProjectError as exc:
        save_to = getattr(request, "save_to", None)
        if str(exc) == "path is outside approved roots" and isinstance(save_to, str) and save_to:
            exc.refused_side, exc.refused_path = "output", save_to
        raise


def _refused_input_words(key: str) -> str:
    role, _sep, index = key.partition("/")
    word = _REFUSED_INPUT_ROLES.get(role, "A chosen file")
    return f"{word} {int(index) + 1}" if index.isdigit() and role in ("keyframes", "reference_images", "reference_videos", "reference_audios") else word


_v4_exception_before_refused_path = _v4_exception


def _v4_exception(exc: BaseException, *, prefix: str | None = None) -> dict[str, Any]:  # noqa: F811
    side, path = getattr(exc, "refused_side", None), getattr(exc, "refused_path", None)
    if side not in ("input", "output") or not isinstance(path, str) or not path or not isinstance(exc, ValueError):
        return _v4_exception_before_refused_path(exc, prefix=prefix)
    name = Path(path).name or path
    if side == "output":
        code, sentence = "output_folder_not_approved", f"The output folder \u201c{name}\u201d is not an approved media folder"
    else:
        words = _refused_input_words(str(getattr(exc, "refused_key", "") or ""))
        literal = str(exc)
        why = ("is not inside an approved media folder" if "outside approved roots" in literal
               else _V4_PROJECT_MESSAGES.get(literal, "cannot be used").replace("A chosen folder or file ", "").replace("A chosen path ", "").replace("A chosen medium ", ""))
        code, sentence = "path_refused", f"{words} \u201c{name}\u201d {why}"
    full = f"{sentence} ({side}: {path})"
    return {"error": f"{prefix}: {full}" if prefix else full, "reason_code": code, "reason_text": sentence,
            "refused_side": side, "refused_path": path}


# Lane w45-s4 item 1 (release run finding 1): every failed /submit return is the receipt of its failed row with the
# cause as reason_text (the page's line, the Jobs cause, Hermes' data). Five returns handed back the raw JobRecord;
# /submit then answered HTTP 500 and Hermes read agent_backend_unavailable.
def _v4_failed_receipt(row: Any, project_id: str | None, reason: str, operation: Any, text: str | None) -> dict[str, Any]:
    receipt = _receipt_from_job(_v4_finish_receipt_failure(row, project_id, reason, operation))
    cause = _job_cause_text(text) if text else None
    if cause:
        _job_cause_note(row.studio_job_id, cause)
    if not receipt.get("reason_text"):
        receipt["reason_text"] = cause or generation.contract.public_reason(reason)
    return receipt


def _v4_health_sentence(health: Any) -> str:
    """The engine check's answer as one fact: its reason and the node class/input it names."""
    text = generation.contract.public_reason(getattr(health, "reason_code", None) or "unverified_runtime")
    detail = getattr(health, "reason_detail", None)
    return f"{text}: {detail}" if detail else text


def _v4_upload_sentence() -> str:
    try:
        address = _comfy_endpoint_module.comfy_label()
    except Exception:  # noqa: BLE001 - an invalid address setting: the address stays unnamed
        address = None
    return f"The input upload to ComfyUI at {address} did not complete" if address else "The input upload to ComfyUI did not complete"
