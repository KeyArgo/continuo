from __future__ import annotations

# --- w47-t1 item 3 (cr50 H9): the line's starter can never block its own recovery ------------------------------------
# Loaded after video_line_order_1.py (same namespace); the starter moved here from video_line_1.py (the 800-line cap).
# - Every await of a step that can hang (the claimed preparation, the submit) runs under asyncio.wait_for
#   (_VQ_STEP_SECONDS, below the claim deadline), and the whole step runs on a helper thread the starter waits for at
#   most _VQ_STEP_HARD_SECONDS, so a hang in synchronous code is bounded too. On a timeout the starter gives its claim up
#   (it is no longer a live claim of this process), runs recovery, which fences it (ledgered -> started, otherwise back
#   at its place or removed with its cancel settled), and goes on. The hung call's late writes carry the old claim
#   generation and miss.
# - The starter beats (_VQ_FLAG["beat"]) at every turn. A wake that finds it active but silent for longer than the
#   deadline starts a replacement (take_owners_1._take_wake stale=); the old one leaves at its next look (epoch).
# - Recovery also runs from the request side (every poll, cancel and Jobs list through _vq_wake_if_waiting): no engine
#   call, under the line's own timed lock; so a stuck starter is never the only actor.
_VQ_STEP_SECONDS = 240.0  # one await of a step (the local submit bounds itself at 120 s)
_VQ_STEP_HARD_SECONDS = 270.0  # the whole step, synchronous code included (below the 300 s claim deadline)
_VQ_STEP_BOX: contextvars.ContextVar = contextvars.ContextVar("film_suite_video_line_step", default=None)


def _vq_worker_stale() -> bool:
    """Called under _VQ_LOCK: the active starter has not beaten for longer than the claim deadline (it hangs)."""
    beat = _VQ_FLAG.get("beat")
    return isinstance(beat, (int, float)) and time.time() - float(beat) > float(_VQ_STARTING_DEADLINE_SECONDS)


def _vq_give_up(box: Mapping[str, Any]) -> None:
    """A step of this starter timed out: its claim is no longer this process's live claim, and recovery decides it.
    Its ledger row, if one was written and not yet handed to ComfyUI, is ended by the same compare-and-set every
    give-up uses (w47-t1 item 1): it can never be sent afterwards."""
    _vq_abandon(box)
    try:
        line_row = _vq_get(box["job_id"]) if box.get("job_id") else None
        record = _read_client_row(line_row["client_request_id"]) if line_row else None
        if record is not None and record.state == "submitting" and not record.provider_job_id:
            moved, _current = _v4_cas_unsent(record, record.project_id, "failed", "unreachable")
            if moved:
                _job_cause_note(record.studio_job_id, V4_SUBMIT_TIMEOUT_CAUSE)
    except Exception:  # noqa: BLE001 - the lost-submit rule ends it later
        pass
    try:
        _vq_recover()
    except Exception:  # noqa: BLE001 - the next step or any request recovers again
        pass


def _vq_abandon(box: dict[str, Any]) -> None:
    """The step's claim is no longer this process's live claim. Marked first, so the hung step's own cleanup later
    leaves a newer claim of the same take (by a replacement) in _vq_claims_here."""
    box["abandoned"] = True
    here = _vq_claims_here()
    for key in ("job_id", "generation"):
        if box.get(key):
            here.discard(box[key])


def _vq_loop_run(coroutine: Any) -> Any:
    """Run one step on its own loop; helper threads a timed-out await left blocked are never waited for."""
    import concurrent.futures
    loop = asyncio.new_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="fs-video-line-io")
    loop.set_default_executor(executor)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        try:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.wait(pending, timeout=1.0))
        except Exception:  # noqa: BLE001
            pass
        executor.shutdown(wait=False, cancel_futures=True)
        loop.close()


