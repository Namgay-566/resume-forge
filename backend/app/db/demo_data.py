# ruff: noqa: E501  (sample resume text reads better unwrapped)
"""Demo job seekers from several fields, each with a sample resume. Used by `python -m
app.db.demo` (local testing) and by the demo-user tests. All people are fictional."""

from dataclasses import dataclass
from typing import Any

from app.models.enums import ExperienceLevel, ResumeType


@dataclass(frozen=True)
class DemoUser:
    key: str
    email: str
    name: str
    role_slug: str
    level: ExperienceLevel
    title: str
    data: dict[str, Any]
    resume_type: ResumeType = ResumeType.RESUME


def _person(name: str, email: str, headline: str, location: str) -> dict[str, Any]:
    return {
        "full_name": name,
        "headline": headline,
        "email": email,
        "phone": "+44 7700 900123",
        "location": location,
        "profile_links": [
            {"label": "LinkedIn", "url": f"linkedin.com/in/{name.lower().replace(' ', '-')}"}
        ],
    }


def _skills(*names: str) -> list[dict[str, str]]:
    return [{"name": n} for n in names]


def _entries(kind: str, *items: dict[str, Any]) -> dict[str, Any]:
    return {"id": kind, "kind": kind, "entries": list(items)}


NURSE = DemoUser(
    key="nurse",
    email="nurse@demo.resumeforge.dev",
    name="Priya Shah",
    role_slug="registered-nurse",
    level=ExperienceLevel.MID,
    title="Staff Nurse resume",
    data={
        "personal_info": _person(
            "Priya Shah", "nurse@demo.resumeforge.dev", "Registered Nurse (Adult)", "London, UK"
        ),
        "summary": (
            "Registered Nurse with four years on a busy acute surgical ward, skilled in patient "
            "assessment, medication administration and infection control. Known for calm, "
            "compassionate care and clear handovers."
        ),
        "experience": [
            {
                "company": "St Mary's Hospital",
                "title": "Staff Nurse, Surgical Ward",
                "start_date": "2021-09",
                "is_current": True,
                "bullets": [
                    "Assessed and monitored up to 8 post-operative patients per shift using NEWS2 early warning scores",
                    "Administered medications and IV therapy safely, with zero medication errors in the 2023 audit",
                    "Led infection control on the ward, raising hand hygiene compliance from 82% to 97%",
                    "Mentored 6 student nurses through their surgical placements",
                ],
                "tools_and_skills": ["Electronic health records", "NEWS2"],
            }
        ],
        "education": [
            {
                "institution": "King's College London",
                "degree": "BSc",
                "field_of_study": "Adult Nursing",
                "start_date": "2018-09",
                "end_date": "2021-07",
                "grade": "First Class Honours",
            }
        ],
        "certifications": [
            {
                "name": "NMC Registration",
                "issuer": "Nursing and Midwifery Council",
                "credential_id": "18I2345E",
            },
            {
                "name": "Basic Life Support (BLS)",
                "issuer": "Resuscitation Council UK",
                "issue_date": "2025-02",
            },
        ],
        "skills": _skills(
            "Patient assessment",
            "Medication administration",
            "Infection control",
            "Electronic health records",
            "Communication",
            "Teamwork",
            "Empathy",
        ),
        "sections": [
            {"id": "summary", "kind": "summary"},
            {"id": "certifications", "kind": "certifications"},
            _entries(
                "clinical_experience",
                {
                    "title": "Student Nurse",
                    "organization": "Guy's Hospital",
                    "location": "Cardiology ward",
                    "start_date": "2020-01",
                    "end_date": "2020-06",
                    "bullets": [
                        "Supported cardiac monitoring and patient education for 20 patients"
                    ],
                },
            ),
            {"id": "experience", "kind": "experience"},
            {"id": "education", "kind": "education"},
            {"id": "skills", "kind": "skills"},
        ],
    },
)

