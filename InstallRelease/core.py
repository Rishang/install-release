import sys
import re
import glob
import platform
from typing import List, Union
from abc import ABC, abstractmethod
from urllib.parse import urlparse

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
    GithubRelease,
    GithubReleaseAssets,
    GithubRepoInfo,
    GitlabRelease,
    GitlabRepoInfo,
    _platform_words,
)
from InstallRelease.constants import HOME

# --------------- CODE ------------------

__exec_pattern = r"application\/x-(\w+-)?(executable|binary)"


class RepoInfo(ABC):
    """Base class for repository providers like GitHub and GitLab"""

    headers = {}
    response = None

    def __init__(self, repo_url, data: dict = {}, token: str = "") -> None:
        self.repo_url = repo_url
        self.token = token
        self.data = data

    @abstractmethod
    def _req(self, url):
        """Make an API request"""
        pass

    @abstractmethod
    def repository(self):
        """Get repository information"""
        pass

    @abstractmethod
    def release(self, tag_name: str = "", pre_release: bool = False):
        """Get release information"""
        pass


class GithubInfo(RepoInfo):
    owner = ""
    repo_name = ""

    headers = {"Accept": "application/vnd.github.v3+json"}
    response = None

    # https://api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # https://api.github.com/repos/OWNER/REPO/releases/latest

    def __init__(self, repo_url, data: dict = {}, token: str = "") -> None:
        super().__init__(repo_url, data, token)

        if "https://github.com/" not in repo_url:
            logger.error("repo url must contain 'github.com'")
            sys.exit(1)

        if repo_url[-1] == "/":
            repo_url = repo_url[:-1]

        repo_url_attr: list = repo_url.split("/")

        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.api = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"

        self.info: GithubRepoInfo = GithubRepoInfo(**self._req(self.api))

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
                GithubRelease(
                    url=self.repo_url,
                    assets=r["assets"],
                    tag_name=r["tag_name"],
                    prerelease=r["prerelease"],
                    published_at=r["published_at"],
                    name=self.repo_name,
                )
                for r in req
            ]

        return self.response


