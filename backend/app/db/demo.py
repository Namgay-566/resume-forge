"""Seed demo job seekers (a nurse, a teacher, an accountant, a marketer, a fresh graduate and
a career changer), each with a sample resume, for local testing.

Usage (from backend/, after `python -m app.db.seed`):
    DEMO_PASSWORD=... python -m app.db.demo

Idempotent: re-running resets each demo user's resume to the sample. Refuses to run in
production, and the password comes from the environment, never from code.
"""

import asyncio
import os

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.demo_data import DEMO_USERS, DemoUser
from app.models import Resume, TargetRole, User
from app.schemas.resume import ResumeCreate
from app.schemas.resume_data import ResumeData
from app.services.resume_service import ResumeService
from app.services.sections.layout import with_layout
from app.services.sections.service import SectionService


class DemoSeedError(Exception):
    pass


async def seed_demo_user(session: AsyncSession, demo: DemoUser, password: str) -> Resume:
    role_id = await session.scalar(select(TargetRole.id).where(TargetRole.slug == demo.role_slug))
    if role_id is None:
        raise DemoSeedError(f"role {demo.role_slug!r} not found: run `python -m app.db.seed` first")
    user = await session.scalar(select(User).where(User.email == demo.email))
    if user is None:
        user = User(email=demo.email, name=demo.name, hashed_password=hash_password(password))
        session.add(user)
    else:
        user.name, user.hashed_password = demo.name, hash_password(password)
    await session.flush()
    await session.execute(delete(Resume).where(Resume.user_id == user.id))
    data = ResumeData.model_validate(demo.data)
    if "sections" not in demo.data:  # lay it out the way a new resume for the role would be
        layout, _ = await SectionService(session).suggest(
            user, role_id=role_id, level=demo.level, resume_type=demo.resume_type
        )
        data = with_layout(data, layout)
    # Through the normal service, so the template and checks are what a real user gets.
    return await ResumeService(session).create_resume(
        user,
        ResumeCreate(
            title=demo.title,
            type=demo.resume_type,
            target_role_id=role_id,
            experience_level=demo.level,
            data=data,
        ),
    )


async def run(password: str) -> None:
    from app.db.session import SessionLocal, engine

    try:
        async with SessionLocal() as session:
            for demo in DEMO_USERS:
                resume = await seed_demo_user(session, demo, password)
                print(f"{demo.key:<15} {demo.email:<34} {demo.role_slug} ({resume.template})")
    finally:
        await engine.dispose()


def main() -> None:
    from app.core.config import get_settings

    if get_settings().is_production:
        raise SystemExit("Refusing to create demo users in production.")
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 8:
        raise SystemExit("Set DEMO_PASSWORD (8+ characters) to seed demo users.")
    asyncio.run(run(password))


if __name__ == "__main__":
    main()
