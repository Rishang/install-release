from tempfile import TemporaryDirectory
from core import get_release, install_bin, GithubInfo
from data import GithubRepo
from utils import mkdir, rprint, logger
import os
from state import State


cache = State("temp-state.json", obj=GithubRepo)


def get(repo: GithubInfo):
    HOME = os.environ.get("HOME")
    dest = f"{HOME}/.releases-bin"

    releases = repo.release()

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    _gr = get_release(releases=releases, repo_url=repo.repo_url, at=at.name)

    if _gr == False:
        return

    cache.set(repo.repo_url, value=releases[0])
    cache.save()

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=True, name=repo.repo_name)


def upgrade():

    state: dict[str, GithubRepo] = cache.state

    for url in state:
        rprint(f"Fetching: {url}")

        repo = GithubInfo(url)
        releases = repo.release()

        if releases[0].tag_name != state[url].tag_name:
            get(repo)
        else:
            logger.info(f"No updates")


def remove(tool):
    ...
