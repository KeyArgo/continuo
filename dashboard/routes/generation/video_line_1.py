from __future__ import annotations

import contextvars
import hashlib
import json
import threading

# --- One line for local video takes (lane w46-a, HER-094 / VID-172; study docs/studies/w39-queue-STUDY.md) -----------
# The ledger runs one comfyui-local job at a time (its one-active index). A take sent while one runs used to be refused
# provider_busy and thrown away. The line is a small private SQLite store BESIDE the ledger (the ledger itself is not
# changed): one row per admitted take with a reserved studio job id, its normalised request and its author. A take enters
# the ledger only when the engine is free, through the unchanged /submit path, started by one daemon thread per process.
# Rows: waiting -> starting (claimed by one process, owner token of generation/take_owner.py) -> started (its ledger row
# exists under the same id) | failed (refused at start, with code and cause) | removed (cancelled, proven never sent).
#
# w47-s1: the take line's five invariants and the one rule that enforces each (docs: IL/w47-s1-REPORT.md).
# 1. A cancel intent is durable until settled. cancel_requested 1 (pending) / 3 (settle under way) is unsettled; 2 is
#    settled. Rule: no statement ends, prunes or deletes a row while its cancel is unsettled, except the one that settles
#    it: the ledger job ended (_vq_settle_cancel) or the take is proven never sent (_VQ_NEVER_SENT_SQL sets 2 with 'removed').
# 2. "Never sent" is only proven. Rule: the ledger row of a line take is inserted only inside a line-store write
#    transaction that first checks the claim (owner + claim generation) and marks submit_started = 2 (_vq_fenced_insert).
#    Recovery decides a starting row in its own write transaction: ledgered (mark 2 or ledger row) -> started; else it
#    changes the claim generation (the fence) and puts the take back. After that transaction the old submit can never
#    insert, so "no ledger row" is a proof, for a dead owner and for a live one past the deadline alike.
# 3. One authority for order, fail closed. Rule: every admission is decided in the line store's write transaction; when
#    that transaction cannot be had the answer is "The take line is busy; try again" (_vq_busy_answer), never a direct submit.
# 4. Nothing live blocks the line forever. Rule: a waiting row being prepared and a starting row both carry claimed_at;
#    past _VQ_STARTING_DEADLINE_SECONDS recovery fences them (generation cleared); a fenced preparer's writes are
#    discarded, its row is plain waiting (prepared 0) and is prepared again by the claimant that starts it.
# 5. Comments, tool texts and the catalog disclosure promise only the four above.

VIDEO_LINE_MAX = 200  # waiting takes per engine connection (every one fits one continuo_jobs_list answer)
VIDEO_LINE_KEEP = 2_000  # ended rows kept for /poll and Jobs (oldest dropped)
VIDEO_LINE_CONNECTION = "comfyui-local"
_VQ_STATES = ("waiting", "starting", "started", "failed", "removed")
_VQ_BUSY_SECONDS = 10.0  # how long a line-store write waits for another writer before the decision is refused (busy)


