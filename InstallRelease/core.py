import sys
import re
import glob
import platform
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from abc import ABC, abstractmethod

# pipi
import requests
from requests.auth import HTTPBasicAuth
from magic.compat import detect_from_filename

# locals
from InstallRelease.utils import (
    logger,
    extract,
    download,
    sh,
)
from InstallRelease.data import (
    Release,
    ReleaseAssets,
    RepositoryInfo,
)
from InstallRelease.release_scorer import ReleaseScorer
from InstallRelease.constants import HOME

# --------------- CODE ------------------

__exec_pattern = r"application\/x-(\w+-)?(executable|binary)"


class RepositoryError(Exception):
    """Base exception for repository operations"""

    pass


class UnsupportedRepositoryError(RepositoryError):
    """Exception raised for unsupported repository types"""

    pass


class ApiError(RepositoryError):
    """Exception raised for API errors"""

    pass


class RepoInfo(ABC):
    """Abstract base class for repository information"""

    owner: str = ""
    repo_name: str = ""
    headers: Dict[str, str] = {}
    response: Optional[List[Release]] = None
    repo_url: str = ""
    api: str = ""
    token: str = ""
    data: Dict[str, Any] = {}
    info: RepositoryInfo = RepositoryInfo()

    def _validate_url(self, repo_url: str, domain: str) -> str:
        """Validate and normalize repository URL"""
        if domain not in repo_url:
            raise UnsupportedRepositoryError(f"Repository URL must contain '{domain}'")

        # Remove trailing slash if present
        if repo_url.endswith("/"):
            return repo_url[:-1]

        return repo_url

    @abstractmethod
    def _req(self, url: str) -> Dict[str, Any]:
        """Make a request to the repository API"""
        pass

    @abstractmethod
    def repository(self) -> Dict[str, Any]:
        """Get repository information"""
        pass

    @abstractmethod
    def release(self, tag_name: str = "", pre_release: bool = False) -> List[Release]:
        """Get release information"""
        pass


class GitHubInfo(RepoInfo):
    """GitHub repository information handler"""

    headers: Dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    response: Optional[List[Release]] = None

    # https://api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # https://api.github.com/repos/OWNER/REPO/releases/latest

    def __init__(
        self,
        repo_url: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> None:
        """Initialize a GitHub repository handler

        Args:
            repo_url: The URL of the GitHub repository
            data: Additional data to send with API requests
            token: GitHub API token for authentication

        Raises:
            UnsupportedRepositoryError: If the URL is not a valid GitHub repository URL
        """
        # Initialize data to empty dict if None
        data = data or {}

        # Validate and normalize the URL
        repo_url = self._validate_url(repo_url, "github.com")

        # Parse repository information from URL
        repo_url_attr = repo_url.split("/")

        self.repo_url = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.api = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"
        self.token = token or ""  # Convert None to empty string

        self.data = data

        # Initialize repository info
        try:
            self.info = RepositoryInfo(**self._req(self.api))
        except Exception as e:
            logger.error(f"Failed to fetch repository information: {str(e)}")
            raise ApiError(f"Failed to fetch repository information: {str(e)}")

    def _req(self, url: str) -> Dict[str, Any]:
        """Make a request to the GitHub API

        Args:
            url: The API URL to request

        Returns:
            The JSON response as a dictionary

        Raises:
            ApiError: If the API request fails
        """
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
                json=self.data,
            )
            response.raise_for_status()  # Raise exception for HTTP errors
            data = response.json()

            # Check for API error messages
            if isinstance(data, dict) and data.get("message"):
                error_msg = data.get("message", "Unknown API error")
                logger.error(f"GitHub API error: {error_msg}")
                raise ApiError(f"GitHub API error: {error_msg}")

            return data
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise ApiError(f"Request failed: {str(e)}")

    def repository(self) -> Dict[str, Any]:
        """Get repository information

        Returns:
            Dictionary containing repository information
        """
        return self._req(self.api)

    def release(self, tag_name: str = "", pre_release: bool = False) -> List[Release]:
        """Get release information

        Args:
            tag_name: The specific tag name to fetch, or empty for latest
            pre_release: Whether to include pre-releases

        Returns:
            List of Release objects
        """
        # Build the API URL based on tag name and pre-release flag
        if tag_name:
            api = f"{self.api}/releases/tags/{tag_name}"
        else:
            api = f"{self.api}/releases{'/latest' if not pre_release else ''}"

        # Fetch releases if not already cached
        if not self.response:
            logger.debug(f"Fetching GitHub release from: {api}")

            try:
                req = self._req(api)

                # Ensure we have a list of releases
                if not isinstance(req, list):
                    req_dict: List[Dict[str, Any]] = (
                        [req] if isinstance(req, dict) else []
                    )
                else:
                    req_dict = req

                # Convert API response to Release objects
                self.response = []
                for r in req_dict:
                    # Process assets to convert them to ReleaseAssets objects
                    assets_list: List[ReleaseAssets] = []
                    if (
                        isinstance(r, dict)
                        and "assets" in r
                        and isinstance(r["assets"], list)
                    ):
                        for asset_data in r["assets"]:
                            if isinstance(asset_data, dict):
                                assets_list.append(ReleaseAssets(**asset_data))

                    # Create Release object with properly typed assets
                    if isinstance(r, dict):
                        release = Release(
                            url=self.repo_url,
                            assets=assets_list,
                            tag_name=r.get("tag_name", ""),
                            prerelease=bool(r.get("prerelease", False)),
                            published_at=r.get("published_at", ""),
                            name=self.repo_name,
                        )
                        if self.response is None:
                            self.response = []
                        self.response.append(release)
            except Exception as e:
                logger.error(f"Failed to fetch releases: {str(e)}")
                return []

        return self.response