TEACHER = DemoUser(
    key="teacher",
    email="teacher@demo.resumeforge.dev",
    name="Daniel Okafor",
    role_slug="primary-school-teacher",
    level=ExperienceLevel.MID,
    title="Primary teacher resume",
    data={
        "personal_info": _person(
            "Daniel Okafor",
            "teacher@demo.resumeforge.dev",
            "Primary School Teacher (QTS)",
            "Manchester, UK",
        ),
        "summary": (
            "Primary teacher with five years in Key Stage 2, confident with lesson planning, "
            "differentiation and assessment. Raised Year 5 reading attainment and built strong "
            "partnerships with parents."
        ),
        "experience": [
            {
                "company": "Oakfield Primary School",
                "title": "Year 5 Class Teacher",
                "start_date": "2020-09",
                "is_current": True,
                "bullets": [
                    "Planned and taught the full Year 5 curriculum for a class of 30 pupils",
                    "Raised the share of pupils reading at the expected standard from 64% to 83% in one year",
                    "Differentiated lessons for 5 pupils with special educational needs, working with the SENCO",
                    "Led termly parent consultations and a weekly home-reading newsletter",
                ],
            }
        ],
        "education": [
            {
                "institution": "University of Manchester",
                "degree": "BEd",
                "field_of_study": "Primary Education",
                "start_date": "2016-09",
                "end_date": "2020-06",
            }
        ],
        "certifications": [
            {"name": "Qualified Teacher Status (QTS)", "issuer": "Teaching Regulation Agency"},
            {
                "name": "Safeguarding training (DBS check)",
                "issuer": "Manchester City Council",
                "issue_date": "2025-09",
            },
        ],
        "skills": _skills(
            "Lesson planning",
            "Classroom management",
            "Student assessment",
            "Differentiated instruction",
            "Parent communication",
            "Safeguarding",
        ),
        "sections": [
            {"id": "summary", "kind": "summary"},
            {"id": "certifications", "kind": "certifications"},
            _entries(
                "teaching_experience",
                {
                    "title": "Trainee Teacher (placement)",
                    "organization": "St Anne's Primary",
                    "start_date": "2019-01",
                    "end_date": "2019-04",
                    "bullets": ["Taught Year 2 phonics and maths to groups of 8"],
                },
            ),
            {"id": "experience", "kind": "experience"},
            {"id": "education", "kind": "education"},
            {"id": "skills", "kind": "skills"},
        ],
    },
)

ACCOUNTANT = DemoUser(
    key="accountant",
    email="accountant@demo.resumeforge.dev",
    name="Mei Chen",
    role_slug="accountant",
    level=ExperienceLevel.ENTRY,
    title="Accountant resume",
    data={
        "personal_info": _person(
            "Mei Chen", "accountant@demo.resumeforge.dev", "Assistant Accountant, ACCA", "Leeds, UK"
        ),
        "summary": (
            "ACCA-qualified assistant accountant with two years in month-end close, "
            "reconciliations and VAT returns for a mid-sized manufacturer."
        ),
        "experience": [
            {
                "company": "Northern Components Ltd",
                "title": "Assistant Accountant",
                "start_date": "2023-08",
                "is_current": True,
                "bullets": [
                    "Prepared monthly management accounts and balance sheet reconciliations for 3 entities",
                    "Cut month-end close from 8 to 5 working days by automating accruals in Excel",
                    "Filed quarterly VAT returns with no HMRC queries across 8 quarters",
                ],
                "tools_and_skills": ["Excel", "Xero", "Sage"],
            }
        ],
        "education": [
            {
                "institution": "University of Leeds",
                "degree": "BSc",
                "field_of_study": "Accounting and Finance",
                "start_date": "2020-09",
                "end_date": "2023-06",
            }
        ],
        "certifications": [{"name": "ACCA", "issuer": "ACCA", "issue_date": "2025-06"}],
        "skills": _skills(
            "Bookkeeping", "Financial reporting", "IFRS", "Excel", "Taxation", "Attention to detail"
        ),
    },
)

