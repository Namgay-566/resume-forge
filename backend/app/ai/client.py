import logging
import time
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.errors import (
    AIError,
    AIInputTooLargeError,
    AIInvalidOutputError,
    AIResponseValidationError,
)
from app.ai.prompts import TrustedText, render_prompt
from app.ai.providers.factory import build_provider
from app.ai.types import AIRequest, AIResponse, ImageInput
from app.core.config import get_settings

logger = logging.getLogger("app.ai")

ModelT = TypeVar("ModelT", bound=BaseModel)

MAX_ATTEMPTS = 2  # first try + one retry, per CLAUDE.md
MAX_ERROR_CHARS = 2000  # how much of the validation error to show the model on retry
# Backstop on prompt size (~40k tokens). Callers bound their own inputs well below this;
# this stops a missed limit from turning into a huge bill.
MAX_PROMPT_CHARS = 160_000


class AIClient:
    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[ModelT],
        *,
        system: str | None = None,
        task: str = "generic",
        max_tokens: int = 16000,
        images: tuple[ImageInput, ...] = (),
    ) -> ModelT:
        """Send `prompt` (plus optional images), require JSON matching `response_model`, and
        return the validated model.

        If the output doesn't validate, retry once with the validation error included in the
        prompt. If it still fails, raise AIResponseValidationError. Provider outages
        (AIUnavailableError) and refusals are raised immediately, without a retry.
        """
        if len(prompt) + len(system or "") > MAX_PROMPT_CHARS:
            logger.warning("ai_call task=%s refused: prompt is %d chars", task, len(prompt))
            raise AIInputTooLargeError(f"Prompt for {task} is over {MAX_PROMPT_CHARS} characters")
        attempt_prompt = prompt
        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = AIRequest(
                prompt=attempt_prompt,
                response_model=response_model,
                system=system,
                max_tokens=max_tokens,
                images=images,
            )
            try:
                response = await self._call(request, task=task, attempt=attempt)
                return response_model.model_validate_json(response.text)
            except ValidationError as exc:
                last_error = str(exc)
                self._log_invalid(task, attempt, response_model, last_error)
            except AIInvalidOutputError as exc:  # truncated/empty/unparseable from the provider
                last_error = str(exc)
            if attempt < MAX_ATTEMPTS:
                attempt_prompt = render_prompt(
                    "retry_invalid_output",
                    original_prompt=TrustedText(prompt),
                    error=last_error[:MAX_ERROR_CHARS],
                )
        raise AIResponseValidationError(response_model.__name__, last_error)

    async def _call(self, request: AIRequest, *, task: str, attempt: int) -> AIResponse:
        """One provider call, logged with token usage and latency whatever the outcome."""
        started = time.perf_counter()
        try:
            response = await self.provider.generate(request)
        except AIError as exc:
            self._log_call(task, attempt, type(exc).__name__, started, None, error=str(exc))
            raise
        self._log_call(task, attempt, "ok", started, response)
        return response

    def _log_call(
        self,
        task: str,
        attempt: int,
        outcome: str,
        started: float,
        response: AIResponse | None,
        error: str | None = None,
    ) -> None:
        latency_ms = round((time.perf_counter() - started) * 1000)
        fields = {
            "ai_task": task,
            "ai_provider": self.provider.name,
            "ai_model": response.model if response else self.provider.model,
            "ai_attempt": attempt,
            "ai_outcome": outcome,
            "ai_input_tokens": response.input_tokens if response else None,
            "ai_output_tokens": response.output_tokens if response else None,
            "ai_latency_ms": latency_ms,
        }
        message = " ".join(f"{k.removeprefix('ai_')}={v}" for k, v in fields.items())
        if error:
            message += f" error={error[:300]!r}"
        level = logging.INFO if outcome == "ok" else logging.WARNING
        logger.log(level, "ai_call %s", message, extra=fields)

    def _log_invalid(self, task: str, attempt: int, model: type[BaseModel], error: str) -> None:
        logger.warning(
            "ai_validation task=%s attempt=%d model=%s error=%r",
            task,
            attempt,
            model.__name__,
            error[:300],
        )


@lru_cache
def _default_client() -> AIClient:
    return AIClient(build_provider(get_settings()))


def get_ai_client() -> AIClient:
    """FastAPI dependency returning the configured client. Tests override it."""
    return _default_client()


async def generate_structured(
    prompt: str,
    response_model: type[ModelT],
    *,
    system: str | None = None,
    task: str = "generic",
    max_tokens: int = 16000,
    client: AIClient | None = None,
) -> ModelT:
    """Module-level convenience around AIClient.generate_structured (uses AI_PROVIDER)."""
    return await (client or get_ai_client()).generate_structured(
        prompt, response_model, system=system, task=task, max_tokens=max_tokens
    )
