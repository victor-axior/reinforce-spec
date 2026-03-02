"""Unit tests for the async job queue."""

from __future__ import annotations

import asyncio

import pytest

from reinforce_spec._internal._queue import JobQueue, JobStatus


@pytest.mark.asyncio()
class TestJobQueue:
    """Test in-process async job queue."""

    async def test_enqueue_and_process(self) -> None:
        queue = JobQueue(max_concurrent=1)
        await queue.start()

        result_holder: list[str] = []

        async def task() -> str:
            result_holder.append("done")
            return "completed"

        job = await queue.enqueue("test-task", task)
        assert job.status == JobStatus.PENDING

        # Give worker time to process
        await asyncio.sleep(0.5)

        assert job.status == JobStatus.COMPLETED
        assert result_holder == ["done"]

        await queue.stop()

    async def test_get_job(self) -> None:
        queue = JobQueue(max_concurrent=1)
        await queue.start()

        async def noop() -> None:
            pass

        job = await queue.enqueue("noop", noop)
        found = queue.get_job(job.id)
        assert found is not None
        assert found.name == "noop"

        await queue.stop()

    async def test_unknown_job_returns_none(self) -> None:
        queue = JobQueue(max_concurrent=1)
        assert queue.get_job("nonexistent") is None

    async def test_pending_count(self) -> None:
        queue = JobQueue(max_concurrent=1)
        # Don't start workers so jobs stay pending
        event = asyncio.Event()

        async def blocking() -> None:
            await event.wait()

        await queue.start()
        # Enqueue a blocking job to fill the single worker
        await queue.enqueue("block", blocking)
        await asyncio.sleep(0.1)  # let worker pick up first job
        # Now enqueue more that will queue up
        await queue.enqueue("pending-1", blocking)
        await queue.enqueue("pending-2", blocking)
        assert queue.pending_count >= 1
        event.set()
        await asyncio.sleep(0.5)
        await queue.stop()

    async def test_failed_task(self) -> None:
        queue = JobQueue(max_concurrent=1)
        await queue.start()

        async def fail() -> None:
            raise RuntimeError("intentional failure")

        job = await queue.enqueue("fail-task", fail)
        await asyncio.sleep(0.5)
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert "intentional failure" in job.error
        await queue.stop()

    async def test_job_has_timestamps(self) -> None:
        queue = JobQueue(max_concurrent=1)
        await queue.start()

        async def quick() -> str:
            return "ok"

        job = await queue.enqueue("ts-task", quick)
        await asyncio.sleep(0.5)
        assert job.status == JobStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.result == "ok"
        await queue.stop()

    async def test_start_idempotent(self) -> None:
        queue = JobQueue(max_concurrent=1)
        await queue.start()
        await queue.start()  # second start should be no-op
        await queue.stop()
