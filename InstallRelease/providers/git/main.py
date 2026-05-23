from __future__ import annotations

import platform
import sys
from tempfile import TemporaryDirectory
from typing import Any, cast

from InstallRelease.config import config, dest, pre_release_enabled
from InstallRelease.helper import (
    detect_package_type_from_asset_name,
    detect_package_type_from_os_release,
    extract_url,
    install_bin,
    load_state,
    save_state,
)
from InstallRelease.helper.release_scorer import PACKAGE_ALIASES, PENALTY_EXTENSIONS
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
from InstallRelease.providers.git.schemas import Release, ReleaseAssets
from InstallRelease.utils import (
    DIM_TABLE_THEME,
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


def _appimage_ok() -> bool:
    return platform.system().lower() in PACKAGE_ALIASES.get("AppImage", [])


def get_repo_info(repo_url: str, data: dict[str, Any] | None = None) -> RepoInfo:
    """Factory: return the appropriate RepoInfo subclass for *repo_url*."""
    provider_name = Provider.resolve_provider(repo_url)
    try:
        if provider_name is None:
            raise UnsupportedRepositoryError(
                "Unsupported repository URL. Only GitHub and GitLab URLs are supported."
            )
        cls, get_token = _PROVIDER_CLASSES[provider_name]
        return cls(repo_url, data or {}, get_token(config))
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


def _available_package_type(releases: list[Release]) -> str | None:
    if not os_package_type:
        return None
    for release in releases:
        types = {
            t
            for a in release.assets
            if (t := detect_package_type_from_asset_name(a.name))
        }
        if os_package_type in types:
            return os_package_type
        if _appimage_ok() and "AppImage" in types:
            return "AppImage"
    return None


def _show_pkg_hint(
    releases: list[Release], package_mode: bool, repo_url: str = ""
) -> None:
    if package_mode or not os_package_type:
        return
    pkg = _available_package_type(releases)
    if pkg:
        pprint(
            f"\n[bold orange1]>> 📦 A [green]{pkg}[/green] package is "
            f"available for this release. Use [green]ir get {repo_url} --pkg[/green] to install it.[/bold orange1]"
        )


def _selectable_assets(release: Release) -> dict[int, ReleaseAssets]:
    selectable = [
        asset
        for asset in release.assets
        if not any(asset.name.lower().endswith(ext) for ext in PENALTY_EXTENSIONS)
    ]
    return dict(enumerate(selectable, 1))


def _show_release_assets(release: Release, toolname: str) -> dict[int, ReleaseAssets]:
    choices = _selectable_assets(release)
    if not choices:
        pprint("[red]No assets available for this release[/red]")
        return choices
    show_table(
        [
            {
                "Asset ID": did,
                "Filename": a.name,
                "Size (MB)": a.size_mb(),
                "Downloads": a.download_count,
            }
            for did, a in choices.items()
        ],
        title=f"📦 Available Assets for {toolname}",
        theme=DIM_TABLE_THEME,
    )
    return choices


def _select_asset_by_id(release: Release, selection: str) -> ReleaseAssets | None:
    choices = _selectable_assets(release)
    try:
        sid = int(selection)
    except ValueError:
        pprint("[red]Invalid input. Please enter a number or 'n' to cancel[/red]")
        return None
    if sid in choices:
        return choices[sid]
    pprint(f"[red]Invalid ID. Please select between 1 and {len(choices)}[/red]")
    return None


# ── GitInteractProvider ──────────────────────────────────────────────────────


class GitInteractProvider(InteractProvider):
    """Interactive installer for GitHub/GitLab repositories."""

    def __init__(
        self,
        repo: RepoInfo,
        package_mode: bool = False,
        package_type: str | None = None,
    ) -> None:
        self.repo = repo
        self.package_mode = package_mode
        self.package_type: str | None = package_type or os_package_type
        self._releases: list[Release] = []
        self._selected_release: Release | None = None

    def resolve(self, version: str = "", pre_release: bool = False) -> list[Release]:
        pre_release = pre_release or pre_release_enabled()
        self._releases = self.repo.release(tag_name=version, pre_release=pre_release)
        return self._releases

    def _filter_assets_for_pkg_mode(self, candidates: list[Release]) -> None:
        """Narrow each release's assets to the target package type (or AppImage fallback)."""
        for release in candidates:
            native = [
                a
                for a in release.assets
                if detect_package_type_from_asset_name(a.name) == self.package_type
            ]
            if native:
                release.assets = native
                continue
            if _appimage_ok():
                fallback = [
                    a
                    for a in release.assets
                    if detect_package_type_from_asset_name(a.name) == "AppImage"
                ]
                if fallback:
                    release.assets = fallback
                    if self.package_type != "AppImage":
                        logger.info(
                            f"No {self.package_type} package found, falling back to AppImage"
                        )
                        self.package_type = "AppImage"
                    continue
            release.assets = []

    def select(self, candidates: list[Release], **hints: Any) -> ReleaseAssets | None:
        extra_words: list[str] | None = hints.get("extra_words")
        disable_adjustments: bool = hints.get("disable_adjustments", False)
        known_names: set[str] = hints.get("known_names", set())

        if self.package_mode:
            if not self.package_type:
                logger.error(
                    "Could not detect appropriate package type for your system"
                )
                return None
            self._filter_assets_for_pkg_mode(candidates)

        if not candidates:
            return None

        self._selected_release = candidates[0]

        # Fast path: exact asset name match from --file or cache
        for a in candidates[0].assets:
            if a.name in known_names:
                logger.debug(f"Exact asset match: '{a.name}'")
                return a

        # Score all assets by OS/arch compatibility
        fallback_pkg = (
            _available_package_type(candidates) if not self.package_mode else None
        )
        result = get_release(
            releases=candidates,
            repo_url=self.repo.repo_url,
            extra_words=extra_words,
            disable_adjustments=disable_adjustments,
            package_type=self.package_type if self.package_mode else None,
        )

        if result is not False:
            return cast(ReleaseAssets, result)

        # Auto-switch to --pkg mode if a native package is available
        if fallback_pkg:
            logger.info(
                f"No standalone asset matched; switching to --pkg mode ({fallback_pkg})"
            )
            self.package_mode = True
            self.package_type = fallback_pkg
            return self.select(
                candidates,
                extra_words=extra_words,
                disable_adjustments=disable_adjustments,
                known_names=known_names,
            )

        logger.error("No suitable release assets found")
        repo_name = self.repo.repo_url.rstrip("/").rsplit("/", 1)[-1]
        pprint(
            f"[bold cyan]\nYou can retry installing via [mise] provider: "
            f"\n[green]ir get mise@{repo_name}[/green][/]\n"
        )
        return None

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
        _show_release_assets(release, toolname)
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
        pprint("[color(34)]Install selected tool? [Y/n/ Asset ID]: ", end="")
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
        name: str | None = None,
        hold: bool = False,
        **kwargs: Any,
    ) -> None:
        asset_file: str = kwargs.get("asset_file", "")
        custom_words = (
            _extract_words_from_filename(asset_file)
            if not is_none(asset_file)
            else None
        )

        # Step 1: fetch releases
        releases = self.resolve(version=version)
        if not releases:
            logger.error(f"No releases found: {self.repo.repo_url}")
            return
        if self.package_mode and not self.package_type:
            logger.error("Could not detect appropriate package type for your system")
            return

        # Build matching hints
        toolname = self.repo.repo_name.lower() if is_none(name) else name.lower()
        state_key = f"{self.repo.repo_url}#{toolname}"
        cached = load_state(state_key)
        cached_words = cached.custom_release_words if cached else None
        extra_words = custom_words or cached_words
        disable_adjustments = extra_words is not None

        known_names: set[str] = set()
        if not is_none(asset_file):
            known_names.add(asset_file)
        if cached and cached.assets:
            known_names.add(cached.assets[0].name)

        _show_pkg_hint(releases, self.package_mode, self.repo.repo_url)

        # Step 2: pick best asset
        asset = self.select(
            releases,
            extra_words=extra_words,
            disable_adjustments=disable_adjustments,
            known_names=known_names,
        )
        if asset is None:
            return

        # Step 3: confirm with user
        if prompt:
            decision = self.prompt(toolname, asset)
            if decision == "n":
                return
            if decision != "y":
                if self._selected_release is None:
                    return
                selected = _select_asset_by_id(self._selected_release, decision)
                if selected is None:
                    return
                asset = selected
                custom_words = _extract_words_from_filename(asset.name)
            pprint("\n[magenta]Downloading...[/magenta]")

        # Step 4: install
        with TemporaryDirectory(prefix=f"dn_{self.repo.repo_name}_") as tmp:
            if not self.install(asset, toolname=toolname, temp_dir=tmp, local=local):
                return

        # Step 5: persist state
        release = self._selected_release
        if release is None:
            return
        release.hold_update = hold
        resolved_words = custom_words or cached_words
        if resolved_words:
            release.custom_release_words = resolved_words
        if self.repo.info and self.repo.info.description:
            release.description = self.repo.info.description
        self.save_state(state_key, release)
