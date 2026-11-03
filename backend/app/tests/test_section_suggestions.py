"""Verified proofs are suggested for the section they belong in: publications to
Publications, portfolio pieces to Portfolio, work samples to the job they fit (or Projects),
licences to Licenses & Certifications. Links are printed as plain text."""

import uuid

from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import (
    LicenseInfo,
    PortfolioInfo,
    ProofReport,
    PublicationInfo,
    SkillVerdict,
    UploadInfo,
    UrlCheck,
    WorkSampleInfo,
)
from app.schemas.resume_data import ResumeData
from app.schemas.suggestions import ResumeSuggestion
from app.services.suggestions.engine import ProofView, SkillView, suggest

ASSESS, FALLS, DESIGN = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def view(kind: ProofType, report: ProofReport, url: str | None = None, **kw: object) -> ProofView:
    return ProofView(
        id=kw.get("id", uuid.uuid4()),  # type: ignore[arg-type]
        type=kind,
        status=kw.get("status", ProofStatus.VERIFIED),  # type: ignore[arg-type]
        url=url,
        report=report,
        skill_ids=frozenset(kw.get("skills", ())),  # type: ignore[arg-type]
        created_order=1,
    )


def publication(**overrides: object) -> ProofView:
    info = PublicationInfo(
        input="10.1234/jps.2023.44",
        doi="10.1234/jps.2023.44",
        url="https://doi.org/10.1234/jps.2023.44",
        source="crossref",
        registered=True,
        title="Drought shifts the wheat root microbiome",
        venue="Journal of Plant Science",
        published="2023-03-14",
        authors=["Tomas Novak", "Sarah Hill"],
    )
    report = ProofReport(publication=info, verification_level="verified")
    return view(ProofType.PUBLICATION, report, "https://doi.org/10.1234/jps.2023.44", **overrides)


def portfolio() -> ProofView:
    info = PortfolioInfo(
        url="https://www.behance.net/gallery/123/bakery-rebrand",
        final_url="https://www.behance.net/gallery/123/bakery-rebrand/",
        reachable=True,
        title="Bakery rebrand",
        description="Identity and packaging for a family bakery.",
        platform="Behance",
    )
    report = ProofReport(portfolio=info, verification_level="verified")
    return view(ProofType.PORTFOLIO_LINK, report, info.url)


def work_sample(kind: str = "a falls-prevention care plan") -> ProofView:
    report = ProofReport(
        work_sample=WorkSampleInfo(kind=kind, text_chars=900),
        upload=UploadInfo(filename="care-plan.docx", content_type="application/pdf"),
        skills=[
            SkillVerdict(
                skill_id=ASSESS, name="Patient Assessment", verdict="demonstrated", evidence=[]
            ),  # noqa: E501
            SkillVerdict(
                skill_id=FALLS, name="Falls Prevention", verdict="demonstrated", evidence=[]
            ),  # noqa: E501
            SkillVerdict(
                skill_id=DESIGN, name="Care Planning", verdict="not_demonstrated", evidence=[]
            ),  # noqa: E501
        ],
        summary="A person-centred falls plan for an older patient on a medical ward.",
        verification_level="verified",
    )
    return view(ProofType.WORK_SAMPLE, report, skills={ASSESS, FALLS})


def licence() -> ProofView:
    report = ProofReport(
        license=LicenseInfo(
            license_type="Registered Nurse (Adult)",
            license_number="12A3456E",
            issuing_body="Nursing and Midwifery Council",
            register_check=UrlCheck(
                url="https://www.nmc.org.uk/registration/search", reachable=True
            ),  # noqa: E501
        ),
        verification_level="verified",
    )
    return view(ProofType.PROFESSIONAL_LICENSE, report)


SKILLS = [
    SkillView(ASSESS, "Patient Assessment", frozenset({"patient assessment"})),
    SkillView(FALLS, "Falls Prevention", frozenset({"falls prevention"})),
]
NURSE = {
    "skills": [{"name": "Patient Assessment"}, {"name": "Falls Prevention"}],
    "experience": [
        {"company": "Tesco", "title": "Customer Assistant", "bullets": ["Served customers"]},
        {
            "company": "St Mary's Hospital",
            "title": "Staff Nurse",
            "bullets": ["Assessed patients on a medical ward", "Led falls prevention audits"],
        },
    ],
}


def by_kind(data: dict[str, object], *proofs: ProofView) -> dict[str, ResumeSuggestion]:
    return {s.kind: s for s in suggest(ResumeData.model_validate(data), proofs, SKILLS)}


def test_publication_goes_to_publications_with_its_doi_as_text() -> None:
    proof = publication()

    [found] = suggest(ResumeData(), [proof], [])

    assert found.kind == "add_section_entry" and found.id == f"entry:{proof.id}"
    assert (found.section_kind, found.section_heading) == ("publications", "Publications")
    assert found.entry is not None
    assert found.entry.title == "Drought shifts the wheat root microbiome"
    assert found.entry.organization == "Journal of Plant Science"
    assert found.entry.start_date == "2023-03"
    assert found.entry.description == "Tomas Novak, Sarah Hill"
    assert found.entry.link == "doi.org/10.1234/jps.2023.44"  # plain text, no scheme
    assert found.entry.proof_id == proof.id
    assert found.title == "Add “Drought shifts the wheat root microbiome” to Publications?"


