from typing import TYPE_CHECKING

from sqlalchemy import SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.target_role import TargetRole


class Industry(UUIDPrimaryKeyMixin, Base):
    """A field of work (Healthcare, Education, Skilled Trades...). Every target role has one."""

    __tablename__ = "industries"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Display order in the role picker.
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # Suggested resume sections (SectionKind values) in order, and ones the ATS requires.
    default_sections: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )
    required_sections: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )
    # Who reviews proof for this field, e.g. "a senior nurse and clinical educator".
    reviewer_persona: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )
    # The results people in this field are judged on ("patient outcomes, safety..."), so
    # AI writing help uses the field's language rather than generic or tech metrics.
    # Profile links to suggest on resumes in this field, by label ("LinkedIn", "ORCID"...).
    profile_links: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list, server_default=text("'{}'")
    )
    # Resume template suggested for the field (a ResumeTemplate value).
    recommended_template: Mapped[str] = mapped_column(
        String(32), nullable=False, default="classic", server_default=text("'classic'")
    )
    impact_language: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )

    roles: Mapped[list["TargetRole"]] = relationship(back_populates="industry", lazy="raise")
