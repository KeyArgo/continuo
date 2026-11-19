from __future__ import annotations

import contextvars

# --- Who did it: Hermes or the artist (lane w5-backend items 1-2) -------------------------------------
#
# A Hermes tool call runs the very routes the page calls (agent_tools.py: in-process ASGI). agent_tools
# sets _FILM_CALLER to "hermes" around its dispatch; every page request leaves the default "artist".
# The submit paths note the caller per NEW job id (the image announce of a new row, the Shoot announce of
# a submitted take) in one small private SQLite table under the Hermes state folder; /jobs/list answers it
# as ``by``. A job without a note (sent before this existed) reads "artist". The first note wins: a replay
# of the same request by the other side never takes a job over. The takes of a Generate x N batch that the
# backend submits later inherit the author of the batch's first take (same client request id stem).
# Notes never fail a route: every helper swallows its own errors.

_FILM_CALLER = contextvars.ContextVar("film_suite_caller", default="artist")
_JOB_AUTHORS_MAX = 20_000
_JOB_AUTHORS_LOCK = _thread.allocate_lock()


def _film_caller() -> str:
    """"hermes" inside an agent tool call, else "artist"."""
    return "hermes" if _FILM_CALLER.get() == "hermes" else "artist"


def _caller_by(by: Any) -> str:
    """The author a change is recorded under (lane w34-sec, scan finding 18; as _script_by, SCR-072): an agent call is
    always Hermes', whatever ``by`` it sends; the page keeps the ``by`` it sends."""
    return "hermes" if _film_caller() == "hermes" else by


def _job_authors_path() -> Path:
    base = _local_data.records_base()
    return Path(state_root(Path(base) / "hermes")) / "job-authors.sqlite3"


def _job_authors_connect() -> sqlite3.Connection:
    path = _job_authors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=5)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS job_authors (job_id TEXT PRIMARY KEY, by TEXT NOT NULL CHECK (by IN ('artist', 'hermes')), at REAL NOT NULL)"
    )
    # w45-s1 item 6 (MED-108): the run a batch member belongs to (member job id -> the run's first job id). A run has
    # one author: whoever started it, so an author note on the first job (a Hermes bridge action names only that one)
    # is every member's author.
    connection.execute("CREATE TABLE IF NOT EXISTS job_runs (job_id TEXT PRIMARY KEY, head TEXT NOT NULL)")
    # w45-s7 item 1 (HER-101): a Vary the Hermes tool handed to the pane (written by __init__._grant_hermes_jobs).
    # w45-s9 item 1: the same table holds the grant of every bridge action that makes jobs after its ack (an edit, a
    # palette Generate); ``cells`` is the number of jobs the action may make. A row s7 wrote reads exactly as before.
    connection.execute("CREATE TABLE IF NOT EXISTS vary_grants (action_id TEXT PRIMARY KEY, cells INTEGER NOT NULL, expires REAL NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS vary_grant_jobs (job_id TEXT PRIMARY KEY, action_id TEXT NOT NULL)")
    _grant_binding_tables(connection)
    return connection


# w45-s20 item 1 (cold review s5-s9 High 1): the action id is seen by the page, so it is no secret. A grant is bound to
# what the tool started: the owner the action was sent against, the route kind it causes ("edit": /image/edit, "submit":
# a producer or workflow submit) and its number of operations; each operation id is bound to the grant on its first
# job. A row without these columns (written by s7/s9 code) binds to the kind and owner of its first job and one operation.
# w47-q4 item 1 (s23 High 3): a grant the tool writes now is exact: it pre-allocates the operation ids (one per Vary
# cell / per submit), stores them in vary_grant_ops with the grant before the action is visible and hands them to the
# pane on the action; only those ids are Hermes'. Any other operation is the artist's, even of the same kind under the
# same action id at the same moment. w47-r2 item 2 (cold review H2): a grant written before (exact NULL, 1.1.x) is no
# longer bound by first use: it grants nothing, so its operations are the artist's.
GRANT_KINDS = ("edit", "submit")