def test_publication_already_listed_is_not_suggested_again() -> None:
    by_link = {
        "sections": [
            {
                "id": "publications",
                "kind": "publications",
                "entries": [{"title": "Old title", "link": "https://doi.org/10.1234/jps.2023.44"}],
            },  # noqa: E501
        ]
    }
    by_title = {
        "sections": [
            {
                "id": "publications",
                "kind": "publications",
                "entries": [{"title": "Drought shifts the wheat root microbiome."}],
            },  # noqa: E501
        ]
    }

    assert suggest(ResumeData.model_validate(by_link), [publication()], []) == []
    assert suggest(ResumeData.model_validate(by_title), [publication()], []) == []


def test_unverified_or_untitled_publications_are_not_suggested() -> None:
    pending = publication(status=ProofStatus.NEEDS_MORE)
    untitled = publication()
    assert untitled.report and untitled.report.publication
    untitled.report.publication.title = None

    assert suggest(ResumeData(), [pending, untitled], []) == []


def test_portfolio_piece_goes_to_portfolio_with_its_link() -> None:
    [found] = suggest(ResumeData(), [portfolio()], [])

    assert found.section_kind == "portfolio" and found.entry is not None
    assert found.entry.title == "Bakery rebrand"
    assert found.entry.link == "behance.net/gallery/123/bakery-rebrand"
    assert found.entry.description == "Identity and packaging for a family bakery."


def test_work_sample_becomes_a_bullet_on_the_job_it_fits() -> None:
    proof = work_sample()

    found = by_kind(NURSE, proof)["add_bullet"]

    assert found.target is not None
    assert found.target.section_id == "experience"
    assert found.target.item_index == 1  # the nursing job, not the shop
    assert found.target.label == "Staff Nurse at St Mary's Hospital"
    assert found.bullet == (
        "Produced a falls-prevention care plan, "
        "demonstrating patient assessment and falls prevention"
    )
    assert "no link is printed" in found.detail


def test_work_sample_can_go_to_clinical_or_teaching_experience() -> None:
    data = {
        "sections": [
            {
                "id": "clinical_experience",
                "kind": "clinical_experience",
                "entries": [
                    {
                        "title": "Student Nurse",
                        "organization": "King's College Hospital",
                        "bullets": ["Supported falls prevention checks for older patients"],
                    },
                ],
            }
        ]
    }

    found = by_kind(data, work_sample())["add_bullet"]

    assert found.target is not None
    assert found.target.section_id == "clinical_experience"
    assert found.target.item_title == "Student Nurse"


def test_work_sample_with_no_matching_job_goes_to_projects() -> None:
    data = {"experience": [{"company": "Tesco", "title": "Customer Assistant"}]}

    found = by_kind(data, work_sample("a lesson plan for Year 5 fractions"))["add_project"]

    project = found.project
    assert project is not None
    assert project.name == "Lesson plan for Year 5 fractions"
    assert project.bullets[0].startswith("Produced a lesson plan for Year 5 fractions")
    assert project.tools_and_skills == ["Patient Assessment", "Falls Prevention"]
    assert project.link is None  # private upload
    assert found.repo_url is None


def test_work_sample_already_added_is_not_suggested_again() -> None:
    proof = work_sample()
    added = {
        **NURSE,
        "experience": [
            {
                "company": "St Mary's Hospital",
                "title": "Staff Nurse",
                "bullets": [
                    "Produced a falls-prevention care plan, demonstrating patient assessment and falls prevention"  # noqa: E501
                ],
            }
        ],
    }
    as_project = {"projects": [{"name": "Care plan", "proof_id": str(proof.id)}]}

    assert "add_bullet" not in by_kind(added, proof)
    assert not {"add_bullet", "add_project"} & set(by_kind(as_project, proof))


def test_licence_still_goes_to_licenses_and_certifications() -> None:
    [found] = suggest(ResumeData(), [licence()], [])

    assert found.kind == "add_certification" and found.certification is not None
    assert found.certification.name == "Registered Nurse (Adult)"
    assert found.certification.credential_url == "https://www.nmc.org.uk/registration/search"
    assert "Licenses & Certifications" in found.title


def test_work_sample_matching_tolerates_word_forms() -> None:
    # "patients"/"patient", "assessed"/"assessment": the demo nurse's real bullets.
    data = {
        "experience": [
            {
                "company": "St Mary's Hospital",
                "title": "Staff Nurse",
                "bullets": ["Assessed and monitored up to 8 post-operative patients per shift"],
            }
        ]
    }

    found = by_kind(data, work_sample())

    assert "add_bullet" in found and "add_project" not in found
