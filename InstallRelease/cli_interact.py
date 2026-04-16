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
from InstallRelease.providers.base import PROVIDER_STATE_KEY_PREFIXES, InteractProvider
from InstallRelease.providers.git.main import get_repo_info, GitInteractProvider
from InstallRelease.providers.mise.main import MiseInteractProvider
from InstallRelease.providers.docker.main import (
    DockerInteractProvider,
    needs_update as docker_needs_update,
)
from InstallRelease.config import cache, cache_config, config, dest, pre_release_enabled  # noqa: F401


console = Console(width=40)
install_release_version = PackageVersion("install-release")


def is_package(state, k):
    """Check if a tool was installed as an OS package (deb/rpm/appimage)."""
    return state[k].is_package


# ------- cli ----------


def state_info() -> None:
    """Log current cache and install paths for debugging."""
    logger.debug(cache.state_file)
    logger.debug(cache_config.state_file)
    logger.debug(dest)


def get(
    url: str,
    version: str = "",
    asset_file: str = "",
    local: bool = True,
    prompt: bool = False,
    name: Optional[str] = None,
    pkg: bool = False,
) -> None:
    """Resolve URL to provider and install the tool."""
    state_info()

    # User-facing prefixes (typed by the user)
    # State-key prefixes (used internally by upgrade/pull_state)
    _mise_user, _mise = "mise@", PROVIDER_STATE_KEY_PREFIXES["mise"]
    _docker_user, _docker = "docker@", PROVIDER_STATE_KEY_PREFIXES["docker"]
    if url.startswith(_mise_user):
        provider: InteractProvider = MiseInteractProvider(url[len(_mise_user) :])
    elif url.startswith(_mise):
        provider = MiseInteractProvider(url[len(_mise) :])
    elif url.startswith(_docker_user):
        provider = DockerInteractProvider(url[len(_docker_user) :])
    elif url.startswith(_docker):
        provider = DockerInteractProvider(url[len(_docker) :])
    else:
        url = "/".join(url.split("/")[:5])
        provider = GitInteractProvider(get_repo_info(url), package_mode=pkg)
    provider.get(
        version=version, asset_file=asset_file, local=local, prompt=prompt, name=name
    )


def upgrade(
    force: bool = False, skip_prompt: bool = False, packages_only: bool = False
) -> None:
    """Check all installed tools for newer versions and upgrade them.

    Phase 1: Concurrently fetch latest versions for all tools (git + mise).
    Phase 2: Show pending upgrades, prompt user, then install sequentially.
    """
    state_info()

    state: TypeState = cache.state

    # Collect upgrade candidates: name -> (url, new_version, is_package)
    upgrades: dict[str, tuple[str, str, bool]] = {}
    pkg_upgrades: set[str] = set()  # names only, for notification
    _lock = threading.Lock()
    _mise = PROVIDER_STATE_KEY_PREFIXES["mise"]
    _docker = PROVIDER_STATE_KEY_PREFIXES["docker"]

    def task(k: str) -> None:
        """Fetch latest version for one tool and bucket it if newer."""
        i = irKey.parse(k)
        release = state[k]

        if packages_only and not release.is_package:
            return

        if release.hold_update:
            return

        # ── mise tools ──────────────────────────────────────────────────────
        if i.url.startswith(_mise):
            toolname = i.url[len(_mise) :]
            pprint(f"Fetching: {toolname}")
            versions = MiseInteractProvider(toolname).resolve()
            if versions and (force or versions[0] != state[k].tag_name):
                with _lock:
                    upgrades[i.name] = (i.url, versions[0], False)
            return

        # ── docker tools ─────────────────────────────────────────────────────
        if i.url.startswith(_docker):
            image_ref = i.url[len(_docker) :]
            tag = state[k].tag_name
            cli_image = (
                image_ref[len("library/") :]
                if image_ref.startswith("library/")
                else image_ref
            )
            pprint(f"Checking: docker@{cli_image}:{tag}")
            if docker_needs_update(image_ref, tag, force=force):
                with _lock:
                    upgrades[i.name] = (i.url, tag, False)
            return

        # ── git tools ───────────────────────────────────────────────────────
        repo = get_repo_info(i.url)
        pprint(f"Fetching: {k}")
        releases = repo.release(pre_release=pre_release_enabled())

        if not releases:
            logger.warning(f"No releases found for: {k}")
            return

        if releases[0].published_dt() > state[k].published_dt() or force:
            with _lock:
                if is_package(state, k) and not packages_only:
                    pkg_upgrades.add(i.name)
                else:
                    upgrades[i.name] = (
                        repo.repo_url,
                        releases[0].tag_name,
                        is_package(state, k),
                    )

    # Phase 1: concurrent version checks
    threads(task, data=list(state), max_workers=20, return_result=False)

    # Notify about package upgrades when not in --pkg mode
    if not packages_only and pkg_upgrades:
        pprint("\n[bold cyan]Following package can be upgraded.[/]\n")
        pprint("[bold indian_red]" + " ".join(pkg_upgrades))
        pprint(
            "\n[bold white]To upgrade packages, run: [green]ir upgrade --pkg[/green][/]\n"
        )

    # Phase 2: prompt and install pending upgrades
    if upgrades:
        pprint("\n[bold magenta]Following tool will get upgraded.\n")
        console.print("[bold yellow]" + " ".join(upgrades))
        pprint("\n[bold blue]Upgrade these tools, (Y/n):", end=" ")

        if not skip_prompt:
            r = input()
            if r.lower() != "y":
                return
    else:
        pprint("[bold green]All tools are onto latest version")
        return

    for name in track(upgrades, description="Upgrading..."):
        url, new_version, pkg_mode = upgrades[name]
        k = f"{url}#{name}"
        pprint(
            f"[bold yellow]Updating: {name}, {state[k].tag_name} => {new_version}[/]"
        )
        get(url, version=new_version, prompt=False, name=name, pkg=pkg_mode)