class GitlabInfo(RepoInfo):
    project_id = ""
    repo_name = ""

    headers = {"Accept": "application/json"}
    response = None

    def __init__(self, repo_url, data: dict = {}, token: str = "") -> None:
        super().__init__(repo_url, data, token)

        if "https://gitlab.com/" not in repo_url:
            logger.error("repo url must contain 'gitlab.com'")
            sys.exit(1)

        if repo_url[-1] == "/":
            repo_url = repo_url[:-1]

        # Extract project path from URL
        parsed_url = urlparse(repo_url)
        project_path = parsed_url.path.strip("/")
        self.repo_name = project_path.split("/")[-1]

        # Store the full project path
        self.project_path = project_path

        # URL-encode the project path for API requests
        import urllib.parse

        encoded_path = urllib.parse.quote_plus(project_path)
        self.project_id = encoded_path
        self.api = f"https://gitlab.com/api/v4/projects/{encoded_path}"

        # Set auth headers if token provided
        if not is_none(self.token):
            self.headers["PRIVATE-TOKEN"] = self.token

        # Try to get repo info, falling back to public access if needed
        try:
            self.info: GitlabRepoInfo = GitlabRepoInfo(**self._req(self.api))
        except Exception as e:
            # If token was used but failed, try without token
            if not is_none(self.token):
                logger.debug(
                    f"Authentication failed with token, trying public access: {e}"
                )
                self.headers.pop("PRIVATE-TOKEN", None)  # Remove token and try again
                self.token = ""
                self.info: GitlabRepoInfo = GitlabRepoInfo(**self._req(self.api))
            else:
                # If already using public access, re-raise the exception
                raise

    def _req(self, url):
        try:
            response = requests.get(
                url,
                headers=self.headers,
                json=self.data,
            )

            if response.status_code == 401:
                # Handle unauthorized case gracefully for public repositories
                if "PRIVATE-TOKEN" in self.headers:
                    # Try again without the token
                    logger.debug("Unauthorized with token, trying public access")
                    headers = self.headers.copy()
                    headers.pop("PRIVATE-TOKEN", None)
                    response = requests.get(
                        url,
                        headers=headers,
                        json=self.data,
                    )

            if response.status_code != 200:
                logger.error(
                    f"GitLab API error: {response.status_code} - {response.text}"
                )
                if response.status_code == 404:
                    logger.error(f"Repository not found or not accessible: {url}")
                    exit(1)

                # For other errors, try to continue if possible
                if url.endswith("/releases"):
                    # If getting releases fails, return empty list
                    return []
                else:
                    # For other errors, exit
                    exit(1)

            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            exit(1)

    def repository(self):
        return self._req(self.api)

    def release(self, tag_name: str = "", pre_release: bool = False):
        if tag_name == "":
            # Get all releases and sort by created_at to get the latest
            api = f"{self.api}/releases"
        else:
            api = f"{self.api}/releases/{tag_name}"

        if not self.response:
            logger.debug(f"get: {api}")
            try:
                req = self._req(api)

                if (
                    not isinstance(req, list) and req
                ):  # Check if req is not empty dict/list
                    req = [req]

                # Handle empty response
                if not req:
                    logger.warning(f"No releases found for {self.repo_url}")
                    return []

                # Sort by created_at if getting latest (tag_name == "")
                if tag_name == "":
                    req = sorted(
                        req, key=lambda x: x.get("created_at", ""), reverse=True
                    )
                    # If pre_release is False, filter out pre-releases
                    if not pre_release:
                        req = [r for r in req if not r.get("upcoming_release", False)]
                    # Take the first one (latest)
                    if req:
                        req = [req[0]]

                self.response = [
                    GitlabRelease(
                        url=self.repo_url,
                        assets=self._process_gitlab_assets(r),
                        tag_name=r["tag_name"],
                        prerelease=r.get("upcoming_release", False),
                        published_at=r["created_at"],
                        name=self.repo_name,
                    )
                    for r in req
                ]
            except Exception as e:
                logger.error(f"Error processing GitLab releases: {e}")
                self.response = []

        return self.response

    def _process_gitlab_assets(self, release):
        """Process GitLab release assets to match GitHub format"""
        assets = []

        # Get direct download URLs for release assets
        if "assets" in release and "links" in release["assets"]:
            for link in release["assets"]["links"]:
                # Fix the URL encoding in the name to prevent issues during download
                name = link["name"]

                asset = {
                    "browser_download_url": link["url"],
                    "content_type": link.get("link_type", "application/octet-stream"),
                    "created_at": release["created_at"],
                    "download_count": 0,  # GitLab doesn't provide this
                    "id": link.get("id", 0),
                    "name": name,  # Use the unencoded name
                    "node_id": "",  # GitLab doesn't have this
                    "size": 0,  # GitLab doesn't provide this in the API
                    "state": "uploaded",
                    "updated_at": release["created_at"],
                }
                assets.append(asset)

        # If no assets, try to get release artifacts using the tag_name
        if not assets and "tag_name" in release:
            tag = release["tag_name"]
            # Try to get standard release assets for common platforms
            platforms = [
                {
                    "name": f"{self.repo_name}_{tag.lstrip('v')}_linux_amd64.tar.gz",
                    "platform": "linux_amd64",
                },
                {
                    "name": f"{self.repo_name}_{tag.lstrip('v')}_darwin_amd64.tar.gz",
                    "platform": "darwin_amd64",
                },
                {
                    "name": f"{self.repo_name}_{tag.lstrip('v')}_windows_amd64.zip",
                    "platform": "windows_amd64",
                },
            ]

            for platform_info in platforms:
                # Create direct download URL using GitLab release URL pattern
                download_url = f"https://gitlab.com/{self.project_id}/-/releases/{tag}/downloads/{platform_info['name']}"

                asset = {
                    "browser_download_url": download_url,
                    "content_type": "application/gzip"
                    if platform_info["name"].endswith(".tar.gz")
                    else "application/zip",
                    "created_at": release["created_at"],
                    "download_count": 0,
                    "id": 0,
                    "name": platform_info["name"],
                    "node_id": "",
                    "size": 0,
                    "state": "uploaded",
                    "updated_at": release["created_at"],
                }
                assets.append(asset)

        return assets


def create_repo_info(
    repo_url: str, data: dict = {}, token: str = ""
) -> Union[GithubInfo, GitlabInfo]:
    """Factory function to create the appropriate repo info instance based on URL"""
    if "github.com" in repo_url:
        return GithubInfo(repo_url, data, token)
    elif "gitlab.com" in repo_url:
        return GitlabInfo(repo_url, data, token)
    else:
        logger.error(
            "Unsupported repository URL. Only GitHub and GitLab are supported."
        )
        sys.exit(1)


class installRelease:
    """
    Install a release from github
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


def get_release(releases: List[GithubRelease], repo_url: str, extra_words: list = []):
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


def extract_release(item: GithubReleaseAssets, at):
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

    irelease = installRelease(source=bin_files[0], name=name)
    irelease.install(local, at=dest)
