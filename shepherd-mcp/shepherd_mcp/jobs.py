"""In-memory job store for drone pipeline jobs."""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPILING = "compiling"
    CORRECTING = "correcting"
    REVIEWING = "reviewing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class DroneJob:
    job_id: str
    spec: str
    model: str
    project_path: str
    worktree_path: Optional[str] = None
    branch: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    files: dict[str, str] = field(default_factory=dict)       # path → content
    errors: list[str] = field(default_factory=list)
    correction_rounds: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    review_notes: Optional[str] = None
    failure_reason: Optional[str] = None
    feedback: Optional[str] = None                             # set on reject


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, DroneJob] = {}

    def create(self, spec: str, model: str, project_path: str) -> DroneJob:
        job_id = str(uuid.uuid4())
        job = DroneJob(job_id=job_id, spec=spec, model=model, project_path=project_path)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> DroneJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"No job with id {job_id!r}")
        return job

    def all(self) -> list[DroneJob]:
        return list(self._jobs.values())


# Module-level singleton — shared across all tool invocations in a server process
store = JobStore()
