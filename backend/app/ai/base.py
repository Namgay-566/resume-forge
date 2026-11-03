from typing import Protocol

from app.ai.types import AIRequest, AIResponse


class AIProvider(Protocol):
    """One implementation per vendor (see app/ai/providers/).

    `generate` must ask the model for JSON matching `request.response_model` (using the vendor's
    structured-output feature) and return the raw JSON text with token usage. It raises:
      - AIUnavailableError: missing/invalid credentials, network, rate limit, outage,
      - AIRefusalError: the model declined,
      - AIInvalidOutputError: output truncated, empty or not parseable.
    Pydantic validation happens in AIClient, so every provider is held to the same contract.
    """

    name: str
    model: str

    async def generate(self, request: AIRequest) -> AIResponse: ...
