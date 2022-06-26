import os
from tempfile import TemporaryDirectory

# locals
from src.state import State
from src.data import GithubRelease, TypeState
from src.utils import mkdir, rprint, logger, show_table
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

    state: TypeState = cache.state

    for url in state:
        rprint(f"Fetching: {url}")

        repo = GithubInfo(url)
        releases = repo.release()

        if releases[0].tag_name != state[url].tag_name:
            get(repo)
        else:
            logger.info(f"No updates")


def listInstalled():
    state: TypeState = cache.state

    _table = []
    for i in state:
        _table.append({"name": state[i].name, "url": i})

    show_table(_table)


def remove(name: str):
    state: TypeState = cache.state
    popKey = ""

    for i in state:
        if state[i].name == name:
            popKey = i
            if os.path.exists(f"{dest}/{name}"):
                os.remove(f"{dest}/{name}")
            break

    if popKey != "":
        del state[popKey]
        cache.save()
        logger.info(f"Removed {name}")
