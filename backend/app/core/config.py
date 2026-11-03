from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ResumeForge"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://resumeforge:resumeforge@localhost:5432/resumeforge"
    cors_origins: str = "http://localhost:5173"
    # Where the backend redirects the browser after GitHub login.
    frontend_url: str = "http://localhost:5173"

    # Auth. No default for the secret: the app must not start with a guessable key.
    jwt_secret_key: Annotated[SecretStr, Field(min_length=32)]
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    # Must be true in production (HTTPS). False lets the cookie work on http://localhost.
    cookie_secure: bool = False
    # "lax" when the frontend and API share a site (app.example.com + api.example.com).
    # "none" only if they're on different sites (e.g. *.vercel.app + *.onrender.com);
    # that requires COOKIE_SECURE=true.
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # GitHub OAuth (optional). Login with GitHub is disabled unless both are set.
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    # Google and LinkedIn sign-in (optional, OpenID Connect). Each is disabled unless its
    # client id and secret are both set.
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    linkedin_client_id: str | None = None
    linkedin_client_secret: SecretStr | None = None
    linkedin_redirect_uri: str = "http://localhost:8000/api/auth/linkedin/callback"
    # GitHub REST API token for repo analysis (fine-grained, public-repo read access is enough).
    # Optional: without it the API allows only 60 requests/hour per server IP.
    github_api_token: SecretStr | None = None

    # Uploaded proof files. "local" writes under STORAGE_LOCAL_DIR (dev); "s3" uses any
    # S3-compatible store (AWS S3, Cloudflare R2, MinIO) and needs boto3 installed.
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None  # None for AWS; set for R2/MinIO
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None

    # AI. AI_PROVIDER picks the vendor; AI_MODEL overrides that vendor's default model.
    ai_provider: Literal["anthropic", "openai"] = "anthropic"
    ai_model: str | None = None
    # With no key, each SDK falls back to its own credential discovery; if nothing is found,
    # AI endpoints return 503.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    # Anthropic only: low | medium | high | xhigh | max.
    ai_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    ai_timeout_seconds: float = 120
    # Per-user limit on AI endpoints (slowapi syntax, ";"-separated), and where counters live.
    # memory:// is per-process; use redis://host:6379 when running several workers.
    ai_rate_limit: str = "10/hour;30/day"
    rate_limit_storage_uri: str = "memory://"
    # Per client IP on login/register/refresh (brute force), per user on uploads and exports.
    auth_rate_limit: str = "10/minute;100/hour"
    # Token refresh runs on every page load; it's cookie-authenticated (not guessable), so it
    # only needs a loose abuse limit, not the tight password-guessing one.
    refresh_rate_limit: str = "120/minute"
    upload_rate_limit: str = "20/hour;60/day"
    export_rate_limit: str = "60/hour"
    # Referee requests (emails to someone else) per user, and employer-email codes per user.
    referee_rate_limit: str = "5/day;20/month"
    employment_code_rate_limit: str = "5/hour;10/day"
    # The public referee page (no sign-in), per client IP.
    referee_page_rate_limit: str = "30/hour"

    # Outgoing email (referee requests, work-email codes). "console" logs messages instead
    # of sending them (dev); "smtp" sends through SMTP_HOST.
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "ResumeForge <no-reply@localhost>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    # "starttls" (port 587), "ssl" (port 465) or "none" (a local relay only).
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_timeout_seconds: float = 15

    # Requests larger than this are refused before they're read (uploads are 5 MB + form).
    max_request_bytes: int = 6 * 1024 * 1024

    # Background jobs (proof analysis). "rq" runs them on a separate worker via Redis
    # (`rq worker proofs`); "inline" runs them in the API process (dev and tests only).
    job_queue: Literal["inline", "rq"] = "inline"
    redis_url: str = "redis://localhost:6379/0"
    job_timeout_seconds: int = 600

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, value: str) -> str:
        """Accept the URL managed Postgres hosts hand out (Render, Railway, Neon, Supabase):
        postgres:// or postgresql:// with ?sslmode=..., which asyncpg spells ?ssl=..."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value.replace("sslmode=", "ssl=")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        """Refuse to start in production with settings that are only safe on localhost."""
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        if not self.is_production:
            return self
        problems = []
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if any("localhost" in o or "127.0.0.1" in o for o in self.cors_origin_list):
            problems.append("CORS_ORIGINS must not include localhost")
        if self.email_backend != "smtp":
            problems.append("EMAIL_BACKEND must be smtp")
        if self.rate_limit_storage_uri.startswith("memory://"):
            problems.append("RATE_LIMIT_STORAGE_URI must be shared (redis://...)")
        if self.job_queue == "inline":
            problems.append("JOB_QUEUE must be rq")
        if "change-me" in self.jwt_secret_key.get_secret_value():
            problems.append("JWT_SECRET_KEY is still the example value")
        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def github_enabled(self) -> bool:
        return _configured(self.github_client_id, self.github_client_secret)

    @property
    def google_enabled(self) -> bool:
        return _configured(self.google_client_id, self.google_client_secret)

    @property
    def linkedin_enabled(self) -> bool:
        return _configured(self.linkedin_client_id, self.linkedin_client_secret)


def _configured(client_id: str | None, secret: SecretStr | None) -> bool:
    return bool(client_id and secret and secret.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required fields come from the environment
