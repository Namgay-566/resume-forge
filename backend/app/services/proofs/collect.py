"""Collect evidence about a GitHub repo for proof review, within a fixed size budget."""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from app.schemas.proof_report import Contributor, RepoFacts
from app.services.github.client import GitHubAPI, TreeEntry
from app.services.github.urls import RepoRef

# Budgets keep the AI prompt bounded (~15k tokens) whatever the repo size.
README_CHARS = 8_000
CONFIG_CHARS = 3_000
SOURCE_CHARS = 6_000
MAX_SOURCE_FILES = 4
MAX_CONFIG_FILES = 8
MAX_TREE_LINES = 400

CONFIG_NAMES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "setup.py",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "tsconfig.json",
    "pytest.ini",
    "jest.config.js",
    "jest.config.ts",
    "vitest.config.ts",
    "vite.config.ts",
    "alembic.ini",
    "Makefile",
}
SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".rs",
    ".cs",
    ".php",
    ".swift",
    ".sql",
    ".vue",
    ".svelte",
    ".scala",
    ".c",
    ".cpp",
    ".h",
}
_SKIP_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".next",
    "out",
    "target",
    "venv",
    ".venv",
    "__pycache__",
    "coverage",
    "migrations",
    "site-packages",
    ".git",
    "public",
    "static",
}
# Folders that rarely hold the candidate's application code.
_NOT_SOURCE_DIRS = {"docs", "doc", "documentation", "benchmarks", "fixtures", "scripts"}
_TEST_DIR = {"test", "tests", "__tests__", "spec", "specs", "e2e"}
_TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$|Test\.java$)")
_PREFERRED_DIRS = {"src", "app", "lib", "server", "api", "backend", "frontend", "cmd", "pkg"}


@dataclass
class Collected:
    facts: RepoFacts
    owner_login: str
    readme: str | None
    tree_listing: str
    config_files: dict[str, str] = field(default_factory=dict)
    source_files: dict[str, str] = field(default_factory=dict)
    recent_commits: list[dict[str, Any]] = field(default_factory=list)


def _skipped(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(p in _SKIP_DIRS or p.startswith(".") and p != ".github" for p in parts[:-1])


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path)
    return any(part.lower() in _TEST_DIR for part in p.parts[:-1]) or bool(
        _TEST_FILE.search(p.name)
    )


def pick_config_files(entries: list[TreeEntry]) -> list[str]:
    paths = [e.path for e in entries if not _skipped(e.path)]
    picked = [p for p in paths if PurePosixPath(p).name in CONFIG_NAMES and p.count("/") <= 2]
    picked.sort(key=lambda p: (p.count("/"), p))
    workflows = sorted(
        p for p in paths if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
    )
    return (picked[: MAX_CONFIG_FILES - 2] + workflows[:2])[:MAX_CONFIG_FILES]


def pick_source_files(entries: list[TreeEntry]) -> list[str]:
    """A few representative, hand-written source files: not tests, vendored or generated code,
    reasonably sized, preferring src/app-style folders and spreading across directories."""
    candidates = [
        e
        for e in entries
        if PurePosixPath(e.path).suffix in SOURCE_EXTENSIONS
        and not _skipped(e.path)
        and not is_test_path(e.path)
        and not any(p.lower() in _NOT_SOURCE_DIRS for p in PurePosixPath(e.path).parts[:-1])
        and 300 <= e.size <= 60_000
        and ".min." not in e.path
    ]

    def score(e: TreeEntry) -> tuple[int, int, int]:
        parts = PurePosixPath(e.path).parts
        preferred = int(any(p in _PREFERRED_DIRS for p in parts[:-1]))
        return (-preferred, len(parts), -e.size)

    ranked = sorted(candidates, key=score)
    picked: list[str] = []
    seen_dirs: set[str] = set()
    # First one file per folder for breadth, then fill the remaining slots with the next best.
    for e in ranked:
        folder = str(PurePosixPath(e.path).parent)
        if folder not in seen_dirs:
            picked.append(e.path)
            seen_dirs.add(folder)
    for e in ranked:
        if e.path not in picked:
            picked.append(e.path)
    return picked[:MAX_SOURCE_FILES]


