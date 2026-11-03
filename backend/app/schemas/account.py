"""Requests for the Settings page: profile, sign-in, preferences and account deletion."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import ExperienceLevel, PageSize, ResumeTemplate, ResumeType, Spelling
from app.schemas.auth import Password

# Asked for on sensitive changes when the account has a password. No length rule, as on
# login: never reveal the policy to someone guessing.
CurrentPassword = Annotated[str, Field(min_length=1, max_length=128)]
Provider = Literal["github", "google", "linkedin"]


class ProfileUpdate(BaseModel):
    """Only fields present are changed. Send `"linkedin_url": null` to clear it."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    linkedin_url: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, name: str | None) -> str | None:
        if name is None:
            raise ValueError("may not be null")
        if not (stripped := name.strip()):
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("linkedin_url")
    @classmethod
    def check_linkedin(cls, url: str | None) -> str | None:
        if url is None or not (url := url.strip()):
            return None
        bare = url.lower().removeprefix("https://").removeprefix("http://").removeprefix("www.")
        if not bare.startswith("linkedin.com/") or len(bare) <= len("linkedin.com/"):
            raise ValueError("Enter a LinkedIn profile link, like linkedin.com/in/your-name")
        return url


class PasswordChange(BaseModel):
    """Change the password, or set a first one on an account made with Google, LinkedIn or
    GitHub (then `current_password` is omitted)."""

    model_config = ConfigDict(extra="forbid")

    current_password: CurrentPassword | None = None
    new_password: Password


class EmailChangeStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_email: EmailStr
    current_password: CurrentPassword | None = None

    @field_validator("new_email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return email.lower()


class EmailChangeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(pattern=r"^\s*\d{6}\s*$")]


class EmailChangePending(BaseModel):
    new_email: str


class PreferencesUpdate(BaseModel):
    """Only fields present are changed. Nullable ones accept null to go back to "not set"."""

    model_config = ConfigDict(extra="forbid")

    default_resume_type: ResumeType | None = None
    default_experience_level: ExperienceLevel | None = None
    default_template: ResumeTemplate | None = None
    page_size: PageSize | None = None
    spelling: Spelling | None = None
    email_proof_updates: bool | None = None

    @field_validator("default_resume_type", "page_size", "email_proof_updates", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("may not be null")
        return value


class AccountDelete(BaseModel):
    """The user types their email to confirm; and their password, if they have one."""

    model_config = ConfigDict(extra="forbid")

    confirm_email: Annotated[str, Field(min_length=1, max_length=320)]
    current_password: CurrentPassword | None = None
