# One image, two roles: the API (default command) and the proof worker
# (`rq worker proofs --url $REDIS_URL`). Build from this folder: docker build -t resumeforge-api backend

FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install -r requirements.txt

FROM python:3.12-slim
# WeasyPrint (PDF export) needs Pango; Liberation fonts are metric-compatible with the
# templates' Arial and Times New Roman.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
       fonts-liberation fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
ENV PATH="/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 WEB_CONCURRENCY=2
COPY --from=build /venv /venv
WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
# Local file storage (STORAGE_BACKEND=local) writes here; mount a volume or use S3 in production.
RUN mkdir -p /app/storage && chown app:app /app/storage
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)"
# --proxy-headers: client IPs (auth rate limits) and https come from the load balancer.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
