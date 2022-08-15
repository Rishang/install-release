import os
from typing import Dict
from tempfile import TemporaryDirectory

# pipi
from rich.progress import track
from rich.console import Console

# locals
from InstallRelease.state import State, platform_path
from InstallRelease.data import GithubRelease, TypeState
from InstallRelease.constants import state_path, bin_path
from InstallRelease.utils import mkdir, rprint, logger, show_table, isNone
from InstallRelease.core import get_release, extract_release, install_bin, GithubInfo


console = Console(width=40)

dest = platform_path(paths=bin_path, alt="../temp/bin")

cache = State(
    file_path=platform_path(paths=state_path, alt="./temp-state.json"),
    obj=GithubRelease,
)


def get(
    repo: GithubInfo,
    tag_name: str = "",
    local: bool = True,
    prompt: bool = False,
    name: str = None,
):

    logger.debug(cache.state_file)
    logger.debug(dest)

    releases = repo.release(tag_name=tag_name)

    if isNone(name):
        toolname = releases[0].name
    else:
        toolname = name

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    _gr = get_release(releases=releases, repo_url=repo.repo_url, extra_words=[toolname])

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
                        "Name": toolname,
                        "Selected Item": _gr.name,
                        "Version": releases[0].tag_name,
                        "Size Mb": _gr.size_mb(),
                        "Downloads": _gr.download_count,
                    }
                ],
                title=f"🚀 Install: {toolname}",
            )

            rprint("[color(34)]Install this tool (Y/n): ", end="")
            yn = input()
            if yn.lower() != "y":
                return

        extract_release(item=_gr, at=at.name)

    releases[0].assets = [_gr]
    cache.set(f"{repo.repo_url}#{toolname}", value=releases[0])
    cache.save()

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=local, name=toolname)


def upgrade():

    state: TypeState = cache.state

    upgrades: Dict[str, GithubInfo] = {}
    for k in track(state, description="Fetching..."):
        url = k.split("#")[0]
        name = k.split("#")[1]

        repo = GithubInfo(url)
        rprint(f"Fetching: {k}")
        releases = repo.release()

        if releases[0].published_dt() > state[k].published_dt():
            upgrades[name] = repo

    # ask prompt to upgrade listed tools
    if len(upgrades) > 0:

        rprint("\n[bold magenta]Following tool will get upgraded.\n")
        console.print("[bold yellow]" + " ".join(upgrades.keys()))
        rprint("[bold blue]Upgrade these tools, (Y/n)", end=" ")

        r = input()
        if r.lower() != "y":
            return
    else:
        rprint("[bold green]All tools are onto latest version")
        return

    for name in track(upgrades, description="Upgrading..."):
        repo = upgrades[name]
        releases = repo.release()
        k = f"{repo.repo_url}#{name}"

        rprint(
            "[bold yellow]"
            f"Updating: {name}, {state[k].tag_name} => {releases[0].tag_name}"
            "[/]"
        )
        get(repo, prompt=False, name=name)


def list_installed():
    state: TypeState = cache.state

    _table = []
    for i in state:
        _table.append(
            {
                "Name": i.split("#")[-1],
                "Version": state[i].tag_name,
                "Url": state[i].url,
            }
        )

    show_table(_table, title="Installed tools")


def remove(name: str):
    state: TypeState = cache.state
    popKey = ""

    for i in state:
        if i.split("#")[-1] == name:
            popKey = i
            if os.path.exists(f"{dest}/{name}"):
                os.remove(f"{dest}/{name}")
            break

    if popKey != "":
        del state[popKey]
        cache.save()
        logger.info(f"Removed: {name}")
