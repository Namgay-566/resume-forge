# ResumeForge — Project Brief

This is the permanent brief for the project. Read it before every task.

## Product

**ResumeForge** is an AI resume builder. **The resume is the center of everything.**

### Core features

1. **ATS-friendly resumes and CVs.** Users build resumes that pass applicant tracking systems:
   - Single column layout
   - Standard section headings
   - No tables, images, text boxes, or columns in exports
   - Standard fonts
   - Selectable text
2. **Target role and skill gap report.** Users choose a target role (e.g. Full Stack Developer). The app compares the resume against that role's required skills and produces a skill gap report (e.g. "Git is missing and it is critical for Full Stack Developer").
3. **Learning recommendations.** For every gap, the app recommends learning resources and a small proof project.
4. **Proof and verification.** Users upload proof: GitHub repo links, live project links, certificate PDFs/images. AI reviews the proof like a senior developer. If it holds up, the skill becomes **Verified** and can be added to the resume with the proof link.
5. **Resume feedback loop.** Every feature must feed back into a better resume.

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
