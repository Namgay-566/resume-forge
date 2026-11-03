"""Deterministic proof rules: ownership, minimum evidence, and the final decision.

The AI judges whether the code demonstrates each skill; these rules decide whether that
judgement is enough to mark the skill verified. Matches the requirements shown on the
roadmap: a repo you own with 10+ meaningful commits over 3+ days and a README.
"""

from dataclasses import dataclass
from typing import Literal

from app.schemas.proof_report import Ownership, ProofCheck, RepoFacts, SkillVerdict

MIN_COMMITS = 10
MIN_COMMIT_DAYS = 3
MIN_README_CHARS = 300
MEANINGFUL_SHARE = 0.25  # of all commits
MEANINGFUL_COMMITS = 20  # or this many, whatever the share (large team repos)
VERIFY_SCORE = 70
REJECT_SCORE = 30

Decision = Literal["verified", "needs_more", "rejected"]


def check_ownership(facts: RepoFacts, owner_login: str, github_username: str | None) -> Ownership:
    total = sum(c.commits for c in facts.contributors)
    if not github_username:
        return Ownership(
            status="unknown",
            detail="Log in with GitHub so we can confirm this repository is yours.",
        )
    me = github_username.lower()
    mine = next((c.commits for c in facts.contributors if c.login.lower() == me), 0)
    share = round(mine / total, 3) if total else None
    if owner_login.lower() == me:
        return Ownership(
            status="confirmed", detail=f"You own {facts.full_name}.", user_commits=mine, share=share
        )
    if mine and (mine >= MEANINGFUL_COMMITS or (share or 0) >= MEANINGFUL_SHARE):
        percent = f" ({share:.0%} of all commits)" if share is not None else ""
        return Ownership(
            status="confirmed",
            detail=f"You authored {mine} commits{percent}.",
            user_commits=mine,
            share=share,
        )
    return Ownership(
        status="failed",
        detail=(
            f"@{github_username} doesn't own {facts.full_name} and authored "
            f"{mine} of its {total} commits. Submit a repo you built, or one where you "
            "wrote a meaningful share of the code."
        ),
        user_commits=mine,
        share=share,
    )


def run_checks(facts: RepoFacts, ownership: Ownership) -> list[ProofCheck]:
    checks: list[ProofCheck] = []
    ownership_status = {"confirmed": "pass", "unknown": "warn", "failed": "fail"}[ownership.status]
    checks.append(
        ProofCheck(
            id="ownership",
            status=ownership_status,  # type: ignore[arg-type]
            title="Repository is yours",
            detail=ownership.detail,
        )
    )

    if facts.fork:
        if facts.ahead_of_parent == 0:
            checks.append(
                ProofCheck(
                    id="fork",
                    status="fail",
                    title="Fork with no original commits",
                    detail=f"This is a fork of {facts.parent} with no commits of its own.",
                )
            )
        elif facts.ahead_of_parent is None:
            checks.append(
                ProofCheck(
                    id="fork",
                    status="warn",
                    title="Fork: couldn't compare with the original",
                    detail=f"Forked from {facts.parent}. We couldn't count your own commits.",
                )
            )
        else:
            checks.append(
                ProofCheck(
                    id="fork",
                    status="pass",
                    title="Fork with original work",
                    detail=f"{facts.ahead_of_parent} commits beyond {facts.parent}.",
                )
            )

    # Commits that count: the user's own if we know them, otherwise the repo's total.
    commits = ownership.user_commits if ownership.user_commits else facts.commit_count
    if facts.fork and facts.ahead_of_parent is not None:
        commits = min(commits, facts.ahead_of_parent)
    checks.append(
        ProofCheck(
            id="commits",
            status="pass" if commits >= MIN_COMMITS else "warn" if commits >= 3 else "fail",
            title=f"{commits} commit{'s' if commits != 1 else ''}",
            detail=f"At least {MIN_COMMITS} meaningful commits show real, incremental work."
            if commits < MIN_COMMITS
            else "Enough history to show incremental work.",
        )
    )
    days = facts.commit_days
    checks.append(
        ProofCheck(
            id="commit_days",
            status="pass" if days >= MIN_COMMIT_DAYS else "warn",
            title=f"Commits on {days} day{'s' if days != 1 else ''}",
            detail="Work spread over several days."
            if days >= MIN_COMMIT_DAYS
            else f"Spread work over at least {MIN_COMMIT_DAYS} days; one big upload looks copied.",
        )
    )
    readme_ok = facts.readme_chars >= MIN_README_CHARS
    checks.append(
        ProofCheck(
            id="readme",
            status="pass" if readme_ok else "warn" if facts.has_readme else "fail",
            title="README explains the project"
            if readme_ok
            else "README is very short"
            if facts.has_readme
            else "No README",
            detail="Explains the project."
            if readme_ok
            else "Describe what the project does, how to run it, and what you built.",
        )
    )
    checks.append(
        ProofCheck(
            id="tests",
            status="pass" if facts.has_tests else "warn",
            gate=False,
            title="Tests found" if facts.has_tests else "No tests found",
            detail="Automated tests are a strong quality signal."
            if facts.has_tests
            else "Adding a few tests makes the repo far more convincing.",
        )
    )
    return checks


@dataclass(frozen=True)
class Outcome:
    status: Decision
    reason: str
    verified_skill_ids: list[object]


def hard_rejection(facts: RepoFacts, checks: list[ProofCheck]) -> str | None:
    """Failures no code review can fix. Returned before spending an AI call."""
    by_id = {c.id: c for c in checks}
    if by_id["ownership"].status == "fail":
        return by_id["ownership"].detail
    if "fork" in by_id and by_id["fork"].status == "fail":
        return by_id["fork"].detail + " Submit your own repository instead."
    if facts.commit_count == 0 or facts.file_count == 0:
        return "The repository is empty."
    return None


def decide(checks: list[ProofCheck], skills: list[SkillVerdict], ai_score: int | None) -> Outcome:
    demonstrated = [s for s in skills if s.verdict == "demonstrated"]
    if ai_score is None:
        return Outcome(
            "needs_more", "The code review couldn't run. Try re-running the analysis later.", []
        )
    if (
        not demonstrated
        and all(s.verdict == "not_demonstrated" for s in skills)
        and ai_score < REJECT_SCORE
    ):
        return Outcome("rejected", "The code doesn't demonstrate the claimed skills.", [])
    failing = [c for c in checks if c.gate and c.status != "pass"]
    if demonstrated and not failing and ai_score >= VERIFY_SCORE:
        names = ", ".join(s.name for s in demonstrated)
        return Outcome("verified", f"Verified: {names}.", [s.skill_id for s in demonstrated])
    reasons = [c.title for c in failing]
    if not demonstrated:
        reasons.append("the claimed skills aren't clearly demonstrated yet")
    elif ai_score < VERIFY_SCORE:
        reasons.append(f"review score {ai_score} is below {VERIFY_SCORE}")
    return Outcome("needs_more", "Almost there. To verify, fix: " + "; ".join(reasons) + ".", [])
