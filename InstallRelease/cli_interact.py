import os
from typing import Dict, Union
from tempfile import TemporaryDirectory
import platform

# pipi
from rich.progress import track
from rich.console import Console

# locals
from InstallRelease.state import State, platform_path
from InstallRelease.data import GithubRelease, GitlabRelease, ToolConfig, irKey

from InstallRelease.data import TypeState

from InstallRelease.constants import state_path, bin_path, config_path
from InstallRelease.utils import (
    mkdir,
    pprint,
    logger,
    show_table,
    is_none,
    threads,
    PackageVersion,
    requests_session,
)

from InstallRelease.core import (
    get_release,
    extract_release,
    install_bin,
    create_repo_info,
    RepoInfo,
)


console = Console(width=40)

install_release_version = PackageVersion("install-release")

if os.environ.get("installState", "") == "test":
    temp_dir = "../temp"
    __spath = {
        "state_path": f"{temp_dir}/temp-state.json",
        "config_path": f"{temp_dir}/temp-config.json",
    }
    logger.info(f"installState={os.environ.get('installState')}")
else:
    __spath = {"state_path": "", "config_path": ""}

cache = State(
    file_path=platform_path(paths=state_path, alt=__spath["state_path"]),
    obj=GithubRelease,  # We use GithubRelease as base type, but we'll handle GitlabRelease in code
)

cache_config = State(
    file_path=platform_path(paths=config_path, alt=__spath["config_path"]),
    obj=ToolConfig,
)


def load_config():
    """
    Load config from cache_config
    """
    config: ToolConfig = cache_config.state.get("config")

    if config is not None:
        return config
    else:
        cache_config.set("config", ToolConfig())
        cache_config.save()
        return ToolConfig()


config: ToolConfig = load_config()

dest = platform_path(paths=bin_path, alt=config.path)

# ------- cli ----------


def state_info():
    logger.debug(cache.state_file)
    logger.debug(cache_config.state_file)
    logger.debug(dest)


def get(
    repo: RepoInfo,
    tag_name: str = "",
    local: bool = True,
    prompt: bool = False,
    name: str = None,
):
    """
    | Get a release from a GitHub or GitLab repository
    """
    state_info()

    logger.debug(f"Python version: {platform.python_version()}")
    logger.debug(f"Platform: {platform.platform()}")
    try:
        logger.debug(f"Platform version: {platform.version()}")
        logger.debug(f"Platform release: {platform.release()}")
    except Exception as e:
        logger.error(f"Error getting platform info: {e}")

    releases = repo.release(tag_name=tag_name, pre_release=config.pre_release)

    if not len(releases) > 0:
        logger.error(f"No releases found: {repo.repo_url}")
        return

    if is_none(name):
        toolname = releases[0].name
    else:
        toolname = name

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    _gr = get_release(releases=releases, repo_url=repo.repo_url, extra_words=[toolname])

    logger.debug(_gr)

    if _gr is False:
        return
    else:
        if prompt is not False:
            pprint(
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
            pprint(f"[color(6)]\nPath: {dest}")
            pprint("[color(34)]Install this tool (Y/n): ", end="")
            yn = input()
            if yn.lower() != "y":
                return
            else:
                pprint("\n[magenta]Downloading...[/magenta]")

        extract_release(item=_gr, at=at.name)

    releases[0].assets = [_gr]

    # hold update if tag_name is not empty
    if tag_name != "":
        releases[0].hold_update = True

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=local, name=toolname)

    cache.set(f"{repo.repo_url}#{toolname}", value=releases[0])
    cache.save()


