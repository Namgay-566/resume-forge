# ResumeForge

AI resume builder: ATS-friendly resumes, skill gap reports for a target role, and verified skills backed by proof. See [CLAUDE.md](CLAUDE.md) for the full project brief.

## Layout

```
backend/             FastAPI + SQLAlchemy (async) + Pydantic v2
frontend/            React + Vite + TypeScript + Tailwind + shadcn/ui
docker-compose.yml   PostgreSQL 16 for local development
```

## Prerequisites

- Python 3.11+
- Node.js 20.19+
- Docker with Compose

## 1. Database

```bash
cp .env.example .env          # optional: override Postgres credentials/port
docker compose up -d db
docker compose ps             # wait for "healthy"
```

## 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

- Health check: <http://localhost:8000/api/health>
- API docs: <http://localhost:8000/docs>

Lint, format, test:

```bash
ruff check .
ruff format .
pytest
```

Dependencies are in `requirements.txt` (runtime) and `requirements-dev.txt` (adds pytest, httpx, ruff). `pyproject.toml` holds ruff and pytest config only.

## 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>. The dashboard at `/app` shows **Backend connected** when the API is reachable.

Other scripts: `npm run build`, `npm run lint`, `npm run preview`.

## Environment variables

| File | Variable | Default | Purpose |
| --- | --- | --- | --- |
| `.env` | `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `resumeforge` | Postgres container credentials |
| `.env` | `POSTGRES_PORT` | `5432` | Host port for Postgres |
| `backend/.env` | `APP_NAME` | `ResumeForge` | App name in API responses |
| `backend/.env` | `ENVIRONMENT` | `development` | Runtime environment label |
| `backend/.env` | `DATABASE_URL` | `postgresql+asyncpg://resumeforge:resumeforge@localhost:5432/resumeforge` | Async SQLAlchemy URL |
| `backend/.env` | `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `frontend/.env` | `VITE_API_URL` | `http://localhost:8000/api` | Backend base URL used by Axios |
