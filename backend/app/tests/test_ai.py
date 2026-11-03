"""AI layer unit tests. No network: providers are mocked (FakeProvider) or have their SDK
client replaced with a stub, so these run offline and cost nothing."""

import json
import logging
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from httpx import AsyncClient
from jinja2 import UndefinedError
from pydantic import BaseModel

from app.ai.client import AIClient, generate_structured, get_ai_client
from app.ai.errors import (
    AIInvalidOutputError,
    AIRefusalError,
    AIResponseValidationError,
    AIUnavailableError,
)
from app.ai.prompts import available_prompts, render_prompt
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.factory import build_provider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.resume_parser import section_guide
from app.ai.types import AIRequest
from app.core.config import Settings, get_settings
from app.main import app
from app.tests.fakes import FakeProvider


class Answer(BaseModel):
    city: str
    population: int


VALID = json.dumps({"city": "Thimphu", "population": 115000})


def settings(**overrides: Any) -> Settings:
    return Settings(jwt_secret_key="x" * 40, **overrides)  # type: ignore[arg-type]


# --- generate_structured ----------


async def test_returns_validated_model() -> None:
    provider = FakeProvider(VALID)

    result = await AIClient(provider).generate_structured("Capital of Bhutan?", Answer)

    assert result == Answer(city="Thimphu", population=115000)
    assert provider.requests[0].response_model is Answer
    assert provider.requests[0].prompt == "Capital of Bhutan?"


async def test_retries_once_with_validation_error_in_prompt() -> None:
    provider = FakeProvider(json.dumps({"city": "Thimphu", "population": "lots"}), VALID)

    result = await AIClient(provider).generate_structured("Capital of Bhutan?", Answer)

    assert result.population == 115000
    assert len(provider.requests) == 2
    retry = provider.prompts[1]
    assert retry.startswith("Capital of Bhutan?")  # original prompt kept
    assert "population" in retry and "valid integer" in retry  # the actual Pydantic error
    assert "<validation_error>" in retry  # rendered from prompts/retry_invalid_output.j2


async def test_raises_clean_error_after_one_retry() -> None:
    provider = FakeProvider("not json", '{"city": 1}', VALID)

    with pytest.raises(AIResponseValidationError) as info:
        await AIClient(provider).generate_structured("q", Answer)

    assert len(provider.requests) == 2  # never a third attempt
    assert str(info.value) == "AI response did not match Answer after retrying"
    assert "population" in info.value.errors  # details kept for logs


async def test_truncated_output_is_retried_like_invalid_json() -> None:
    provider = FakeProvider(AIInvalidOutputError("cut off at max_tokens"), VALID)

    result = await AIClient(provider).generate_structured("q", Answer)

    assert result.city == "Thimphu"
    assert "cut off at max_tokens" in provider.prompts[1]


@pytest.mark.parametrize("error", [AIUnavailableError("down"), AIRefusalError("no")])
async def test_outages_and_refusals_are_not_retried(error: Exception) -> None:
    provider = FakeProvider(error, VALID)

    with pytest.raises(type(error)):
        await AIClient(provider).generate_structured("q", Answer)
    assert len(provider.requests) == 1


async def test_system_prompt_and_max_tokens_reach_the_provider() -> None:
    provider = FakeProvider(VALID)

    await AIClient(provider).generate_structured("q", Answer, system="Be terse", max_tokens=500)

    assert provider.requests[0].system == "Be terse"
    assert provider.requests[0].max_tokens == 500


async def test_module_level_function_uses_given_client() -> None:
    provider = FakeProvider(VALID)

    result = await generate_structured("q", Answer, client=AIClient(provider))

    assert result.city == "Thimphu"


# --- logging ----------


@pytest.fixture
def ai_logs(caplog: pytest.LogCaptureFixture):  # type: ignore[no-untyped-def]
    """The "app" logger doesn't propagate to root (avoids duplicate lines), so attach directly."""
    logger = logging.getLogger("app.ai")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="app.ai")
    yield caplog
    logger.removeHandler(caplog.handler)


