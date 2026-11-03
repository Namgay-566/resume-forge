"""Turn check results and keyword coverage into category scores, an overall score, and a
fix list ranked by how many points each fix would recover."""

from app.schemas.ats import (
    AIReview,
    CategoryKey,
    CategoryScore,
    CheckResult,
    Fix,
    KeywordReport,
    Location,
)

CATEGORY_WEIGHTS: dict[CategoryKey, float] = {
    "formatting": 0.20,
    "keywords": 0.30,
    "impact": 0.25,
    "completeness": 0.25,
}
LABELS: dict[CategoryKey, str] = {
    "formatting": "Formatting",
    "keywords": "Keywords",
    "impact": "Impact",
    "completeness": "Completeness",
}
CREDIT = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
MAX_KEYWORD_FIXES = 5
# Scored fixes first, but always leave room for a few AI suggestions.
MAX_SCORED_FIXES = 12
MAX_AI_FIXES = 3


def _effective_weights(keywords_scored: bool) -> dict[CategoryKey, float]:
    """Without keywords to compare against, spread their weight over the other categories."""
    if keywords_scored:
        return dict(CATEGORY_WEIGHTS)
    others = {k: w for k, w in CATEGORY_WEIGHTS.items() if k != "keywords"}
    total = sum(others.values())
    return {**{k: w / total for k, w in others.items()}, "keywords": 0.0}


def keyword_score(report: KeywordReport) -> float | None:
    total = sum(h.weight for h in report.matched + report.missing)
    if report.source is None or total == 0:
        return None
    return 100 * sum(h.weight for h in report.matched) / total


def score(
    checks: list[CheckResult], keywords: KeywordReport
) -> tuple[int, list[CategoryScore], list[CheckResult]]:
    kw_score = keyword_score(keywords)
    weights = _effective_weights(kw_score is not None)

    categories: list[CategoryScore] = []
    raw: dict[CategoryKey, float] = {}
    scored_checks: list[CheckResult] = []
    for key in CATEGORY_WEIGHTS:
        if key == "keywords":
            value = kw_score
        else:
            in_cat = [c for c in checks if c.category == key]
            total = sum(c.weight for c in in_cat)
            value = 100 * sum(c.weight * CREDIT[c.status] for c in in_cat) / total if total else 100
            for c in in_cat:
                lost = weights[key] * (c.weight / total) * (1 - CREDIT[c.status]) * 100
                scored_checks.append(c.model_copy(update={"points_lost": round(lost, 1)}))
        if value is not None:
            raw[key] = value
        categories.append(
            CategoryScore(
                key=key,
                label=LABELS[key],
                score=None if value is None else round(value),
                weight=round(weights[key], 3),
            )
        )
    overall = round(sum(raw[k] * weights[k] for k in raw))
    return max(0, min(100, overall)), categories, scored_checks


def _severity(points: float, status: str) -> str:
    if status == "fail" and points >= 4:
        return "high"
    if points >= 2 or status == "fail":
        return "medium"
    return "low"


def build_fixes(
    checks: list[CheckResult], keywords: KeywordReport, review: AIReview | None
) -> list[Fix]:
    fixes: list[Fix] = [
        Fix(
            priority=0,
            severity=_severity(c.points_lost, c.status),  # type: ignore[arg-type]
            title=c.title,
            detail=c.detail,
            source="check",
            location=c.location,
            points=c.points_lost,
        )
        for c in checks
        if c.status != "pass" and c.points_lost > 0
    ]

    kw_total = sum(h.weight for h in keywords.matched + keywords.missing)
    if keywords.source and kw_total:
        weight = CATEGORY_WEIGHTS["keywords"]
        context = (
            "the job description" if keywords.source == "job_description" else "your target role"
        )
        for hit in sorted(keywords.missing, key=lambda h: -h.weight)[:MAX_KEYWORD_FIXES]:
            points = round(weight * hit.weight / kw_total * 100, 1)
            fixes.append(
                Fix(
                    priority=0,
                    severity="high"
                    if hit.importance == "required" and points >= 4
                    else "medium"
                    if hit.importance == "required"
                    else "low",
                    title=f"Add '{hit.keyword}' if you have it",
                    detail=f"{context.capitalize()} asks for {hit.keyword}"
                    + (" (preferred)" if hit.importance == "preferred" else "")
                    + ". Add it to Skills and mention where you used it. Don't claim skills "
                    "you don't have; build a small proof project instead.",
                    source="keywords",
                    location=Location(section="skills"),
                    points=points,
                )
            )

    ranked = sorted(fixes, key=lambda f: -(f.points or 0))[:MAX_SCORED_FIXES]
    ai_fixes: list[Fix] = []
    if review:
        order = {"weak": 0, "ok": 1, "strong": 2}
        for section in sorted(review.sections, key=lambda s: order[s.rating]):
            if section.rating == "strong" or not section.suggestions:
                continue
            ai_fixes.append(
                Fix(
                    priority=0,
                    severity="medium" if section.rating == "weak" else "low",
                    title=section.suggestions[0],
                    detail=section.feedback,
                    source="ai",
                    location=Location(section=section.section),
                )
            )
    ranked += ai_fixes[:MAX_AI_FIXES]
    return [f.model_copy(update={"priority": i}) for i, f in enumerate(ranked, 1)]
