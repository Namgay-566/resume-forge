from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.ai.rate_limit import limiter, rate_limit_exceeded_handler
from app.api.routers import (
    ats,
    auth,
    dashboard,
    employment,
    health,
    proofs,
    referee,
    resume_sections,
    resumes,
    roadmap,
    skill_gap,
    suggestions,
    target_roles,
    users,
    writing,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    # No interactive docs or schema in production: less surface, nothing to scrape.
    docs = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Lets the frontend read the download filename.
        expose_headers=["Content-Disposition"],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    # Outermost, so even CORS preflights and 413s carry the headers.
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=settings.is_production,
        docs_paths=("/docs", "/openapi.json") if docs else (),
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(resumes.router, prefix="/api")
    app.include_router(target_roles.router, prefix="/api")
    app.include_router(target_roles.industries_router, prefix="/api")
    app.include_router(resume_sections.router, prefix="/api")
    app.include_router(ats.router, prefix="/api")
    app.include_router(writing.router, prefix="/api")
    app.include_router(skill_gap.router, prefix="/api")
    app.include_router(roadmap.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(proofs.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api")
    app.include_router(referee.router, prefix="/api")
    app.include_router(employment.router, prefix="/api")
    return app


app = create_app()
