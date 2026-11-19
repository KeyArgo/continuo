"""Bring a finished run's picture home: fetch once, validate, publish.

A ready job only means ComfyUI finished.  The picture still sits in ComfyUI's
temp output, which ComfyUI clears on its own.  This collector turns ``ready``
into ``published``: it fetches the bytes through the pinned client (``/view``,
loopback only), and hands them to the ingestor, which validates them against
the job's own ledger facts and publishes them content-addressed.

The synchronous publication runs on one short-lived daemon thread per publication (lane w45-s21), so the request's
event loop stays free; the thread holds the job's lock until it really ends.

Authority stays in the ledger.  The output descriptor comes from the
coordinator's validated poll, never from a caller, and the evidence is built
from the job record - so a caller cannot point this at another file.
"""
from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from typing import Any, Awaitable, Callable, Mapping

from . import image_contract as contract

_LOCK_POLL_SECONDS = 0.01
# Admission covers fetch bytes as well as the worker, across all collectors.
_PUBLICATION_SLOTS = threading.BoundedSemaphore(4)


class ImageCollectError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.reason_code = code
        super().__init__(code)


class ImageResultCollector:
    """ready (or ingested, after a stop mid-publication) -> published, idempotent, one run at a time per job."""

    def __init__(
        self,
        *,
        job_store: Any,
        ingestor: Any,
        fetch: Callable[[Mapping[str, str]], Awaitable[bytes]],
    ) -> None:
        if job_store is None or ingestor is None or not callable(fetch):
            raise ImageCollectError("collector-owner-required")
        self.job_store = job_store
        self.ingestor = ingestor
        self.fetch = fetch
        # Lane w32-rel (IMG-224, review R3; same fix as the coordinator in 6834063d, w25-imgfix): the composition root
        # shares this collector across the profile, and the page's routes and Hermes' tool dispatch run on different
        # event loops. An asyncio.Lock per job bound itself to the first loop that waited on it, and the next loop
        # raised "bound to a different event loop" (the picture stayed unpublished). The per-job lock is a
        # threading.Lock awaited without blocking any loop (any loop or thread may hold and release it).
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._publishing: dict[str, float] = {}  # owned by the publication thread until it ends

    async def _hold(self, image_producer_job_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.setdefault(image_producer_job_id, threading.Lock())
        while not lock.acquire(blocking=False):
            await asyncio.sleep(_LOCK_POLL_SECONDS)  # a cancelled waiter holds nothing
        return lock

    @staticmethod
    def _evidence(job: Mapping[str, Any], result_sha256: str) -> dict[str, Any]:
        return {
            "provider_id": contract.PROVIDER_ID,
            "provider_prompt_id": job["provider"]["prompt_id"],
            "target_id": job["provider"]["target_id"],
            "capability_manifest_sha256": job["capability_manifest_sha256"],
            "api_graph_sha256": job["api_graph_sha256"],
            "request_snapshot_sha256": job["request_snapshot_sha256"],
            "context_basis": dict(job["context_basis"]),
            "result_sha256": result_sha256,
        }

    @staticmethod
    def _ingested_evidence(job: Mapping[str, Any]) -> dict[str, Any]:
        """The evidence recorded with the ingested job, kept as it is (the ingestor refuses any other)."""
        evidence = job.get("result_evidence")
        if not isinstance(evidence, Mapping):
            raise ImageCollectError("collect-evidence-missing")
        return dict(evidence)

    @staticmethod
    def _replay_descriptor(job: Mapping[str, Any]) -> dict[str, str]:
        """The descriptor shape the ingestor checks on replay. An ingested job needs no retrieval identity (its bytes
        are already local and are checked against the recorded pending output); ComfyUI's file name is not kept in
        the ledger, so the replay names the job itself - it is never used to fetch or to name the published file."""
        return {"filename": f"{job['image_producer_job_id']}.png", "subfolder": "", "type": "temp",
                "mime_type": "image/png", "extension": ".png"}

    async def collect(self, image_producer_job_id: str, descriptor: Mapping[str, Any] | None) -> dict[str, Any]:
        """Bring one job home inside the caller's request, awaited to the end.

        Lane w45-s17 (cold review of s14): no executor, no service, no task of its own; the fetch is awaited (a
        cancelled caller stops it and holds nothing: no bytes, no lock).
        Lane w45-s21 (measured on 4bb057bd with the repository timing script picture_publication_timing (not shipped), real ingestor, random-noise
        PNGs, 5 runs, median/max): one publication takes 59/65 ms at 2 MP, 326/333 ms at 16 MP and 612/620 ms at
        33 MP, and one Jobs list call publishing 4 x 16 MP held the event loop for 1474 ms - every other request of the
        dashboard waited that long. So the synchronous publication runs on one short-lived daemon thread of its own
        (no executor), and the loop only awaits its result. The thread owns the job's lock from then on and releases it
        in its own ``finally`` once the publication has really ended: a cancelled caller, or a loop that is gone,
        never frees the job early, and the thread still finishes. A stop after record_ingested can be replayed locally;
        before that record, a later look may need the provider output again. While a call waits for its publication,
        ``publishing(job)`` answers True, so a caller with a deadline stops a fetch but waits for a publication.
        """
        lock = await self._hold(image_producer_job_id)
        handed_over = False
        admitted = False
        try:
            work = self._prepare_held(image_producer_job_id, descriptor)
            if not isinstance(work, _Work):
                return work
            admitted = _PUBLICATION_SLOTS.acquire(blocking=False)
            if not admitted:
                return self.job_store.get_job(image_producer_job_id)
            data = await work.fetch() if work.fetch is not None else None
            with self._locks_guard:
                self._publishing[image_producer_job_id] = time.monotonic()
            def finish() -> None:
                with self._locks_guard:
                    self._publishing.pop(image_producer_job_id, None)
            try:
                published = self._publish_on_thread(lock, lambda: work.publish(data), finish)
            except BaseException:
                finish()
                raise
            handed_over = True  # the thread owns the lock and slot until it ends
            return await published
        finally:
            if not handed_over:
                if admitted:
                    _PUBLICATION_SLOTS.release()
                lock.release()

    def publishing(self, image_producer_job_id: str) -> bool:
        """True while a collect of this job waits for its publication thread (past the fetch)."""
        with self._locks_guard:
            return image_producer_job_id in self._publishing

    def overdue(self, image_producer_job_id: str, seconds: float) -> bool:
        with self._locks_guard:
            started = self._publishing.get(image_producer_job_id)
            return started is not None and time.monotonic() - started >= seconds

    @staticmethod
    def _publish_on_thread(lock: threading.Lock, publish: Callable[[], dict[str, Any]], finish: Callable[[], None]) -> "asyncio.Future[dict[str, Any]]":
        """Run ``publish`` on its own daemon thread, which releases ``lock`` when it ends; awaited through a future."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()

        def settle(result: Any, error: BaseException | None) -> None:
            if future.done():  # the caller was cancelled: nobody waits for the answer any more
                return
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)

        def run() -> None:
            result: Any = None
            error: BaseException | None = None
            try:
                result = publish()
            except BaseException as exc:  # noqa: BLE001 - handed to the awaiting caller
                error = exc
            finally:
                finish()
                lock.release()  # only here: the publication has really ended
                _PUBLICATION_SLOTS.release()
            try:
                loop.call_soon_threadsafe(settle, result, error)
            except RuntimeError:
                pass  # the loop is gone; the publication finished and the job is released all the same

        thread = threading.Thread(target=run, name="continuo-publish", daemon=True)
        thread.start()
        return future

    def _prepare_held(self, image_producer_job_id: str, descriptor: Mapping[str, Any] | None) -> "dict[str, Any] | _Work":
        # Called with the job held (one collect at a time per job, from any loop). Answers the published job as it is,
        # or the work still to do: an optional fetch (awaited on the loop) and the synchronous publication.
        job = self.job_store.get_job(image_producer_job_id)
        if job["state"] == "published":
            return job
        if job["state"] == "ingested":
            # w45-s14 item 2: a process stop between record_ingested and record_published left the picture fetched,
            # validated and staged (or already linked). Nothing is fetched again: the ingestor's replay of an ingested
            # job finishes it, checked against the evidence and pending output the ledger recorded for THIS job.
            evidence = self._ingested_evidence(job)
            replay = self._replay_descriptor(job)
            return _Work(None, lambda _data: self.ingestor.ingest_and_publish(
                image_producer_job_id, stream=[], descriptor_count=1, descriptor=replay, result_evidence=evidence))
        if job["state"] != "ready":
            raise ImageCollectError("collect-state")
        if not isinstance(descriptor, Mapping) or any(
            not isinstance(descriptor.get(key), str) for key in ("filename", "subfolder", "type")
        ):
            raise ImageCollectError("collect-descriptor-missing")
        reference = {key: descriptor[key] for key in ("filename", "subfolder", "type")}
        given = dict(descriptor)

        async def fetch() -> bytes:
            try:
                data = await self.fetch(reference)
            except Exception as exc:  # noqa: BLE001 - transport is not ledger authority
                if getattr(exc, "http_status", None) == 404:
                    # ComfyUI answered and no longer has the file (its temp
                    # output was cleared). Waiting will not bring it back, so
                    # end the job honestly instead of leaving it "ready".
                    self.job_store.quarantine(image_producer_job_id, "output_missing")
                    raise ImageCollectError("collect-output-missing") from exc
                raise ImageCollectError("collect-fetch-failed") from exc
            if type(data) is not bytes or not data or len(data) > contract.MAX_BYTES:
                raise ImageCollectError("collect-fetch-failed")
            return data

        def publish(data: bytes) -> dict[str, Any]:
            # The ingestor re-validates everything against the job and quarantines on any mismatch. Synchronous file
            # work, on the publication thread: nothing can cancel it half way.
            evidence = self._evidence(job, hashlib.sha256(data).hexdigest())
            return self.ingestor.ingest_and_publish(
                image_producer_job_id, stream=[data], descriptor_count=1, descriptor=given, result_evidence=evidence)
        return _Work(fetch, publish)


class _Work:
    """What is left to do for one held job: an optional fetch on the loop, then the publication on its thread."""

    __slots__ = ("fetch", "publish")

    def __init__(self, fetch: Callable[[], Awaitable[bytes]] | None, publish: Callable[[Any], dict[str, Any]]) -> None:
        self.fetch = fetch
        self.publish = publish

__all__ = ["ImageCollectError", "ImageResultCollector"]
