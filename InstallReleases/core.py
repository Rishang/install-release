import os
import re
import glob
import platform
from typing import List

# pipi
import requests
from requests.auth import HTTPBasicAuth
from magic.compat import detect_from_filename

# locals
from InstallReleases.utils import logger, listItemsMatcher, extract, download, sh
from InstallReleases.data import (
    GithubRelease,
    GithubReleaseAssets,
    GithubRepoInfo,
    _platform_words,
)


# --------------- CODE ------------------


class GithubInfo:
    owner = ""
    repo_name = ""

    headers = {"Accept": "application/vnd.github.v3+json"}
    response = None

    # https://api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # https://api.github.com/repos/OWNER/REPO/releases/latest

    def __init__(self, repo_url) -> None:
        if "https://github.com/" not in repo_url:
            raise Exception("repo url must contain github.com")

        if repo_url[-1] == "/":
            repo_url = repo_url[:-1]

        repo_url_attr: list = repo_url.split("/")

        self.repo_url: str = repo_url
        self.owner, self.repo_name = repo_url_attr[-2], repo_url_attr[-1]
        self.api = f"https://api.github.com/repos/{self.owner}/{self.repo_name}"

        self.info: GithubRepoInfo = GithubRepoInfo(**self._req(self.api))

    def _req(self, url):

        response = requests.get(
            url, headers=self.headers, auth=HTTPBasicAuth("user", "pass")
        ).json()

        if isinstance(response, dict):
            if (
                response.get("message") != None
                and "API rate limit exceeded" in response["message"]
            ):
                raise Exception(response["message"])
        return response

    def repository(self):
        return self._req(self.api)

    def release(self):
        api = self.api + "/releases"
        logger.debug(f"api: {api}")

        # Github release info api
        if not self.response:

            self.response = [
                GithubRelease(
                    url=self.repo_url,
                    assets=r["assets"],
                    tag_name=r["tag_name"],
                    prerelease=r["prerelease"],
                    published_at=r["published_at"],
                    name=self.repo_name,
                )
                for r in self._req(api)
            ]

        return self.response


class installRelease:
    USER: str
    SUDO_USER: str
    HOME: str
    _all_paths = {"linux": {"local": "~/.local/bin", "global": "/usr/local/bin"}}

    def __init__(self, source: str, name: str = None) -> None:
        pl = platform.system()
        self.paths = self._all_paths[pl.lower()]
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
            return True

    def _install_darwin(self, local: bool, at: str = None):
        ...

    def _install_windows(self, local: bool, at: str = None):
        ...


def get_release(releases: List[GithubRelease], repo_url: str, version: str = None):
    probability = 0.0
    name = ""

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
        match = listItemsMatcher(patterns=_platform_words, word=i.name.lower())
        if match > 0:
            if probability == 0:
                probability = match
                name = i.name
            elif match > probability:
                probability = match
                name = i.name
            logger.debug(f"name: '{i.name}', chances: {probability}")

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
        f"File: '{item.name}', content_type: '{item.content_type}', chances: {probability}"
    )
    if probability < 0.2:
        logger.warning(
            f"Final Selected item has low probability"
            f"Object: {item.name}, content_type: {item.content_type}, chances: {probability}"
        )
    return item


def extract_release(item: GithubReleaseAssets, at):

    logger.debug(f"Download path: {at}")

    path = download(item.browser_download_url, at)
    logger.debug(f"path: {path}")

    logger.debug(f"Extracting: {path}")
    if "executable" not in detect_from_filename(path).mime_type:
        extract(path=path, at=at)
        logger.debug("Extracting done.")

    return True


def install_bin(src: str, dest: str, local: bool, name: str = None):
    bin_files = []
    for file in glob.iglob(f"{src}/**", recursive=True):
        f = detect_from_filename(file)
        if f.name == "directory":
            continue
        elif not re.match(r"application\/x-(\w+-)?executable", f.mime_type):
            continue

        bin_files.append(file)

    if len(bin_files) > 1:
        logger.error(f"Expect single binary file got more:\n{bin_files}")
        raise Exception()

    irelease = installRelease(source=bin_files[0], name=name)
    irelease.install(local, at=dest)
