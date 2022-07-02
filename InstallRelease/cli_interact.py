import os
from tempfile import TemporaryDirectory

# pipi
from rich.progress import track

# locals
from InstallRelease.state import State, platform_path
from InstallRelease.data import GithubRelease, TypeState
from InstallRelease.constants import state_path, bin_path
from InstallRelease.utils import mkdir, rprint, logger, show_table
from InstallRelease.core import get_release, extract_release, install_bin, GithubInfo


dest = platform_path(paths=bin_path, alt="../temp/bin")

cache = State(
    file_path=platform_path(paths=state_path, alt="./temp-state.json"),
    obj=GithubRelease,
)


def get(repo: GithubInfo, tag_name: str = "", local: bool = True, prompt: bool = False):

    logger.debug(cache.state_file)
    logger.debug(dest)

    releases = repo.release(tag_name=tag_name)

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    _gr = get_release(releases=releases, repo_url=repo.repo_url)

    logger.debug(_gr)

    if _gr == False:
        return
    else:
        if prompt != False:

            rprint(
                f"\n[green bold]📑 Repo     : {repo.info.full_name}"
                f"\n[blue]🌟 Stars    : {repo.info.stargazers_count}"
                f"\n[magenta]🔮 Language : {repo.info.language}"
                f"\n[yellow]🔥 Title    : {repo.info.description}"
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
                title=f"🚀 Install: {releases[0].name}",
            )

            rprint("[color(34)]Install this tool (Y/n): ", end="")
            yn = input()
            if yn.lower() != "y":
                return

        extract_release(item=_gr, at=at.name)

    cache.set(repo.repo_url, value=releases[0])
    cache.save()

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=local, name=repo.info.name)


def upgrade():

    state: TypeState = cache.state

    for url in track(state, description="Progress..."):
        rprint(f"\nFetching: {url}")

        repo = GithubInfo(url)
        releases = repo.release()

        if releases[0].tag_name != state[url].tag_name:
            rprint(
                "[bold yellow]"
                f"Updating: {repo.repo_name}, {state[url].tag_name} => {releases[0].tag_name}"
                "[/]"
            )
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
