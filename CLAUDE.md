# ResumeForge — Project Brief

This is the permanent brief for the project. Read it before every task.

## Product

**ResumeForge** is an AI resume builder for **every job seeker in every career and industry**: healthcare, education, finance, marketing, sales, design, engineering, hospitality, skilled trades, government, research, and more. That includes freshers with no work experience and career changers. **The resume is the center of everything.**

ResumeForge is **not** a developer tool. Tech is one industry among many.

### Core features

1. **ATS-friendly resumes and CVs.** Users build resumes that pass applicant tracking systems:
   - Single column layout
   - Standard section headings
   - No tables, images, text boxes, or columns in exports
   - Standard fonts
   - Selectable text
2. **Target role and skill gap report.** Users choose a target role in any field (e.g. Registered Nurse, Financial Analyst, Primary School Teacher, Electrician, Full Stack Developer). The app compares the resume against that role's required skills and produces a skill gap report (e.g. "BLS certification is missing and it is critical for Registered Nurse").
3. **Learning recommendations.** For every gap, the app recommends learning resources and a small, field-appropriate way to practise and show the skill.
4. **Proof and verification.** Users upload proof that fits their field: certificates and licences, portfolios, work samples, publications, live links, references, or code repositories for technical roles. AI reviews the proof like an experienced professional in that field. If it holds up, the skill becomes **Verified** and can be added to the resume with the proof link.
5. **Resume feedback loop.** Every feature must feed back into a better resume.

## Every career, not just tech

- **No tech assumptions anywhere.** Code, UI text, placeholders, examples, empty states, and AI prompts must never assume the user is a developer or works in tech. Use neutral wording ("your work", "a project", "proof") or examples from several fields.
- **Data-driven, not hardcoded.** Skills, target roles, resume sections, section labels, proof types, and verification rules vary by industry. They come from data (seed files and database tables), not from `if tech` branches or hardcoded lists in code.
- **Freshers and career changers are first-class.** No required work-experience section; education, projects, volunteering, and transferable skills must be able to carry a resume.
- **AI reviewers match the field.** Prompts take the user's field and role as input and review as a professional in that field would, not "as a senior developer".

## Architecture (monorepo)

```
/backend             Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic,
                     Pydantic v2, PostgreSQL, JWT auth, pytest
/frontend            React + Vite + TypeScript, Tailwind, shadcn/ui, React Router,
                     TanStack Query, React Hook Form + Zod, Axios
docker-compose.yml   Runs PostgreSQL locally
```

## Rules for the coding agent

### Scope
- Work in small steps. Build **only** what the current prompt asks for.

### Backend layering
- `routers` (HTTP only) → `services` (business logic) → `repositories` / `models` (DB).
- No DB queries inside routers.

### AI integration
- All AI calls go through `backend/app/ai/` behind one provider interface.
- Every AI response must be JSON validated with a Pydantic model. Retry once if invalid.

### Secrets and config
- Never hardcode secrets. Use `.env` and keep `.env.example` updated.

### Recommendations
- Never invent course URLs. Recommendations only come from the curated resources table.

### Code quality
- Type everything: Python type hints, TypeScript `strict` mode.
- Write pytest tests for business logic.

### After each task
1. Summarize what changed.
2. List new env vars.
3. Explain how to test it manually.