def _vq_run_step() -> bool:
    box: dict[str, Any] = {}

    def run() -> None:
        _VQ_STEP_BOX.set(box)  # what this step claimed, for the starter to give up when it hangs
        try:
            box["more"] = _vq_loop_run(_vq_step())
        except BaseException as exc:  # noqa: BLE001 - handed back to the starter
            box["error"] = exc
    helper = threading.Thread(target=run, name="fs-video-line-step", daemon=True)
    helper.start()
    deadline = time.monotonic() + float(_VQ_STEP_HARD_SECONDS)
    look = time.monotonic() + 1.0
    while helper.is_alive() and time.monotonic() < deadline:
        helper.join(0.05)
        if helper.is_alive() and time.monotonic() >= look:
            look = time.monotonic() + 1.0
            if _vq_claim_fenced(box):  # recovery (any request, any process) fenced this step's claim: go on now
                _vq_abandon(box)
                return True
    if helper.is_alive():  # hung in code no await can bound: the claim is given up; the helper's writes miss
        _vq_give_up(box)
        return True
    if isinstance(box.get("error"), Exception):
        raise box["error"]
    return bool(box.get("more"))


def _vq_claim_fenced(box: Mapping[str, Any]) -> bool:
    """The step's claim was taken back by recovery (put back at its place or removed): its generation is gone."""
    job_id, mine = box.get("job_id"), box.get("generation")
    if not job_id or not mine:
        return False
    try:
        row = _vq_get(job_id)
    except Exception:  # noqa: BLE001 - unreadable: keep waiting within the bound
        return False
    return row is not None and row["state"] in ("waiting", "removed") and row.get("claim_generation") != mine


def _vq_worker() -> None:
    me = getattr(threading.current_thread(), "take_epoch", None)

    def mine() -> bool:  # a replacement started: this starter leaves without touching the flag
        return me is None or _VQ_FLAG.get("epoch") == me
    try:
        while True:
            with _VQ_LOCK:
                if not mine():
                    return
                generation_seen = _VQ_FLAG.get("generation", 0)
                _VQ_FLAG["beat"] = time.time()
            if _VQ_FLAG["halt"] or globals().get("_comfy_job_store") is None:
                more = False
            else:
                try:
                    more = _vq_run_step()
                except Exception:  # noqa: BLE001 - one bad step never ends the line; it is tried again
                    more = True
            with _VQ_LOCK:
                if not mine():
                    return
                _VQ_FLAG["beat"] = time.time()
                if (not more and not _VQ_FLAG["halt"] and globals().get("_comfy_job_store") is not None
                        and _VQ_FLAG.get("generation", 0) != generation_seen):
                    continue
                if not more or _VQ_FLAG["halt"]:
                    _VQ_FLAG["active"] = False
                    return
            deadline = time.monotonic() + float(_VQ_POLL_SECONDS)
            while time.monotonic() < deadline and not _VQ_FLAG["halt"] and mine():
                time.sleep(min(0.05, float(_VQ_POLL_SECONDS)))
    except BaseException:
        with _VQ_LOCK:
            if mine():
                _VQ_FLAG["active"] = False
        raise


async def _vq_bounded(awaitable: Any) -> Any:
    return await asyncio.wait_for(awaitable, float(_VQ_STEP_SECONDS))


