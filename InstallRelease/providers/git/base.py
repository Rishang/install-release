from typing import Any, Optional
from abc import abstractmethod

import requests

from InstallRelease.utils import logger
from InstallRelease.providers.git.schemas import Release, ReleaseAssets, RepositoryInfo
from InstallRelease.providers.base import Provider
from InstallRelease.providers.git.release_scorer import ReleaseScorer


# ── Exceptions ──────────────────────────────────────────────────────────


class RepositoryError(Exception):
    pass


class UnsupportedRepositoryError(RepositoryError):
    pass


class ApiError(RepositoryError):
    pass


# ── Git provider ABC ────────────────────────────────────────────────────


class RepoInfo(Provider):
    """Abstract base for git-hosted repository providers (GitHub, GitLab)."""

    headers: dict[str, str] = {}
    response: Optional[list[Release]] = None
    api: str = ""
    token: str = ""
    data: dict[str, Any] = {}
    info: RepositoryInfo = RepositoryInfo()

    def _validate_url(self, repo_url: str, domain: str) -> str:
        if domain not in repo_url:
            raise UnsupportedRepositoryError(f"Repository URL must contain '{domain}'")
        return repo_url.rstrip("/")

    def _check_api_error(self, data: dict[str, Any], provider: str) -> None:
        if isinstance(data, dict) and data.get("message"):
            raise ApiError(f"{provider} API error: {data['message']}")

    def _handle_request_error(self, exc: requests.RequestException) -> None:
        raise ApiError(f"Request failed: {exc}")

    @abstractmethod
    def _req(self, url: str) -> dict[str, Any]: ...

    def repository(self) -> dict[str, Any]:
        return self._req(self.api)


# ── Release selection ───────────────────────────────────────────────────


def get_release(
    releases: list[Release],
    repo_url: str,
    extra_words: Optional[list[str]] = None,
    disable_adjustments: bool = False,
    package_type: Optional[str] = None,
) -> ReleaseAssets | bool:
    """Select the best-matching release asset using the platform scorer."""
    extra_words = list(extra_words or [])
    if package_type:
        extra_words.append(package_type)

    scorer = ReleaseScorer(
        extra_words=extra_words, disable_adjustments=disable_adjustments
    )
    logger.debug(f"Scorer patterns: {scorer.get_info()['all_patterns']}")

    if not releases:
        logger.warning(f"No releases found for: {repo_url}")
        return False

    target = next((r for r in releases if r.assets and not r.prerelease), None)
    if not target or not target.assets:
        logger.warning("No suitable release found (non-prerelease with assets)")
        return False

    best_name = scorer.select_best([a.name for a in target.assets])
    if not best_name:
        logger.warning(f"No matching release found for {repo_url}")
        return False

    return next((a for a in target.assets if a.name == best_name), False)
