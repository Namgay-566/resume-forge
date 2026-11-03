import base64
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class ImageInput:
    """An image for vision-capable models (JPEG/PNG bytes, already size-limited)."""

    data: bytes
    media_type: str  # "image/jpeg" or "image/png"

    @property
    def base64(self) -> str:
        return base64.standard_b64encode(self.data).decode("ascii")


@dataclass(frozen=True)
class AIRequest:
    prompt: str
    response_model: type[BaseModel]
    system: str | None = None
    max_tokens: int = 16000
    images: tuple[ImageInput, ...] = ()


@dataclass(frozen=True)
class AIResponse:
    """Raw provider output: JSON text plus what the call cost."""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
