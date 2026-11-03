from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.client import AIClient, get_ai_client
from app.api.deps import CurrentUser, SessionDep
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard.service import DashboardService

router = APIRouter(tags=["dashboard"])

AIDep = Annotated[AIClient, Depends(get_ai_client)]


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard(user: CurrentUser, session: SessionDep, ai: AIDep) -> DashboardSummary:
    """Home screen: resume cards with score history, the next best action and roadmap
    progress for the most recently edited resume with a target role. Never calls the AI."""
    return await DashboardService(session, ai).summary(user)
