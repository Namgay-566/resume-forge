import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class EmploymentCheckStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: Annotated[str, Field(min_length=1, max_length=200)]
    email: Annotated[str, Field(min_length=3, max_length=320)]


class EmploymentCheckConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(pattern=r"^\s*\d{6}\s*$")]


class EmploymentCheckRead(BaseModel):
    id: uuid.UUID
    company: str
    # j•••@stmarys.nhs.uk: enough to recognise, not the full address.
    email_masked: str
    email_domain: str
    # Whether the domain plausibly belongs to the company (shown as a hint, not a gate).
    domain_matches_company: bool
    verified: bool
    verified_at: datetime | None
    code_sent_at: datetime | None
    code_expires_at: datetime | None