class _VQTimedLock:
    """w47-t1 item 3 (cr50 H9): the in-process line mutex is taken with a bound (_VQ_BUSY_SECONDS). A thread hung while
    holding it never blocks the others: they get the same busy answer as a busy SQLite store (sqlite3.OperationalError)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire(self, timeout: float | None = None) -> bool:
        return self._lock.acquire(timeout=float(_VQ_BUSY_SECONDS if timeout is None else timeout))

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> "_VQTimedLock":
        if not self.acquire():
            raise sqlite3.OperationalError("the take line is busy")
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


_VQ_DB_LOCK = _VQTimedLock()
_VQ_UNSETTLED = "cancel_requested IN (1, 3)"
# w47-s1 invariants 1 and 2: the one statement that puts a take that is proven never sent back: at its place, or out of
# the line with its cancel settled (2) when one was asked. The fence: the claim (owner, generation) is cleared with it.
_VQ_NEVER_SENT_SQL = ("UPDATE video_line SET state = CASE WHEN cancel_requested IN (1, 3) THEN 'removed' ELSE 'waiting' END,"
                      " ended_at = CASE WHEN cancel_requested IN (1, 3) THEN ? ELSE ended_at END,"
                      " reason_code = CASE WHEN cancel_requested IN (1, 3) THEN 'cancelled' ELSE reason_code END,"
                      " cancel_requested = CASE WHEN cancel_requested IN (1, 3) THEN 2 ELSE cancel_requested END,"
                      " owner = NULL, claimed_at = NULL, claim_generation = NULL, submit_started = 0")


class _VideoLineFull(Exception):
    pass


class _VideoLineConflict(Exception):
    pass


def _vq_path() -> Path:
    # Resolve the default path without constructing the ledger: a read-only startup must not create it.
    store = globals().get("_comfy_job_store")
    if store is not None:
        return Path(store.path).parent / "video-line.sqlite3"
    module = _comfy_job_store_module
    return module.state_root(Path(module.get_hermes_home()) / "plugin-data") / "video-line.sqlite3"


def _vq_connect() -> sqlite3.Connection:
    path = _vq_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=float(_VQ_BUSY_SECONDS), isolation_level=None, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS video_line (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " studio_job_id TEXT NOT NULL UNIQUE, client_request_id TEXT NOT NULL UNIQUE, connection_id TEXT NOT NULL,"
        " project_id TEXT, by TEXT NOT NULL CHECK (by IN ('artist', 'hermes')), request_json TEXT NOT NULL,"
        " request_sha256 TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', target_id TEXT NOT NULL, requested_basename TEXT,"
        " state TEXT NOT NULL CHECK (state IN ('waiting', 'starting', 'started', 'failed', 'removed')),"
        " owner TEXT, claimed_at REAL, claim_generation TEXT, created_at REAL NOT NULL, ended_at REAL, reason_code TEXT, cause TEXT)"
    )
    # Upgrade stores made by earlier releases; two processes may attempt the upgrade together.
    if "claim_generation" not in {row[1] for row in connection.execute("PRAGMA table_info(video_line)")}:
        try:
            connection.execute("ALTER TABLE video_line ADD COLUMN claim_generation TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                connection.close()
                raise
    # w47-q1 item 1: a cancel that meets a take being started is kept in the row (cancel_requested); submit_started
    # marks the moment the starter crossed into the submit (read and written in one transaction with the intent).
    columns = {row[1] for row in connection.execute("PRAGMA table_info(video_line)")}
    # w47-r1 item 1 (cr48 H1): the ledger cancel of a started take is claimed by one process (settle_owner, settle_at),
    # so a settle whose process died is taken over by recovery and never lost.
    for name, kind in (("cancel_requested", "INTEGER NOT NULL DEFAULT 0"), ("submit_started", "INTEGER NOT NULL DEFAULT 0"),
                       ("settle_owner", "TEXT"), ("settle_at", "REAL"), ("settle_generation", "TEXT"),
                       # w47-s1 invariant 4: 0 = a waiting take whose request was not yet validated as it will start
                       # (its preparer was fenced); the claimant that starts it prepares it. Older rows were prepared.
                       ("prepared", "INTEGER NOT NULL DEFAULT 1")):
        if name not in columns:
            try:
                connection.execute(f"ALTER TABLE video_line ADD COLUMN {name} {kind}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    connection.close()
                    raise
    # w47-t1 item 2 (cr50 H8): the upgrade only adds columns. An unsettled cancel of any state is settled by recovery
    # against the ledger (video_line_settle_1._vq_reconcile_ended), never by the upgrade.
    # w47-q1 item 2 (#4): only one take per engine connection can be starting, whichever process writes. A store left
    # with two starting rows by an earlier release keeps working (its claims stay guarded) until recovery clears them.
    try:
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS video_line_one_starting ON video_line (connection_id)"
                           " WHERE state = 'starting'")
    except sqlite3.IntegrityError:
        pass
    return connection


def _vq_dict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _vq_with_positions(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Position 1 = the next take to start, over the whole connection (one engine for every project)."""
    order = [r[0] for r in connection.execute(
        "SELECT seq FROM video_line WHERE state IN ('waiting', 'starting') ORDER BY seq").fetchall()]
    places = {seq: index + 1 for index, seq in enumerate(order)}
    for row in rows:
        row["position"] = places.get(row["seq"])
    return rows


