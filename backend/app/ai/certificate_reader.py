from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.prompts import render_prompt
from app.ai.types import ImageInput


class CertificateFields(BaseModel):
    is_certificate: bool
    issuer: str | None = None
    recipient_name: str | None = None
    course_name: str | None = None
    issue_date: str | None = None
    credential_id: str | None = None
    verification_url: str | None = None
    skills: list[str] = Field(default_factory=list, max_length=10)


async def read_certificate(
    ai: AIClient, *, text: str | None, image: bytes | None, skills: list[str]
) -> CertificateFields:
    return await ai.generate_structured(
        render_prompt("certificate_user", text=text, skills=skills),
        CertificateFields,
        system=render_prompt("certificate_system"),
        task="certificate_read",
        max_tokens=2000,
        images=(ImageInput(data=image, media_type="image/jpeg"),) if image else (),
    )
