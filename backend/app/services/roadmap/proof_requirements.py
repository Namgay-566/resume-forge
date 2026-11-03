"""What a user must upload to get a skill verified.

Deliberately deterministic (not AI): the proof reviewer checks against exactly these
requirements, so they must be stable and the same for everyone. The rules live in
services/proofs/rules.json.
"""

from app.schemas.roadmap import ProofRequirement
from app.services.proofs.rules import get_rules, skill_proof_types


def proof_requirement(
    slug: str, category: str, skill_name: str, stored_types: list[str] | None = None
) -> ProofRequirement:
    accepted = skill_proof_types(slug, category, stored_types or [])
    return ProofRequirement(
        accepted=accepted,
        must_include=get_rules().must_include(accepted[0], skill_name, slug),
    )
