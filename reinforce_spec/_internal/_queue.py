"""Lightweight async job queue.

Provides a simple in-process job queue for fire-and-forget tasks such as
background policy training and async feedback ingestion.

For production deployments requiring durability, replace this with Celery,
ARQ, or a persistent message broker.
"""

from __future__ import annotations

import asyncio
import dataclasses
import traceback
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

from reinforce_spec._internal._utils import utc_now

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime


class JobStatus(str, Enum):
    """Lifecycle states for a queued job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclasses.dataclass
class Job:
    """A unit of background work.

    Attributes
    ----------
    id : str
        Unique job identifier.
    name : str
        Human-readable task name (e.g. ``"train_policy"``).
    status : JobStatus
        Current lifecycle state.
    created_at : datetime
        UTC timestamp of creation.
    started_at : datetime or None
        UTC timestamp when execution began.
    completed_at : datetime or None
        UTC timestamp when execution finished.
    result : Any
        Return value of the callable (on success).
    error : str or None
        Traceback string (on failure).

    """

    id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = dataclasses.field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None


class JobQueue:
    """In-process async job queue.

    Parameters
    ----------
    max_concurrent : int
        Maximum number of jobs running in parallel.

    Examples
    --------
    >>> queue = JobQueue(max_concurrent=2)
    >>> await queue.start()
    >>> job = await queue.enqueue("train", train_policy, n_steps=1000)
    >>> await queue.stop()

    """

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max_concurrent = max_concurrent
        self._queue: asyncio.Queue[
            tuple[Job, Callable[..., Awaitable[Any]], tuple[Any, ...], dict[str, Any]]
        ] = asyncio.Queue()
        self._jobs: dict[str, Job] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        """Start background worker tasks."""
        if self._running:
            return
        self._running = True
        for i in range(self._max_concurrent):
            task = asyncio.create_task(self._worker(i), name=f"job-worker-{i}")
            self._workers.append(task)
        logger.info("job_queue_started | workers={n}", n=self._max_concurrent)

    async def stop(self) -> None:
        """Drain the queue and cancel workers."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("job_queue_stopped")

    async def enqueue(
        self,
        name: str,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> Job:
        """Submit a job to the queue.

        Parameters
        ----------
        name : str
            Human-readable job name.
        fn : Callable
            Async callable to run.
        *args : Any
            Positional arguments for *fn*.
        job_id : str or None
            Optional custom job id. Auto-generated ULID if omitted.
        **kwargs : Any
            Keyword arguments for *fn*.

        Returns
        -------
        Job
            The submitted job (initially ``PENDING``).

        """
        from reinforce_spec._internal._utils import generate_request_id

        jid = job_id or generate_request_id()
        job = Job(id=jid, name=name)
        self._jobs[jid] = job
        await self._queue.put((job, fn, args, kwargs))
        logger.info("job_enqueued | id={id} name={name}", id=jid, name=name)
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Look up a job by ID."""
        return self._jobs.get(job_id)

    @property
    def pending_count(self) -> int:
        """Number of jobs waiting in the queue."""
        return self._queue.qsize()

    # ── Internal ──────────────────────────────────────────────────────

    async def _worker(self, worker_id: int) -> None:
        """Process jobs from the queue."""
        while self._running:
            try:
                job, fn, args, kwargs = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            job.status = JobStatus.RUNNING
            job.started_at = utc_now()
            logger.info(
                "job_started | id={id} name={name} worker={w}",
                id=job.id,
                name=job.name,
                w=worker_id,
            )

            try:
                job.result = await fn(*args, **kwargs)
                job.status = JobStatus.COMPLETED
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = traceback.format_exc()
                logger.error(
                    "job_failed | id={id} name={name} error={error}",
                    id=job.id,
                    name=job.name,
                    error=str(exc),
                )
            finally:
                job.completed_at = utc_now()

            self._queue.task_done()
