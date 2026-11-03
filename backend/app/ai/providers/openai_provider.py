import openai
from pydantic import ValidationError

from app.ai.errors import AIInvalidOutputError, AIRefusalError, AIUnavailableError
from app.ai.types import AIRequest, AIResponse
from app.core.config import Settings

# Change with AI_MODEL; must be a model that supports structured outputs.
DEFAULT_MODEL = "gpt-5"


class OpenAIProvider:
    """OpenAI via the official SDK, using structured outputs (strict JSON schema from Pydantic)."""

    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._api_key = (
            settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        )
        self._timeout = settings.ai_timeout_seconds
        self._client: openai.AsyncOpenAI | None = None
        self.model = settings.ai_model or DEFAULT_MODEL

    def _get_client(self) -> openai.AsyncOpenAI:
        # Built lazily: the SDK raises at construction when no key exists (OPENAI_API_KEY env
        # is used if the setting is empty), and that must surface as "not configured", not crash.
        if self._client is None:
            try:
                self._client = openai.AsyncOpenAI(
                    api_key=self._api_key or None, timeout=self._timeout
                )
            except openai.OpenAIError as exc:
                raise AIUnavailableError("OpenAI is not configured (no API key)") from exc
        return self._client

    async def generate(self, request: AIRequest) -> AIResponse:
        messages: list[dict[str, object]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        if request.images:
            parts: list[dict[str, object]] = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{i.media_type};base64,{i.base64}"},
                }
                for i in request.images
            ]
            messages.append(
                {"role": "user", "content": [*parts, {"type": "text", "text": request.prompt}]}
            )
        else:
            messages.append({"role": "user", "content": request.prompt})
        try:
            completion = await self._get_client().chat.completions.parse(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                response_format=request.response_model,
                max_completion_tokens=request.max_tokens,
            )
        except openai.LengthFinishReasonError as exc:
            raise AIInvalidOutputError("Output was cut off at max_completion_tokens") from exc
        except openai.ContentFilterFinishReasonError as exc:
            raise AIRefusalError("The response was blocked by the content filter") from exc
        except ValidationError as exc:
            raise AIInvalidOutputError(str(exc)) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise AIUnavailableError("OpenAI credentials are missing or invalid") from exc
        except openai.RateLimitError as exc:
            raise AIUnavailableError("OpenAI rate limit or quota reached") from exc
        except openai.BadRequestError as exc:
            raise AIUnavailableError(f"OpenAI rejected the request: {exc.message}") from exc
        except openai.APIStatusError as exc:
            raise AIUnavailableError(f"OpenAI API error ({exc.status_code})") from exc
        except openai.APIConnectionError as exc:
            raise AIUnavailableError("Could not reach the OpenAI API") from exc

        message = completion.choices[0].message
        if message.refusal:
            raise AIRefusalError("The model declined this request")
        if not message.content:
            raise AIInvalidOutputError("The model returned no content")
        usage = completion.usage
        return AIResponse(
            text=message.content,
            model=completion.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