class GitlabInfo(RepoInfo):
    """GitLab repository information handler"""

    headers: Dict[str, str] = {"Accept": "application/json"}
    response: Optional[List[Release]] = None

    def __init__(
        self,
        repo_url: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        gitlab_token: Optional[str] = None,
    ) -> None:
        """Initialize a GitLab repository handler

        Args:
            repo_url: The URL of the GitLab repository
            data: Additional data to send with API requests
            token: Generic token for authentication
            gitlab_token: GitLab-specific token for authentication (preferred)

        Raises:
            UnsupportedRepositoryError: If the URL is not a valid GitLab repository URL
        """
        # Initialize data to empty dict if None
        data = data or {}

        # Validate and normalize the URL
        repo_url = self._validate_url(repo_url, "gitlab.com")

        # Parse repository information from URL
        repo_url_attr = repo_url.split("/")

        self.repo_url = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.response = None

        # URL encode the project path (owner/repo_name) for GitLab API
        from urllib.parse import quote

        project_path = f"{self.owner}/{self.repo_name}"
        encoded_path = quote(project_path, safe="")

        self.api = f"https://gitlab.com/api/v4/projects/{encoded_path}"

        # Prefer gitlab_token if provided, otherwise fall back to token
        self.token = gitlab_token or token or ""

        self.data = data

        try:
            repo_info = self._req(self.api)

            # Convert GitLab API response to format compatible with GitHub format
            github_compatible_info = {
                "name": repo_info.get("name", ""),
                "full_name": repo_info.get("path_with_namespace", ""),
                "html_url": repo_info.get("web_url", ""),
                "description": repo_info.get("description", ""),
                "language": repo_info.get("predominant_language", ""),
                "stargazers_count": repo_info.get("star_count", 0),
            }

            self.info = RepositoryInfo(**github_compatible_info)
        except Exception as e:
            logger.error(f"Failed to fetch GitLab repository information: {str(e)}")
            raise ApiError(f"Failed to fetch GitLab repository information: {str(e)}")

    def _req(self, url: str) -> Dict[str, Any]:
        """Make a request to the GitLab API

        Args:
            url: The API URL to request

        Returns:
            The JSON response as a dictionary

        Raises:
            ApiError: If the API request fails
        """
        headers = self.headers.copy()

        if self.token:
            headers["PRIVATE-TOKEN"] = self.token

        try:
            response = requests.get(
                url,
                headers=headers,
                json=self.data,
            )
            response.raise_for_status()  # Raise exception for HTTP errors
            data = response.json()

            # Check for API error messages
            if isinstance(data, dict) and data.get("message"):
                error_msg = data.get("message", "Unknown API error")
                logger.error(f"GitLab API error: {error_msg}")
                raise ApiError(f"GitLab API error: {error_msg}")

            return data
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise ApiError(f"Request failed: {str(e)}")

    def repository(self) -> Dict[str, Any]:
        """Get repository information

        Returns:
            Dictionary containing repository information
        """
        return self._req(self.api)

    def release(self, tag_name: str = "", pre_release: bool = False) -> List[Release]:
        """Get release information

        Args:
            tag_name: The specific tag name to fetch, or empty for latest
            pre_release: Whether to include pre-releases

        Returns:
            List of Release objects
        """
        # Skip if we already have the releases cached
        if self.response:
            return self.response

        self.response = []  # Initialize empty list
        releases_api = f"{self.api}/releases"

        try:
            logger.debug(f"Fetching GitLab releases from: {releases_api}")

            # Fetch all releases
            releases_data = self._req(releases_api)

            # Ensure we have a list of dictionaries
            if not isinstance(releases_data, list):
                req_dict: List[Dict[str, Any]] = (
                    [releases_data] if isinstance(releases_data, dict) else []
                )
            else:
                req_dict = releases_data

            # Make sure we're working with dictionaries
            req_list: List[Dict[str, Any]] = []
            for item in req_dict:
                if isinstance(item, dict):
                    req_list.append(item)
                else:
                    logger.warning(f"Unexpected response type: {type(item)}")

            # Filter by tag name if specified
            if tag_name:
                logger.debug(f"Filtering for tag: {tag_name}")
                req_list = [r for r in req_list if r.get("tag_name") == tag_name]

            # Filter out pre-releases if needed
            if not pre_release and len(req_list) > 0:
                req_list = [r for r in req_list if not r.get("upcoming_release", False)]

            # Sort by created_at to get latest first and take the latest if no tag specified
            if not tag_name and len(req_list) > 0:
                req_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                if req_list:
                    req_list = [req_list[0]]

            # Process releases
            for r in req_list:
                # Process release assets
                assets = []
                if "assets" in r and "links" in r["assets"]:
                    for link in r["assets"]["links"]:
                        # In GitLab, the "url" is an API URL, but we need a direct download URL
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

                # Standardize datetime format
                published_at = r.get("created_at", "")
                try:
                    if published_at:
                        dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        published_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    # Try alternative format
                    try:
                        dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                        published_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        # Keep original if parsing fails
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

        except Exception as e:
            logger.error(f"Failed to fetch GitLab releases: {str(e)}")
            return []

        return self.response


