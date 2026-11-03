class AIError(Exception):
    """Base class for AI layer failures. Messages are safe to log, not to show users verbatim."""


class AIUnavailableError(AIError):
    """The provider can't be reached or isn't configured (no credentials, outage, rate limit)."""


class AIInvalidOutputError(AIError):
    """The model's output was unusable (truncated, empty, or not valid JSON)."""


class AIResponseValidationError(AIInvalidOutputError):
    """Output still didn't match the response model after the retry.

    `errors` holds the last Pydantic error list for logs and debugging.
    """

    def __init__(self, model_name: str, errors: str) -> None:
        super().__init__(f"AI response did not match {model_name} after retrying")
        self.model_name = model_name
        self.errors = errors


class AIRefusalError(AIError):
    """The model declined the request."""


class AIInputTooLargeError(AIError):
    """The prompt is over the size limit; it was never sent."""
