from typing import Any, ClassVar
from urllib.parse import urlsplit

import requests

from InstallRelease.providers.git.base import ApiError, UnsupportedRepositoryError
from InstallRelease.providers.git.github import GitHubInfo
from InstallRelease.providers.git.schemas import RepositoryInfo
from InstallRelease.utils import FilterDataclass, logger


class ForgejoInfo(GitHubInfo):
    """Forgejo / Gitea repository handler (Codeberg + self-hosted instances).

    Forgejo's ``/api/v1`` REST API is GitHub-compatible for the release and
    repository endpoints we use, so this subclasses :class:`GitHubInfo` and only
    overrides what differs: the API base URL (derived from the repo host),
    the auth header style (``Authorization: token <token>``) and the stars field
    name (``stars_count`` vs GitHub's ``stargazers_count``). The release-parsing
    logic in ``release()`` is inherited unchanged.

    The API base is derived from the repository host, so the same class works
    for codeberg.org and any self-hosted Forgejo/Gitea instance.
    """

    headers: ClassVar[dict[str, str]] = {"Accept": "application/json"}
    response = None

    def __init__(
        self,
        repo_url: str,
        data: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> None:
        data = data or {}
        repo_url = repo_url.rstrip("/")

        split = urlsplit(repo_url)
        if not split.scheme or not split.netloc:
            raise UnsupportedRepositoryError(
                f"Invalid Forgejo/Codeberg repository URL: {repo_url}"
            )

        parts = repo_url.split("/")
        if len(parts) < 5:
            raise UnsupportedRepositoryError(
                f"Repository URL must be of the form "
                f"https://<host>/<owner>/<repo>: {repo_url}"
            )

        self.repo_url = repo_url
        self.owner, self.repo_name = parts[-2], parts[-1]
        self.api = (
            f"{split.scheme}://{split.netloc}"
            f"/api/v1/repos/{self.owner}/{self.repo_name}"
        )
        self.token = token or ""
        self.schemas = data
        self.response = None

        try:
            raw = self._req(self.api)
            # Forgejo/Gitea exposes star count as ``stars_count``; map it onto
            # the GitHub-style field RepositoryInfo expects.
            self.info = FilterDataclass(
                {**raw, "stargazers_count": raw.get("stars_count", 0)},
                obj=RepositoryInfo,
            )
        except Exception as e:
            logger.error(f"Failed to fetch repository information: {e!s}")
            raise ApiError(f"Failed to fetch repository information: {e!s}") from e

    def _req(self, url: str) -> dict[str, Any]:
        headers = dict(self.headers)
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        else:
            logger.debug("Forgejo/Codeberg token not set")

        try:
            response = requests.get(url, headers=headers, json=self.schemas)
            response.raise_for_status()
            data = response.json()
            self._check_api_error(data, "Forgejo")
            return data
        except requests.RequestException as e:
            self._handle_request_error(e)