def get_repo_info(
    repo_url: str,
    data: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    gitlab_token: Optional[str] = None,
) -> RepoInfo:
    """Factory method to get the appropriate repo info handler based on URL

    Args:
        repo_url: The repository URL (GitHub or GitLab)
        data: Additional data to send with API requests
        token: Generic API token for authentication
        gitlab_token: GitLab-specific token (used only for GitLab URLs)

    Returns:
        An instance of the appropriate RepoInfo subclass

    Raises:
        UnsupportedRepositoryError: If the URL is not supported
    """
    # Initialize data to empty dict if None
    data = data or {}

    try:
        if "github.com" in repo_url:
            return GitHubInfo(repo_url, data, token)
        elif "gitlab.com" in repo_url:
            return GitlabInfo(repo_url, data, token, gitlab_token)
        else:
            error_msg = (
                "Unsupported repository URL. Only GitHub and GitLab URLs are supported."
            )
            logger.error(error_msg)
            raise UnsupportedRepositoryError(error_msg)
    except UnsupportedRepositoryError as e:
        logger.error(str(e))
        sys.exit(1)
    except ApiError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
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

    def __init__(self, source: str, name: str = "") -> None:
        """Initialize the InstallRelease object

        Args:
            source: Path to the source binary to install
            name: Name to give the installed binary
        """
        pl = platform.system()
        self.paths = self.bin_path[pl.lower()]
        self.pl = pl
        self.source = source
        self.name = name

    def install(self, local: bool, at: Optional[str] = None) -> bool:
        """Install the release binary

        Args:
            local: Whether to install to local user bin or system bin
            at: Optional path to install to, overrides default paths

        Returns:
            True if installation succeeded, False otherwise
        """
        system = platform.system().lower()

        if system == "linux":
            return self._install_linux(local, at)
        elif system == "darwin":
            return self._install_darwin(local, at)
        else:
            logger.error(f"Unsupported platform: {system}")
            return False

    def _install_linux(self, local: bool, at: Optional[str] = None) -> bool:
        """Install on Linux platforms

        Args:
            local: Whether to install to local user bin or system bin
            at: Optional path to install to, overrides default paths

        Returns:
            True if installation succeeded, False otherwise
        """
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

    def _install_darwin(self, local: bool, at: Optional[str] = None) -> bool:
        """Install on macOS platforms

        Args:
            local: Whether to install to local user bin or system bin
            at: Optional path to install to, overrides default paths

        Returns:
            True if installation succeeded, False otherwise
        """
        return self._install_linux(local, at)

    def _install_windows(self, local: bool, at: Optional[str] = None) -> None:
        """Install on Windows platforms (not implemented)

        Args:
            local: Whether to install to local user bin or system bin
            at: Optional path to install to, overrides default paths
        """
        ...


