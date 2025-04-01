import sys
import re
import glob
import platform
from typing import List
from datetime import datetime

# pipi
import requests
from requests.auth import HTTPBasicAuth
from magic.compat import detect_from_filename

# locals
from InstallRelease.utils import (
    logger,
    listItemsMatcher,
    extract,
    download,
    sh,
    is_none,
)
from InstallRelease.data import (
    Release,
    ReleaseAssets,
    RepositoryInfo,
    _platform_words,
)
from InstallRelease.constants import HOME

# --------------- CODE ------------------

__exec_pattern = r"application\/x-(\w+-)?(executable|binary)"


class RepoInfo:
    """Base class for repository information"""

    owner = ""
    repo_name = ""
    headers = {}
    response = None
    repo_url = ""
    api = ""
    token = ""
    data = {}
    info: RepositoryInfo = RepositoryInfo()

    def _req(self, url):
        pass

    def repository(self):
        pass

    def release(self, tag_name: str = "", pre_release: bool = False):
        pass


class GitHubInfo(RepoInfo):
    """GitHub repository information handler"""

    headers = {"Accept": "application/vnd.github.v3+json"}
    response = None

    # https://api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # https://api.github.com/repos/OWNER/REPO/releases/latest

    def __init__(self, repo_url, data: dict = {}, token: str = "") -> None:
        # Validate GitHub URL properly
        if "https://github.com/" not in repo_url:
            logger.error("repo url must contain 'github.com'")
            sys.exit(1)

        if repo_url[-1] == "/":
            repo_url = repo_url[:-1]

        repo_url_attr: list = repo_url.split("/")

        self.repo_url: str = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.api = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"
        self.token = token

        self.data = data
        self.info: RepositoryInfo = RepositoryInfo(**self._req(self.api))

    def _req(self, url):
        if not is_none(self.token):
            auth = HTTPBasicAuth("user", self.token)
        else:
            logger.debug("Token not set")
            auth = HTTPBasicAuth("user", "pass")

        response = requests.get(
            url,
            headers=self.headers,
            auth=auth,
            json=self.data,
        ).json()

        if isinstance(response, dict):
            if response.get("message"):
                logger.error(response)
                exit(1)

        return response

    def repository(self):
        return self._req(self.api)

    def release(self, tag_name: str = "", pre_release: bool = False):
        if tag_name == "":
            api = (
                self.api + "/releases" + f"{'/latest' if pre_release is False else ''}"
            )
        else:
            api = self.api + "/releases/tags/" + tag_name

        # Github release info api
        if not self.response:
            logger.debug(f"get: {api}")
            req = self._req(api)

            if not isinstance(req, list):
                req = [req]

            self.response = [
                Release(
                    url=self.repo_url,
                    assets=[ReleaseAssets(**a) for a in r["assets"]],
                    tag_name=r["tag_name"],
                    prerelease=r["prerelease"],
                    published_at=r["published_at"],
                    name=self.repo_name,
                )
                for r in req
            ]

        return self.response