def show_state():
    """Print the raw state file contents for debugging."""
    state_info()
    if os.path.isfile(cache.state_file):
        with open(cache.state_file) as f:
            print(f.read())


def list_install(
    state: Optional[TypeState] = None,
    title: str = "Installed tools",
    hold_update: bool = False,
) -> None:
    """Render a table of installed tools, optionally filtering to held ones only."""
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
            if state[key].hold_update:
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

        if state[key].hold_update:
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
    """Uninstall a tool by name — removes the binary/package and clears state."""
    state_info()
    state: TypeState = cache.state
    pop_key = ""

    # Find the tool in state, uninstall its binary or package
    for key in state:
        i = irKey.parse(key)
        if i.name == name:
            pop_key = key
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

    # Purge from state after successful uninstall
    if pop_key:
        try:
            del state[pop_key]
            cache.save()
            logger.info(f"Removed: {name}")
        except Exception as e:
            logger.error(f"Failed to update state: {e}")
    else:
        logger.warning(f"Tool not found: {name}")


def hold(name: str, hold_update: bool) -> None:
    """Toggle the hold_update flag for a tool, skipping it during upgrades."""
    state_info()
    state: TypeState = cache.state

    for _k in state:
        key = irKey.parse(_k)
        if key.name == name:
            state[_k].hold_update = hold_update
            logger.info(f"Update on hold for, {name} to {hold_update}")
            break
    cache.save()


def pull_state(url: str = "", override: bool = False) -> None:
    """Import tools from a remote state URL, installing any that are new or outdated."""
    logger.debug(url)
    if is_none(url):
        return None

    # Fetch remote state and parse into Release objects
    r: dict = requests_session.get(url=url).json()
    data: dict[str, Release] = {k: Release(**r[k]) for k in r}
    state: TypeState = cache.state

    # Filter to tools that need installing (new or version mismatch with override)
    temp: dict[str, Release] = {}
    for key in data:
        try:
            i = irKey.parse(key)
        except Exception:
            logger.warning(f"Invalid input: {key}")
            continue

        if key in state and (state[key].tag_name == data[key].tag_name or not override):
            logger.debug(f"Skipping: {key}")
            continue
        temp[key] = data[key]

    logger.debug(temp)

    if not temp:
        return None

    list_install(state=temp, title="Tools to be installed")
    pprint("\n[bold magenta]Following tool will get Installed.\n")
    pprint("[bold blue]Install these tools, (Y/n):", end=" ")

    _i = input()
    if _i.lower() != "y":
        return None

    for key in temp:
        i = irKey.parse(key)
        get(i.url, version=temp[key].tag_name, prompt=False, name=i.name)
