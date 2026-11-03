"""How a proof was verified, in words for its badge: "Verified by referee", "Verified via
GitHub", "Self-reported". The level alone ("Verified") hides the difference between a
public register and a referee's word; the method makes every badge honest about it."""

import uuid

from app.models.enums import ProofType
from app.schemas.proof_report import ProofReport, VerificationLevel

# What checked it, per proof type (and per source where one type has several).
_SOURCE = {
    ProofType.GITHUB_REPO: "via GitHub",
    ProofType.LIVE_LINK: "via its GitHub repository",
    ProofType.CERTIFICATE: "on the issuer's site",
    ProofType.PROFESSIONAL_LICENSE: "on the public register",
    ProofType.PORTFOLIO_LINK: "via the portfolio page",
    ProofType.PUBLICATION: "via the DOI registry",
    ProofType.REFEREE_CONFIRMATION: "by referee",
}


def method_label(
    proof_type: ProofType, level: VerificationLevel | None, report: ProofReport | None
) -> str | None:
    """None while it's running or if it was rejected (there's nothing to claim)."""
    if level is None:
        return None
    if level == "self_reported" or proof_type not in _SOURCE:
        # Work samples and letters: reviewed, but nobody independent confirmed them.
        return "Self-reported"
    source = _SOURCE[proof_type]
    publication = report.publication if report else None
    if proof_type is ProofType.PUBLICATION and publication and publication.source == "page":
        source = "via the publisher's page"
    if level == "verified":
        return f"Verified {source}"
    personal = report is not None and report.referee_domain_kind == "free"
    if proof_type is ProofType.REFEREE_CONFIRMATION and personal:
        return "Partly verified by referee (personal email)"
    return f"Partly verified {source}"


def verified_skill_ids(skill_ids: set[uuid.UUID], report: ProofReport | None) -> set[uuid.UUID]:
    """The skills a verified proof actually verified: those judged "demonstrated" when the
    review judged skills one by one (repos, work samples, referee answers), else all the
    proof's skills (a licence or certificate covers what it's for)."""
    if report and report.skills:
        return {v.skill_id for v in report.skills if v.verdict == "demonstrated"}
    return skill_ids