def get_release(
    releases: List[Release], repo_url: str, extra_words: Optional[List[str]] = None
) -> Union[ReleaseAssets, bool]:
    """Get the release with the highest priority

    Args:
        releases: List of releases to choose from
        repo_url: The repository URL
        extra_words: Additional keywords to match against

    Returns:
        The best matching ReleaseAssets or False if no match found
    """
    # Initialize empty list if None
    extra_words = extra_words or []

    # Create scorer with platform words and extra words
    scorer = ReleaseScorer(extra_words=extra_words, debug=False)

    # Log scorer information
    scorer_info = scorer.get_info()
    logger.debug("=== USING NEW RELEASE SCORER ===")
    logger.debug(f"platform_words: {scorer_info['all_patterns']}")
    logger.debug(f"glibc_system: {scorer_info['is_glibc_system']}")

    if len(releases) == 0:
        logger.warning(f"No releases found for: {repo_url}")
        return False

    # Find the first release with assets that is not a prerelease
    target_release = None
    for release in releases:
        if len(release.assets) > 0 and not release.prerelease:
            target_release = release
            break

    if not target_release:
        logger.warning("No suitable release found (non-prerelease with assets)")
        return False

    if not target_release.assets:
        logger.warning("No release assets found")
        return False

    # Extract asset names and score them
    asset_names = [asset.name for asset in target_release.assets]
    best_name = scorer.select_best(asset_names)

    if not best_name:
        logger.warning(f"No matching release found for {repo_url}")
        return False

    # Find the asset with the best name
    for asset in target_release.assets:
        if asset.name == best_name:
            logger.debug(
                f"Selected file: \n"
                f"File: '{asset.name}', content_type: '{asset.content_type}'"
            )
            return asset

    return False


def extract_release(item: ReleaseAssets, at: str) -> bool:
    """Download and extract release

    Args:
        item: The release asset to download and extract
        at: The directory to extract to

    Returns:
        True if extraction succeeded
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


def install_bin(src: str, dest: str, local: bool, name: Optional[str] = None) -> bool:
    """Install single binary executable file from source to destination

    Args:
        src: Source directory to search for binaries
        dest: Destination directory to install to
        local: Whether to install locally or system-wide
        name: Optional name for the binary

    Returns:
        True if installation succeeded, False otherwise
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
        return False

    irelease = InstallRelease(source=bin_files[0], name=name or "")
    return irelease.install(local, at=dest)
