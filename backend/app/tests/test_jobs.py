"""Proof analysis on the RQ queue: the API only enqueues, a worker does the work."""

import asyncio
import uuid
from typing import Any

import fakeredis
import pytest
from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue, SimpleWorker
from rq.timeouts import TimerDeathPenalty
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.jobs.proofs as proof_jobs
import app.jobs.queue as job_queue
from app.ai.client import AIClient
from app.core.config import get_settings
from app.models import Proof, Skill
from app.models.enums import ProofStatus
from app.services.proofs.service import AnalysisDeps, run_proof_analysis
from app.services.storage.files import get_file_storage
from app.services.web.fetch import get_fetcher
from app.tests.conftest import TEST_DATABASE_URL
from app.tests.test_proofs import (  # noqa: F401  (skills is a fixture)
    REVIEW,
    FakeGitHub,
    FakeRepo,
    ReviewProvider,
    fetch,
    signup,
    skills,
    submit,
    wire,
)


class ThreadWorker(SimpleWorker):
    """SimpleWorker that can run off the main thread: no signal handlers, timer timeouts.
    Production workers are ordinary `rq worker` processes."""

    death_penalty_class = TimerDeathPenalty

    def _install_signal_handlers(self) -> None:
        pass


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeRedis:
    """JOB_QUEUE=rq against an in-memory Redis."""
    server = fakeredis.FakeRedis()
    rq_settings = get_settings().model_copy(update={"job_queue": "rq"})
    monkeypatch.setattr(job_queue, "get_settings", lambda: rq_settings)
    monkeypatch.setattr("redis.Redis.from_url", lambda *a, **k: server)
    return server


async def test_api_enqueues_instead_of_analysing(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],  # noqa: F811
    redis: fakeredis.FakeRedis,
) -> None:
    github = FakeGitHub(FakeRepo())
    wire(github)
    headers = await signup(client, db_session)

    response = await submit(client, headers, skills)

    assert response.status_code == 202
    proof_id = response.json()["id"]
    assert (await fetch(client, headers, proof_id))["status"] == "pending"
    assert github.calls == []  # nothing ran in the API process
    [job] = Queue(job_queue.PROOF_QUEUE, connection=redis).get_jobs()
    assert job.func_name == job_queue.PROOF_JOB and job.args == (proof_id,)
    assert job.timeout == get_settings().job_timeout_seconds and job.retries_left == 2


async def test_worker_runs_the_queued_analysis(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],  # noqa: F811
    redis: fakeredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The worker builds its own engine and clients from settings; point them at test doubles.
    worker_settings = get_settings().model_copy(update={"database_url": TEST_DATABASE_URL})
    monkeypatch.setattr(proof_jobs, "get_settings", lambda: worker_settings)
    github = FakeGitHub(FakeRepo())
    provider = ReviewProvider(REVIEW)
    monkeypatch.setattr(proof_jobs, "get_github_client", lambda: github)
    monkeypatch.setattr(proof_jobs, "get_ai_client", lambda: AIClient(provider))
    wire(github)
    headers = await signup(client, db_session)
    proof_id = (await submit(client, headers, skills)).json()["id"]

    # A real RQ worker, in its own thread (it runs its own event loop, as in production).
    queue = Queue(job_queue.PROOF_QUEUE, connection=redis)
    worker = ThreadWorker([queue], connection=redis)
    await asyncio.to_thread(worker.work, burst=True)

    body = await fetch(client, headers, proof_id)
    assert body["status"] == "verified" and body["score"] == 82
    assert len(provider.requests) == 1
    assert queue.finished_job_registry.count == 1


async def test_a_retry_resumes_an_interrupted_analysis(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],  # noqa: F811
    redis: fakeredis.FakeRedis,
) -> None:
    wire(FakeGitHub(FakeRepo()))
    headers = await signup(client, db_session)
    proof_id = (await submit(client, headers, skills)).json()["id"]
    # The worker died mid-analysis.
    await db_session.execute(update(Proof).values(status=ProofStatus.ANALYZING))
    await db_session.commit()
    analysis = AnalysisDeps(
        async_sessionmaker(db_session.bind, expire_on_commit=False),
        FakeGitHub(FakeRepo()),
        AIClient(ReviewProvider(REVIEW)),
        get_file_storage(),
        get_fetcher(),
    )

    await run_proof_analysis(uuid.UUID(proof_id), analysis)  # inline runner: not its job to resume
    status = await db_session.scalar(select(Proof.status).execution_options(populate_existing=True))
    assert status is ProofStatus.ANALYZING
    await run_proof_analysis(uuid.UUID(proof_id), analysis, resume_interrupted=True)  # queue retry
    assert (await fetch(client, headers, proof_id))["status"] == "verified"


async def test_redis_outage_keeps_the_proof_and_says_so(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],  # noqa: F811
    redis: fakeredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def down(*args: Any, **kwargs: Any) -> None:
        raise RedisConnectionError("connection refused")

    monkeypatch.setattr(Queue, "enqueue", down)
    wire(FakeGitHub(FakeRepo()))
    headers = await signup(client, db_session)

    response = await submit(client, headers, skills)

    assert response.status_code == 503 and "Re-run" in response.json()["detail"]
    [proof] = (await client.get("/api/proofs", headers=headers)).json()
    assert proof["status"] == "pending"  # saved; re-running queues it again
