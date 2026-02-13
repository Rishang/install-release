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

from InstallRelease.pkgs.main import (
    detect_package_type_from_asset_name,
    detect_package_type_from_os_release,
    install_package,
)
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
    to_words,
    download,
)

from InstallRelease.core import (
    get_release,
    extract_release,
    install_bin,
    get_repo_info,
    RepoInfo,
)

from InstallRelease.release_scorer import PENALTY_KEYWORDS


console = Console(width=40)

install_release_version = PackageVersion("install-release")
os_package_type = detect_package_type_from_os_release()

logger.debug(f"os_package_type: {os_package_type}")

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


def is_package(state, k):
    return hasattr(state[k], "install_method") and (
        state[k].install_method == "package"
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


def _show_and_select_asset(release: Release, toolname: str) -> Optional[ReleaseAssets]:
    """Show all release assets in a table and let user select one by ID

    Args:
        release: The release object containing assets
        toolname: Name of the tool being installed

    Returns:
        Selected ReleaseAssets object or None if cancelled
    """
    if not release.assets:
        pprint("[red]No assets available for this release[/red]")
        return None

    # Prepare data for table display
    assets_data = []
    for idx, asset in enumerate[ReleaseAssets](release.assets, start=1):
        if any(word in asset.name.lower() for word in PENALTY_KEYWORDS):
            continue
        assets_data.append(
            {
                "ID": idx,
                "Filename": asset.name,
                "Size (MB)": asset.size_mb() if hasattr(asset, "size_mb") else "N/A",
                "Downloads": asset.download_count
                if hasattr(asset, "download_count")
                else "N/A",
            }
        )

    # Display table
    show_table(assets_data, title=f"📦 Available Assets for {toolname}")

    # Get user selection
    pprint(
        "\n[yellow]Enter your desired file ID to install (or 'n' to cancel): [/yellow]",
        end="",
    )
    selection = input().strip()

    if selection.lower() == "n":
        return None

    try:
        selected_id = int(selection)
        if 1 <= selected_id <= len(release.assets):
            return release.assets[selected_id - 1]
        else:
            pprint(
                f"[red]Invalid ID. Please select between 1 and {len(release.assets)}[/red]"
            )
            return None
    except ValueError:
        pprint("[red]Invalid input. Please enter a number or 'n' to cancel[/red]")
        return None


def state_info():
    logger.debug(cache.state_file)
    logger.debug(cache_config.state_file)
    logger.debug(dest)


def get(
    repo: RepoInfo,
    tag_name: str = "",
    asset_file: str = "",
    local: bool = True,
    prompt: bool = False,
    name: Optional[str] = None,
    package_mode: bool = False,
) -> None:
    """Get a release from a GitHub/GitLab repository

    Args:
        repo: Repository information handler
        tag_name: Specific tag to fetch
        asset_file: Filename pattern to extract words from
        local: Whether to install locally (ignored for packages)
        prompt: Whether to prompt for confirmation
        name: Optional name to give the installed tool
        package_mode: Whether to install as a package (auto-detects type)
    """
    state_info()

    logger.debug(f"Python version: {platform.python_version()}")
    logger.debug(f"Platform: {platform.platform()}")
    try:
        logger.debug(f"Platform version: {platform.version()}")
        logger.debug(f"Platform release: {platform.release()}")
    except Exception as e:
        logger.error(f"Error getting platform info: {e}")

    # Extract words from asset_file if provided
    custom_release_words = None
    if not is_none(asset_file):
        filename = asset_file.rsplit(".", 1)[0]
        custom_release_words = to_words(
            text=filename.replace(".", "-"), ignore_words=["v", "unknown"]
        )

    pre_release = bool(config.pre_release) if hasattr(config, "pre_release") else False
    releases = repo.release(tag_name=tag_name, pre_release=pre_release)

    # When --pkg is selected, keep only assets matching the OS package type
    if package_mode and os_package_type:
        for release in releases:
            release.assets = [
                a
                for a in release.assets
                if detect_package_type_from_asset_name(a.name) == os_package_type
            ]

    if not releases:
        logger.error(f"No releases found: {repo.repo_url}")
        return

    toolname = repo.repo_name.lower() if is_none(name) else name.lower()
    at = TemporaryDirectory(prefix=f"dn_{repo.repo_name}_")

    # Check for cached custom_release_words from previous installation
    cached_release = cache.get(f"{repo.repo_url}#{toolname}")
    cached_custom_words = None
    if (
        cached_release
        and hasattr(cached_release, "custom_release_words")
        and cached_release.custom_release_words
    ):
        cached_custom_words = cached_release.custom_release_words

    # Determine extra_words: prioritize new custom words > cached custom words > None
    if custom_release_words:
        extra_words = custom_release_words
        disable_penalties = True
    elif cached_custom_words:
        extra_words = cached_custom_words
        disable_penalties = True
    else:
        extra_words = None
        disable_penalties = False

    logger.debug(f"custom_release_words: {custom_release_words}")
    logger.debug(f"cached_custom_words: {cached_custom_words}")
    logger.debug(f"extra_words: {extra_words}")
    logger.debug(f"disable_penalties: {disable_penalties}")

    # Detect package type if in package mode
    package_type = os_package_type
    if package_mode:
        if not package_type:
            logger.error("Could not detect appropriate package type for your system")
            return
        logger.info(f"Installing as {package_type} package")

    result = get_release(
        releases=releases,
        repo_url=repo.repo_url,
        extra_words=extra_words,
        disable_penalties=disable_penalties,
        package_type=package_type if package_mode else None,
    )

    logger.debug(result)

    if result is False:
        logger.error("No suitable release assets found")
        return

    asset = cast(ReleaseAssets, result)

    for _r in releases:
        for _a in _r.assets:
            if detect_package_type_from_asset_name(_a.name) == os_package_type:
                pprint(
                    f"[bold green]\n[INFO]: A `{os_package_type}` package is available for this release. Add `--pkg` to install it.[/bold green]"
                )
                break
    del _r, _a

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
        pprint("[color(34)]Install this tool (Y/n/?): ", end="")
        yn = input()

        if yn.lower() == "?":
            selected_asset = _show_and_select_asset(releases[0], toolname)
            if selected_asset is None:
                return
            asset = selected_asset
            # Extract custom_release_words from user's manual selection
            filename = asset.name.rsplit(".", 1)[0]
            custom_release_words = to_words(
                text=filename.replace(".", "-"), ignore_words=["v", "unknown"]
            )
            pprint("\n[magenta]Downloading...[/magenta]")
        elif yn.lower() != "y":
            return
        else:
            pprint("\n[magenta]Downloading...[/magenta]")

    # Install: package (deb/rpm/appimage) or binary (extract + install_bin)
    effective_pkg = (
        package_type
        if package_mode
        else detect_package_type_from_asset_name(asset.name)
    )

    if effective_pkg:
        download(asset.browser_download_url, at.name)
        logger.debug(f"Downloaded package to: {at.name}")

        success = install_package(
            package_type=effective_pkg,
            name=toolname,
            temp_dir=at.name,
        )
        if not success:
            logger.error(f"Failed to install {toolname} as {effective_pkg} package")
            return

        releases[0].assets = [asset]
        releases[0].package_type = effective_pkg
        releases[0].install_method = "package"
    else:
        extract_release(item=asset, at=at.name)
        releases[0].assets = [asset]
        mkdir(dest)
        is_installed = install_bin(src=at.name, dest=dest, local=local, name=toolname)
        if not is_installed:
            return

    # Lock to specific version if tag was provided
    releases[0].hold_update = bool(tag_name)

    # Persist custom_release_words: new custom words > cached custom words
    if custom_release_words:
        releases[0].custom_release_words = custom_release_words
    elif cached_custom_words:
        releases[0].custom_release_words = cached_custom_words

    cache.set(f"{repo.repo_url}#{toolname}", value=releases[0])
    cache.save()


def upgrade(
    force: bool = False, skip_prompt: bool = False, packages_only: bool = False
) -> None:
    """Upgrade all installed tools

    Args:
        force: Whether to force upgrade even if not newer
        skip_prompt: Whether to skip confirmation prompt
        packages_only: Whether to upgrade only packages (not binaries)
    """
    state_info()

    state: TypeState = cache.state

    upgrades: Dict[str, RepoInfo] = {}
    pkg_upgrades: Dict[str, RepoInfo] = {}

    def task(k: str) -> None:
        i = irKey(k)
        release = state[k]

        # Filter by package type if requested
        if packages_only:
            if (
                not hasattr(release, "install_method")
                or release.install_method != "package"
            ):
                return

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

    # ask prompt to upgrade listed tools
    if len(upgrades) > 0:
        pprint("\n[bold magenta]Following tool will get upgraded.\n")
        console.print("[bold yellow]" + " ".join(upgrades.keys()))
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
        releases = repo.release()
        k = f"{repo.repo_url}#{name}"

        pprint(
            "[bold yellow]"
            f"Updating: {name}, {state[k].tag_name} => {releases[0].tag_name}"
            "[/]"
        )

        get(repo, prompt=False, name=name, package_mode=is_package(state, k))


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
        state[key]

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

        # Add package type info if it's a package
        version_str = state[key].tag_name
        if is_package(state, key):
            version_str += " [cyan](pkg)[/cyan]"

        if state[key].hold_update is True:
            version_str += "[yellow] *HOLD_UPDATE*[/yellow]"

        _table.append(
            {
                "Name": i.name,
                "Version": version_str,
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
        as_package: Whether to remove as a package (use system package manager)

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
            release = state[key]

            if is_package(state, key):
                if not hasattr(release, "package_type"):
                    logger.warning(f"{name} was not installed as a package")
                else:
                    package_type = release.package_type
                    logger.info(f"Removing {name} as {package_type} package")

                    try:
                        if package_type == "deb":
                            from InstallRelease.pkgs.deb import DebPackage

                            installer = DebPackage(name)
                            installer.uninstall()
                        elif package_type == "rpm":
                            from InstallRelease.pkgs.rpm import RpmPackage

                            installer = RpmPackage(name)
                            installer.uninstall()
                        elif package_type == "AppImage":
                            from InstallRelease.pkgs.app_images import AppImageInstaller

                            installer = AppImageInstaller(name)
                            installer.uninstall()
                    except Exception as e:
                        logger.error(f"Failed to uninstall package: {e}")
            else:
                # Remove binary file (existing code)
                try:
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
