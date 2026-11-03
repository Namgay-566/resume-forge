import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import ExperienceLevel, PageSize, ResumeTemplate, ResumeType, Spelling

Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    name: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return email.lower()

    @field_validator("name")
    @classmethod
    def strip_name(cls, name: str) -> str:
        if not (stripped := name.strip()):
            raise ValueError("name must not be blank")
        return stripped


class LoginRequest(BaseModel):
    email: EmailStr
    # No length rule on login: never tell an attacker what the password policy rejected.
    password: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return email.lower()


class UserPreferences(BaseModel):
    """Defaults for new resumes, export and AI writing, and email choices (Settings)."""

    model_config = ConfigDict(from_attributes=True)

    default_resume_type: ResumeType = ResumeType.RESUME
    default_experience_level: ExperienceLevel | None = None
    # Null: the template recommended for the resume's field.
    default_template: ResumeTemplate | None = None
    page_size: PageSize = PageSize.A4
    # Null: follow the spelling already used in the resume.
    spelling: Spelling | None = None
    email_proof_updates: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    github_username: str | None
    # Signed in with LinkedIn at least once; its public profile URL, when LinkedIn shared it.
    linkedin_connected: bool = False
    linkedin_url: str | None = None
    # How this account can sign in (Settings shows these and never removes the last one).
    has_password: bool = False
    github_connected: bool = False
    google_connected: bool = False
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _nest_preferences(cls, value: Any) -> Any:
        """Read from a User row: preferences are columns on the same row."""
        if isinstance(value, dict):
            return value
        fields = {
            name: getattr(value, name)
            for name in cls.model_fields
            if name != "preferences" and hasattr(value, name)
        }
        return {**fields, "preferences": UserPreferences.model_validate(value)}


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserRead
