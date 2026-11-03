# ruff: noqa: E501  (CV text keeps its real line lengths)
"""Sample CVs from three fields, and what a faithful parse of each looks like. The texts
are also used for a manual check against a real model (see test_import_sections.py)."""

from typing import Any

NURSE_CV = """Priya Shah
Registered Nurse (Adult)
priya.shah@example.com | 07700 900123 | London | linkedin.com/in/priya-shah

Professional Summary
Adult nurse with three years on a busy cardiology ward.

Licenses & Registrations
NMC Registered Nurse (Adult), PIN 12A3456E, 2021
Basic Life Support (BLS), Resuscitation Council UK, 2024

Work Experience
Staff Nurse, St Mary's Hospital, London, Sep 2021 - Present
- Assessed and monitored 8 cardiac patients per shift
- Administered IV medication in line with trust policy

Clinical Placements
Student Nurse, King's College Hospital, A&E, Jan 2021 - Apr 2021
- Triaged walk-in patients under supervision

Education
BSc (Hons) Adult Nursing, King's College London, 2018 - 2021

Volunteer Work
First Aid Volunteer, St John Ambulance, 2017 - 2021
- Provided first aid at community events

Languages
Gujarati - Native
Spanish - Conversational

Professional Memberships
Royal College of Nursing, Member, 2021 - Present

Interests
Half-marathon running and community choir

Referees
Available on request
"""

RESEARCHER_CV = """Dr Tomas Novak
Curriculum Vitae
t.novak@example.ac.uk | ORCID: orcid.org/0000-0002-1825-0097

Research Interests
Soil microbiomes and drought resilience in cereal crops.

Education
PhD Plant Sciences, University of Leeds, 2016 - 2020
Thesis: Root-associated microbes under water stress

Research Experience
Postdoctoral Research Associate, John Innes Centre, 2020 - Present
- Designed field trials across 3 sites
- Analysed amplicon sequencing data in R

Publications
Novak T., Hill S. (2023). Drought shifts the wheat root microbiome. Journal of Plant Science, 12, 44-58. doi.org/10.1234/jps.2023.44
Novak T. (2021). Sampling soil microbes at scale. Methods in Ecology, 8, 101-110.

Conferences & Presentations
Invited talk: Microbes and drought, British Ecological Society Annual Meeting, Edinburgh, Dec 2023

Teaching
Seminar Leader, Plant Biology (Year 2), University of Leeds, 2017 - 2019
- Led weekly seminars for 20 undergraduates

Grants and Fellowships
BBSRC Discovery Fellowship, 2022

Skills
R, Amplicon sequencing, Experimental design

Fieldwork Sites
Rothamsted, Hertfordshire (2021 - 2023)
"""

TEACHER_CV = """Grace Okafor
Primary School Teacher
grace.okafor@example.com | Manchester

Personal Statement
Primary teacher with QTS and five years in Key Stage 2.

Teaching Experience
Year 5 Class Teacher, Oakfield Primary School, Manchester, Sep 2019 - Present
- Raised reading scores for a class of 28 through small-group phonics
- Planned and taught the full KS2 curriculum

Qualifications
PGCE Primary with QTS, University of Manchester, 2018 - 2019
BA English Literature, University of Leeds, 2015 - 2018

Certifications
Qualified Teacher Status (QTS), Department for Education, 2019
Paediatric First Aid, St John Ambulance, 2023

Professional Development
Safeguarding Level 2, NSPCC, 2024
Teaching Phonics with Read Write Inc, Ruth Miskin Training, 2022

Extracurricular Activities
Chess Club Lead, Oakfield Primary School, 2020 - Present
- Run a weekly club for 15 pupils

Awards
Teacher of the Year, Manchester Schools Trust, 2023

DBS
Enhanced DBS check, on the Update Service
"""

# What a faithful parse of each CV looks like: every section kept, known ones in their kind,
# the rest as custom sections under the CV's own heading.
NURSE_PARSED: dict[str, Any] = {
    "document_type": "resume",
    "personal_info": {
        "full_name": "Priya Shah",
        "headline": "Registered Nurse (Adult)",
        "email": "priya.shah@example.com",
        "phone": "07700 900123",
        "location": "London",
        "profile_links": [{"label": "LinkedIn", "url": "linkedin.com/in/priya-shah"}],
    },
    "summary": "Adult nurse with three years on a busy cardiology ward.",
    "experience": [
        {
            "company": "St Mary's Hospital",
            "title": "Staff Nurse",
            "location": "London",
            "start_date": "2021-09",
            "is_current": True,
            "bullets": [
                "Assessed and monitored 8 cardiac patients per shift",
                "Administered IV medication in line with trust policy",
            ],
        }
    ],
    "education": [
        {
            "institution": "King's College London",
            "degree": "BSc (Hons) Adult Nursing",
            "start_date": "2018",
            "end_date": "2021",
        }
    ],
    "certifications": [
        {"name": "NMC Registered Nurse (Adult)", "issuer": "NMC", "issue_date": "2021"},
        {"name": "Basic Life Support (BLS)", "issuer": "Resuscitation Council UK"},
    ],
    "sections": [
        {
            "kind": "clinical_experience",
            "heading": "Clinical Placements",
            "entries": [
                {
                    "title": "Student Nurse",
                    "organization": "King's College Hospital",
                    "location": "A&E",
                    "start_date": "2021-01",
                    "end_date": "2021-04",
                    "bullets": ["Triaged walk-in patients under supervision"],
                }
            ],
        },
        {
            "kind": "volunteer",
            "heading": "Volunteer Work",
            "entries": [
                {
                    "title": "First Aid Volunteer",
                    "organization": "St John Ambulance",
                    "start_date": "2017",
                    "end_date": "2021",
                    "bullets": ["Provided first aid at community events"],
                }
            ],
        },
        {
            "kind": "languages",
            "heading": "Languages",
            "entries": [
                {"title": "Gujarati", "organization": "Native"},
                {"title": "Spanish", "organization": "Conversational"},
            ],
        },
        {
            "kind": "memberships",
            "heading": "Professional Memberships",
            "entries": [
                {
                    "title": "Royal College of Nursing",
                    "organization": "Member",
                    "start_date": "2021",
                    "is_current": True,
                }
            ],
        },
        {
            "kind": "custom",
            "heading": "Interests",
            "entries": [{"title": "Half-marathon running and community choir"}],
        },
        {
            "kind": "custom",
            "heading": "Referees",
            "entries": [{"title": "Available on request"}],
        },
    ],
}

