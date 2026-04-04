from typing import Any, Optional
from urllib.parse import quote

import requests

from InstallRelease.utils import logger, FilterDataclass
from InstallRelease.providers.git.schemas import Release, ReleaseAssets, RepositoryInfo
from InstallRelease.providers.git.base import RepoInfo, ApiError


class GitlabInfo(RepoInfo):
    """GitLab repository information handler."""

    headers: dict[str, str] = {"Accept": "application/json"}
    response: Optional[list[Release]] = None

    def __init__(
        self,
        repo_url: str,
        data: Optional[dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> None:
        data = data or {}

        repo_url = self._validate_url(repo_url, "gitlab.com")

        repo_url_attr = repo_url.split("/")

        self.repo_url = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.response = None

        project_path = f"{self.owner}/{self.repo_name}"
        encoded_path = quote(project_path, safe="")

        self.api = f"https://gitlab.com/api/v4/projects/{encoded_path}"

        self.token = token or ""

        self.schemas = data

        try:
            repo_info = self._req(self.api)

            github_compatible_info = {
                "name": repo_info.get("name", ""),
                "full_name": repo_info.get("path_with_namespace", ""),
                "html_url": repo_info.get("web_url", ""),
                "description": repo_info.get("description", ""),
                "language": repo_info.get("predominant_language", ""),
                "stargazers_count": repo_info.get("star_count", 0),
            }

            self.info = FilterDataclass(github_compatible_info, obj=RepositoryInfo)
        except Exception as e:
            logger.error(f"Failed to fetch GitLab repository information: {str(e)}")
            raise ApiError(f"Failed to fetch GitLab repository information: {str(e)}")

    def _req(self, url: str) -> dict[str, Any]:
        headers = self.headers.copy()

        if self.token:
            headers["PRIVATE-TOKEN"] = self.token

        try:
            response = requests.get(
                url,
                headers=headers,
                json=self.schemas,
            )
            response.raise_for_status()
            data = response.json()
            self._check_api_error(data, "GitLab")
            return data
        except requests.RequestException as e:
            self._handle_request_error(e)

    def release(self, tag_name: str = "", pre_release: bool = False) -> list[Release]:
        if self.response is not None:
            return self.response

        releases_api = f"{self.api}/releases"
        logger.debug(f"Fetching GitLab releases from: {releases_api}")
        self.response = []

        try:
            data = self._req(releases_api)
            req_list: list[dict[str, Any]] = [
                r
                for r in (data if isinstance(data, list) else [data])
                if isinstance(r, dict)
            ]

            if tag_name:
                req_list = [r for r in req_list if r.get("tag_name") == tag_name]
            if not pre_release:
                req_list = [r for r in req_list if not r.get("upcoming_release", False)]
            if not tag_name and req_list:
                req_list = [max(req_list, key=lambda x: x.get("created_at", ""))]

            for r in req_list:
                assets = []
                for link in r.get("assets", {}).get("links", []):
                    direct_url = link.get("direct_asset_url", "")
                    if not direct_url:
                        tag = r.get("tag_name", "")
                        asset_name = link.get("name", "")
                        if tag and asset_name:
                            direct_url = (
                                f"https://gitlab.com/{self.owner}/{self.repo_name}"
                                f"/-/releases/{tag}/downloads/{asset_name}"
                            )
                    assets.append(
                        ReleaseAssets(
                            browser_download_url=direct_url or link.get("url", ""),
                            content_type=link.get("link_type", ""),
                            created_at=r.get("created_at", ""),
                            download_count=link.get("count", 0),
                            id=link.get("id", 0),
                            name=link.get("name", ""),
                            node_id="",
                            size=link.get("size", 0),
                            state="uploaded",
                            updated_at=r.get("created_at", ""),
                        )
                    )
                self.response.append(
                    Release(
                        url=self.repo_url,
                        assets=assets,
                        tag_name=r.get("tag_name", ""),
                        prerelease=r.get("upcoming_release", False),
                        published_at=r.get("created_at", ""),
                        name=self.repo_name,
                    )
                )

        except Exception as e:
            logger.error(f"Failed to fetch GitLab releases: {e}")
            return []

        return self.response