def upgrade(force: bool = False, skip_prompt: bool = False):
    """
    | Upgrade all tools
    """
    state_info()

    state: TypeState = cache.state

    upgrades: Dict[str, RepoInfo] = {}

    def task(k: str):
        i = irKey(k)

        try:
            if state[k].hold_update is True:
                return
        except AttributeError:
            ...

        repo = create_repo_info(i.url, token=config.token)
        pprint(f"Fetching: {k}")
        releases = repo.release(pre_release=config.pre_release)

        if releases[0].published_dt() > state[k].published_dt() or force is True:
            upgrades[i.name] = repo

    threads(task, data=[k for k in state], max_workers=20, return_result=False)

    # ask prompt to upgrade listed tools
    if len(upgrades) > 0:
        pprint("\n[bold magenta]Following tool will get upgraded.\n")
        console.print("[bold yellow]" + " ".join(upgrades.keys()))
        pprint("[bold blue]Upgrade these tools, (Y/n):", end=" ")

        if skip_prompt is False:
            r = input()
            if r.lower() != "y":
                return
    else:
        pprint("[bold green]All tools are onto latest version")
        return

    for name in track(upgrades, description="Upgrading..."):
        repo = upgrades[name]
        releases = repo.release()
        k = f"{repo.repo_url}#{name}"

        pprint(
            "[bold yellow]"
            f"Updating: {name}, {state[k].tag_name} => {releases[0].tag_name}"
            "[/]"
        )
        get(repo, prompt=False, name=name)


def show_state():
    """
    | Show state of all tools
    """
    state_info()
    if os.path.exists(cache.state_file) and os.path.isfile(cache.state_file):
        with open(cache.state_file) as f:
            print(f.read())


def list_install(
    state: TypeState = None, title: str = "Installed tools", hold_update=False
):
    """
    | List all installed tools
    """
    if state is None:
        state_info()
        state = cache.state

    _table = []
    _hold_table = []
    for key in state:
        i = irKey(key)
        if hold_update:
            if state[key].hold_update is True:
                _hold_table.append(
                    {
                        "Name": i.name,
                        "Version": f"[dim]{state[key].tag_name}",
                        "Url": f"[dim]{state[key].url}",
                    }
                )
            continue

        _table.append(
            {
                "Name": i.name,
                "Version": (
                    state[key].tag_name + "[yellow] *HOLD_UPDATE*[/yellow]"
                    if state[key].hold_update is True
                    else state[key].tag_name
                ),
                "Url": state[key].url,
            }
        )

    if hold_update:
        show_table(_hold_table, title=f"{title} kept on hold")
    else:
        show_table(_table, title=title)


def remove(name: str):
    """
    | Remove any cli tool.
    """
    state_info()
    state: TypeState = cache.state
    popKey = ""

    for key in state:
        i = irKey(key)
        if i.name == name:
            popKey = key
            if os.path.exists(f"{dest}/{name}"):
                os.remove(f"{dest}/{name}")
            break

    if popKey != "":
        del state[popKey]
        cache.save()
        logger.info(f"Removed: {name}")


def hold(name: str, hold_update: bool):
    """
    | Holds updates of any cli tool.
    """
    state_info()
    state: TypeState = cache.state

    for _k in state:
        key = irKey(_k)
        if key.name == name:
            state[_k].hold_update = hold_update
            logger.info(f"Update on hold for, {name} to {hold_update}")
            break
    cache.save()


def pull_state(url: str = "", override: bool = False):
    """
    | Install tools from remote state
    """
    logger.debug(url)

    if is_none(url):
        return

    r: dict = requests_session.get(url=url).json()

    # Determine if it's GitHub or GitLab based on URL
    data: dict = {}
    for k in r:
        if "gitlab.com" in r[k].get("url", ""):
            data[k] = GitlabRelease(**r[k])
        else:
            data[k] = GithubRelease(**r[k])

    state: TypeState = cache.state

    temp: Dict[str, Union[GithubRelease, GitlabRelease]] = {}

    for key in data:
        try:
            i = irKey(key)
        except Exception:
            logger.warning(f"Invalid input: {key}")
            continue

        if state.get(key) is not None:
            if state[key].tag_name == data[key].tag_name or override is False:
                logger.debug(f"Skipping: {key}")
                continue
            else:
                temp[key] = data[key]
        else:
            temp[key] = data[key]

    logger.debug(temp)

    if len(temp) == 0:
        return

    list_install(state=temp, title="Tools to be installed")
    pprint("\n[bold magenta]Following tool will get Installed.\n")
    pprint("[bold blue]Install these tools, (Y/n):", end=" ")

    _i = input()
    if _i.lower() != "y":
        return

    for key in temp:
        try:
            i = irKey(key)
        except Exception:
            logger.warning(f"Invalid input: {key}")
            continue
        get(
            create_repo_info(i.url, token=config.token),
            tag_name=temp[key].tag_name,
            prompt=False,
            name=i.name,
        )
