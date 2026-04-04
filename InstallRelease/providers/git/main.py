from __future__ import annotations

import platform
import sys
from tempfile import TemporaryDirectory
from typing import Any, Optional, cast

from InstallRelease.config import config, dest, pre_release_enabled
from InstallRelease.helper import (
    detect_package_type_from_asset_name,
    detect_package_type_from_os_release,
    extract_url,
    install_bin,
    load_state,
    save_state,
)
from InstallRelease.pkgs.base import PACKAGE_ALIASES
from InstallRelease.pkgs.main import PackageInstaller
from InstallRelease.providers.base import InteractProvider, Provider
from InstallRelease.providers.git.base import (
    ApiError,
    RepoInfo,
    UnsupportedRepositoryError,
    get_release,
)
from InstallRelease.providers.git.github import GitHubInfo
from InstallRelease.providers.git.gitlab import GitlabInfo
from InstallRelease.providers.git.release_scorer import PENALTY_EXTENSIONS
from InstallRelease.providers.git.schemas import Release, ReleaseAssets
from InstallRelease.utils import (
    download,
    is_none,
    logger,
    mkdir,
    pprint,
    show_table,
    to_words,
)

os_package_type = detect_package_type_from_os_release()

_PROVIDER_CLASSES: dict[str, Any] = {
    "github": (GitHubInfo, lambda cfg: cfg.token),
    "gitlab": (GitlabInfo, lambda cfg: cfg.gitlab_token),
}


def get_repo_info(repo_url: str, data: Optional[dict[str, Any]] = None) -> RepoInfo:
    """Factory: return the appropriate RepoInfo subclass for *repo_url*."""
    data = data or {}
    provider_name = Provider.resolve_provider(repo_url)
    try:
        if provider_name is None:
            raise UnsupportedRepositoryError(
                "Unsupported repository URL. Only GitHub and GitLab URLs are supported."
            )
        cls, get_token = _PROVIDER_CLASSES[provider_name]
        return cls(repo_url, data, get_token(config))
    except (UnsupportedRepositoryError, ApiError) as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_words_from_filename(filename: str) -> list[str]:
    basename = filename.rsplit(".", 1)[0]
    return to_words(text=basename.replace(".", "-"), ignore_words=["v", "unknown"])


def _resolve_release_words(
    custom: Optional[list[str]], cached: Optional[list[str]]
) -> tuple:
    """Return (extra_words, disable_adjustments); priority: custom > cached > None."""
    if custom:
        return custom, True
    if cached:
        return cached, True
    return None, False


def _show_pkg_hint(releases: list[Release], package_mode: bool) -> None:
    if package_mode or not os_package_type:
        return
    for release in releases:
        for asset in release.assets:
            if detect_package_type_from_asset_name(asset.name) == os_package_type:
                pprint(
                    f"[bold green]\n[INFO]: A `{os_package_type}` package is "
                    f"available for this release. Add `--pkg` to install it.[/bold green]"
                )
                return


def _show_and_select_asset(release: Release, toolname: str) -> Optional[ReleaseAssets]:
    """Display all assets in a table and let the user pick one by ID."""
    if not release.assets:
        pprint("[red]No assets available for this release[/red]")
        return None

    assets_data = []
    idx_map: dict[int, int] = {}
    display_id = 1
    for actual_idx, asset in enumerate(release.assets):
        if any(asset.name.lower().endswith(ext) for ext in PENALTY_EXTENSIONS):
            continue
        assets_data.append(
            {
                "ID": display_id,
                "Filename": asset.name,
                "Size (MB)": asset.size_mb(),
                "Downloads": asset.download_count,
            }
        )
        idx_map[display_id] = actual_idx
        display_id += 1

    show_table(assets_data, title=f"📦 Available Assets for {toolname}")
    pprint(
        "\n[yellow]Enter your desired file ID to install (or 'n' to cancel): [/yellow]",
        end="",
    )
    selection = input().strip()

    if selection.lower() == "n":
        return None
    try:
        selected_id = int(selection)
        if selected_id in idx_map:
            return release.assets[idx_map[selected_id]]
        pprint(f"[red]Invalid ID. Please select between 1 and {len(idx_map)}[/red]")
    except ValueError:
        pprint("[red]Invalid input. Please enter a number or 'n' to cancel[/red]")
    return None