class GitlabInfo(RepoInfo):
    """GitLab repository information handler"""

    headers = {"Accept": "application/json"}

    def __init__(
        self, repo_url, data: dict = {}, token: str = "", gitlab_token: str = ""
    ) -> None:
        if "https://gitlab.com/" not in repo_url:
            logger.error("repo url must contain 'gitlab.com'")
            sys.exit(1)

        if repo_url[-1] == "/":
            repo_url = repo_url[:-1]

        repo_url_attr: list = repo_url.split("/")

        self.repo_url: str = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.response: list[Release] = list()  # type: ignore

        # URL encode the project path (owner/repo_name) for GitLab API
        project_path = f"{self.owner}/{self.repo_name}"
        encoded_path = requests.utils.quote(project_path, safe="")

        self.api = f"https://gitlab.com/api/v4/projects/{encoded_path}"

        # Prefer gitlab_token if provided, otherwise fall back to token
        self.token = gitlab_token if not is_none(gitlab_token) else token

        self.data = data
        repo_info = self._req(self.api)

        # Convert GitLab API response to format compatible with GithubRepoInfo
        github_compatible_info = {
            "name": repo_info.get("name", ""),
            "full_name": repo_info.get("path_with_namespace", ""),
            "html_url": repo_info.get("web_url", ""),
            "description": repo_info.get("description", ""),
            "language": repo_info.get("predominant_language", ""),
            "stargazers_count": repo_info.get("star_count", 0),
        }

        self.info: RepositoryInfo = RepositoryInfo(**github_compatible_info)

    def _req(self, url):
        headers = self.headers.copy()

        if not is_none(self.token):
            headers["PRIVATE-TOKEN"] = self.token

        response = requests.get(
            url,
            headers=headers,
            json=self.data,
        ).json()

        if isinstance(response, dict):
            if response.get("message"):
                logger.error(response)
                exit(1)

        return response

    def repository(self):
        return self._req(self.api)

    def release(self, tag_name: str = "", pre_release: bool = False):
        if not self.response:
            releases_api = f"{self.api}/releases"

            if tag_name:
                # Filter for specific tag on client side since GitLab API doesn't have direct tag endpoint
                logger.debug(f"get: {releases_api} (will filter for tag: {tag_name})")
                req = self._req(releases_api)

                if isinstance(req, list):
                    req = [r for r in req if r.get("tag_name") == tag_name]
            else:
                logger.debug(f"get: {releases_api}")
                req = self._req(releases_api)

                if not pre_release and isinstance(req, list):
                    # Filter out pre-releases if needed
                    req = [r for r in req if not r.get("upcoming_release", False)]

                # Sort by created_at to get latest first
                if isinstance(req, list) and len(req) > 0:
                    req.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                    # Take only the latest release
                    req = [req[0]]

            if not isinstance(req, list):
                req = [req]

            for r in req:
                # Process release assets
                assets = []
                if "assets" in r and "links" in r["assets"]:
                    for link in r["assets"]["links"]:
                        # In GitLab, the "url" is an API URL, but we need a direct download URL
                        # We'll use the "direct_asset_url" if available or construct a direct URL
                        direct_url = link.get("direct_asset_url", "")
                        if not direct_url:
                            # Try to construct a direct URL from the name
                            tag = r.get("tag_name", "")
                            asset_name = link.get("name", "")
                            if tag and asset_name:
                                direct_url = f"https://gitlab.com/{self.owner}/{self.repo_name}/-/releases/{tag}/downloads/{asset_name}"

                        asset = ReleaseAssets(
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
                        assets.append(asset)

                # Convert the datetime format to match GitHub's format if needed
                published_at = r.get("created_at", "")
                try:
                    if published_at:
                        # Attempt to standardize the datetime format
                        dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        published_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    # Keep the original format if parsing fails
                    pass

                release = Release(
                    url=self.repo_url,
                    assets=assets,
                    tag_name=r.get("tag_name", ""),
                    prerelease=r.get("upcoming_release", False),
                    published_at=published_at,
                    name=self.repo_name,
                )

                self.response.append(release)

        return self.response


def get_repo_info(
    repo_url: str, data: dict = {}, token: str = "", gitlab_token: str = ""
) -> RepoInfo:
    """Factory method to get the appropriate repo info handler based on URL"""
    if "github.com" in repo_url:
        return GitHubInfo(repo_url, data, token)
    elif "gitlab.com" in repo_url:
        return GitlabInfo(repo_url, data, token, gitlab_token)
    else:
        logger.error(
            "Unsupported repository URL. Only GitHub and GitLab URLs are supported."
        )
        sys.exit(1)


class InstallRelease:
    """
    Install a release from GitHub/GitLab
    """

    USER: str
    SUDO_USER: str

    bin_path = {
        "linux": {"local": f"{HOME}/.local/bin", "global": "/usr/local/bin"},
        "darwin": {"local": f"{HOME}/.local/bin", "global": "/usr/local/bin"},
    }

    def __init__(self, source: str, name: str = None) -> None:
        pl = platform.system()
        self.paths = self.bin_path[pl.lower()]
        self.pl = pl
        self.source = source
        self.name = name

    def install(self, local: bool, at: str):
        system = platform.system().lower()

        if system == "linux":
            return self._install_linux(local, at)
        elif system == "darwin":
            return self._install_darwin(local, at)

    def _install_linux(self, local: bool, at: str = None):
        if local:
            cmd = f"install {self.source} {at or self.paths['local']}"
        else:
            cmd = f"sudo install {self.source} {at or self.paths['global']}"

        if self.name:
            cmd += f"/{self.name}"

        logger.info(cmd)
        out = sh(cmd)

        if out.returncode != 0:
            logger.error(out.stderr)
            return False
        else:
            logger.info(
                f"[bold yellow]Installed: {self.name}[/]", extra={"markup": True}
            )
            return True

    def _install_darwin(self, local: bool, at: str = None):
        self._install_linux(local, at)

    def _install_windows(self, local: bool, at: str = None): ...


def get_release(releases: List[Release], repo_url: str, extra_words: list = []):
    """
    Get the release with the highest priority
    """
    selected = 0.0
    name = ""

    # temp fix: install not configured for distro based on platform
    platform_words = _platform_words + ["(.tar|.zip)"]

    logger.debug(msg=("platform_words: ", platform_words))

    if len(releases) == 0:
        logger.warning(f"No releases found for: {repo_url}")
        return False

    for release in releases:
        if len(release.assets) == 0 or release.prerelease is True:
            continue
        else:
            break

    if len(release.assets) == 0:
        logger.warning(f"No release assets found for: {repo_url}")
        return False

    _index: int = int()
    for index, e in enumerate(release.assets):
        match = listItemsMatcher(
            patterns=platform_words + extra_words, word=e.name.lower()
        )
        logger.debug(f"name: '{e.name}', chances: {match}")

        if match > 0:
            if selected == 0:
                selected = match
                name = e.name
                _index = index
            elif match > selected:
                selected = match
                name = e.name
                _index = index

    if name == "":
        logger.warn(f"No match release prefix match found for {repo_url}")
        return False

    item = release.assets[_index]
    logger.debug(
        "Selected file: \n"
        f"File: '{item.name}', content_type: '{item.content_type}', chances: {selected}"
    )
    if selected < 0.2:
        logger.warning(
            f"Final Selected item has low probability"
            f"Object: {item.name}, content_type: {item.content_type}, chances: {selected}"
        )
    return item


def extract_release(item: ReleaseAssets, at):
    """
    Download and extract release
    """
    logger.debug(f"Download path: {at}")

    path = download(item.browser_download_url, at)
    logger.debug(f"path: {path}")

    logger.debug(f"Extracting: {path}")
    if not re.match(
        pattern=__exec_pattern, string=detect_from_filename(path).mime_type
    ):
        extract(path=path, at=at)
        logger.debug("Extracting done.")

    return True


def install_bin(src: str, dest: str, local: bool, name: str = None):
    """
    Install single binary executable file from source to destination
    """
    bin_files = []

    for file in glob.iglob(f"{src}/**", recursive=True):
        f = detect_from_filename(file)
        if f.name == "directory":
            continue
        elif not re.match(pattern=__exec_pattern, string=f.mime_type):
            continue

        bin_files.append(file)

    if len(bin_files) > 1 or len(bin_files) == 0:
        logger.error(f"Expect single binary file got more or less:\n{bin_files}")
        exit(1)

    irelease = InstallRelease(source=bin_files[0], name=name)
    irelease.install(local, at=dest)
