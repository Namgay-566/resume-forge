from pydantic import BaseModel

from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import KindSpec, ProfileLinkType


class SectionCatalogRead(BaseModel):
    kinds: list[KindSpec]
    # Kinds of profile link, with placeholders for the editor.
    profile_links: list[ProfileLinkType]


class SectionSuggestions(BaseModel):
    # Suggested layout, in order.
    sections: list[SectionKind]
    # Sections the ATS checker requires for this role and career stage.
    required: list[SectionKind]
    role_name: str | None = None