def tree_listing(entries: list[TreeEntry]) -> str:
    paths = sorted(e.path for e in entries if not _skipped(e.path))
    shown = paths[:MAX_TREE_LINES]
    more = len(paths) - len(shown)
    return "\n".join(shown) + (f"\n... and {more} more files" if more > 0 else "")


def _date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


async def collect(gh: GitHubAPI, ref: RepoRef) -> Collected:
    repo = await gh.repo(ref.owner, ref.name)
    owner, name, branch = repo["owner"]["login"], repo["name"], repo["default_branch"]

    (
        languages,
        readme,
        (entries, truncated),
        commit_count,
        commits,
        contributors,
    ) = await asyncio.gather(
        gh.languages(owner, name),
        gh.readme(owner, name),
        gh.tree(owner, name, branch),
        gh.commit_count(owner, name),
        gh.recent_commits(owner, name, 100),
        gh.contributors(owner, name),
    )

    ahead = None
    parent = repo.get("parent") or {}
    if repo.get("fork") and parent:
        ahead = await gh.ahead_of_parent(
            owner, name, branch, parent["owner"]["login"], parent["default_branch"]
        )

    config_paths = pick_config_files(entries)
    source_paths = pick_source_files(entries)
    texts = await asyncio.gather(
        *(gh.file(owner, name, p, branch) for p in config_paths + source_paths)
    )
    config = {p: _truncate(t, CONFIG_CHARS) for p, t in zip(config_paths, texts, strict=False) if t}
    sources = {
        p: _truncate(t, SOURCE_CHARS)
        for p, t in zip(source_paths, texts[len(config_paths) :], strict=False)
        if t
    }

    total_bytes = sum(languages.values()) or 1
    days = {
        c["commit"]["author"]["date"][:10] for c in commits if c.get("commit", {}).get("author")
    }
    paths = [e.path for e in entries]
    facts = RepoFacts(
        full_name=repo["full_name"],
        url=repo["html_url"],
        description=repo.get("description"),
        default_branch=branch,
        fork=bool(repo.get("fork")),
        parent=parent.get("full_name"),
        ahead_of_parent=ahead,
        stars=int(repo.get("stargazers_count") or 0),
        homepage=repo.get("homepage") or None,
        created_at=_date(repo.get("created_at")),
        pushed_at=_date(repo.get("pushed_at")),
        languages={
            k: round(100 * v / total_bytes, 1)
            for k, v in sorted(languages.items(), key=lambda kv: -kv[1])
        },
        commit_count=commit_count,
        commit_days=len(days),
        contributors=[
            Contributor(login=c["login"], commits=int(c["contributions"]))
            for c in contributors
            if c.get("login")
        ],
        file_count=len(entries),
        tree_truncated=truncated,
        has_readme=bool(readme and readme.strip()),
        readme_chars=len(readme.strip()) if readme else 0,
        readme_excerpt=readme.strip()[:3000] if readme else None,
        has_tests=any(is_test_path(p) for p in paths),
        has_ci=any(p.startswith(".github/workflows/") for p in paths)
        or any(p in {".gitlab-ci.yml", ".circleci/config.yml", "Jenkinsfile"} for p in paths),
        has_docker=any(
            PurePosixPath(p).name
            in {"Dockerfile", "docker-compose.yml", "compose.yaml", "docker-compose.yaml"}
            for p in paths
        ),
        key_files=list(config),
        sampled_files=list(sources),
    )
    return Collected(
        facts=facts,
        owner_login=owner,
        readme=_truncate(readme, README_CHARS) if readme else None,
        tree_listing=tree_listing(entries),
        config_files=config,
        source_files=sources,
        recent_commits=commits,
    )