def _vq_admit(entry: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Admit one take (fails closed: it exists only once its row is written). Answers (row, replayed).

    The same client_request_id with the same request hash, target and project answers the stored row (replayed True);
    anything else under that id is a conflict. More than VIDEO_LINE_MAX waiting takes: _VideoLineFull, nothing added."""
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = _vq_dict(connection.execute(
                    "SELECT * FROM video_line WHERE client_request_id = ?", (entry["client_request_id"],)).fetchone())
                if existing is not None:
                    if (existing["request_sha256"] != entry["request_sha256"] or existing["target_id"] != entry["target_id"]
                            or existing["project_id"] != entry.get("project_id")):
                        raise _VideoLineConflict()
                    connection.execute("COMMIT")
                    return _vq_with_positions(connection, [existing])[0], True
                (waiting,) = connection.execute(
                    "SELECT COUNT(*) FROM video_line WHERE connection_id = ? AND state IN ('waiting', 'starting')",
                    (entry.get("connection_id") or VIDEO_LINE_CONNECTION,)).fetchone()
                if waiting >= VIDEO_LINE_MAX:
                    raise _VideoLineFull()
                connection.execute(
                    "INSERT INTO video_line (studio_job_id, client_request_id, connection_id, project_id, by, request_json,"
                    " request_sha256, label, target_id, requested_basename, state, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', ?)",
                    (entry["studio_job_id"], entry["client_request_id"], entry.get("connection_id") or VIDEO_LINE_CONNECTION,
                     entry.get("project_id"), entry["by"] if entry.get("by") in ("artist", "hermes") else "artist",
                     entry["request_json"], entry["request_sha256"], entry.get("label") or "", entry["target_id"],
                     entry.get("requested_basename"), float(entry.get("created_at") or time.time())))
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            row = _vq_dict(connection.execute(
                "SELECT * FROM video_line WHERE client_request_id = ?", (entry["client_request_id"],)).fetchone())
            return _vq_with_positions(connection, [row])[0], False
        finally:
            connection.close()


def _vq_read(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    if not _vq_path().is_file():
        return []
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            return _vq_with_positions(connection, [dict(r) for r in connection.execute(sql, params).fetchall()])
        finally:
            connection.close()


def _vq_get(studio_job_id: str) -> dict[str, Any] | None:
    rows = _vq_read("SELECT * FROM video_line WHERE studio_job_id = ?", (studio_job_id,))
    return rows[0] if rows else None


def _vq_get_by_request(client_request_id: str) -> dict[str, Any] | None:
    rows = _vq_read("SELECT * FROM video_line WHERE client_request_id = ?", (client_request_id,))
    return rows[0] if rows else None


def _vq_rows(project_id: str | None, states: tuple[str, ...]) -> list[dict[str, Any]]:
    """One scope's rows in the given states, in submit order, each with its position (None once it left the line)."""
    marks = ",".join("?" * len(states))
    return _vq_read(f"SELECT * FROM video_line WHERE project_id IS ? AND state IN ({marks}) ORDER BY seq", (project_id, *states))


def _vq_count(states: tuple[str, ...] = ("waiting", "starting")) -> int:
    return len(_vq_read(f"SELECT seq FROM video_line WHERE state IN ({','.join('?' * len(states))})", tuple(states)))


def _vq_prune(connection: sqlite3.Connection) -> None:
    """Retention: the oldest ended rows beyond VIDEO_LINE_KEEP go; a row whose cancel is unsettled is never one of them
    (w47-s1 invariant 1) and does not count against the bound."""
    connection.execute("DELETE FROM video_line WHERE seq IN (SELECT seq FROM video_line WHERE state IN ('started', 'failed',"
                       " 'removed') AND NOT " + _VQ_UNSETTLED + " ORDER BY seq DESC LIMIT -1 OFFSET ?)", (VIDEO_LINE_KEEP,))


def _vq_write(sql: str, params: tuple[Any, ...], *, prune: bool = False) -> int:
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                changed = connection.execute(sql, params).rowcount
                if prune and changed:
                    _vq_prune(connection)
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return changed
        finally:
            connection.close()


def _vq_remove(studio_job_id: str) -> bool:
    """A waiting take leaves the line and never runs (True); any other state is left as it is (False)."""
    return _vq_write("UPDATE video_line SET state = 'removed', ended_at = ?, reason_code = 'cancelled'"
                     " WHERE studio_job_id = ? AND state = 'waiting'", (time.time(), studio_job_id), prune=True) == 1


def _vq_cancel_intent(studio_job_id: str) -> bool:
    """One statement: a take that has not crossed into its submit (waiting, or starting before the starter's
    _vq_begin_submit) leaves the line for good, its cancel settled (2: proven never sent, the same transaction order as
    _vq_begin_submit); a take whose submit is on its way keeps the intent pending (1) until it is settled (invariant 1).
    False: the take was no longer in the line."""
    return _vq_write("UPDATE video_line SET cancel_requested = CASE WHEN submit_started = 0 OR state = 'waiting' THEN 2 ELSE 1 END,"
                     " state = CASE WHEN submit_started = 0 OR state = 'waiting' THEN 'removed' ELSE state END,"
                     " ended_at = CASE WHEN submit_started = 0 OR state = 'waiting' THEN ? ELSE ended_at END,"
                     " reason_code = CASE WHEN submit_started = 0 OR state = 'waiting' THEN 'cancelled' ELSE reason_code END"
                     " WHERE studio_job_id = ? AND state IN ('waiting', 'starting')",
                     (time.time(), studio_job_id), prune=True) == 1


def _vq_begin_submit(studio_job_id: str, claim: Mapping[str, Any]) -> bool:
    """The starter crosses into the submit only if its claim still holds and no cancel came first (one transaction
    with _vq_cancel_intent's: exactly one of the two wins)."""
    return _vq_write("UPDATE video_line SET submit_started = 1 WHERE studio_job_id = ? AND state = 'starting'"
                     " AND cancel_requested = 0 AND owner IS ? AND claim_generation IS ?",
                     (studio_job_id, claim.get("owner"), claim.get("claim_generation"))) == 1


def _vq_claim(owner: str, connection_id: str = VIDEO_LINE_CONNECTION, generation: str | None = None) -> dict[str, Any] | None:
    """The lowest waiting take becomes this owner's (state starting) in ONE guarded statement, and only while no take of
    the connection is starting (w47-q1 item 2): of two processes' starters exactly one wins; the other gets None and
    sends nothing. The take after it waits until the first left 'starting' (started, failed, removed or put back).
    w47-r1 item 2: a lowest take still being prepared by its sender (owner set while waiting) is not passed; the
    caller may name the claim generation beforehand so that it is known as its own before the row is written."""
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                generation = generation or uuid.uuid4().hex
                try:
                    row = connection.execute(
                        "UPDATE video_line SET state = 'starting', owner = ?, claimed_at = ?, claim_generation = ?,"
                        " submit_started = 0, cancel_requested = 0"
                        " WHERE seq = (SELECT seq FROM video_line WHERE connection_id = ? AND state = 'waiting'"
                        " ORDER BY seq LIMIT 1) AND owner IS NULL"
                        " AND NOT EXISTS (SELECT 1 FROM video_line WHERE connection_id = ? AND state = 'starting')"
                        " RETURNING *", (owner, time.time(), generation, connection_id, connection_id)).fetchall()
                    row = _vq_dict(row[0]) if row else None
                except sqlite3.IntegrityError:  # the store's own guard: another take is starting
                    row = None
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return row
        finally:
            connection.close()


def _vq_release(studio_job_id: str, claim: Mapping[str, Any] | None = None) -> bool:
    """Return a claim to its place only if it still belongs to this starter."""
    guard = " AND owner IS ? AND claim_generation IS ?" if claim is not None else ""
    params = (studio_job_id,) + ((claim.get("owner"), claim.get("claim_generation")) if claim is not None else ())
    # Only a take whose submit returned without a ledger row is released (submit_started < 2): it is proven never sent,
    # so a cancel that came meanwhile is settled here and the take never waits again (invariants 1 and 2).
    return _vq_write(_VQ_NEVER_SENT_SQL + " WHERE studio_job_id = ? AND state = 'starting' AND submit_started < 2" + guard,
                     (time.time(),) + params, prune=True) == 1


def _vq_finish(studio_job_id: str, state: str, reason_code: str | None = None, cause: str | None = None,
               claim: Mapping[str, Any] | None = None) -> bool:
    if state not in ("started", "failed"):
        raise ValueError("a line row ends started or failed")
    guard = " AND owner IS ? AND claim_generation IS ?" if claim is not None else ""
    params = (state, time.time(), reason_code, cause, studio_job_id) + (
        (claim.get("owner"), claim.get("claim_generation")) if claim is not None else ())
    # A take ends failed only while it has no ledger row (submit_started < 2): never sent, so an unsettled cancel is
    # settled with it. A started take keeps its intent for _vq_settle_cancel (invariant 1).
    settle = (", cancel_requested = CASE WHEN " + _VQ_UNSETTLED + " THEN 2 ELSE cancel_requested END"
              if state == "failed" else "")
    unsent = " AND submit_started < 2" if state == "failed" else ""
    changed = _vq_write("UPDATE video_line SET state = ?, ended_at = ?, reason_code = ?, cause = ?" + settle +
                        " WHERE studio_job_id = ? AND state IN ('waiting', 'starting')" + unsent + guard,
                        params, prune=True) == 1
    return changed


def _vq_owner_token() -> str:
    return _take_owner_module().process_token()


def _vq_claims_here() -> set:
    """The takes this process is starting right now (process-wide: a reloaded plugin copy sees them)."""
    holder = sys.modules.setdefault("_film_suite_video_line_state", type(sys)("_film_suite_video_line_state"))
    if not hasattr(holder, "claims"):
        holder.claims = set()
    return holder.claims


# w47-r1 item 3 / w47-s1 invariants 2 and 4: a claim (a starting take, or a waiting take being prepared) that has not
# moved on for longer than the bound on an unanswered submit (lifecycle_1.py) is fenced, whether its owner runs or not.
_VQ_STARTING_DEADLINE_SECONDS = V4_LOST_SUBMIT_LIMIT_SECONDS


# _vq_claim_live, _vq_decide_starting and _vq_recover live in video_line_settle_1.py (the 800-line cap).


# --- Admission (A2): a local take sent while the engine is busy waits in the line ---------------------------------
# Wrapped append-only around _v4_submit_route (the pattern of managed_submit_1's in-flight wrap). A take is admitted
# when the ledger has an active comfyui-local row or the line already holds a take (a newcomer never overtakes). It is
# validated cheaply first (target, request id, destination once: the project's take counter moves once, media), so a
# take that cannot run is refused now, not hours later. The answer is a receipt: details {id, status waiting, position}.

_VQ_RESERVED: contextvars.ContextVar = contextvars.ContextVar("film_suite_video_line_reserved", default=None)
_VQ_SUBMIT_PREFIX = "Generation submission failed"


def _vq_reserved_for(client_request_id: Any) -> str | None:
    """The job id the line reserved for this request while its starter submits it (managed_submit_1 uses it)."""
    held = _VQ_RESERVED.get()
    return held[1] if isinstance(held, tuple) and held[0] == client_request_id else None


def _vq_reserved_claim(client_request_id: Any) -> Mapping[str, Any] | None:
    """The claim (owner, claim generation) the reservation was made under: the fence _vq_fenced_insert checks."""
    held = _VQ_RESERVED.get()
    return held[2] if isinstance(held, tuple) and len(held) > 2 and held[0] == client_request_id else None


def _vq_applies(request: SubmitRequest) -> bool:
    if request.provider_id != VIDEO_LINE_CONNECTION or not request.client_request_id or not request.target_id:
        return False
    if _h3k_fans_out(request):
        return False
    try:
        resolved = _generation_registry.resolve(request.provider_id, request.target_id)
    except Exception:  # noqa: BLE001 - the submit path refuses it by name
        return False
    return resolved.provider_id == request.provider_id and resolved.target_id == request.target_id


def _vq_request_sha256(request: SubmitRequest) -> str:
    body = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _vq_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    """A line take's receipt in the /submit and /poll shape (no ledger row yet)."""
    state = row["state"]
    status = {"waiting": "waiting", "starting": "waiting", "removed": "cancelled", "failed": "failed"}.get(state, "queued")
    try:
        args = (json.loads(row["request_json"]) or {}).get("args") or {}
    except (TypeError, ValueError):
        args = {}
    details = {
        "id": row["studio_job_id"], "provider_job_id": None, "provider_id": VIDEO_LINE_CONNECTION, "target_id": row["target_id"],
        "status": status, "requested_basename": row.get("requested_basename"), "queued_at": None, "running_at": None,
        "completed_at": None, "saved_path": None, "saved_bytes": None, "requested": _public_requested_args(args),
        "effective": None, "row_contract": 4, "project_id": row.get("project_id"), "position": row.get("position"),
    }
    receipt: dict[str, Any] = {"result": None, "details": details, "reason_code": None, "retry_after": None}
    if status == "cancelled":
        receipt["reason_code"] = "cancelled"
    elif status == "failed":
        receipt["reason_code"] = row.get("reason_code") or "unknown"
        receipt["reason_text"] = row.get("cause") or generation.contract.public_reason(receipt["reason_code"])
    return receipt


def _vq_validated(request: SubmitRequest, *, identity: bool = True) -> tuple[SubmitRequest | None, dict[str, Any] | None]:
    """The request as it will be started (a project take keeps the file name resolved now), or the refusal."""
    try:
        try:
            _directory, basename, project_id = _v4_destination(request)
        except ValueError as exc:
            if type(exc) is ValueError and str(exc) == "project output destination is invalid" and request.save_to and not request.requested_basename:
                return None, _v4_named("output_name_missing", _VQ_SUBMIT_PREFIX)
            if type(exc) is ValueError and str(exc) == "save_to is not a folder":
                return None, _v4_named("save_to_not_folder", _VQ_SUBMIT_PREFIX)
            raise
        try:
            if identity:
                _v4_identity_args(request)
        except _h3k_module.H3ControlError as exc:
            import logging
            logging.getLogger(__name__).debug("H3 control refusal: %s", exc.diagnostic.get("detail"))
            return None, {"error": exc.diagnostic["message"], "reason_code": exc.reason_code if exc.reason_code in generation.contract.REASON_CODES else "invalid_request"}
        except (_h3x_module.H3ContinuationError, _vsr_module.VideoUpscaleError) as exc:
            return None, {"error": f"{_VQ_SUBMIT_PREFIX}: {exc}", "reason_code": exc.reason_code}
    except Exception as exc:  # noqa: BLE001 - the same finite mapping as the submit path
        return None, _v4_exception(exc, prefix=_VQ_SUBMIT_PREFIX)
    if project_id is not None and not request.save_to:
        request = request.model_copy(update={"requested_basename": basename})  # T5: the rule's name, reserved once
    return request, None


_v4_submit_route_before_line = _v4_submit_route


async def _v4_submit_route(request: SubmitRequest) -> dict[str, Any]:  # noqa: F811
    if _VQ_RESERVED.get() is not None or not _vq_applies(request):
        return await _v4_submit_route_before_line(request)
    # Owner merge w46: the destination is checked before the line touches the ledger, as the submit path does
    # (a removed or not-approved folder and a pending project move are refused with no ledger or engine access).
    _started, refusal = await asyncio.to_thread(_vq_validated, request, identity=False)
    if refusal is not None:
        return refusal
    try:
        existing = await asyncio.to_thread(_read_client_row, request.client_request_id)
    except Exception:  # noqa: BLE001 - w47-s1 invariant 3: no decision, no submit; refused, retryable
        return _vq_busy_answer()
    if existing is not None:
        return await _v4_submit_route_before_line(request)  # the ledger's own exact-retry answer
    # w47-r1 item 2 (cr48 M1): the line store decides in one write transaction whether this take waits or starts now
    # (video_line_settle_1.py, _vq_direct_submit); no look outside that transaction decides.
    return await _vq_direct_submit(request, _started)


# --- The starter (A3): one daemon thread per process, its own event loop per step (never a task on a request loop) ---
# Each step: stale claims of a gone owner are recovered; an active local take is polled through /poll (so it is
# published and its end seen with no page open); a free engine starts the lowest waiting take through the unchanged
# submit path, under its reserved id and as its recorded author. A busy answer puts the take back at its place (another
# process started one); any other refusal ends it failed with its code and cause. The thread ends when nothing waits.
_VQ_POLL_SECONDS = 4.0
_VQ_LOCK = threading.Lock()
_VQ_FLAG: dict[str, Any] = {"active": False, "halt": False}
_VQ_THREADS: list = []


def _vq_wake() -> None:
    """Wake this process's starter. In memory only (never busy, never blocked by the store); w47-t1 item 3: a starter
    whose heartbeat is older than the deadline is replaced (the old one leaves at its next look)."""
    try:
        with _VQ_LOCK:
            _VQ_FLAG["generation"] = _VQ_FLAG.get("generation", 0) + 1
        _take_wake(_VQ_LOCK, _VQ_FLAG, _VQ_THREADS, _vq_worker, "fs-video-line", stale=_vq_worker_stale)
    except Exception:  # noqa: BLE001 - a later admission, poll or list wakes it again
        pass


def _vq_stop(timeout: float = 10.0) -> None:
    """Stop this process's starter and wait for it (plugin unload; a test's end). Waiting takes stay waiting."""
    _VQ_FLAG["halt"] = True
    try:
        for thread in list(_VQ_THREADS):
            if thread is not threading.current_thread():
                thread.join(timeout)
    finally:
        _VQ_FLAG["halt"] = False


# _vq_worker_stale, _vq_worker and _vq_step live in video_line_worker_1.py (the 800-line cap).


def _vq_on_startup() -> None:
    """The host mounted the routes (a Hermes start): takes that waited through a restart start by themselves, and a
    cancel that a gone process left unsettled is carried out (w47-r1 item 1)."""
    try:
        # w47-u1 item 1b: a live tombstone is looked up at start too (the starter's step runs the tombstone pass).
        tombs = globals().get("_vq_tomb_maybe", lambda: False)()  # w47-v1: an unreadable store may hold some
        if _vq_has_work() or tombs:
            _comfy_store()  # only an existing line with work needs its ledger opened
            _vq_wake()
        if tombs:  # w47-v1 H15: and the low-rate watcher keeps looking after the starter ended
            globals().get("_vq_tomb_watch_start", lambda: None)()
    except Exception:  # noqa: BLE001 - a later admission, poll or list wakes it
        pass


router.on_startup.append(_vq_on_startup)



# --- Poll, cancel and the Jobs list know the line (A4) -------------------------------------------------------------
# A line take has its job id before its ledger row. /poll and /cancel look in the line when the ledger does not know an
# id: waiting -> the receipt with its position; removed -> cancelled; failed (refused at start) -> failed with its cause;
# started -> the ledger answers (same id). A waiting take is cancelled by leaving the line; it never runs. The Jobs list
# shows active work first and waiting takes in order, within the limit, then line takes
# that ended without a ledger row. Each of the three also wakes the starter when takes wait (a restart, a dead thread).

def _vq_wake_if_waiting() -> None:
    # w47-t1 item 3 (cr50 H9): the request side recovers too (no engine call; the line's timed lock), so a stuck starter
    # is never the only actor; then the starter is woken (replaced when its heartbeat is stale).
    try:
        if _vq_has_work():
            try:
                _vq_recover(settle=False)
            except Exception:  # noqa: BLE001 - the starter recovers on its next step
                pass
            _vq_wake()
    except Exception:  # noqa: BLE001 - a later call wakes it
        pass


def _vq_scoped(request: Any, studio_job_id: str, *, starting: bool = False) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(line row, None) for an id only the line knows, (None, refusal) for another project's take, (None, None) else.
    starting=True (cancel): a take the line is still starting is the line's even once its ledger row exists."""
    try:
        if not studio_job_id.startswith("studio:"):
            return None, None
        if _read_client_row_by_job(studio_job_id) is not None:
            row = _vq_get(studio_job_id) if starting else None
            if row is None or row["state"] != "starting":
                return None, None
        else:
            row = _vq_get(studio_job_id)
    except Exception:  # noqa: BLE001 - the ledger path answers
        return None, None
    if row is None or row["state"] == "started":
        return None, None
    present = "expected_project_id" in getattr(request, "model_fields_set", set()) or row.get("project_id") is None
    if not present or request.expected_project_id != row.get("project_id"):
        return None, _v4_error("project_scope_mismatch")
    return row, None


_poll_route_before_line = _poll_route


async def _poll_route(request: PollRequest) -> dict[str, Any]:  # noqa: F811
    await asyncio.to_thread(_vq_wake_if_waiting)
    row, refusal = await asyncio.to_thread(_vq_scoped, request, request.id.strip())
    if refusal is not None:
        return refusal
    if row is not None:
        return _vq_receipt(row)
    return await _poll_route_before_line(request)


_cancel_route_before_line = _cancel_route


async def _cancel_route(request: CancelRequest) -> dict[str, Any]:  # noqa: F811
    studio_job_id = request.id.strip()
    row, refusal = await asyncio.to_thread(_vq_scoped, request, studio_job_id, starting=True)
    if refusal is not None:
        return refusal
    if row is None:
        result = await _cancel_route_before_line(request)
    else:
        # w47-q1 item 1: the intent is written in one statement (a take not yet sent leaves the line at once); a take
        # whose submit is on its way is answered once that submit's outcome is known, and it is stopped on the ledger.
        await asyncio.to_thread(_vq_cancel_intent, studio_job_id)
        current = await _vq_cancel_outcome(studio_job_id)
        if current is not None and current["state"] == "started":  # it reached the ledger: stop it there
            result = await _vq_settle_cancel(studio_job_id, current.get("project_id"))
            if result is None:  # the starter stopped it (or is doing so): the ledger answers once that is done
                current = await _vq_cancel_outcome(studio_job_id)
                result = await _cancel_route_before_line(request)
            result = _vq_cancel_truth(studio_job_id, result)
        elif current is not None and current["state"] == "starting":  # past the wait: the intent is kept (H1)
            result = _vq_pending_receipt(current)
        else:
            result = _vq_receipt(current or row)
    await asyncio.to_thread(_vq_wake_if_waiting)
    return result


_VQ_CANCEL_WAIT_SECONDS = 60.0  # how long a cancel waits for a submit already on its way (then: intent kept, honest)


async def _vq_cancel_outcome(studio_job_id: str) -> dict[str, Any] | None:
    """The row once its submit's outcome is known (left 'starting' and, when started, the starter's own ledger cancel
    is done). A starter that is gone is recovered meanwhile. Past the bound the row is answered as it stands."""
    deadline = time.monotonic() + float(_VQ_CANCEL_WAIT_SECONDS)
    alive = _take_owner_module().token_alive
    while True:
        current = await asyncio.to_thread(_vq_get, studio_job_id)
        if current is None:
            return None
        settling = current["state"] == "started" and current.get("cancel_requested") == 3
        if current["state"] != "starting" and not settling:
            return current
        if time.monotonic() >= deadline:
            return current
        owner = current.get("owner")
        if current["state"] == "starting" and owner != _vq_owner_token() and not alive(owner):
            await asyncio.to_thread(_vq_recover)
        await asyncio.sleep(0.05)


def _vq_waiting_total(project_id: str | None) -> int:
    """w47-q1 item 3 (L3): how many of this scope's local takes wait (or are being started), whatever a limit shows."""
    rows = _vq_read("SELECT seq FROM video_line WHERE project_id IS ? AND state IN ('waiting', 'starting')", (project_id,))
    return len(rows)


def _vq_jobs_for_scope(project_id: str | None, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(waiting rows, ended rows without a ledger row) of one scope in the Jobs row shape."""
    waiting, ended = [], []
    for row in _vq_rows(project_id, ("waiting", "starting", "failed", "removed")):
        base = {"module": "shoot", "job_id": row["studio_job_id"], "label": row.get("label") or "",
                "result_name": row.get("requested_basename"), "target_id": row["target_id"],
                "created_at": _finite_epoch(row["created_at"]), "started_at": None}
        if row["state"] in ("waiting", "starting"):
            waiting.append({**base, "state": "queued", "raw_state": "waiting", "position": row.get("position"),
                            "finished_at": None, "error": None, "reason_code": None})
        else:
            failed = row["state"] == "failed"
            ended.append({**base, "state": "failed" if failed else "cancelled", "raw_state": row["state"],
                          "finished_at": _finite_epoch(row.get("ended_at")),
                          "error": _job_label(row.get("cause") or generation.contract.public_reason(row.get("reason_code"))) if failed else None,
                          "reason_code": _job_reason_code(row.get("reason_code")) if failed else None})
    ended.sort(key=lambda job: job.get("created_at") or 0.0, reverse=True)
    return waiting, ended[:limit]


_video_jobs_for_scope_before_line = _video_jobs_for_scope


def _video_jobs_for_scope(project_id: str | None, limit: int) -> list[dict[str, Any]]:  # noqa: F811
    _vq_wake_if_waiting()
    try:
        waiting, ended = _vq_jobs_for_scope(project_id, limit)
    except Exception:  # noqa: BLE001 - the ledger's jobs still list
        waiting, ended = [], []
    if not waiting:
        listed = _video_jobs_for_scope_before_line(project_id, limit)
        return sorted(listed + ended, key=lambda job: job.get("created_at") or 0.0, reverse=True)[:limit] if ended else listed
    # Active ledger work must remain visible even when all 200 waiting places are occupied.
    # Active takes lead, followed by the oldest waiting takes, within the requested bound.
    listed = _video_jobs_for_scope_before_line(project_id, max(limit, VIDEO_LINE_MAX))
    active_records = [r for r in _comfy_store().active_rows(VIDEO_LINE_CONNECTION) if r.project_id == project_id]
    active_ids = {r.studio_job_id for r in active_records}
    active = [job for job in listed if job.get("job_id") in active_ids]
    visible = {job["job_id"] for job in active}
    for record in active_records:
        if record.studio_job_id in visible:
            continue
        prompt = (record.request.get("args") or {}).get("prompt") if isinstance(record.request, Mapping) else None
        facts = _h3_public_facts(record.studio_job_id) if _h3_is_take(record) else None
        motion = {key: facts[key] for key in ("motion_activity", "frozen") if facts and key in facts}
        active.append({**motion, "module": "shoot", "job_id": record.studio_job_id,
                       "state": _VIDEO_JOB_STATE_VIEW.get(record.state, "queued"), "raw_state": record.state,
                       "label": _job_label(prompt or record.requested_basename),
                       "result_name": record.requested_basename, "target_id": record.target_id,
                       "created_at": _finite_epoch(record.created_at), "started_at": _finite_epoch(record.running_at),
                       "finished_at": _finite_epoch(record.completed_at), "error": None, "reason_code": None})
    rest = [job for job in listed if job.get("job_id") not in active_ids]
    if ended:
        rest = sorted(rest + ended, key=lambda job: job.get("created_at") or 0.0, reverse=True)
    return (active + waiting + rest)[:limit]