def _grant_binding_tables(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS vary_grant_ops (op_key TEXT PRIMARY KEY, action_id TEXT NOT NULL)")
    have = {row[1] for row in connection.execute("PRAGMA table_info(vary_grants)")}
    for column, kind in (("owner_scope", "TEXT"), ("kind", "TEXT"), ("ops", "INTEGER"), ("exact", "INTEGER")):
        if column not in have:
            connection.execute(f"ALTER TABLE vary_grants ADD COLUMN {column} {kind}")


def _bridge_job_note(action_id: Any, job_id: Any, *, owner_scope: Any = None, kind: Any = None, operation_id: Any = None) -> None:
    """w45-s7 item 1 (HER-101), w45-s9 item 1, w45-s20 item 1: a NEW job the pane submits under a bridge action the
    Hermes tool started is Hermes' (a Vary cell, a variant of an agent's edit, the run of a palette Generate).

    The page names the bridge action it runs (``bridge_action_id``); only an action the tool itself enqueued with a
    grant (``vary``, the edit actions, ``run_command`` Generate) has one. The grant is bound to the owner, the route kind
    and the operations it may make, and covers its number of jobs until it expires; anything else grants nothing. A
    route calls this BEFORE it notes the caller: a job the artist's note already names (an artist's job replayed under an
    observed id) keeps its author and takes no place; a job the tool noted itself (a Vary's first cell from the ack)
    takes its place. First note wins: nothing here replaces a note."""
    try:
        if type(action_id) is not str or type(job_id) is not str or not 0 < len(job_id) <= 160:
            return
        if kind not in GRANT_KINDS or type(owner_scope) is not str or type(operation_id) is not str or not operation_id:
            return
        now = time.time()
        op_key = f"{kind}|{owner_scope}|{operation_id}"
        with _JOB_AUTHORS_LOCK:
            connection = _job_authors_connect()
            try:
                with connection:
                    grant = connection.execute("SELECT cells, expires, owner_scope, kind, ops, exact FROM vary_grants WHERE action_id = ?", (action_id,)).fetchone()
                    if grant is None or float(grant[1]) <= now:
                        return
                    if not grant[5]:
                        # w47-r2 item 2 (cold review H2): a grant written before exact ids (1.1.x: bound by first use) has
                        # expired with the upgrade; the operations sent under it are the artist's.
                        return
                    noted = connection.execute("SELECT by FROM job_authors WHERE job_id = ?", (job_id,)).fetchone()
                    if noted is not None and noted[0] != "hermes":
                        return  # an artist's job (a replay under an observed id): its first note stands, no place used
                    if connection.execute("SELECT 1 FROM vary_grant_jobs WHERE job_id = ?", (job_id,)).fetchone() is not None:
                        return
                    want_owner, want_kind = grant[2], grant[3]
                    if want_owner != owner_scope or want_kind != kind:
                        return
                    op = connection.execute("SELECT action_id FROM vary_grant_ops WHERE op_key = ?", (op_key,)).fetchone()
                    if op is None or op[0] != action_id:
                        return  # w47-q4 item 1: an exact grant counts only the operation ids the tool stored for it
                    (used,) = connection.execute("SELECT COUNT(*) FROM vary_grant_jobs WHERE action_id = ?", (action_id,)).fetchone()
                    if used >= int(grant[0]):
                        return
                    connection.execute("INSERT INTO vary_grant_jobs (job_id, action_id) VALUES (?, ?)", (job_id, action_id))
                    connection.execute("INSERT OR IGNORE INTO job_authors (job_id, by, at) VALUES (?, 'hermes', ?)", (job_id, now))
            finally:
                connection.close()
    except Exception:  # noqa: BLE001 - a note never fails a route
        pass


def _job_runs_note(job_ids: Any) -> None:
    """Members 1..N-1 of a batch run belong to member 0 (``job_ids[0]``); a note never fails a route."""
    try:
        ids = [job_id for job_id in (job_ids or ()) if type(job_id) is str and 0 < len(job_id) <= 160]
        if len(ids) < 2:
            return
        with _JOB_AUTHORS_LOCK:
            connection = _job_authors_connect()
            try:
                with connection:
                    connection.executemany("INSERT OR IGNORE INTO job_runs (job_id, head) VALUES (?, ?)", [(m, ids[0]) for m in ids[1:]])
            finally:
                connection.close()
    except Exception:  # noqa: BLE001
        pass


def _job_authors_note(job_ids: Any, by: str | None = None) -> None:
    try:
        who = by if by in ("artist", "hermes") else _film_caller()
        ids = [job_id for job_id in (job_ids or ()) if type(job_id) is str and 0 < len(job_id) <= 160]
        if not ids:
            return
        now = time.time()
        with _JOB_AUTHORS_LOCK:
            connection = _job_authors_connect()
            try:
                with connection:
                    connection.executemany("INSERT OR IGNORE INTO job_authors (job_id, by, at) VALUES (?, ?, ?)", [(job_id, who, now) for job_id in ids])
                    (count,) = connection.execute("SELECT COUNT(*) FROM job_authors").fetchone()
                    if count > _JOB_AUTHORS_MAX:
                        connection.execute(
                            "DELETE FROM job_authors WHERE job_id IN (SELECT job_id FROM job_authors ORDER BY at ASC LIMIT ?)",
                            (count - _JOB_AUTHORS_MAX,),
                        )
            finally:
                connection.close()
    except Exception:  # noqa: BLE001 - a note never fails a route
        pass


def _job_authors_read(job_ids: Any) -> dict[str, str]:
    """job id -> "artist" | "hermes" for the ids that carry a note."""
    ids = [job_id for job_id in (job_ids or ()) if type(job_id) is str and job_id]
    found: dict[str, str] = {}
    if not ids or not _job_authors_path().is_file():
        return found
    try:
        with _JOB_AUTHORS_LOCK:
            connection = _job_authors_connect()
            try:
                for start in range(0, len(ids), 400):
                    chunk = ids[start:start + 400]
                    rows = connection.execute(
                        f"SELECT job_id, by FROM job_authors WHERE job_id IN ({','.join('?' * len(chunk))})", chunk
                    ).fetchall()
                    found.update({job_id: who for job_id, who in rows})
                    # w45-s1 item 6 (MED-108): a batch member is by the run's author (its head's note wins, so a Hermes
                    # note on member 0 covers every member, whoever noted the member itself first).
                    heads = dict(connection.execute(
                        f"SELECT job_id, head FROM job_runs WHERE job_id IN ({','.join('?' * len(chunk))})", chunk
                    ).fetchall())
                    if heads:
                        wanted = sorted(set(heads.values()))
                        head_rows = dict(connection.execute(
                            f"SELECT job_id, by FROM job_authors WHERE job_id IN ({','.join('?' * len(wanted))})", wanted
                        ).fetchall())
                        for member, head in heads.items():
                            if head in head_rows:
                                found[member] = head_rows[head]
            finally:
                connection.close()
    except Exception:  # noqa: BLE001 - unknown reads as the artist
        return {}
    return found


def _job_authors_tag(items: list[dict[str, Any]], key: str = "item_id") -> None:
    """w36-media (GEM-231): each item's ``by`` (hermes | artist) from its job's author note, one read for the list."""
    authors = _job_authors_read([item.get(key) for item in items])
    for item in items:
        item["by"] = "hermes" if authors.get(item.get(key)) == "hermes" else "artist"


def _job_authors_note_shoot(studio_job_id: Any) -> None:
    """A submitted Shoot take: its author, by take id and by client request id (batch stem inherited)."""
    try:
        if type(studio_job_id) is not str or not studio_job_id:
            return
        crid = None
        try:
            crid = getattr(_read_ledger_row(studio_job_id), "client_request_id", None)
        except Exception:  # noqa: BLE001 - a row we cannot read is noted by id only
            crid = None
        who = None
        if type(crid) is str and ":take-" in crid:
            who = _job_authors_read(["crid:" + crid.split(":take-")[0]]).get("crid:" + crid.split(":take-")[0])
        keys = [studio_job_id] + (["crid:" + crid] if type(crid) is str and crid else [])
        _job_authors_note(keys, who)
    except Exception:  # noqa: BLE001
        pass


def _job_authors_apply(jobs: list[dict[str, Any]]) -> None:
    authors = _job_authors_read([job.get("job_id") for job in jobs])
    for job in jobs:
        job["by"] = authors.get(job.get("job_id"), "artist")
