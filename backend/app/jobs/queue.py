"""Where proof analysis runs. The API only enqueues; it never waits for the analysis."""

import uuid
from typing import Protocol

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.services.proofs.service import AnalysisDeps, run_proof_analysis

PROOF_QUEUE = "proofs"
PROOF_JOB = "app.jobs.proofs.analyze_proof"


class QueueUnavailableError(Exception):
    """The job couldn't be queued (Redis down). The proof stays pending; re-running retries."""


class ProofQueue(Protocol):
    def enqueue(self, proof_id: uuid.UUID) -> None: ...


class InlineProofQueue:
    """Runs the analysis in the API process after the response is sent. Dev and tests only:
    a restart loses queued work, and analyses compete with requests for CPU."""

    def __init__(self, background: BackgroundTasks, deps: AnalysisDeps) -> None:
        self.background = background
        self.deps = deps

    def enqueue(self, proof_id: uuid.UUID) -> None:
        self.background.add_task(run_proof_analysis, proof_id, self.deps)


class RQProofQueue:
    """Hands the analysis to an RQ worker through Redis. Survives API restarts, retries after
    a worker crash, and scales separately from the API."""

    def __init__(self, redis_url: str, timeout: int) -> None:
        from redis import Redis
        from rq import Queue

        self.queue = Queue(PROOF_QUEUE, connection=Redis.from_url(redis_url))
        self.timeout = timeout

    def enqueue(self, proof_id: uuid.UUID) -> None:
        from redis.exceptions import RedisError
        from rq import Retry

        try:
            self._enqueue(proof_id, Retry(max=2, interval=[30, 120]))
        except RedisError as exc:
            raise QueueUnavailableError(str(exc)) from exc

    def _enqueue(self, proof_id: uuid.UUID, retry: object) -> None:
        self.queue.enqueue(
            PROOF_JOB,
            str(proof_id),
            job_id=f"proof-{proof_id}-{uuid.uuid4().hex[:8]}",
            job_timeout=self.timeout,
            retry=retry,
            result_ttl=3600,
            failure_ttl=7 * 24 * 3600,
        )


def build_proof_queue(background: BackgroundTasks, deps: AnalysisDeps) -> ProofQueue:
    settings = get_settings()
    if settings.job_queue == "rq":
        return RQProofQueue(settings.redis_url, settings.job_timeout_seconds)
    return InlineProofQueue(background, deps)
