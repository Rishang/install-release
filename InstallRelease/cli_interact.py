import os
import threading
from typing import Optional

from rich.progress import track
from rich.console import Console

from InstallRelease.schemas import irKey
from InstallRelease.providers.git.schemas import Release, TypeState
from InstallRelease.pkgs.main import PackageInstaller
from InstallRelease.utils import (
    pprint,
    logger,
    show_table,
    is_none,
    threads,
    PackageVersion,
    requests_session,
)
from InstallRelease.providers.base import InteractProvider
from InstallRelease.providers.git.base import RepoInfo
from InstallRelease.providers.git.main import get_repo_info, GitInteractProvider
from InstallRelease.providers.mise.main import MiseInteractProvider
from InstallRelease.config import cache, cache_config, config, dest, pre_release_enabled  # noqa: F401


console = Console(width=40)
install_release_version = PackageVersion("install-release")


def is_package(state, k):
    return state[k].is_package


# ------- cli ----------


def state_info() -> None:
    logger.debug(cache.state_file)
    logger.debug(cache_config.state_file)
    logger.debug(dest)


def get(
    provider: InteractProvider,
    version: str = "",
    asset_file: str = "",
    local: bool = True,
    prompt: bool = False,
    name: Optional[str] = None,
) -> None:
    """Install a tool via any InteractProvider."""
    state_info()
    provider.get(
        version=version, asset_file=asset_file, local=local, prompt=prompt, name=name
    )


def upgrade(
    force: bool = False, skip_prompt: bool = False, packages_only: bool = False
) -> None:
    """Upgrade all installed tools"""
    state_info()

    state: TypeState = cache.state

    upgrades: dict[str, RepoInfo] = {}
    pkg_upgrades: dict[str, RepoInfo] = {}
    mise_upgrades: dict[str, tuple[str, str]] = {}  # bin_name -> (toolname, version)
    _lock = threading.Lock()

    def task(k: str) -> None:
        i = irKey.parse(k)
        release = state[k]

        if packages_only and not release.is_package:
            return

        if release.hold_update:
            return

        # ── mise tools ──────────────────────────────────────────────────────
        if i.url.startswith("mise:"):
            toolname = i.url[len("mise:") :]
            pprint(f"Fetching: {toolname}")
            versions = MiseInteractProvider(toolname).resolve()
            if versions and (force or versions[0] != state[k].tag_name):
                with _lock:
                    mise_upgrades[i.name] = (toolname, versions[0])
            return

        # ── git tools ───────────────────────────────────────────────────────
        repo = get_repo_info(i.url)
        pprint(f"Fetching: {k}")
        releases = repo.release(pre_release=pre_release_enabled())

        if not releases:
            logger.warning(f"No releases found for: {k}")
            return

        if releases[0].published_dt() > state[k].published_dt() or force is True:
            with _lock:
                if is_package(state, k) and not packages_only:
                    pkg_upgrades[i.name] = repo
                else:
                    upgrades[i.name] = repo

    threads(task, data=[k for k in state], max_workers=20, return_result=False)

    if packages_only is False and len(pkg_upgrades) > 0:
        pprint("\n[bold cyan]Following package can be upgraded.[/]\n")
        pprint("[bold indian_red]" + " ".join(pkg_upgrades.keys()))
        pprint(
            "\n[bold white]To upgrade packages, run: [green]ir upgrade --pkg[/green][/]\n"
        )

    pending = list(upgrades.keys()) + list(mise_upgrades.keys())
    if pending:
        pprint("\n[bold magenta]Following tool will get upgraded.\n")
        console.print("[bold yellow]" + " ".join(pending))
        pprint("\n[bold blue]Upgrade these tools, (Y/n):", end=" ")

        if skip_prompt is False:
            r = input()
            if r.lower() != "y":
                return
    else:
        pprint("[bold green]All tools are onto latest version")
        return

    for name in track(upgrades, description="Upgrading...", disable=packages_only):
        repo = upgrades[name]
        k = f"{repo.repo_url}#{name}"

        pprint(
            "[bold yellow]"
            f"Updating: {name}, {state[k].tag_name} => {repo.release()[0].tag_name}"
            "[/]"
        )

        get(
            GitInteractProvider(repo, package_mode=is_package(state, k)),
            prompt=False,
            name=name,
        )

    for name in track(mise_upgrades, description="Upgrading (mise)..."):
        toolname, version = mise_upgrades[name]
        k = f"mise:{toolname}#{name}"
        pprint(
            f"[bold yellow]Updating: {name} (mise), {state[k].tag_name} => {version}[/]"
        )
        get(MiseInteractProvider(toolname), version=version, prompt=False, name=name)


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
    """List all installed tools"""
    if state is None:
        state_info()
        state = cache.state

    _table = []
    _hold_table = []
    desc_length = 50
    for key in state:
        i = irKey.parse(key)
        desc_raw = state[key].description or ""
        desc = (
            (desc_raw[:desc_length].rstrip() + "..")
            if len(desc_raw) > desc_length
            else desc_raw
        )

        if hold_update:
            if state[key].hold_update is True:
                _hold_table.append(
                    {
                        "Name": i.name,
                        "Version": f"[dim]{state[key].tag_name}",
                        "Title": (f"[dim yellow]{desc}[/dim yellow]"),
                        "Url": f"[dim]{state[key].url}",
                    }
                )
            continue

        version_str = state[key].tag_name
        if is_package(state, key):
            version_str += " [cyan](pkg)[/cyan]"

        if state[key].hold_update is True:
            version_str += "[yellow] *HOLD_UPDATE*[/yellow]"

        _table.append(
            {
                "Name": i.name,
                "Version": version_str,
                "Title": (f"[yellow]{desc}[/yellow]"),
                "Url": state[key].url,
            }
        )

    if hold_update:
        show_table(_hold_table, title=f"{title} kept on hold")
    else:
        show_table(_table, title=title)


