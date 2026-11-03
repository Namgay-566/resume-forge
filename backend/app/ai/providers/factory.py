from app.ai.base import AIProvider
from app.core.config import Settings


def build_provider(settings: Settings) -> AIProvider:
    """Pick the implementation from AI_PROVIDER."""
    # Imported lazily so only the chosen vendor's SDK is loaded.
    if settings.ai_provider == "openai":
        from app.ai.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    from app.ai.providers.anthropic_provider import AnthropicProvider

    return AnthropicProvider(settings)
