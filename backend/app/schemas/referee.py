"""Referee confirmation: what the candidate asks a referee to confirm, the referee's
answers (never shown to the candidate), and the API bodies."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.resume_data import YearMonth

# Names, roles and organisations go into an email to someone else: plain words only.
_LINKISH = re.compile(r"https?://|www\.|[<>]|\.(?:com|net|org|io|ru|xyz|top)\b", re.IGNORECASE)


def _plain(value: str) -> str:
    value = " ".join(value.split())
    if _LINKISH.search(value):
        raise ValueError("Use plain words here, without links or web addresses.")
    return value


PlainText = Annotated[str, Field(min_length=1, max_length=120)]
OrgText = Annotated[str, Field(min_length=1, max_length=200)]
DomainKind = Literal["company", "free"]
RequestStatus = Literal["sent", "confirmed", "declined", "expired", "failed"]
Relationship = Literal["manager", "colleague", "client", "teacher", "other"]


class ClaimedSkill(BaseModel):
    id: uuid.UUID
    name: str


class RefereeClaim(BaseModel):
    """What the referee is asked to confirm (a snapshot: later resume edits don't change it)."""

    role_title: str
    organization: str
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    skills: list[ClaimedSkill]


class SkillAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: uuid.UUID
    confirmed: bool
    comment: Annotated[str, Field(max_length=300)] = ""


class RefereeAnswers(BaseModel):
    """The referee's response. Stored for the record; the candidate only ever sees the
    outcome (verified or not, and which skills were verified)."""

    model_config = ConfigDict(extra="forbid")

    role_confirmed: bool
    dates_confirmed: bool
    relationship: Relationship
    skills: Annotated[list[SkillAnswer], Field(max_length=5)]
    comment: Annotated[str, Field(max_length=1000)] = ""
    # The referee ticks "This is accurate to the best of my knowledge".
    attested: bool

    @model_validator(mode="after")
    def check_attested(self) -> Self:
        if not self.attested:
            raise ValueError("Please confirm your answers are accurate.")
        return self


class RefereeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referee_name: PlainText
    referee_role: PlainText
    referee_organization: OrgText
    referee_email: Annotated[str, Field(min_length=3, max_length=320)]
    role_title: PlainText
    organization: OrgText
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    is_current: bool = False
    skill_ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=5)]

    @field_validator(
        "referee_name", "referee_role", "referee_organization", "role_title", "organization"
    )
    @classmethod
    def plain(cls, value: str) -> str:
        return _plain(value)

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.is_current:
            self.end_date = None
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The end date is before the start date.")
        return self


class RefereeRequestInfo(BaseModel):
    """What the candidate sees about their request: who and when, never the answers."""

    referee_name: str
    referee_role: str
    referee_organization: str
    # The domain only (the candidate typed the address; it isn't repeated back in full).
    email_domain: str
    domain_kind: DomainKind
    domain_matches_organization: bool
    status: RequestStatus
    sent_at: datetime | None
    expires_at: datetime | None
    responded_at: datetime | None
    can_resend: bool
    claim: RefereeClaim


class RefereePage(BaseModel):
    """What the referee sees on the one-time page."""

    candidate_name: str
    referee_name: str
    claim: RefereeClaim
    expires_at: datetime


class RefereeDecline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["dont_know", "cant_confirm", "not_me"]
    # Never email this address again, for anyone.
    stop_emails: bool = False