async def test_logs_token_usage_and_latency_per_call(ai_logs: pytest.LogCaptureFixture) -> None:
    provider = FakeProvider('{"bad": true}', VALID, input_tokens=1234)

    await AIClient(provider).generate_structured("q", Answer, task="unit_test")
    caplog = ai_logs

    calls = [r for r in caplog.records if r.getMessage().startswith("ai_call")]
    assert len(calls) == 2  # one line per provider call, including the failed attempt
    first = calls[0]
    assert first.ai_task == "unit_test"  # type: ignore[attr-defined]
    assert first.ai_provider == "fake"  # type: ignore[attr-defined]
    assert first.ai_input_tokens == 1234  # type: ignore[attr-defined]
    assert first.ai_output_tokens == 42  # type: ignore[attr-defined]
    assert isinstance(first.ai_latency_ms, int)  # type: ignore[attr-defined]
    assert [c.ai_attempt for c in calls] == [1, 2]  # type: ignore[attr-defined]
    assert "input_tokens=1234" in first.getMessage()
    assert any("ai_validation" in r.getMessage() for r in caplog.records)


async def test_failed_calls_are_logged_too(ai_logs: pytest.LogCaptureFixture) -> None:
    provider = FakeProvider(AIUnavailableError("no credentials"))

    with pytest.raises(AIUnavailableError):
        await AIClient(provider).generate_structured("q", Answer)
    caplog = ai_logs

    (record,) = [r for r in caplog.records if r.getMessage().startswith("ai_call")]
    assert record.ai_outcome == "AIUnavailableError"  # type: ignore[attr-defined]
    assert record.levelno == logging.WARNING


# --- prompt templates ----------


def test_all_prompts_are_files_and_render() -> None:
    assert {"resume_parse_system", "resume_parse_user", "retry_invalid_output"} <= set(
        available_prompts()
    )
    assert "<resume>\nHELLO\n</resume>" in render_prompt("resume_parse_user", resume_text="HELLO")
    parse_system = render_prompt("resume_parse_system", sections=section_guide())
    assert "Never invent" in parse_system and "- publications (" in parse_system


def test_missing_prompt_variable_fails_loudly() -> None:
    with pytest.raises(UndefinedError):
        render_prompt("resume_parse_user")


def test_prompt_text_is_not_html_escaped() -> None:
    assert "<b>&</b>" in render_prompt("resume_parse_user", resume_text="<b>&</b>")


# --- provider selection ----------


def test_factory_picks_provider_from_setting() -> None:
    assert isinstance(build_provider(settings(ai_provider="anthropic")), AnthropicProvider)
    assert isinstance(build_provider(settings(ai_provider="openai")), OpenAIProvider)


def test_default_models_and_override() -> None:
    assert build_provider(settings()).model == "claude-opus-5"
    assert build_provider(settings(ai_provider="openai")).model == "gpt-5"
    assert build_provider(settings(ai_provider="openai", ai_model="gpt-x")).model == "gpt-x"


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="ai_provider"):
        settings(ai_provider="llama")


# --- Anthropic provider, SDK stubbed ----------


def _response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.example/v1"))


def stub_anthropic(result: object) -> AnthropicProvider:
    provider = AnthropicProvider(settings(anthropic_api_key="test-key"))

    async def parse(**kwargs: Any) -> object:
        parse.kwargs = kwargs  # type: ignore[attr-defined]
        if isinstance(result, Exception):
            raise result
        return result

    provider._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))  # type: ignore[assignment]
    provider.parse = parse  # type: ignore[attr-defined]
    return provider


def anthropic_message(text: str = VALID, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-opus-5",
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=321, output_tokens=54),
    )


