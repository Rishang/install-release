import os
from tempfile import TemporaryDirectory

# locals
from src.state import State
from src.data import GithubRelease
from src.utils import mkdir, rprint, logger
from src.core import get_release, install_bin, GithubInfo

HOME = os.environ.get("HOME")
dest = f"{HOME}/.releases-bin"

cache = State("temp-state.json", obj=GithubRelease)


def get(repo: GithubInfo):

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

    state: dict[str, GithubRelease] = cache.state

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