MARKETER = DemoUser(
    key="marketer",
    email="marketer@demo.resumeforge.dev",
    name="Sofia Alvarez",
    role_slug="digital-marketing-specialist",
    level=ExperienceLevel.MID,
    title="Digital marketing resume",
    data={
        "personal_info": _person(
            "Sofia Alvarez",
            "marketer@demo.resumeforge.dev",
            "Digital Marketing Specialist",
            "Bristol, UK",
        ),
        "summary": (
            "Digital marketer with five years running paid search, SEO and email campaigns for "
            "e-commerce brands, focused on measurable growth in leads and revenue."
        ),
        "experience": [
            {
                "company": "Bloom Home Goods",
                "title": "Digital Marketing Specialist",
                "start_date": "2021-03",
                "is_current": True,
                "bullets": [
                    "Managed a £40k monthly Google Ads budget at a 4.2x return on ad spend",
                    "Grew organic traffic 65% in a year through an SEO content programme",
                    "Built email journeys that lifted repeat purchase rate from 18% to 26%",
                ],
                "tools_and_skills": ["Google Ads", "Google Analytics", "Mailchimp"],
            }
        ],
        "education": [
            {
                "institution": "University of the West of England",
                "degree": "BA",
                "field_of_study": "Marketing",
                "start_date": "2015-09",
                "end_date": "2018-06",
            }
        ],
        "certifications": [
            {"name": "Google Ads Search Certification", "issuer": "Google", "issue_date": "2025-01"}
        ],
        "skills": _skills(
            "Digital marketing",
            "SEO",
            "Paid advertising",
            "Marketing analytics",
            "Email marketing",
            "Social media marketing",
            "Content writing",
        ),
        "sections": [
            {"id": "summary", "kind": "summary"},
            {"id": "experience", "kind": "experience"},
            _entries(
                "portfolio",
                {
                    "title": "Spring sale campaign case study",
                    "organization": "Bloom Home Goods",
                    "description": "Search, social and email plan with results",
                    "link": "sofiaalvarez.co.uk/spring",
                },
            ),
            {"id": "skills", "kind": "skills"},
            {"id": "education", "kind": "education"},
            {"id": "certifications", "kind": "certifications"},
        ],
    },
)

FRESHER = DemoUser(
    key="fresher",
    email="graduate@demo.resumeforge.dev",
    name="Aisha Rahman",
    role_slug="marketing-coordinator",
    level=ExperienceLevel.STUDENT,
    title="Graduate resume",
    data={
        "personal_info": _person(
            "Aisha Rahman",
            "graduate@demo.resumeforge.dev",
            "Business & Marketing graduate",
            "Birmingham, UK",
        ),
        "summary": (
            "Business and Marketing graduate with a campaign internship, a society leadership "
            "role and hands-on social media experience, looking for a first marketing role."
        ),
        "education": [
            {
                "institution": "University of Birmingham",
                "degree": "BA",
                "field_of_study": "Business and Marketing",
                "start_date": "2022-09",
                "end_date": "2025-06",
                "grade": "2:1",
                "bullets": ["Dissertation: how Gen Z discovers local brands on TikTok"],
            }
        ],
        "projects": [
            {
                "name": "Campus coffee launch plan",
                "description": "Group project: a launch plan for a student-run coffee cart",
                "bullets": [
                    "Planned the social media calendar and wrote 20 posts that reached 6,000 students"
                ],
            }
        ],
        "skills": _skills(
            "Social media marketing",
            "Content writing",
            "Microsoft Office",
            "Organisation",
            "Communication",
        ),
        "sections": [
            {"id": "summary", "kind": "summary"},
            {"id": "education", "kind": "education"},
            {"id": "projects", "kind": "projects"},
            _entries(
                "internships",
                {
                    "title": "Marketing Intern",
                    "organization": "Midlands Arts Festival",
                    "start_date": "2024-06",
                    "end_date": "2024-08",
                    "bullets": [
                        "Coordinated email campaigns to 12,000 subscribers",
                        "Organised 3 influencer visits during festival week",
                    ],
                },
            ),
            {"id": "skills", "kind": "skills"},
            _entries(
                "extracurriculars",
                {
                    "title": "Events Officer",
                    "organization": "Marketing Society",
                    "start_date": "2023-09",
                    "end_date": "2025-06",
                    "bullets": ["Ran 8 industry talks with 60+ attendees each"],
                },
            ),
        ],
    },
)

