import os
from typing import Dict, Optional, cast
from tempfile import TemporaryDirectory
import platform

# pipi
from rich.progress import track
from rich.console import Console

# locals
from InstallRelease.state import State, platform_path
from InstallRelease.data import Release, ToolConfig, irKey, TypeState, ReleaseAssets

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
    get_repo_info,
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
    obj=Release,
)

cache_config = State(
    file_path=platform_path(paths=config_path, alt=__spath["config_path"]),
    obj=ToolConfig,
)


def load_config() -> ToolConfig:
    """Load config from cache_config

    Returns:
        The loaded configuration object or a new one if not found
    """
    config = cache_config.state.get("config")

    if config is not None and isinstance(config, ToolConfig):
        return config
    else:
        new_config = ToolConfig()
        cache_config.set("config", new_config)
        cache_config.save()
        return new_config


config: ToolConfig = load_config()

# Handle the path, ensuring it's a string
config_path_str = str(config.path) if config.path is not None else ""
dest = platform_path(paths=bin_path, alt=config_path_str)

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
    name: Optional[str] = None,
) -> None:
    """Get a release from a GitHub/GitLab repository

    Args:
        repo: Repository information handler
        tag_name: Specific tag to fetch, or empty for latest
        local: Whether to install locally
        prompt: Whether to prompt for confirmation
        name: Optional name to give the installed tool
    """
    state_info()

    logger.debug(f"Python version: {platform.python_version()}")
    logger.debug(f"Platform: {platform.platform()}")
    try:
        logger.debug(f"Platform version: {platform.version()}")
        logger.debug(f"Platform release: {platform.release()}")
    except Exception as e:
        logger.error(f"Error getting platform info: {e}")

    # Ensure pre_release is boolean
    pre_release = bool(config.pre_release) if hasattr(config, "pre_release") else False
    releases = repo.release(tag_name=tag_name, pre_release=pre_release)

    if not len(releases) > 0:
        logger.error(f"No releases found: {repo.repo_url}")
        return

    # Determine tool name from release info or provided name
    if is_none(name):
        toolname = repo.repo_name.lower()
    else:
        toolname = name.lower()

    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    result = get_release(
        releases=releases, repo_url=repo.repo_url, extra_words=[toolname]
    )

    logger.debug(result)

    # Handle the case where get_release returns False
    if result is False:
        logger.error("No suitable release assets found")
        return

    # At this point, result must be a ReleaseAssets object
    # Using cast to tell mypy that we've already checked the type
    asset = cast(ReleaseAssets, result)

    if prompt is not False:
        pprint(
            f"\n[green bold]📑 Repo     : {repo.info.full_name}"
            f"\n[blue]🌟 Stars    : {repo.info.stargazers_count}"
            f"\n[magenta]🔮 Language : {repo.info.language if repo.info.language else 'N/A'}"
            f"\n[yellow]🔥 Title    : {repo.info.description}"
        )
        show_table(
            data=[
                {
                    "Name": toolname,
                    "Selected Item": asset.name,
                    "Version": releases[0].tag_name,
                    "Size Mb": asset.size_mb() if hasattr(asset, "size_mb") else "N/A",
                    "Downloads": asset.download_count
                    if hasattr(asset, "download_count")
                    else "N/A",
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

    extract_release(item=asset, at=at.name)

    # Update the releases with the selected asset
    releases[0].assets = [asset]

    # hold update if tag_name is not empty
    if tag_name != "":
        releases[0].hold_update = True

    mkdir(dest)
    install_bin(src=at.name, dest=dest, local=local, name=toolname)

    # """For ignoring holds in get too"""
    # check_key = cache.get(f"{repo.repo_url}#{toolname}")

    # if isinstance(check_key, GithubRelease) and check_key.hold_update == True:
    #     logger.debug(f"hold_update={check_key.hold_update}")
    #     releases[0].hold_update = True

    cache.set(f"{repo.repo_url}#{toolname}", value=releases[0])
    cache.save()


def upgrade(force: bool = False, skip_prompt: bool = False) -> None:
    """Upgrade all installed tools

    Args:
        force: Whether to force upgrade even if not newer
        skip_prompt: Whether to skip confirmation prompt
    """
    state_info()

    state: TypeState = cache.state

    upgrades: Dict[str, RepoInfo] = {}

    def task(k: str) -> None:
        i = irKey(k)

        try:
            if state[k].hold_update is True:
                return
        except AttributeError:
            pass

        repo = get_repo_info(
            i.url, token=config.token, gitlab_token=config.gitlab_token
        )
        pprint(f"Fetching: {k}")
        # Ensure pre_release is boolean
        pre_release = (
            bool(config.pre_release) if hasattr(config, "pre_release") else False
        )
        releases = repo.release(pre_release=pre_release)

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
    state: Optional[TypeState] = None,
    title: str = "Installed tools",
    hold_update: bool = False,
) -> None:
    """List all installed tools

    Args:
        state: Optional state data to list, defaults to global state
        title: Title to display for the list
        hold_update: Whether to show only tools with updates on hold
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

    Args:
        name: The name of the tool to remove

    Returns:
        None
    """
    state_info()
    state: TypeState = cache.state
    popKey = ""

    # Find the tool in the state
    for key in state:
        i = irKey(key)
        if i.name == name:
            popKey = key
            try:
                # Remove the executable
                tool_path = f"{dest}/{name}"
                if os.path.exists(tool_path):
                    os.remove(tool_path)
                    logger.debug(f"Removed file: {tool_path}")
            except OSError as e:
                logger.error(f"Failed to remove file: {e}")
            break

    # Remove from state if found
    if popKey:
        try:
            del state[popKey]
            cache.save()
            logger.info(f"Removed: {name}")
        except Exception as e:
            logger.error(f"Failed to update state: {e}")
    else:
        logger.warning(f"Tool not found: {name}")


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

    data: dict = {k: Release(**r[k]) for k in r}
    state: TypeState = cache.state

    temp: Dict[str, Release] = {}

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
            get_repo_info(i.url, token=config.token, gitlab_token=config.gitlab_token),
            tag_name=temp[key].tag_name,
            prompt=False,
            name=i.name,
        )
