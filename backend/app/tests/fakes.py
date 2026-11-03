import uuid

from app.ai.types import AIRequest, AIResponse
from app.models import Industry


class FakeProvider:
    """Mocked AI provider: returns queued JSON strings (or raises queued exceptions)."""

    name = "fake"
    model = "fake-model-1"

    def __init__(self, *responses: str | Exception, input_tokens: int = 100) -> None:
        self.responses = list(responses)
        self.requests: list[AIRequest] = []
        self.input_tokens = input_tokens

    @property
    def prompts(self) -> list[str]:
        return [r.prompt for r in self.requests]

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return AIResponse(
            text=response, model=self.model, input_tokens=self.input_tokens, output_tokens=42
        )


def an_industry() -> Industry:
    """A fresh industry for test roles (every target role needs one)."""
    tag = uuid.uuid4().hex[:8]
    return Industry(slug=f"test-{tag}", name=f"Test industry {tag}")
