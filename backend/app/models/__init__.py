"""Import every model here so Base.metadata is complete for Alembic and mappers resolve."""

from app.models.ats_analysis import ATSAnalysis
from app.models.industry import Industry
from app.models.learning_plan import LearningPlanItem
from app.models.learning_resource import LearningResource
from app.models.proof import Proof, proof_skills
from app.models.readiness_snapshot import ReadinessSnapshot
from app.models.refresh_token import RefreshToken
from app.models.resume import Resume
from app.models.skill import Skill, UserSkill
from app.models.skill_group import SkillGroup
from app.models.target_role import RoleSkill, TargetRole
from app.models.user import EmailChangeRequest, User
from app.models.verification import EmailSuppression, EmploymentEmailCheck, RefereeRequest

__all__ = [
    "ATSAnalysis",
    "EmailChangeRequest",
    "EmailSuppression",
    "EmploymentEmailCheck",
    "Industry",
    "LearningPlanItem",
    "LearningResource",
    "Proof",
    "ReadinessSnapshot",
    "RefereeRequest",
    "RefreshToken",
    "Resume",
    "RoleSkill",
    "Skill",
    "SkillGroup",
    "TargetRole",
    "User",
    "UserSkill",
    "proof_skills",
]