def remove(name: str) -> None:
    """
    | Remove any cli tool
    """
    state_info()
    state: TypeState = cache.state
    popKey = ""

    for key in state:
        i = irKey.parse(key)
        if i.name == name:
            popKey = key
            release = state[key]

            if is_package(state, key):
                if not release.package_type or release.package_type == "binary":
                    logger.warning(f"{name} was not installed as a package")
                else:
                    pkg_name = release.package_name or name
                    if pkg_name != name:
                        logger.debug(
                            f"Using actual package name '{pkg_name}' instead of '{name}'"
                        )
                    PackageInstaller(
                        pkg_name, package_type=release.package_type
                    ).uninstall()
            else:
                try:
                    tool_path = f"{dest}/{name}"
                    if os.path.exists(tool_path):
                        os.remove(tool_path)
                        logger.debug(f"Removed file: {tool_path}")
                except OSError as e:
                    logger.error(f"Failed to remove file: {e}")
            break

    if popKey:
        try:
            del state[popKey]
            cache.save()
            logger.info(f"Removed: {name}")
        except Exception as e:
            logger.error(f"Failed to update state: {e}")
    else:
        logger.warning(f"Tool not found: {name}")


def hold(name: str, hold_update: bool) -> None:
    """
    | Holds updates of any cli tool.
    """
    state_info()
    state: TypeState = cache.state

    for _k in state:
        key = irKey.parse(_k)
        if key.name == name:
            state[_k].hold_update = hold_update
            logger.info(f"Update on hold for, {name} to {hold_update}")
            break
    cache.save()
    return None


def pull_state(url: str = "", override: bool = False) -> None:
    logger.debug(url)
    if is_none(url):
        return None
    r: dict = requests_session.get(url=url).json()

    data: dict[str, Release] = {k: Release(**r[k]) for k in r}
    state: TypeState = cache.state

    temp: dict[str, Release] = {}

    for key in data:
        try:
            i = irKey.parse(key)
        except Exception:
            logger.warning(f"Invalid input: {key}")
            continue

        if state.get(key) is not None and (
            state[key].tag_name == data[key].tag_name or override is False
        ):
            logger.debug(f"Skipping: {key}")
            continue
        else:
            temp[key] = data[key]

    logger.debug(temp)

    if len(temp) == 0:
        return None

    list_install(state=temp, title="Tools to be installed")
    pprint("\n[bold magenta]Following tool will get Installed.\n")
    pprint("[bold blue]Install these tools, (Y/n):", end=" ")

    _i = input()
    if _i.lower() != "y":
        return None

    for key in temp:
        try:
            i = irKey.parse(key)
        except Exception:
            logger.warning(f"Invalid input: {key}")
            continue

        if i.url.startswith("mise:"):
            toolname = i.url[len("mise:") :]
            provider = MiseInteractProvider(toolname)
        else:
            provider = GitInteractProvider(get_repo_info(i.url))

        get(
            provider,
            version=temp[key].tag_name,
            prompt=False,
            name=i.name,
        )
    return None
