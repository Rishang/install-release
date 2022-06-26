import os
from tempfile import TemporaryDirectory

# locals
from src.state import State
from src.data import GithubRelease, TypeState
from src.utils import mkdir, rprint, logger, show_table
from src.core import get_release, extract_release, install_bin, GithubInfo

HOME = os.environ.get("HOME")
dest = f"{HOME}/.releases-bin"

cache = State("temp-state.json", obj=GithubRelease)

logger.debug(f"state path: {cache.state_file}")


def get(repo: GithubInfo, prompt=False):

    releases = repo.release()

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    _gr = get_release(releases=releases, repo_url=repo.repo_url)

    if _gr == False:
        return
    else:
        if prompt != False:

            rprint(
                f"\n[green bold]Repo     : {repo.info.full_name}"
                f"\n[blue]Stars    : {repo.info.stargazers_count}"
                f"\n[magenta]Language : {repo.info.language}"
                f"\n[yellow]Title    : {repo.info.description}"
            )
            show_table(
                data=[
                    {
                        "Name": releases[0].name,
                        "Selected Item": _gr.name,
                        "Version": releases[0].tag_name,
                        "Size Mb": _gr.size_mb(),
                        "Downloads": _gr.download_count,
                    }
                ],
                title=f"Install: {releases[0].name}",
            )

            rprint("[color(34)]Install this tool (Y/N): ", end="")
            yn = input()
            if yn.lower() != "y":
                return

        extract_release(item=_gr, at=at.name)

    cache.set(repo.repo_url, value=releases[0])
    cache.save()

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=True, name=repo.info.name)


def upgrade():

    state: TypeState = cache.state

    for url in state:
        rprint(f"Fetching: {url}")

        repo = GithubInfo(url)
        releases = repo.release()

        if releases[0].tag_name != state[url].tag_name:
            get(repo, prompt=False)
        else:
            logger.info(f"No updates")


def list_installed():
    state: TypeState = cache.state

    _table = []
    for i in state:
        _table.append({"Name": state[i].name, "Version": state[i].tag_name, "Url": i})

    show_table(_table, title="Installed tools")


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
        logger.info(f"Removed: {name}")