CAREER_CHANGER = DemoUser(
    key="career_changer",
    email="changer@demo.resumeforge.dev",
    name="James Walker",
    role_slug="project-manager",
    level=ExperienceLevel.CAREER_CHANGER,
    title="Project manager resume",
    data={
        "personal_info": _person(
            "James Walker",
            "changer@demo.resumeforge.dev",
            "Retail manager moving into project management",
            "Glasgow, UK",
        ),
        "summary": (
            "Store manager with ten years leading teams of up to 40, now moving into project "
            "management with the Google Project Management Certificate."
        ),
        "experience": [
            {
                "company": "Northside Retail",
                "title": "Store Manager",
                "start_date": "2015-04",
                "end_date": "2025-08",
                "bullets": [
                    "Led a team of 40 and a £3m annual budget across sales, stock and staffing",
                    "Delivered a full store refit on time and 6% under budget while trading stayed open",
                    "Planned rotas and stock deliveries for 12 peak trading periods a year",
                ],
            }
        ],
        "education": [
            {
                "institution": "Glasgow Caledonian University",
                "degree": "HND",
                "field_of_study": "Business Management",
                "start_date": "2012-09",
                "end_date": "2014-06",
            }
        ],
        "certifications": [
            {
                "name": "Google Project Management Certificate",
                "issuer": "Coursera",
                "issue_date": "2025-07",
            }
        ],
        "skills": _skills(
            "Project management",
            "Budgeting",
            "Leadership",
            "Stakeholder management",
            "Communication",
        ),
    },
)

FULL_STACK_DEV = DemoUser(
    key="fullstack",
    email="usertest@user.com",
    name="Dorji",
    role_slug="full-stack-developer",
    level=ExperienceLevel.MID,
    title="Full Stack Developer Resume",
    data={
        "personal_info": _person(
            "Dorji",
            "usertest@user.com",
            "Full Stack Developer",
            "San Francisco, CA",
        ),
        "summary": (
            "Full Stack Developer with 5 years of experience building scalable web applications "
            "using React, Node.js, and PostgreSQL. Proven track record of improving API performance "
            "and leading frontend migrations. Passionate about clean code, accessibility, and "
            "delivering high-impact features."
        ),
        "experience": [
            {
                "company": "TechNova Solutions",
                "title": "Senior Full Stack Developer",
                "start_date": "2022-03",
                "is_current": True,
                "bullets": [
                    "Led the migration of a legacy Angular app to React, reducing page load time by 45% and increasing user retention by 12%",
                    "Architected and built a microservice in Node.js that processed 2M+ daily requests with 99.99% uptime",
                    "Optimized complex PostgreSQL queries and added Redis caching, cutting database response times from 800ms to 50ms",
                    "Mentored 3 junior developers and established a code review process that reduced production bugs by 30%",
                ],
                "tools_and_skills": [
                    "React",
                    "TypeScript",
                    "Node.js",
                    "PostgreSQL",
                    "Redis",
                    "AWS",
                ],
            },
            {
                "company": "WebSphere Digital",
                "title": "Full Stack Developer",
                "start_date": "2019-06",
                "end_date": "2022-02",
                "bullets": [
                    "Developed and shipped 15+ client-facing features using Python (Django) and Vue.js",
                    "Integrated Stripe payment processing, generating $1.5M in processed transactions in the first year",
                    "Wrote 500+ unit and integration tests using Jest and Pytest, increasing test coverage to 85%",
                ],
                "tools_and_skills": ["Python", "Django", "Vue.js", "Docker", "Git"],
            },
        ],
        "education": [
            {
                "institution": "University of California, Berkeley",
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "start_date": "2015-08",
                "end_date": "2019-05",
                "grade": "GPA 3.8/4.0",
            }
        ],
        "certifications": [
            {
                "name": "AWS Certified Solutions Architect",
                "issuer": "Amazon Web Services",
                "issue_date": "2023-05",
                "credential_id": "AWS-ASA-12345",
            }
        ],
        "skills": _skills(
            "React",
            "TypeScript",
            "Node.js",
            "Python",
            "PostgreSQL",
            "Docker",
            "AWS",
            "REST APIs",
            "GraphQL",
            "Git",
            "Agile",
        ),
    },
)

DEMO_USERS: tuple[DemoUser, ...] = (
    NURSE,
    TEACHER,
    ACCOUNTANT,
    MARKETER,
    FRESHER,
    CAREER_CHANGER,
    FULL_STACK_DEV,
)