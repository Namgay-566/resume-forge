import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ResourceType


class LearningResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    provider: str
    url: str
    type: ResourceType
    level: str
    is_free: bool
    est_hours: Decimal | None


class SkillResources(BaseModel):
    skill_id: uuid.UUID
    skill_name: str
    resources: list[LearningResourceRead]
    # Shown when there are no curated resources: something to search for, never a link.
    search_phrase: str
