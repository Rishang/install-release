from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from InstallRelease.utils import logger, FilterDataclass
from InstallRelease.providers.git.schemas import Release, ReleaseAssets, RepositoryInfo
from InstallRelease.providers.git.base import RepoInfo, ApiError


class GitHubInfo(RepoInfo):
    """GitHub repository information handler."""

    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    response: Optional[list[Release]] = None

    def __init__(
        self,
        repo_url: str,
        data: Optional[dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> None:
        data = data or {}

        repo_url = self._validate_url(repo_url, "github.com")

        repo_url_attr = repo_url.split("/")

        self.repo_url = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.api = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"
        self.token = token or ""

        self.schemas = data

        try:
            self.info = FilterDataclass(self._req(self.api), obj=RepositoryInfo)
        except Exception as e:
            logger.error(f"Failed to fetch repository information: {str(e)}")
            raise ApiError(f"Failed to fetch repository information: {str(e)}")

    def _req(self, url: str) -> dict[str, Any]:
        auth = None
        if self.token:
            auth = HTTPBasicAuth("user", self.token)
        else:
            logger.debug("GitHub token not set")

        try:
            response = requests.get(
                url,
                headers=self.headers,
                auth=auth,
                json=self.schemas,
            )
            response.raise_for_status()
            data = response.json()
            self._check_api_error(data, "GitHub")
            return data
        except requests.RequestException as e:
            self._handle_request_error(e)

    def release(self, tag_name: str = "", pre_release: bool = False) -> list[Release]:
        if self.response is not None:
            return self.response

        if tag_name:
            api = f"{self.api}/releases/tags/{tag_name}"
        else:
            api = f"{self.api}/releases{'/latest' if not pre_release else ''}"

        logger.debug(f"Fetching GitHub release from: {api}")
        self.response = []

        try:
            req = self._req(api)
            req_dict: list[dict[str, Any]] = (
                req
                if isinstance(req, list)
                else ([req] if isinstance(req, dict) else [])
            )

            for r in req_dict:
                if not isinstance(r, dict):
                    continue
                assets_list = [
                    FilterDataclass(a, obj=ReleaseAssets)
                    for a in r.get("assets", [])
                    if isinstance(a, dict)
                ]
                self.response.append(
                    Release(
                        url=self.repo_url,
                        assets=assets_list,
                        tag_name=r.get("tag_name", ""),
                        prerelease=bool(r.get("prerelease", False)),
                        published_at=r.get("published_at", ""),
                        name=self.repo_name,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch releases: {e}")
            return []

        return self.response