async def _vq_step() -> bool:
    """One step of the starter; answers whether there is more to do."""
    box = _VQ_STEP_BOX.get()
    box = {} if box is None else box
    await asyncio.to_thread(_vq_recover)
    try:  # w47-u1 item 1b: a late copy of a given-up take is looked up on the engine (best effort: Hermes tries to stop it)
        await _vq_tomb_pass()
    except Exception:  # noqa: BLE001 - the next pass looks again
        pass
    active = await asyncio.to_thread(_comfy_store().active_rows, VIDEO_LINE_CONNECTION)
    waiting = await asyncio.to_thread(_vq_count)
    if active:
        ours = [row for row in active if (await asyncio.to_thread(_vq_get, row.studio_job_id)) is not None]
        if not waiting and not ours:
            return False  # nothing of the line: the page or Hermes follows its own take
        for row in active:
            try:
                await poll(PollRequest(id=row.studio_job_id, expected_project_id=row.project_id))
            except Exception:  # noqa: BLE001 - the next step polls again
                pass
        return True
    if not waiting:
        return bool(await asyncio.to_thread(_vq_unsettled_any))  # a cancel still to settle keeps it going
    here = _vq_claims_here()
    generation = uuid.uuid4().hex
    box["generation"] = generation
    here.add(generation)  # w47-r1 item 2: known as this process's own before the claim is written (no recovery gap)
    try:
        claimed = await asyncio.to_thread(_vq_claim, _vq_owner_token(), VIDEO_LINE_CONNECTION, generation)
    except BaseException:
        here.discard(generation)
        raise
    if claimed is None:
        here.discard(generation)
        return bool(await asyncio.to_thread(_vq_count))
    job_id = claimed["studio_job_id"]
    box["job_id"] = job_id
    here.add(job_id)
    caller = _FILM_CALLER.set(claimed["by"] if claimed["by"] in ("artist", "hermes") else "artist")
    reserved = _VQ_RESERVED.set((claimed["client_request_id"], job_id, claimed))
    try:
        try:
            request = SubmitRequest.model_validate(json.loads(claimed["request_json"]))
        except Exception:  # noqa: BLE001 - a stored request that no longer reads ends this take only
            await asyncio.to_thread(_vq_finish, job_id, "failed", "invalid_request", generation.contract.public_reason("invalid_request"), claimed)
            return True
        try:
            if not claimed.get("prepared", 1):  # w47-s1 invariant 4: its preparer was fenced; prepared now, by the claimant
                request, refusal = await _vq_bounded(asyncio.to_thread(_vq_prepare_claimed, request, claimed))
                if refusal is not None:
                    return True
            if not await asyncio.to_thread(_vq_begin_submit, job_id, claimed):
                # w47-q1 item 1: cancelled before it was sent (it already left the line), or the claim was lost.
                await asyncio.to_thread(_vq_release, job_id, claimed)
                return True
            result = await _vq_bounded(_v4_submit_route(request))
        except asyncio.TimeoutError:  # w47-t1 item 3: hung; the claim is given up and recovery fences it
            await asyncio.to_thread(_vq_give_up, box)
            return True
        if isinstance(result, dict) and result.get("fenced"):
            return True  # w47-s1 invariant 2: this claim was fenced before its ledger row; nothing was sent
        reason_text = _submit_reason_text(result)
        if reason_text and isinstance(result, dict) and not result.get("reason_text"):
            result = {**result, "reason_text": reason_text}
        details = result.get("details") if isinstance(result, dict) else None
        if isinstance(details, Mapping) and details.get("id") == job_id:
            await asyncio.to_thread(_vq_finish, job_id, "started", None, None, claimed)
            _announce_shoot_job(result, submitted=True)
            # w47-q1 item 1: a cancel that came while the submit was on its way stops the take on the ledger now.
            await _vq_settle_cancel(job_id, claimed.get("project_id"))
        elif isinstance(result, dict) and result.get("reason_code") == "provider_busy" and details is None:
            await asyncio.to_thread(_vq_release, job_id, claimed)
        else:
            code = result.get("reason_code") if isinstance(result, dict) else None
            code = code if type(code) is str and code else "unknown"
            cause = (_job_cause_text((result or {}).get("reason_text")) or _job_cause_text((result or {}).get("error"))
                     or generation.contract.public_reason(code))
            await asyncio.to_thread(_vq_finish, job_id, "failed", code, cause, claimed)
            _announce_shoot_job({"details": {"id": job_id, "status": "failed", "project_id": claimed.get("project_id")}})
    finally:
        _VQ_RESERVED.reset(reserved)
        _FILM_CALLER.reset(caller)
        if not box.get("abandoned"):  # an abandoned step's keys were dropped already; a newer claim may hold them now
            here.discard(job_id)
            here.discard(generation)
    return True
