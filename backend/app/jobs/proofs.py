"""Worker side of proof analysis. Run with: rq worker proofs --url $REDIS_URL"""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.client import get_ai_client
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.github.client import get_github_client
from app.services.proofs.service import AnalysisDeps, run_proof_analysis
from app.services.storage.files import get_file_storage
from app.services.web.fetch import get_fetcher

logger = logging.getLogger(__name__)

# One loop for the life of the worker process: the cached HTTP clients (AI SDK, GitHub,
# fetcher) are bound to the loop they were first used on.
_loop: asyncio.AbstractEventLoop | None = None


def analyze_proof(proof_id: str) -> None:
    """RQ entry point (sync). Retries after a crash pick up a proof left in 'analyzing'."""
    global _loop
    if _loop is None or _loop.is_closed():
        configure_logging()
        _loop = asyncio.new_event_loop()
    _loop.run_until_complete(run(uuid.UUID(proof_id)))


async def run(proof_id: uuid.UUID) -> None:
    # NullPool: no connections are kept between jobs, so forked work horses never share one.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        deps = AnalysisDeps(
            async_sessionmaker(engine, expire_on_commit=False),
            get_github_client(),
            get_ai_client(),
            get_file_storage(),
            get_fetcher(),
        )
        await run_proof_analysis(proof_id, deps, resume_interrupted=True)
    finally:
        await engine.dispose()
    logger.info("proof_job done proof_id=%s", proof_id)
