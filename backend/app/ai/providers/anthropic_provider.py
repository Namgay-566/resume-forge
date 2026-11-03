import anthropic
from pydantic import ValidationError

from app.ai.errors import AIInvalidOutputError, AIRefusalError, AIUnavailableError
from app.ai.types import AIRequest, AIResponse
from app.core.config import Settings

DEFAULT_MODEL = "claude-opus-5"
# On a policy decline, the API re-runs the request on a fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _content(request: AIRequest) -> str | list[dict[str, object]]:
    if not request.images:
        return request.prompt
    # Images first, then the instructions (Anthropic's recommended order).
    blocks: list[dict[str, object]] = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": i.media_type, "data": i.base64},
        }
        for i in request.images
    ]
    return [*blocks, {"type": "text", "text": request.prompt}]


class AnthropicProvider:
    """Claude via the official SDK, using structured outputs (JSON schema from Pydantic)."""

    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        # With no key the SDK resolves other credentials (ANTHROPIC_AUTH_TOKEN, `ant` profiles).
        self._client = anthropic.AsyncAnthropic(
            api_key=key or None, timeout=settings.ai_timeout_seconds
        )
        self.model = settings.ai_model or DEFAULT_MODEL
        self._effort = settings.ai_effort

    async def generate(self, request: AIRequest) -> AIResponse:
        try:
            response = await self._client.beta.messages.parse(
                model=self.model,
                max_tokens=request.max_tokens,
                messages=[{"role": "user", "content": _content(request)}],
                output_format=request.response_model,
                output_config={"effort": self._effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                **({"system": request.system} if request.system else {}),
            )
        except ValidationError as exc:  # SDK parsed the JSON but it didn't fit the schema
            raise AIInvalidOutputError(str(exc)) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise AIUnavailableError("Anthropic credentials are missing or invalid") from exc
        except anthropic.RateLimitError as exc:
            raise AIUnavailableError("Anthropic rate limit reached") from exc
        except anthropic.BadRequestError as exc:
            raise AIUnavailableError(f"Anthropic rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise AIUnavailableError(f"Anthropic API error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise AIUnavailableError("Could not reach the Anthropic API") from exc
        except TypeError as exc:
            # SDK 1.x raises this at request time when no credentials can be resolved.
            if "authentication" not in str(exc).lower():
                raise
            raise AIUnavailableError("Anthropic is not configured (no credentials)") from exc

        if response.stop_reason == "refusal":
            raise AIRefusalError("The model declined this request")
        if response.stop_reason == "max_tokens":
            raise AIInvalidOutputError("Output was cut off at max_tokens")
        text = next((block.text for block in response.content if block.type == "text"), None)
        if not text:
            raise AIInvalidOutputError("The model returned no text")
        return AIResponse(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
