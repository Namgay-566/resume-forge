import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.db.types import PydanticJSONB
from app.schemas.resume_data import ExperienceItem, ResumeData

DIALECT = postgresql.dialect()


def full_resume_payload() -> dict[str, object]:
    return {
        "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
        "summary": "Full stack developer.",
        "experience": [
            {
                "company": "Acme",
                "title": "Engineer",
                "start_date": "2022-01",
                "end_date": "2024-06",
                "bullets": ["Shipped the billing service"],
                "tools_and_skills": ["Python", "PostgreSQL"],
            }
        ],
        "education": [{"institution": "MIT", "degree": "BSc", "start_date": "2018-09"}],
        "projects": [
            {
                "name": "ResumeForge",
                "description": "AI resume builder",
                "tools_and_skills": ["FastAPI", "React"],
                "link": "https://github.com/example/resumeforge",
                "proof_id": str(uuid.uuid4()),
            }
        ],
        "skills": [{"name": "Git"}],
        "certifications": [{"name": "AWS Cloud Practitioner", "proof_id": None}],
        "achievements": ["Hackathon winner 2023"],
    }


def test_empty_resume_is_valid() -> None:
    data = ResumeData()

    assert data.experience == []
    assert data.personal_info.full_name == ""


def test_full_resume_round_trips_through_json() -> None:
    data = ResumeData.model_validate(full_resume_payload())

    assert ResumeData.model_validate(data.model_dump(mode="json")) == data
    assert isinstance(data.projects[0].proof_id, uuid.UUID)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ResumeData.model_validate({"photo_url": "https://example.com/me.png"})


@pytest.mark.parametrize("bad_date", ["2024-13", "2024-1", "Jan 2024", "2024-03-01"])
def test_dates_must_be_year_month(bad_date: str) -> None:
    with pytest.raises(ValidationError):
        ExperienceItem(company="Acme", title="Engineer", start_date=bad_date)


def test_end_date_cannot_precede_start_date() -> None:
    with pytest.raises(ValidationError, match="end_date must not be before start_date"):
        ExperienceItem(company="Acme", title="Engineer", start_date="2024-05", end_date="2023-01")


def test_current_role_cannot_have_end_date() -> None:
    with pytest.raises(ValidationError, match="is_current"):
        ExperienceItem(company="Acme", title="Engineer", is_current=True, end_date="2024-01")


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ResumeData.model_validate({"personal_info": {"email": "not-an-email"}})


def test_column_type_validates_dicts_on_write() -> None:
    column_type = PydanticJSONB(ResumeData)

    stored = column_type.process_bind_param(full_resume_payload(), DIALECT)

    assert stored is not None
    assert stored["skills"] == [{"name": "Git", "skill_id": None, "proof_id": None}]


def test_column_type_rejects_invalid_data_on_write() -> None:
    column_type = PydanticJSONB(ResumeData)

    with pytest.raises(ValidationError):
        column_type.process_bind_param({"experience": [{"company": "Acme"}]}, DIALECT)


def test_column_type_returns_model_on_read() -> None:
    column_type = PydanticJSONB(ResumeData)
    stored = column_type.process_bind_param(
        ResumeData.model_validate(full_resume_payload()), DIALECT
    )

    loaded = column_type.process_result_value(stored, DIALECT)

    assert isinstance(loaded, ResumeData)
    assert loaded.projects[0].name == "ResumeForge"


def test_copy_title_stays_within_limit() -> None:
    from app.services.resume_service import MAX_TITLE_LENGTH, copy_title

    assert copy_title("CV") == "CV (copy)"
    assert len(copy_title("x" * MAX_TITLE_LENGTH)) == MAX_TITLE_LENGTH