async def test_anthropic_returns_text_and_usage() -> None:
    provider = stub_anthropic(anthropic_message())

    response = await provider.generate(AIRequest(prompt="q", response_model=Answer, system="s"))

    assert (response.text, response.input_tokens, response.output_tokens) == (VALID, 321, 54)
    sent = provider.parse.kwargs  # type: ignore[attr-defined]
    assert sent["output_format"] is Answer
    assert sent["system"] == "s"
    assert sent["fallbacks"] == "default"


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (anthropic_message(stop_reason="refusal"), AIRefusalError),
        (anthropic_message(stop_reason="max_tokens"), AIInvalidOutputError),
        (
            anthropic.RateLimitError("slow down", response=_response(429), body=None),
            AIUnavailableError,
        ),
        (
            anthropic.AuthenticationError("bad key", response=_response(401), body=None),
            AIUnavailableError,
        ),
        (
            anthropic.InternalServerError("boom", response=_response(500), body=None),
            AIUnavailableError,
        ),
        (
            anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")),
            AIUnavailableError,
        ),
        (TypeError("Could not resolve authentication method"), AIUnavailableError),
    ],
)
async def test_anthropic_maps_failures(result: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        await stub_anthropic(result).generate(AIRequest(prompt="q", response_model=Answer))


async def test_anthropic_does_not_hide_unrelated_type_errors() -> None:
    with pytest.raises(TypeError, match="bug"):
        await stub_anthropic(TypeError("a real bug")).generate(
            AIRequest(prompt="q", response_model=Answer)
        )


# --- OpenAI provider, SDK stubbed ----------


def stub_openai(result: object) -> OpenAIProvider:
    provider = OpenAIProvider(settings(ai_provider="openai", openai_api_key="test-key"))

    async def parse(**kwargs: Any) -> object:
        parse.kwargs = kwargs  # type: ignore[attr-defined]
        if isinstance(result, Exception):
            raise result
        return result

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
    )  # type: ignore[assignment]
    provider.parse = parse  # type: ignore[attr-defined]
    return provider


def openai_completion(content: str | None = VALID, refusal: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        model="gpt-5",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=refusal))],
        usage=SimpleNamespace(prompt_tokens=400, completion_tokens=60),
    )


async def test_openai_returns_text_and_usage() -> None:
    provider = stub_openai(openai_completion())

    response = await provider.generate(AIRequest(prompt="q", response_model=Answer, system="s"))

    assert (response.text, response.input_tokens, response.output_tokens) == (VALID, 400, 60)
    sent = provider.parse.kwargs  # type: ignore[attr-defined]
    assert sent["response_format"] is Answer
    assert sent["messages"][0] == {"role": "system", "content": "s"}
    assert sent["max_completion_tokens"] == 16000


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (openai_completion(content=None, refusal="I can't help with that"), AIRefusalError),
        (openai_completion(content=None), AIInvalidOutputError),
        (openai.RateLimitError("quota", response=_response(429), body=None), AIUnavailableError),
        (
            openai.AuthenticationError("bad key", response=_response(401), body=None),
            AIUnavailableError,
        ),
        (
            openai.APIConnectionError(request=httpx2.Request("POST", "https://x")),
            AIUnavailableError,
        ),
    ],
)
async def test_openai_maps_failures(result: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        await stub_openai(result).generate(AIRequest(prompt="q", response_model=Answer))


async def test_openai_without_any_key_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider(settings(ai_provider="openai"))

    with pytest.raises(AIUnavailableError, match="not configured"):
        await provider.generate(AIRequest(prompt="q", response_model=Answer))


# --- per-user rate limiting ----------


async def _user_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Rate"}
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _import(client: AsyncClient, headers: dict[str, str]) -> int:
    # An unsupported file: rejected cheaply after the limiter has counted the call.
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    response = await client.post("/api/resumes/import", files=files, headers=headers)
    return response.status_code


async def test_ai_endpoint_is_rate_limited_per_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "2/minute")
    app.dependency_overrides[get_ai_client] = lambda: AIClient(FakeProvider())
    alice = await _user_headers(client, "alice@example.com")
    bob = await _user_headers(client, "bob@example.com")

    alice_codes = [await _import(client, alice) for _ in range(3)]
    bob_code = await _import(client, bob)

    assert alice_codes == [415, 415, 429]
    assert bob_code == 415  # Bob has his own budget

    response = await client.post(
        "/api/resumes/import", files={"file": ("a.txt", b"x", "text/plain")}, headers=alice
    )
    assert response.status_code == 429
    assert "limit for AI features" in response.json()["detail"]


async def test_rate_limit_does_not_count_unauthenticated_requests(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "1/minute")

    codes = [
        (
            await client.post("/api/resumes/import", files={"file": ("a", b"x", "text/plain")})
        ).status_code
        for _ in range(3)
    ]

    assert codes == [401, 401, 401]  # auth runs first; no AI budget is spent
