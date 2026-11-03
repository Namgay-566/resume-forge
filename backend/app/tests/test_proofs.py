import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIUnavailableError
from app.ai.proof_review import ProofReview
from app.ai.types import AIRequest, AIResponse
from app.main import app
from app.models import Proof, Skill, User, UserSkill
from app.schemas.proof_report import Contributor, Ownership, ProofCheck, RepoFacts, SkillVerdict
from app.services.github.client import (
    GitHubRateLimitedError,
    RepoNotFoundError,
    TreeEntry,
    get_github_client,
)
from app.services.github.urls import InvalidRepoUrlError, parse_repo_url
from app.services.proofs.analysis import check_ownership, decide, hard_rejection, run_checks
from app.services.proofs.collect import is_test_path, pick_config_files, pick_source_files

# --- URL validation -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "full_name"),
    [
        ("https://github.com/octo/hello-world", "octo/hello-world"),
        ("github.com/octo/hello.js.git", "octo/hello.js"),
        ("https://www.github.com/octo/app/tree/main/src", "octo/app"),
        ("http://github.com/Octo-Cat/repo_1/", "Octo-Cat/repo_1"),
    ],
)
def test_valid_repo_urls(url: str, full_name: str) -> None:
    assert parse_repo_url(url).full_name == full_name


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/a/b",
        "https://github.com/octo",
        "https://gist.github.com/octo/abc",
        "https://github.com/settings/profile",
        "https://github.com/-bad/x",
        "javascript:alert(1)",
        "https://github.com.evil.com/a/b",
        "",
        "ftp://github.com/a/b",
    ],
)
def test_invalid_repo_urls(url: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        parse_repo_url(url)


# --- ownership, checks and decision -----------------------------------------------------------


def facts(**overrides: Any) -> RepoFacts:
    base: dict[str, Any] = dict(
        full_name="ada/tracker",
        url="https://github.com/ada/tracker",
        description=None,
        default_branch="main",
        fork=False,
        stars=0,
        created_at=None,
        pushed_at=None,
        languages={"Python": 100.0},
        commit_count=15,
        commit_days=5,
        contributors=[Contributor(login="ada", commits=15)],
        file_count=20,
        tree_truncated=False,
        has_readme=True,
        readme_chars=800,
        has_tests=True,
        has_ci=False,
        has_docker=False,
        key_files=[],
        sampled_files=[],
    )
    return RepoFacts(**{**base, **overrides})


def test_ownership_rules() -> None:
    team = facts(
        contributors=[
            Contributor(login="lead", commits=60),
            Contributor(login="Ada", commits=25),
            Contributor(login="bob", commits=15),
        ]
    )

    assert check_ownership(facts(), "ada", None).status == "unknown"
    assert check_ownership(facts(), "ADA", "ada").status == "confirmed"  # case-insensitive
    assert check_ownership(team, "lead", "ada").status == "confirmed"  # 25 commits >= 20
    small = facts(
        contributors=[Contributor(login="lead", commits=40), Contributor(login="ada", commits=3)]
    )
    denied = check_ownership(small, "lead", "ada")
    assert denied.status == "failed" and "3 of its 43 commits" in denied.detail
    share = facts(
        contributors=[Contributor(login="x", commits=9), Contributor(login="ada", commits=4)]
    )
    assert check_ownership(share, "x", "ada").status == "confirmed"  # 31% share


def mine(commits: int = 15) -> Ownership:
    return Ownership(status="confirmed", detail="yours", user_commits=commits, share=1.0)


def checks_by_id(repo: RepoFacts, ownership: Ownership) -> dict[str, ProofCheck]:
    return {c.id: c for c in run_checks(repo, ownership)}


def test_forks_without_original_commits_are_rejected() -> None:
    fork = facts(fork=True, parent="tutorial/app", ahead_of_parent=0)
    checks = run_checks(fork, mine())

    assert {c.id: c.status for c in checks}["fork"] == "fail"
    assert "no commits of its own" in (hard_rejection(fork, checks) or "")
    worked = checks_by_id(facts(fork=True, parent="tutorial/app", ahead_of_parent=12), mine(40))
    assert worked["fork"].status == "pass"
    assert worked["commits"].title == "12 commits"  # only the fork's own commits count


def test_minimum_evidence_checks() -> None:
    thin = checks_by_id(facts(commit_count=2, commit_days=1, readme_chars=40), mine(2))

    assert thin["commits"].status == "fail"
    assert thin["commit_days"].status == "warn"
    assert thin["readme"].status == "warn"
    assert checks_by_id(facts(has_readme=False, readme_chars=0), mine())["readme"].status == "fail"
    assert checks_by_id(facts(), mine())["tests"].gate is False  # informational only


def verdict(name: str, value: str) -> SkillVerdict:
    return SkillVerdict(skill_id=uuid.uuid4(), name=name, verdict=value, evidence=[])  # type: ignore[arg-type]


def test_decision_rules() -> None:
    good = run_checks(facts(), mine())
    git, docker = verdict("Git", "demonstrated"), verdict("Docker", "partially")

    verified = decide(good, [git, docker], 82)
    assert verified.status == "verified" and verified.verified_skill_ids == [git.skill_id]
    assert decide(good, [git], 65).status == "needs_more"  # score too low
    assert decide(good, [docker], 90).status == "needs_more"  # nothing fully demonstrated
    low_commits = run_checks(facts(commit_count=4), mine(4))
    needs = decide(low_commits, [git], 90)
    assert needs.status == "needs_more" and "4 commits" in needs.reason
    assert decide(good, [verdict("Git", "not_demonstrated")], 20).status == "rejected"
    assert decide(good, [git], None).status == "needs_more"  # review couldn't run


def test_unknown_ownership_can_never_verify() -> None:
    checks = run_checks(facts(), Ownership(status="unknown", detail="log in"))

    assert decide(checks, [verdict("Git", "demonstrated")], 95).status == "needs_more"


# --- file sampling -----------------------------------------------------------------------------


def test_source_sampling_skips_noise_and_spreads_out() -> None:
    entries = [
        TreeEntry(p, s)
        for p, s in [
            ("node_modules/react/index.js", 5000),
            ("dist/app.min.js", 9000),
            ("src/api/routes.py", 4000),
            ("src/api/models.py", 6000),
            ("src/web/App.tsx", 3000),
            ("tests/test_routes.py", 4000),
            ("src/web/App.test.tsx", 3000),
            ("scripts/tiny.py", 50),
            ("app/core/config.py", 2500),
            ("lib/util.ts", 1200),
            ("deep/a/b/c/d/x.py", 5000),
        ]
    ]

    picked = pick_source_files(entries)

    assert len(picked) == 4
    assert "src/api/models.py" in picked  # largest in its folder, preferred dir
    assert "src/api/routes.py" not in picked  # other folders come first...
    assert not any("node_modules" in p or ".min." in p or "test" in p for p in picked)
    assert "scripts/tiny.py" not in picked


def test_source_sampling_fills_slots_from_one_folder() -> None:
    entries = [TreeEntry(f"src/pkg/{n}.py", 2000 + i) for i, n in enumerate("abcdef")]
    entries.append(TreeEntry("docs/conf.py", 5000))

    picked = pick_source_files(entries)

    assert len(picked) == 4  # ...but a single-package repo still gets 4 files
    assert "docs/conf.py" not in picked


def test_config_and_test_detection() -> None:
    entries = [
        TreeEntry(p, 100)
        for p in [
            "package.json",
            "backend/requirements.txt",
            "Dockerfile",
            ".github/workflows/ci.yml",
            "node_modules/x/package.json",
            "a/b/c/d/package.json",
        ]
    ]

    assert pick_config_files(entries) == [
        "Dockerfile",
        "package.json",
        "backend/requirements.txt",
        ".github/workflows/ci.yml",
    ]
    assert is_test_path("tests/test_api.py") and is_test_path("src/App.test.tsx")
    assert is_test_path("src/__tests__/x.js") and not is_test_path("src/testing_utils.py")


# --- end to end with fake GitHub and AI ----------


@dataclass
class FakeRepo:
    owner: str = "ada"
    name: str = "tracker"
    fork: bool = False
    ahead: int | None = None
    commits: int = 15
    days: int = 5
    contributors: list[tuple[str, int]] = field(default_factory=lambda: [("ada", 15)])
    readme: str | None = "# Tracker\n" + "A habit tracker built with FastAPI and Postgres. " * 20
    paths: dict[str, str] = field(
        default_factory=lambda: {
            "README.md": "",
            "requirements.txt": "fastapi\nsqlalchemy\n",
            "Dockerfile": "FROM python:3.12\n",
            "src/app/main.py": "from fastapi import FastAPI\n" * 40,
            "tests/test_main.py": "def test_x(): pass\n" * 30,
            "node_modules/x/index.js": "x" * 900,
        }
    )


class FakeGitHub:
    def __init__(
        self, repo: FakeRepo | Exception, on_repo: Callable[[], Awaitable[None]] | None = None
    ) -> None:
        self.repo_ = repo
        self.on_repo = on_repo
        self.calls: list[str] = []

    async def repo(self, owner: str, name: str) -> dict[str, Any]:
        self.calls.append("repo")
        if self.on_repo:
            await self.on_repo()
        if isinstance(self.repo_, Exception):
            raise self.repo_
        r = self.repo_
        data: dict[str, Any] = {
            "name": r.name,
            "full_name": f"{r.owner}/{r.name}",
            "owner": {"login": r.owner},
            "html_url": f"https://github.com/{r.owner}/{r.name}",
            "description": "Habits",
            "default_branch": "main",
            "fork": r.fork,
            "stargazers_count": 3,
            "created_at": "2025-01-01T00:00:00Z",
            "pushed_at": "2025-02-01T00:00:00Z",
        }
        if r.fork:
            data["parent"] = {
                "full_name": "tutorial/tracker",
                "owner": {"login": "tutorial"},
                "default_branch": "main",
            }
        return data

    async def languages(self, owner: str, name: str) -> dict[str, int]:
        return {"Python": 9000, "Dockerfile": 1000}

    async def readme(self, owner: str, name: str) -> str | None:
        assert isinstance(self.repo_, FakeRepo)
        return self.repo_.readme

    async def tree(self, owner: str, name: str, ref: str) -> tuple[list[TreeEntry], bool]:
        assert isinstance(self.repo_, FakeRepo)
        return [TreeEntry(p, max(len(t), 400)) for p, t in self.repo_.paths.items()], False

    async def commit_count(self, owner: str, name: str) -> int:
        assert isinstance(self.repo_, FakeRepo)
        return self.repo_.commits

    async def recent_commits(self, owner: str, name: str, limit: int = 100) -> list[dict[str, Any]]:
        assert isinstance(self.repo_, FakeRepo)
        start = datetime(2025, 1, 1, tzinfo=UTC)
        return [
            {
                "commit": {
                    "message": f"Add feature {i}\n\ndetails",
                    "author": {"date": (start + timedelta(days=i % self.repo_.days)).isoformat()},
                }
            }
            for i in range(min(self.repo_.commits, limit))
        ]

    async def contributors(self, owner: str, name: str) -> list[dict[str, Any]]:
        assert isinstance(self.repo_, FakeRepo)
        return [{"login": login, "contributions": n} for login, n in self.repo_.contributors]

    async def file(self, owner: str, name: str, path: str, ref: str) -> str | None:
        assert isinstance(self.repo_, FakeRepo)
        return self.repo_.paths.get(path)

    async def ahead_of_parent(
        self, owner: str, name: str, branch: str, parent_owner: str, parent_branch: str
    ) -> int | None:
        assert isinstance(self.repo_, FakeRepo)
        return self.repo_.ahead


class ReviewProvider:
    name, model = "fake", "fake-1"

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return AIResponse(text=json.dumps(self.answer), model=self.model)


REVIEW = {
    "summary": "A small but genuine FastAPI app with tests and Docker.",
    "skills": [
        {
            "skill": "Git",
            "verdict": "demonstrated",
            "evidence": ["15 commits over 5 days with clear messages"],
        },
        {
            "skill": "Docker",
            "verdict": "partially",
            "evidence": ["Dockerfile exists but no compose"],
        },
        {"skill": "Kubernetes", "verdict": "demonstrated", "evidence": ["not claimed"]},
    ],
    "strengths": ["Typed FastAPI routes in src/app/main.py"],
    "code_quality": ["Clear module layout"],
    "red_flags": [],
    "score": 82,
    "suggestions": ["Add a docker-compose file with the database."],
}


def wire(github: FakeGitHub, review: Any = REVIEW) -> ReviewProvider:
    provider = ReviewProvider(review)
    app.dependency_overrides[get_github_client] = lambda: github
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


@pytest.fixture
async def skills(db_session: AsyncSession) -> dict[str, Skill]:
    items = {
        "git": Skill(name="Git", slug="git", category="tool", aliases=["git"]),
        "docker": Skill(name="Docker", slug="docker", category="tool", aliases=["docker"]),
    }
    db_session.add_all(items.values())
    await db_session.commit()
    return items


async def signup(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str = "prover@example.com",
    github: str | None = "ada",
) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    if github:
        await db_session.execute(
            update(User).where(User.email == email).values(github_username=github)
        )
        await db_session.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def submit(
    client: AsyncClient,
    headers: dict[str, str],
    skills: dict[str, Skill],
    url: str = "https://github.com/ada/tracker",
    names: tuple[str, ...] = ("git", "docker"),
) -> Any:
    return await client.post(
        "/api/proofs",
        json={"type": "github_repo", "url": url, "skill_ids": [str(skills[n].id) for n in names]},
        headers=headers,
    )


async def fetch(client: AsyncClient, headers: dict[str, str], proof_id: str) -> dict[str, Any]:
    return (await client.get(f"/api/proofs/{proof_id}", headers=headers)).json()


async def user_skill_status(db_session: AsyncSession, skill: Skill) -> tuple[str, str]:
    row = await db_session.scalar(
        select(UserSkill)
        .where(UserSkill.skill_id == skill.id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row.verification_status.value, row.source.value


async def test_verified_proof_end_to_end(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    seen: dict[str, str] = {}

    async def during_analysis() -> None:  # runs while the background task queries GitHub
        proof = await db_session.scalar(select(Proof).execution_options(populate_existing=True))
        assert proof is not None
        seen["proof"] = proof.status.value
        seen["skill"] = (await user_skill_status(db_session, skills["git"]))[0]

    provider = wire(FakeGitHub(FakeRepo(), on_repo=during_analysis))
    headers = await signup(client, db_session)

    response = await submit(client, headers, skills)

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "pending"
    assert seen == {"proof": "analyzing", "skill": "pending"}
    body = await fetch(client, headers, response.json()["id"])
    assert body["status"] == "verified" and body["score"] == 82
    assert body["verification_level"] == "verified"
    report = body["report"]
    assert {s["name"]: s["verdict"] for s in report["skills"]} == {
        "Git": "demonstrated",
        "Docker": "partially",
    }
    assert report["ownership"]["status"] == "confirmed"
    assert report["repo"]["commit_count"] == 15 and report["repo"]["commit_days"] == 5
    assert report["repo"]["has_tests"] and report["repo"]["has_docker"]
    assert report["strengths"] == ["Typed FastAPI routes in src/app/main.py"]
    assert "Verified: Git" in body["decision"]
    assert await user_skill_status(db_session, skills["git"]) == ("verified", "verified_proof")
    assert await user_skill_status(db_session, skills["docker"]) == ("unverified", "self_declared")

    prompt = provider.requests[0].prompt
    assert "A habit tracker built with FastAPI" in prompt  # README
    assert '<file path="src/app/main.py">' in prompt and '<file path="Dockerfile">' in prompt
    assert "node_modules/x/index.js" not in prompt  # vendored code never sent
    assert "Claimed skills: Git, Docker" in prompt
    assert len(prompt) < 60_000  # bounded evidence


async def test_fork_without_original_work_is_rejected_without_ai(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    provider = wire(FakeGitHub(FakeRepo(fork=True, ahead=0)))
    headers = await signup(client, db_session)

    proof = (await submit(client, headers, skills)).json()
    body = await fetch(client, headers, proof["id"])

    assert body["status"] == "rejected" and body["score"] == 0
    assert "no commits of its own" in body["decision"]
    assert provider.requests == []
    assert await user_skill_status(db_session, skills["git"]) == ("unverified", "self_declared")


async def test_someone_elses_repo_is_rejected(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    wire(FakeGitHub(FakeRepo(owner="famous", contributors=[("famous", 500), ("ada", 1)])))
    headers = await signup(client, db_session)

    body = await fetch(
        client,
        headers,
        (await submit(client, headers, skills, url="https://github.com/famous/tracker")).json()[
            "id"
        ],
    )

    assert body["status"] == "rejected"
    assert body["report"]["ownership"]["status"] == "failed"


async def test_without_github_login_ownership_is_unknown(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    wire(FakeGitHub(FakeRepo()))
    headers = await signup(client, db_session, github=None)

    body = await fetch(client, headers, (await submit(client, headers, skills)).json()["id"])

    assert body["status"] == "needs_more"
    assert body["report"]["ownership"]["status"] == "unknown"
    assert body["verification_level"] == "self_reported"  # can't confirm it's theirs
    assert "Repository is yours" in body["decision"]


@pytest.mark.parametrize(
    ("github", "status", "text"),
    [
        (
            RepoNotFoundError("Repository not found. Make sure it's public."),
            "rejected",
            "not found",
        ),
        (GitHubRateLimitedError("GitHub's rate limit was reached."), "needs_more", "re-run"),
    ],
)
async def test_github_errors_end_in_a_final_status(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],
    github: Exception,
    status: str,
    text: str,
) -> None:
    wire(FakeGitHub(github))
    headers = await signup(client, db_session)

    body = await fetch(client, headers, (await submit(client, headers, skills)).json()["id"])

    assert body["status"] == status
    assert text in body["decision"]


async def test_ai_outage_needs_more(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    wire(FakeGitHub(FakeRepo()), review=AIUnavailableError("no key"))
    headers = await signup(client, db_session)

    body = await fetch(client, headers, (await submit(client, headers, skills)).json()["id"])

    assert body["status"] == "needs_more" and body["report"]["ai_status"] == "unavailable"
    assert body["report"]["repo"]["full_name"] == "ada/tracker"  # facts still reported


async def test_reanalyze_after_improvements(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    repo = FakeRepo(commits=4, days=1)
    wire(FakeGitHub(repo))
    headers = await signup(client, db_session)
    proof_id = (await submit(client, headers, skills)).json()["id"]
    assert (await fetch(client, headers, proof_id))["status"] == "needs_more"

    repo.commits, repo.days, repo.contributors = 14, 4, [("ada", 14)]
    rerun = await client.post(f"/api/proofs/{proof_id}/reanalyze", headers=headers)

    assert rerun.status_code == 202
    assert (await fetch(client, headers, proof_id))["status"] == "verified"


async def test_create_validation_and_ownership(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    wire(FakeGitHub(FakeRepo()))
    headers = await signup(client, db_session)
    git = str(skills["git"].id)

    bad_url = await client.post(
        "/api/proofs", json={"url": "https://gitlab.com/a/b", "skill_ids": [git]}, headers=headers
    )
    cert = await client.post(
        "/api/proofs", json={"type": "certificate", "url": "x", "skill_ids": [git]}, headers=headers
    )
    no_skill = await client.post(
        "/api/proofs", json={"url": "https://github.com/a/b", "skill_ids": []}, headers=headers
    )
    unknown = await client.post(
        "/api/proofs",
        json={
            "url": "https://github.com/a/b",
            "skill_ids": ["00000000-0000-0000-0000-000000000000"],
        },
        headers=headers,
    )
    assert [r.status_code for r in (bad_url, cert, no_skill, unknown)] == [422] * 4
    assert "github.com" in bad_url.json()["detail"]

    proof_id = (await submit(client, headers, skills)).json()["id"]
    listed = (await client.get("/api/proofs", headers=headers)).json()
    assert [p["id"] for p in listed] == [proof_id]
    assert {s["slug"] for s in listed[0]["skills"]} == {"git", "docker"}
    other = await signup(client, db_session, "other@example.com", github="bob")
    assert (await client.get(f"/api/proofs/{proof_id}", headers=other)).status_code == 404
    assert (
        await client.post(f"/api/proofs/{proof_id}/reanalyze", headers=other)
    ).status_code == 404


async def test_skills_catalog(
    client: AsyncClient, db_session: AsyncSession, skills: dict[str, Skill]
) -> None:
    headers = await signup(client, db_session)

    body = (await client.get("/api/skills", headers=headers)).json()

    assert [s["slug"] for s in body] == ["docker", "git"]


def test_review_schema_accepts_expected_shape() -> None:
    assert ProofReview.model_validate(REVIEW).score == 82


async def test_analysis_reports_its_real_progress(
    client: AsyncClient,
    db_session: AsyncSession,
    skills: dict[str, Skill],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.proofs.service as proof_service

    seen: list[str] = []
    original = proof_service._stage

    async def recording(session: AsyncSession, proof: Proof, stage: str) -> None:
        await original(session, proof, stage)
        stored = await db_session.scalar(
            select(Proof.progress).execution_options(populate_existing=True)
        )
        seen.append(f"{stage}={stored}")  # committed, so a polling client sees it

    monkeypatch.setattr(proof_service, "_stage", recording)
    wire(FakeGitHub(FakeRepo()))
    headers = await signup(client, db_session)

    body = await fetch(client, headers, (await submit(client, headers, skills)).json()["id"])

    assert seen == [
        "fetching=fetching",
        "commits=commits",
        "reviewing=reviewing",
        "writing=writing",
    ]
    assert body["status"] == "verified" and body["progress"] is None