# ── GitInteractProvider ──────────────────────────────────────────────────────


class GitInteractProvider(InteractProvider):
    """Interactive installer for GitHub/GitLab repositories."""

    def __init__(
        self,
        repo: RepoInfo,
        package_mode: bool = False,
        package_type: Optional[str] = None,
    ) -> None:
        self.repo = repo
        self.package_mode = package_mode
        self.package_type: Optional[str] = package_type or os_package_type
        self._releases: list[Release] = []
        self._selected_release: Optional[Release] = None

    def resolve(self, version: str = "", pre_release: bool = False) -> list[Release]:
        pre_release = pre_release or pre_release_enabled()
        self._releases = self.repo.release(tag_name=version, pre_release=pre_release)
        return self._releases

    def select(
        self, candidates: list[Release], **hints: Any
    ) -> Optional[ReleaseAssets]:
        releases = candidates
        extra_words: Optional[list[str]] = hints.get("extra_words")
        disable_adjustments: bool = hints.get("disable_adjustments", False)
        known_names: set[str] = hints.get("known_names", set())

        if self.package_mode:
            if not self.package_type:
                logger.error(
                    "Could not detect appropriate package type for your system"
                )
                return None

            appimage_ok = platform.system().lower() in PACKAGE_ALIASES.get(
                "AppImage", []
            )
            for release in releases:
                native = [
                    a
                    for a in release.assets
                    if detect_package_type_from_asset_name(a.name) == self.package_type
                ]
                if native:
                    release.assets = native
                    continue

                fallback = (
                    [
                        a
                        for a in release.assets
                        if detect_package_type_from_asset_name(a.name) == "AppImage"
                    ]
                    if appimage_ok
                    else []
                )
                release.assets = fallback
                if fallback and self.package_type != "AppImage":
                    logger.info(
                        f"No {self.package_type} package found, falling back to AppImage"
                    )
                    self.package_type = "AppImage"

        if not releases:
            return None

        self._selected_release = releases[0]

        if known_names:
            for a in releases[0].assets:
                if a.name in known_names:
                    logger.debug(f"Exact asset match: '{a.name}'")
                    return a

        result = get_release(
            releases=releases,
            repo_url=self.repo.repo_url,
            extra_words=extra_words,
            disable_adjustments=disable_adjustments,
            package_type=self.package_type if self.package_mode else None,
        )
        if result is False:
            logger.error("No suitable release assets found")
            repo_name = self.repo.repo_url.rstrip("/").rsplit("/", 1)[-1]
            pprint(
                f"[bold cyan]\nYou can retry installing via [mise] provider: "
                f"\n[green]ir get @mise/{repo_name}[/green][/]\n"
            )
            return None
        return cast(ReleaseAssets, result)

    def prompt(self, toolname: str, candidate: ReleaseAssets) -> str:
        release = self._selected_release
        if release is None or self.repo.info is None:
            return "y"

        info = self.repo.info
        pprint(
            f"\n[green bold]📑 Repo     : {info.full_name}"
            f"\n[blue]🌟 Stars    : {info.stargazers_count}"
            f"\n[magenta]🔮 Language : {info.language or 'N/A'}"
            f"\n[yellow]🔥 Title    : {info.description}"
        )
        show_table(
            data=[
                {
                    "Name": toolname,
                    "Selected Item": candidate.name,
                    "Version": release.tag_name,
                    "Size Mb": candidate.size_mb(),
                    "Downloads": candidate.download_count,
                }
            ],
            title=f"🚀 Install: {toolname}",
        )
        pprint(f"[color(6)]\nPath: {dest}")
        pprint("[color(34)]Install this tool (Y/n/?): ", end="")
        return input().strip().lower() or "y"

    def install(
        self, candidate: ReleaseAssets, toolname: str, temp_dir: str, local: bool
    ) -> bool:
        release = self._selected_release
        if release is None:
            return False

        asset_pkg = detect_package_type_from_asset_name(candidate.name)
        effective_pkg = asset_pkg or (self.package_type if self.package_mode else None)

        if effective_pkg:
            if (
                self.package_mode
                and self.package_type
                and effective_pkg != self.package_type
            ):
                logger.info(
                    f"Selected asset '{candidate.name}' is {effective_pkg}; "
                    f"overriding requested {self.package_type} package type"
                )
            download(candidate.browser_download_url, temp_dir)
            pkg_installer = PackageInstaller(package_type=effective_pkg, name=toolname)
            if not pkg_installer.install(source=temp_dir):
                logger.error(f"Failed to install {toolname} as {effective_pkg} package")
                return False
            release.assets = [candidate]
            release.package_type = effective_pkg
            release.install_method = "package"
            release.package_name = pkg_installer.name
        else:
            extract_url(candidate.browser_download_url, temp_dir)
            release.assets = [candidate]
            mkdir(dest)
            if not install_bin(src=temp_dir, dest=dest, local=local, name=toolname):
                return False

        return True

    def save_state(self, key: str, result: Release) -> None:
        save_state(key, result)

    def get(
        self,
        version: str = "",
        local: bool = True,
        prompt: bool = False,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        asset_file: str = kwargs.get("asset_file", "")

        custom_release_words = (
            _extract_words_from_filename(asset_file)
            if not is_none(asset_file)
            else None
        )

        # Step 1: resolve
        releases = self.resolve(version=version)
        if not releases:
            logger.error(f"No releases found: {self.repo.repo_url}")
            return

        if self.package_mode and not self.package_type:
            logger.error("Could not detect appropriate package type for your system")
            return

        # Resolve extra_words (custom > cached > None)
        toolname = self.repo.repo_name.lower() if is_none(name) else name.lower()
        state_key = f"{self.repo.repo_url}#{toolname}"

        cached_release = load_state(state_key)
        cached_custom_words = (
            getattr(cached_release, "custom_release_words", None)
            if cached_release
            else None
        ) or None
        extra_words, disable_adjustments = _resolve_release_words(
            custom_release_words, cached_custom_words
        )

        # Exact name candidates (--file + cache)
        known_names: set[str] = set()
        if not is_none(asset_file):
            known_names.add(asset_file)
        if cached_release and cached_release.assets:
            known_names.add(cached_release.assets[0].name)

        _show_pkg_hint(releases, self.package_mode)

        # Step 2: select
        asset = self.select(
            releases,
            extra_words=extra_words,
            disable_adjustments=disable_adjustments,
            known_names=known_names,
        )
        if asset is None:
            return

        # Step 3: prompt
        if prompt:
            decision = self.prompt(toolname, asset)
            if decision == "?":
                if self._selected_release is None:
                    return
                selected = _show_and_select_asset(self._selected_release, toolname)
                if selected is None:
                    return
                asset = selected
                custom_release_words = _extract_words_from_filename(asset.name)
                pprint("\n[magenta]Downloading...[/magenta]")
            elif decision != "y":
                return
            else:
                pprint("\n[magenta]Downloading...[/magenta]")

        # Step 4: install
        at = TemporaryDirectory(prefix=f"dn_{self.repo.repo_name}_")
        if not self.install(asset, toolname=toolname, temp_dir=at.name, local=local):
            return

        # Step 5: save state
        release = self._selected_release
        if release is None:
            return
        release.hold_update = bool(version)

        resolved_words, _ = _resolve_release_words(
            custom_release_words, cached_custom_words
        )
        if resolved_words:
            release.custom_release_words = resolved_words
        if self.repo.info and self.repo.info.description:
            release.description = self.repo.info.description

        self.save_state(state_key, release)
