
# ResumeForge

AI resume builder: ATS-friendly resumes, skill gap reports for a target role, and verified skills backed by proof. See [CLAUDE.md](CLAUDE.md) for the full project brief.

## Layout

```
backend/                  FastAPI + SQLAlchemy (async) + Pydantic v2, RQ worker (app/jobs)
frontend/                 React + Vite + TypeScript + Tailwind + shadcn/ui
docker-compose.yml        PostgreSQL 16 (and optional Redis) for local development
docker-compose.prod.yml   Self-hosted production stack (nginx, API, worker, Postgres, Redis)
.github/workflows/ci.yml  Lint + tests + Docker builds on every push and PR
```

## Prerequisites

- Python 3.11+
- Node.js 20.19+
- Docker with Compose
- For PDF export (WeasyPrint): Pango and standard fonts. On Debian/Ubuntu:
  `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 fonts-liberation`
  (macOS: `brew install pango`). Liberation fonts are metric-compatible with Arial/Times New Roman.

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
alembic upgrade head          # create/update database tables
python -m app.db.seed         # load skills, target roles, learning resources (safe to re-run)
uvicorn app.main:app --reload --port 8000
```

Seed data lives in `backend/app/db/seed_data/*.json`. Run `python -m app.db.seed --check` to validate the JSON without touching the database; it also lists resource URLs marked `"todo"` for manual verification.

Migrations (run from `backend/` with the venv active):

```bash
alembic revision --autogenerate -m "describe change"   # after editing models; review the file
alembic upgrade head                                     # apply
alembic downgrade -1                                     # undo the last migration
alembic check                                            # fails if models and DB have drifted
```

- Health check: <http://localhost:8000/api/health>
- API docs: <http://localhost:8000/docs>

Lint, format, test (tests use a separate `resumeforge_test` database, created automatically; Postgres must be running):

```bash
ruff check .
ruff format .
pytest
```

Dependencies are in `requirements.txt` (runtime) and `requirements-dev.txt` (adds pytest, pytest-asyncio, ruff). `pyproject.toml` holds ruff and pytest config only.

## 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open <http://localhost:5173>, create an account, and you land on `/dashboard`, which shows **Backend connected** when the API is reachable.

## Auth

- `POST /api/auth/register`, `POST /api/auth/login` return a short-lived JWT access token in the body and set an httpOnly refresh cookie (`rf_refresh`, path `/api/auth`).
- `POST /api/auth/refresh` rotates the refresh cookie and returns a new access token. `POST /api/auth/logout` revokes it. `GET /api/me` returns the current user.
- The frontend keeps the access token in memory only and refreshes it automatically on a 401.

### Social sign-in: Google, LinkedIn, GitHub (all optional)

The login and register pages offer **Google, LinkedIn, GitHub**, then email. Each provider works on its own: set its client ID and secret in `backend/.env` and restart the backend. A provider without credentials shows a "not set up" message when clicked. All three use the same flow: the backend redirects to the provider with a `state` cookie, exchanges the code on `/api/auth/<provider>/callback`, finds the user by provider account id (or links an existing account with the same **verified** email, or creates one), and sets the refresh cookie.

#### Google sign-in

1. In the [Google Cloud Console](https://console.cloud.google.com/), create or pick a project.
2. **APIs & Services → OAuth consent screen**: user type *External*, app name, support email. Scopes: `openid`, `email`, `profile` (all non-sensitive). While the app is in *Testing*, add yourself under *Test users*.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type **Web application**.
   - Authorised JavaScript origins: `http://localhost:5173`
   - Authorised redirect URIs: `http://localhost:8000/api/auth/google/callback`
4. Put the Client ID and Client secret in `backend/.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

#### LinkedIn sign-in

1. Create an app at <https://www.linkedin.com/developers/apps> (it needs a LinkedIn company page; any page you admin works for development).
2. **Products** tab: add **Sign In with LinkedIn using OpenID Connect**. This grants the `openid`, `profile` and `email` scopes.
3. **Auth** tab: under *Authorized redirect URLs for your app*, add `http://localhost:8000/api/auth/linkedin/callback`.
4. Copy the Client ID and Primary Client Secret into `backend/.env` as `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET`.

**LinkedIn profile URL:** LinkedIn's sign-in shares your name and email but not your public profile URL (`linkedin.com/in/...`). If it's ever included (the standard OpenID `profile` claim), new and imported resumes start with it in *Profile links*. Otherwise the editor asks LinkedIn users to paste it once, and it's then pre-filled on every new resume.

#### GitHub login

1. Create an OAuth App at <https://github.com/settings/developers> → **New OAuth App**.
   - Homepage URL: `http://localhost:5173`
   - Authorization callback URL: `http://localhost:8000/api/auth/github/callback`
2. Put the Client ID and a generated Client Secret in `backend/.env` as `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`.

GitHub sign-in also lets the Proof Vault confirm that you own the repositories you submit.

Other scripts: `npm test` (Vitest + React Testing Library), `npm run build`, `npm run lint`, `npm run preview`.

## Resume export

`GET /api/resumes/{id}/export?format=pdf|docx&template=classic|modern_minimal|compact` (template defaults to the one saved on the resume).

- PDF: Jinja2 HTML (`backend/app/services/export/templates/`) rendered by WeasyPrint. DOCX: python-docx with the same structure.
- Template styles live in `backend/app/services/export/templates/css/`. The frontend live preview imports these same files (Vite alias `@resume-templates`), so the preview matches the PDF. Edit them there, not in the frontend.
- `app/tests/test_export.py` extracts text from generated PDFs with pdfplumber and checks every section comes out in order.

## AI layer

Everything AI goes through `backend/app/ai/`:

- `AI_PROVIDER=anthropic|openai` picks the implementation in `providers/` (default models `claude-opus-5` / `gpt-5`, override with `AI_MODEL`). Set the matching `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.
- `client.generate_structured(prompt, response_model)` requires JSON (vendor structured outputs), validates it with Pydantic, retries once with the validation error, then raises `AIResponseValidationError`.
- Prompt templates are files in `ai/prompts/*.j2` (rendered with `render_prompt(name, **vars)`; a missing variable raises).
- Each call logs a line like `ai_call task=resume_parse provider=anthropic model=... attempt=1 outcome=ok input_tokens=... output_tokens=... latency_ms=...` (logger `app.ai`).
- AI endpoints share one per-user budget (`AI_RATE_LIMIT`, default `10/hour;30/day`). Counters are in memory per process in development. Production requires `RATE_LIMIT_STORAGE_URI=redis://...`.

Without credentials, AI endpoints return 503 and everything else works. Resume import (`POST /api/resumes/import`, PDF/DOCX up to 5 MB) rejects scanned PDFs with a message asking for a text-based PDF or DOCX.

## ATS analyzer

`POST /api/resumes/{id}/ats-analyses` (optional `job_description`) scores the saved resume 0-100; `GET .../ats-analyses/latest` returns the last result. Results are stored in `ats_analyses` and the score on the resume.

- **Deterministic checks** (`app/services/ats/checks.py`, no AI): sections, contact info, dates, bullet length, action verbs, quantified results, length vs. experience, special characters, export format. Each check reports pass/warn/fail, why, where in the editor, and exactly how many points it costs.
- **Keywords**: from the job description (AI extraction, or a skills-catalog scan if AI is unavailable), otherwise the target role's required skills; matched via normalised text + catalog aliases.
- **AI recruiter review**: section-by-section feedback. Best-effort: without AI the score is still computed and the report says the review was skipped.
- **Score** = Formatting 20% + Keywords 30% + Impact 25% + Completeness 25% (keywords' weight is spread over the others when there's nothing to compare against). Fixes are ranked by points recovered.

## AI writing help

In the editor (all under `POST /api/resumes/{id}/ai/...`, sharing the per-user AI rate limit):

- **Improve** (sparkle button on each experience/project bullet): 3 rewrites as action + what + how + result.
- **Generate summary**: 2 options from the saved resume, aimed at its target role.
- **Tailor to job**: suggestions for a pasted job description (reword bullets, move bullets up, feature or add skills, rewrite the summary) shown as diffs with Accept / Reject / Undo. Nothing is applied unless accepted, and a suggestion is refused if that part of the resume changed since.

The AI never gets to invent metrics: `app/services/writing/guard.py` replaces any number that isn't in your own text with a placeholder like `[X%]`, the editor highlights it, and the ATS check fails until placeholders are filled in. Skills are only suggested for adding when the resume already shows evidence; otherwise they're listed as gaps.

## Skill gap

`GET /api/resumes/{id}/skill-gap` compares the resume with its target role's `role_skills` (409 if the resume has no target role).

- Evidence, strongest first: a **verified** `user_skills` row, then the resume itself (Skills section, per-job/project technologies, or the skill named in the text) or an unverified `user_skills` row, then **AI inference** from bullet text, else **missing**. All matching uses the skills catalog's aliases.
- AI inference may only pick from the role skills still missing, must quote its evidence, and the quote must really appear in the resume. It's cached by resume content, so it only re-runs after edits, and each run counts toward the per-user AI budget; if the budget is spent the report comes back without inferences.
- **Role readiness** = sum(weight × credit) / sum(weight), using each role skill's weight (critical 8-10, important 5-7, nice-to-have 2-3); credit is 100% verified, 75% on resume, 40% inferred, 0 missing.
- `GET /api/skills/{id}/learning-resources` lists curated resources for a skill (from `learning_resources` only).

## Roadmap

`GET /api/resumes/{id}/roadmap` lists every role skill that isn't verified yet, most important first, each with:

- **Learn**: curated `learning_resources` only (free first, beginner -> advanced, shortest first). AI never produces URLs; `app/ai/project_ideas.py` strips any that slip into AI text.
- **Build**: an AI portfolio-project idea tailored to the target role, with what a reviewer will check (`POST .../roadmap/{skill_id}/project`, saved and reused; `?regenerate=true` for a new one; counts toward the AI budget).
- **Prove**: deterministic proof requirements per skill (`app/services/roadmap/proof_requirements.py`), e.g. Git needs a repo with 10+ meaningful commits, feature branches and merged pull requests.
- **Hours**: starter resource (only if the skill is missing) + project estimate.

Progress (`PUT /api/roadmap/{skill_id}` with `not_started | in_progress | done`) is stored per user and skill in `learning_plan_items`, so it carries across resumes. The home screen is described under [Dashboard](#dashboard).

## Dashboard

`GET /api/dashboard` is the home screen, in one request, and it never calls the AI:

- **Resume cards** for the 12 most recently edited resumes. Each shows the latest ATS score and role readiness, how much each changed since the previous point, and a history chart. The chart has both scores on one 0-100 axis, drawn as steps because a score holds until the next check. It has hover values and a table view.
- **History**: ATS points come from `ats_analyses`. Readiness is computed when you view it, so a `readiness_snapshots` row is written only when the value (or the target role) changes. The chart shows the current role only.
- **Next best action** (`app/services/dashboard/next_action.py`, rule-based): create a resume → choose a role → keep going with a skill in progress (unless a critical gap is being skipped for a smaller one) → close the gap worth the most readiness ("HTML/CSS is your biggest gap. Start here.") or prove a skill you already list → run or improve the ATS check → all set.
- **Roadmap progress** for the most recently edited resume that has a target role, plus the latest proof results (from the Proof Vault list, which refreshes while proofs are running).

The frontend caches the dashboard for 30 s (TanStack Query) and refreshes it after resume saves, ATS checks and finished proofs.

## Proofs (GitHub repos)

`POST /api/proofs` (`type: github_repo`, `url`, `skill_ids` 1-5) returns 202 and analyses in the background (FastAPI `BackgroundTasks`): `pending -> analyzing -> verified | needs_more | rejected`. Poll `GET /api/proofs/{id}`; `POST /api/proofs/{id}/reanalyze` re-runs it.

1. **Collect** (GitHub REST API, `GITHUB_API_TOKEN`): metadata, languages, README, file tree, commit count and recent history, contributors, key config files (package.json, requirements.txt, Dockerfile, CI workflows...) and up to 4 sampled source files, within a fixed size budget.
2. **Deterministic rules** (`app/services/proofs/analysis.py`): ownership (you own the repo, or wrote >=25% / >=20 of its commits; needs GitHub login), forks must have original commits, 10+ commits over 3+ days, a real README.
3. **AI review** as a senior developer: per-skill verdict with evidence, code quality notes, red flags, score, suggestions.
4. **Decision**: verified only if every rule passes, a claimed skill is *demonstrated* and the score is 70+. Verified skills are marked `verified` in `user_skills` (and show up in Skill Gap / Roadmap).

Without GitHub login, ownership can't be confirmed, so proofs stop at *needs more*; logging in with GitHub (same email) links the account.

### Certificates and live links

- **Certificates** (`POST /api/proofs/certificate`, multipart PDF/JPG/PNG up to 5 MB): stored under random keys via `app/services/storage/` (local `storage/` dir in dev, S3-compatible in prod with `STORAGE_BACKEND=s3` + boto3) and served only through the owner-checked `GET /api/proofs/{id}/file`. Images are re-encoded (drops EXIF). Text comes from the PDF, or the image goes to the AI vision model; the AI extracts issuer, recipient, course, date, credential ID and verification URL (for text PDFs, IDs/links must literally appear in the document). The name is matched to your account, and the verification link is fetched to confirm it's live, on the issuer's domain or a known credential platform, and shows your name or ID.
- **Live links** (`POST /api/proofs` with `type: live_link`, optional `linked_proof_id`): reachability, final URL, HTTPS, title and meta. Verified only when tied to a verified GitHub proof (the page links to the repo, or the repo's website setting is this site).
- **Verification level** on every proof: *Verified*, *Partially verified*, or *Self-reported* (recorded, not rejected).
- All server-side fetching goes through `app/services/web/fetch.py`, which refuses private, loopback, link-local and reserved addresses on every redirect hop.

## Proofs back into the resume

A finished proof updates `user_skills`, and Skill Gap, Roadmap and the dashboard recompute on their next read. The frontend refreshes them as soon as a proof stops running.

- **Suggestions** (`GET /api/resumes/{id}/suggestions`, rule-based, no AI) appear as cards at the top of the editor: add a verified skill, link a skill you already list to its proof, add a verified repo as a project, or add a certificate to Certifications (with credential ID, plus the verification link only if it was reachable). Rejected proofs are never suggested. **Not now** (`POST .../suggestions/{id}/dismiss`) hides a card for that resume.
- **Project draft** (`POST .../suggestions/project-draft`, uses the AI budget, cached on the proof, `regenerate: true` for a new one): name, description, 2-3 bullets and tech stack from the repo's facts and README. The link always comes from the proof, AI URLs are stripped, and numbers not found in the repo's own text become `[X]` placeholders. You edit the draft before adding it.
- **Exports** print proof links as plain URLs (a project's repo, a certificate's verification link, `Credential ID: …`) with no icons. The optional **Verified skills** line in Skills (`show_verified_skills`) lists proof-linked skills with their links.
- **ATS before/after**: after you accept a card and it saves, the editor re-scores against your last job description with `review: false`. This skips the AI review and costs no AI budget when the JD is unchanged, because the saved keywords are reused. It then shows `old → new (±N)` per category. Every analysis returns `previous` for the comparison. When the AI budget is spent, a check still scores and reports `ai_status: rate_limited` instead of returning 429.

## Background jobs (proof analysis)

Proof analysis (GitHub collection, AI review, certificate checks) runs off the request path.

- `JOB_QUEUE=rq` (required in production): the API enqueues `app.jobs.proofs.analyze_proof` on the `proofs` queue in Redis and returns 202. A worker process does the work: `rq worker proofs --url $REDIS_URL --with-scheduler`. Jobs time out after `JOB_TIMEOUT_SECONDS` and are retried twice (after 30 s and 2 min). A retry resumes a proof left in *analyzing* by a crashed worker. Finished proofs are never redone.
- `JOB_QUEUE=inline` (default, development and tests): the same function runs in the API process after the response.
- If Redis is down when a proof is submitted, the proof is saved as *pending* and the API returns 503 asking the user to re-run it.
- Running the real queue locally: `docker compose --profile redis up -d redis`, then set `JOB_QUEUE=rq` in `backend/.env` and start `rq worker proofs --with-scheduler` from `backend/` alongside uvicorn.

## Security

- **Auth everywhere:** every route except health and the sign-in endpoints needs a bearer token. Every resume and proof lookup is scoped to its owner, and another user's data returns 404. `app/tests/test_security.py` checks both automatically by walking every registered route, so a new route can't skip them unnoticed.
- **Cookies:** the refresh cookie is `HttpOnly`, `Secure` in production, sent only to `/api/auth`, and uses `SameSite` from `COOKIE_SAMESITE`. Refresh and logout also reject requests from origins not in `CORS_ORIGINS` (CSRF).
- **Rate limits** (shared in Redis in production):
  - AI features: per user (`AI_RATE_LIMIT`).
  - Login, register and refresh: per client IP (`AUTH_RATE_LIMIT`).
  - Uploads and exports: per user (`UPLOAD_RATE_LIMIT`, `EXPORT_RATE_LIMIT`).
  - Behind a proxy, uvicorn runs with `--proxy-headers` so limits see the real client IP.
- **Input limits:**
  - Request bodies over `MAX_REQUEST_BYTES` are refused before they're parsed.
  - Resumes have per-list caps (15 bullets per entry, 30 jobs or projects, 100 skills…) and a 60k-character total.
  - Job descriptions are capped at 20k characters, and imports at 30 pages or 60k characters.
  - The AI client refuses any prompt over 160k characters as a backstop.
- **Uploads:**
  - The type comes from the file's own bytes, not its name or declared type.
  - Size is capped at 5 MB. Images are capped at 40 MP and re-encoded, which drops EXIF.
  - Storage keys are random, and filenames are only used as display labels, with path parts, control characters and bidi overrides removed.
  - Files are served only to their owner, with `nosniff` and `no-store`.
- **Prompt injection:**
  - Resume, job description, repo and certificate text sits inside data tags that it can't close: `</resume>` in user text is defanged by the template engine. Every system prompt says that text is data, not instructions.
  - Where the AI's judgement decides an outcome, deterministic checks decide instead. A repo that contains text aimed at the reviewer (`app/ai/safety.py`) fails a gate check and can't be verified, whatever the model says.
  - Certificate IDs, links and recipient names must literally appear in the document.
  - AI output is always schema-validated, and the model never supplies URLs.
- **Headers:**
  - The API sends `nosniff`, `X-Frame-Options: DENY`, `CSP: default-src 'none'`, and HSTS in production. `/docs` is off in production.
  - The bundled nginx serves the SPA with a strict CSP (no inline scripts, no eval).
- **Refusing unsafe production settings:** with `ENVIRONMENT=production`, the app won't start if any of these hold:
  - the cookie isn't secure
  - `CORS_ORIGINS` includes localhost
  - rate limits are in memory
  - jobs run inline
  - `JWT_SECRET_KEY` is still the example value

## Testing and CI

```bash
cd backend && ruff check . && ruff format --check . && pytest   # needs Postgres running
cd frontend && npm run lint && npm test && npm run build
```

`.github/workflows/ci.yml` runs the same on every push and pull request, against a Postgres service container. It also checks that migrations apply cleanly and that both Docker images build.

## Production with Docker (self-hosted)

One VM or container host runs everything behind nginx on a single origin, so there's no CORS and `SameSite=Lax` cookies work.

```bash
cp .env.production.example .env.production   # fill in secrets, domain, AI key, storage
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

- **Services:** `db` (Postgres 16), `redis` (append-only, so queued jobs survive restarts), `migrate` (`alembic upgrade head`, runs before the API starts), `api`, `worker`, and `web` (nginx, serving the SPA and proxying `/api`).
- **TLS:** put a TLS-terminating proxy (Caddy, Traefik or a cloud load balancer) in front of port `HTTP_PORT` (default 80). `COOKIE_SECURE=true` requires HTTPS.
- **Seed data:** load it once with `docker compose -f docker-compose.prod.yml --env-file .env.production run --rm api python -m app.db.seed`.
- **Uploads:** with `STORAGE_BACKEND=local` they're kept in the `uploads` volume. S3-compatible storage is recommended.
- **Images:** `backend/Dockerfile` is multi-stage, runs as a non-root user and includes Pango and Liberation fonts for PDF export. `frontend/Dockerfile` builds from the repo root, because the preview imports the resume CSS from `backend/`.

## Deploying to managed services

A typical setup: **frontend on Vercel or Netlify**, **API and worker on Render or Railway**, **managed PostgreSQL** (Render, Railway, Neon or Supabase), **managed Redis** (Render Key Value, Railway Redis or Upstash), and S3-compatible storage (Cloudflare R2, AWS S3) for uploads.

**1. Database and Redis.** Create both.

- Paste the Postgres connection string into `DATABASE_URL` as-is: `postgres://…?sslmode=require` is converted for asyncpg.
- Use one Redis for the queue (`REDIS_URL=redis://…/0`) and for rate limits (`RATE_LIMIT_STORAGE_URI=redis://…/1`). Upstash needs `rediss://`.

**2. Backend API.** Deploy a Docker service from `backend/` (Render: root directory `backend`, Dockerfile runtime; Railway: service root `backend`).

- Health check path: `/api/health`.
- Pre-deploy or release command: `alembic upgrade head`. Run `python -m app.db.seed` once after the first deploy.
- The platform's `PORT` is picked up automatically. `WEB_CONCURRENCY` sets the number of uvicorn workers (default 2).
- Environment:
  - `ENVIRONMENT=production`
  - `DATABASE_URL`, `REDIS_URL`, `RATE_LIMIT_STORAGE_URI`, `JOB_QUEUE=rq`
  - `JWT_SECRET_KEY` (random, 48+ chars)
  - `COOKIE_SECURE=true`
  - `CORS_ORIGINS` and `FRONTEND_URL` = your frontend URL
  - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
  - `GITHUB_API_TOKEN`
  - `STORAGE_BACKEND=s3` and the `S3_*` settings. Don't use local storage on these platforms: their disks are wiped on every deploy.

**3. Worker.** Deploy a second service from the same image (Render "Background Worker", or a second Railway service).

- Start command: `rq worker proofs --url $REDIS_URL --with-scheduler`.
- Same environment as the API.

**4. Frontend.**

- **Vercel:** set the project root to `frontend`, with framework preset Vite. Keep "Include files outside the root directory" on: the build reads `backend/app/services/export/templates/css`.
- **Netlify:** set the base directory to `frontend`, the build command to `npm run build`, and the publish directory to `frontend/dist`.
- **Env:** `VITE_API_URL=https://<your-api-host>/api`.
- **SPA routing:** add a rewrite of all paths to `/index.html` (`vercel.json` / `netlify.toml` in `frontend/` handle this).

**5. Cookies across domains.** Prefer one site:

- **Custom domains on one site (recommended):** e.g. `app.example.com` for the frontend and `api.example.com` for the API. Keep `COOKIE_SAMESITE=lax`.
- **Different sites:** e.g. `*.vercel.app` with `*.onrender.com`. The browser only sends the refresh cookie cross-site with `COOKIE_SAMESITE=none` (plus `COOKIE_SECURE=true`). Some browsers block third-party cookies anyway, which means users get signed out on reload. Use custom domains for anything real.

**6. Social sign-in (optional).** For each provider you enable, register the production callback with the provider and put the same URL in its redirect variable: `https://<api-host>/api/auth/google/callback` (`GOOGLE_REDIRECT_URI`), `https://<api-host>/api/auth/linkedin/callback` (`LINKEDIN_REDIRECT_URI`), `https://<api-host>/api/auth/github/callback` (`GITHUB_REDIRECT_URI`). Publish the Google consent screen (out of *Testing*) before launch.

## Environment variables

| File | Variable | Default | Purpose |
| --- | --- | --- | --- |
| `.env` | `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `resumeforge` | Postgres container credentials |
| `.env` | `POSTGRES_PORT` | `5432` | Host port for Postgres |
| `backend/.env` | `APP_NAME` | `ResumeForge` | App name in API responses |
| `backend/.env` | `ENVIRONMENT` | `development` | `production` enables the safety checks and HSTS, and disables `/docs` |
| `backend/.env` | `DATABASE_URL` | `postgresql+asyncpg://resumeforge:resumeforge@localhost:5432/resumeforge` | Async SQLAlchemy URL (managed `postgres://…?sslmode=` URLs accepted) |
| `backend/.env` | `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `backend/.env` | `FRONTEND_URL` | `http://localhost:5173` | Where the browser is sent after Google, LinkedIn or GitHub sign-in |
| `backend/.env` | `JWT_SECRET_KEY` | *(required, ≥ 32 chars)* | Signs access tokens. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `backend/.env` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `backend/.env` | `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Refresh cookie lifetime |
| `backend/.env` | `COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `backend/.env` | `COOKIE_SAMESITE` | `lax` | `none` only when frontend and API are on different sites (needs `COOKIE_SECURE=true`) |
| `backend/.env` | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | *(empty)* | Enables Google sign-in |
| `backend/.env` | `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/auth/google/callback` | Must match the OAuth client's redirect URI |
| `backend/.env` | `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | *(empty)* | Enables LinkedIn sign-in |
| `backend/.env` | `LINKEDIN_REDIRECT_URI` | `http://localhost:8000/api/auth/linkedin/callback` | Must match the LinkedIn app's redirect URL |
| `backend/.env` | `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | *(empty)* | Enables GitHub login |
| `backend/.env` | `GITHUB_REDIRECT_URI` | `http://localhost:8000/api/auth/github/callback` | Must match the OAuth App callback URL |
| `backend/.env` | `STORAGE_BACKEND` | `local` | `local` (writes to `STORAGE_LOCAL_DIR`) or `s3` |
| `backend/.env` | `STORAGE_LOCAL_DIR` | `storage` | Where dev uploads are kept (git-ignored) |
| `backend/.env` | `S3_BUCKET` / `S3_ENDPOINT_URL` / `S3_REGION` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | *(empty)* | S3-compatible storage (AWS, R2, MinIO) |
| `backend/.env` | `GITHUB_API_TOKEN` | *(empty)* | GitHub REST API token for proof analysis (60 req/h without) |
| `backend/.env` | `AI_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `backend/.env` | `AI_MODEL` | *(provider default)* | `claude-opus-5` / `gpt-5` unless set |
| `backend/.env` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | *(empty)* | Key for the chosen provider |
| `backend/.env` | `AI_EFFORT` | `medium` | Anthropic only: `low` … `max` |
| `backend/.env` | `AI_TIMEOUT_SECONDS` | `120` | Per-request timeout for AI calls |
| `backend/.env` | `AI_RATE_LIMIT` | `10/hour;30/day` | Per-user limit on AI endpoints |
| `backend/.env` | `RATE_LIMIT_STORAGE_URI` | `memory://` | Rate-limit counter storage (`redis://…`, required in production) |
| `backend/.env` | `AUTH_RATE_LIMIT` | `10/minute;100/hour` | Per-IP limit on login/register/refresh |
| `backend/.env` | `UPLOAD_RATE_LIMIT` | `20/hour;60/day` | Per-user limit on certificate uploads and resume imports |
| `backend/.env` | `EXPORT_RATE_LIMIT` | `60/hour` | Per-user limit on PDF/DOCX exports |
| `backend/.env` | `MAX_REQUEST_BYTES` | `6291456` | Largest accepted request body |
| `backend/.env` | `JOB_QUEUE` | `inline` | `rq` (Redis + worker, required in production) or `inline` |
| `backend/.env` | `REDIS_URL` | `redis://localhost:6379/0` | Job queue connection |
| `backend/.env` | `JOB_TIMEOUT_SECONDS` | `600` | Max run time of one proof analysis |
| `backend/.env` (tests) | `TEST_DATABASE_URL` | `DATABASE_URL` with db `resumeforge_test` | Database used by pytest |
| `frontend/.env` | `VITE_API_URL` | `http://localhost:8000/api` | Backend base URL used by Axios (baked in at build time) |
| `.env.production` | see `.env.production.example` | | Settings for `docker-compose.prod.yml` |
| host (Docker) | `PORT` / `WEB_CONCURRENCY` | `8000` / `2` | API port and uvicorn worker count in the container |
