"""In-memory job store for generation and voice-conversion work.

Phase 1 keeps this deliberately simple: a dict guarded by a lock, one
sequential worker so the GPU is never contended. Track history moves to
SQLite in a later phase; jobs themselves are ephemeral.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    CONVERTING = "converting"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    kind: str  # "music" or "voice"
    params: dict[str, Any]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: JobStatus = JobStatus.QUEUED
    detail: str = "Waiting in queue"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def update(self, status: JobStatus | None = None, detail: str | None = None) -> None:
        if status is not None:
            self.status = status
        if detail is not None:
            self.detail = detail
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status.value,
            "detail": self.detail,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobQueue:
    """Single-worker queue: one GPU, one job at a time."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[tuple[Job, Callable[[Job], Awaitable[None]]]] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def submit(self, job: Job, runner: Callable[[Job], Awaitable[None]]) -> Job:
        self._jobs[job.id] = job
        self._queue.put_nowait((job, runner))
        self._ensure_worker()
        return job

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.get_running_loop().create_task(self._work())

    async def _work(self) -> None:
        while not self._queue.empty():
            job, runner = await self._queue.get()
            try:
                await runner(job)
                if job.status not in (JobStatus.DONE, JobStatus.ERROR):
                    job.update(status=JobStatus.DONE, detail="Done")
            except Exception as exc:  # noqa: BLE001 - job errors must never kill the worker
                job.error = str(exc)
                job.update(status=JobStatus.ERROR, detail="Failed")
            finally:
                self._queue.task_done()


queue = JobQueue()
