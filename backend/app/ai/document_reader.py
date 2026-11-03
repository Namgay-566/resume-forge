"""Read licences and reference/experience letters: extract their details exactly as printed."""

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.prompts import render_prompt
from app.ai.types import ImageInput


def _images(image: bytes | None) -> tuple[ImageInput, ...]:
    return (ImageInput(data=image, media_type="image/jpeg"),) if image else ()


class LicenseFields(BaseModel):
    is_license: bool
    license_type: str | None = None
    holder_name: str | None = None
    license_number: str | None = None
    issuing_body: str | None = None
    jurisdiction: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    register_url: str | None = None
    skills: list[str] = Field(default_factory=list, max_length=10)


async def read_license(
    ai: AIClient, *, text: str | None, image: bytes | None, skills: list[str]
) -> LicenseFields:
    return await ai.generate_structured(
        render_prompt("license_user", text=text, skills=skills),
        LicenseFields,
        system=render_prompt("license_system"),
        task="license_read",
        max_tokens=2000,
        images=_images(image),
    )


class LetterSkill(BaseModel):
    skill: str
    quote: str = Field(max_length=300)


class LetterFields(BaseModel):
    is_letter: bool
    letter_kind: Literal["reference", "experience", "recommendation", "other"] | None = None
    writer_name: str | None = None
    writer_title: str | None = None
    organization: str | None = None
    date: str | None = None
    subject_name: str | None = None
    relationship: str | None = None
    has_contact_details: bool = False
    skills: list[LetterSkill] = Field(default_factory=list, max_length=12)


async def read_letter(
    ai: AIClient, *, text: str | None, image: bytes | None, skills: list[str]
) -> LetterFields:
    return await ai.generate_structured(
        render_prompt("letter_user", text=text, skills=skills),
        LetterFields,
        system=render_prompt("letter_system"),
        task="letter_read",
        max_tokens=2500,
        images=_images(image),
    )