RESEARCHER_PARSED: dict[str, Any] = {
    "document_type": "cv",
    "personal_info": {
        "full_name": "Dr Tomas Novak",
        "email": "t.novak@example.ac.uk",
        "profile_links": [{"label": "ORCID", "url": "orcid.org/0000-0002-1825-0097"}],
    },
    "education": [
        {
            "institution": "University of Leeds",
            "degree": "PhD",
            "field_of_study": "Plant Sciences",
            "start_date": "2016",
            "end_date": "2020",
            "bullets": ["Thesis: Root-associated microbes under water stress"],
        }
    ],
    "skills": ["R", "Amplicon sequencing", "Experimental design"],
    "sections": [
        {
            "kind": "research",
            "heading": "Research Interests",
            "entries": [
                {"description": "Soil microbiomes and drought resilience in cereal crops."}
            ],
        },
        {
            "kind": "research",
            "heading": "Research Experience",
            "entries": [
                {
                    "title": "Postdoctoral Research Associate",
                    "organization": "John Innes Centre",
                    "start_date": "2020",
                    "is_current": True,
                    "bullets": [
                        "Designed field trials across 3 sites",
                        "Analysed amplicon sequencing data in R",
                    ],
                }
            ],
        },
        {
            "kind": "publications",
            "heading": "Publications",
            "entries": [
                {
                    "title": "Drought shifts the wheat root microbiome",
                    "organization": "Journal of Plant Science",
                    "start_date": "2023",
                    "description": "Novak T., Hill S. 12, 44-58",
                    "link": "doi.org/10.1234/jps.2023.44",
                },
                {
                    "title": "Sampling soil microbes at scale",
                    "organization": "Methods in Ecology",
                    "start_date": "2021",
                    "description": "Novak T. 8, 101-110",
                },
            ],
        },
        {
            "kind": "conferences",
            "heading": "Conferences & Presentations",
            "entries": [
                {
                    "title": "Invited talk: Microbes and drought",
                    "organization": "British Ecological Society Annual Meeting",
                    "location": "Edinburgh",
                    "start_date": "2023-12",
                }
            ],
        },
        {
            "kind": "teaching_experience",
            "heading": "Teaching",
            "entries": [
                {
                    "title": "Seminar Leader, Plant Biology (Year 2)",
                    "organization": "University of Leeds",
                    "start_date": "2017",
                    "end_date": "2019",
                    "bullets": ["Led weekly seminars for 20 undergraduates"],
                }
            ],
        },
        {
            "kind": "awards",
            "heading": "Grants and Fellowships",
            "entries": [{"title": "BBSRC Discovery Fellowship", "start_date": "2022"}],
        },
        {
            "kind": "custom",
            "heading": "Fieldwork Sites",
            "entries": [
                {
                    "title": "Rothamsted",
                    "location": "Hertfordshire",
                    "start_date": "2021",
                    "end_date": "2023",
                }
            ],
        },
    ],
}

TEACHER_PARSED: dict[str, Any] = {
    "document_type": "resume",
    "personal_info": {
        "full_name": "Grace Okafor",
        "headline": "Primary School Teacher",
        "email": "grace.okafor@example.com",
        "location": "Manchester",
    },
    "summary": "Primary teacher with QTS and five years in Key Stage 2.",
    "education": [
        {
            "institution": "University of Manchester",
            "degree": "PGCE Primary with QTS",
            "start_date": "2018",
            "end_date": "2019",
        },
        {
            "institution": "University of Leeds",
            "degree": "BA English Literature",
            "start_date": "2015",
            "end_date": "2018",
        },
    ],
    "certifications": [
        {
            "name": "Qualified Teacher Status (QTS)",
            "issuer": "Department for Education",
            "issue_date": "2019",
        },
        {"name": "Paediatric First Aid", "issuer": "St John Ambulance", "issue_date": "2023"},
    ],
    "sections": [
        {
            "kind": "teaching_experience",
            "heading": "Teaching Experience",
            "entries": [
                {
                    "title": "Year 5 Class Teacher",
                    "organization": "Oakfield Primary School",
                    "location": "Manchester",
                    "start_date": "2019-09",
                    "is_current": True,
                    "bullets": [
                        "Raised reading scores for a class of 28 through small-group phonics",
                        "Planned and taught the full KS2 curriculum",
                    ],
                }
            ],
        },
        {
            "kind": "training",
            "heading": "Professional Development",
            "entries": [
                {"title": "Safeguarding Level 2", "organization": "NSPCC", "start_date": "2024"},
                {
                    "title": "Teaching Phonics with Read Write Inc",
                    "organization": "Ruth Miskin Training",
                    "start_date": "2022",
                },
            ],
        },
        {
            "kind": "extracurriculars",
            "heading": "Extracurricular Activities",
            "entries": [
                {
                    "title": "Chess Club Lead",
                    "organization": "Oakfield Primary School",
                    "start_date": "2020",
                    "is_current": True,
                    "bullets": ["Run a weekly club for 15 pupils"],
                }
            ],
        },
        {
            "kind": "awards",
            "heading": "Awards",
            "entries": [
                {
                    "title": "Teacher of the Year",
                    "organization": "Manchester Schools Trust",
                    "start_date": "2023",
                }
            ],
        },
        {
            "kind": "custom",
            "heading": "DBS",
            "entries": [{"title": "Enhanced DBS check, on the Update Service"}],
        },
    ],
}
