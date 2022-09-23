import sys
import re
import glob
import platform
from typing import List

# pipi
import requests
from requests.auth import HTTPBasicAuth
from magic.compat import detect_from_filename

# locals
from InstallRelease.utils import logger, listItemsMatcher, extract, download, sh, isNone
from InstallRelease.data import (
    GithubRelease,
    GithubReleaseAssets,
    GithubRepoInfo,
    _platform_words,
)
from InstallRelease.constants import HOME

# --------------- CODE ------------------

__exec_pattern = r"application\/x-(\w+-)?(executable|binary)"


class GithubInfo:
    owner = ""
    repo_name = ""

    headers = {"Accept": "application/vnd.github.v3+json"}
    response = None

    # https://api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # https://api.github.com/repos/OWNER/REPO/releases/latest

    def __init__(self, repo_url, data: dict = {}, token: str = "") -> None:
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
        self.info: GithubRepoInfo = GithubRepoInfo(**self._req(self.api))

    def _req(self, url):

        if not isNone(self.token):
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

    def release(self, tag_name: str = ""):

        if tag_name == "":
            api = self.api + "/releases"
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


class installRelease:
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

    def _install_windows(self, local: bool, at: str = None):
        ...


def get_release(releases: List[GithubRelease], repo_url: str, extra_words: list = []):
    selected = 0.0
    name = ""

    # temp fix: install not configured for distro based on platform
    platform_words = _platform_words + ["(.tar|.zip)"]

    logger.debug(msg=("platform_words: ", platform_words))

    if len(releases) == 0:
        logger.warning(f"No releases found for: {repo_url}")
        return False

    for release in releases:
        if len(release.assets) == 0 or release.prerelease == True:
            continue
        else:
            break

    if len(release.assets) == 0:
        logger.warning(f"No release assets found for: {repo_url}")
        return False

    for i in release.assets:
        match = listItemsMatcher(
            patterns=platform_words + extra_words, word=i.name.lower()
        )
        logger.debug(f"name: '{i.name}', chances: {match}")

        if match > 0:
            if selected == 0:
                selected = match
                name = i.name
            elif match > selected:
                selected = match
                name = i.name

    if name == "":
        logger.warn(f"No match release prefix match found for {repo_url}")
        return False

    count = 0
    for i in release.assets:
        if i.name == name:
            break
        count += 1

    item = release.assets[count]
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
