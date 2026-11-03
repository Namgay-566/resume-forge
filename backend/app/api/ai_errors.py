import logging
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, status

from app.ai.errors import (
    AIInputTooLargeError,
    AIInvalidOutputError,
    AIRefusalError,
    AIUnavailableError,
)

logger = logging.getLogger(__name__)


@contextmanager
def ai_http_errors(feature: str) -> Iterator[None]:
    """Turn AI layer failures into user-facing HTTP errors (details go to the log)."""
    try:
        yield
    except AIUnavailableError as exc:
        logger.warning("%s: AI unavailable: %s", feature, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI writing help is temporarily unavailable. Please try again later.",
        ) from exc
    except AIInputTooLargeError as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "This text is too long for the AI to handle."
        ) from exc
    except AIRefusalError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "The AI couldn't help with this text."
        ) from exc
    except AIInvalidOutputError as exc:
        logger.warning("%s: AI output unusable: %s", feature, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The AI returned something unusable. Please try again."
        ) from exc
