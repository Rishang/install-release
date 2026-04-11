"""Mise/Aqua interactive provider."""

from __future__ import annotations

from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from typing import Any, Optional

import requests

from InstallRelease.config import config, dest
from InstallRelease.helper import extract_url, install_bin, save_state
from InstallRelease.providers.base import PROVIDER_STATE_KEY_PREFIXES, InteractProvider
from InstallRelease.providers.git.schemas import Release, ReleaseAssets
from InstallRelease.providers.mise.registry import get_backend, resolve_download_url
from InstallRelease.providers.mise.schemas import AquaAsset, MiseToolInfo
from InstallRelease.utils import logger, mkdir, pprint, show_table

_GITHUB_API = "https://api.github.com"


def _get_github_versions(
    owner: str, repo: str, token: str = "", pre_release: bool = False
) -> list[str]:
    """Return stable release tag names from GitHub (newest first), excluding drafts."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/releases"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return [
            r["tag_name"]
            for r in resp.json()
            if not r.get("draft") and (pre_release or not r.get("prerelease"))
        ]
    except Exception as e:
        logger.debug(f"Failed to fetch GitHub releases for {owner}/{repo}: {e}")
        return []


class MiseInteractProvider(InteractProvider):
    """InteractProvider backed by the mise registry + aqua asset templates.

    Steps
    -----
    1. resolve    → fetch GitHub release tags for the underlying aqua repo
    2. select     → expand the aqua URL template for current OS/arch
    3. prompt     → show tool name, version, resolved URL; ask Y/n
    4. install    → download archive, extract and copy binary
    5. save_state → persist to cache as a ``Release`` object
    """

    def __init__(self, toolname: str) -> None:
        self.toolname = toolname
        self._asset: Optional[AquaAsset] = None
        self._version: str = ""
        self._backend: Optional[MiseToolInfo] = None

    def _ensure_backend(self) -> bool:
        if self._backend is None:
            self._backend = get_backend(self.toolname)
        return self._backend is not None

    # ── Step 1 ───────────────────────────────────────────────────────────

    def resolve(self, version: str = "", pre_release: bool = False) -> list[str]:
        """Return available version tags from GitHub (newest first).

        If *version* is given, returns ``[version]`` without a network call.
        """
        if version:
            return [version]

        if not self._ensure_backend():
            logger.error(
                f"No aqua backend found in mise registry for '{self.toolname}'"
            )
            return []

        owner, repo = self._backend.owner, self._backend.repo  # type: ignore[union-attr]
        token = getattr(config, "token", "")
        versions = _get_github_versions(owner, repo, token, pre_release=pre_release)
        if not versions:
            logger.warning(f"No releases found for {owner}/{repo}")
        return versions

    # ── Step 2 ───────────────────────────────────────────────────────────

    def select(self, candidates: list[str], **hints: Any) -> Optional[AquaAsset]:
        """Expand the aqua URL template for the latest (or pinned) version."""
        if not candidates:
            return None

        version = candidates[0]
        asset = resolve_download_url(self.toolname, version)
        if asset is None:
            logger.error(
                f"Could not resolve download URL for '{self.toolname}' {version}"
            )
            return None

        self._asset = asset
        self._version = version
        return asset

    # ── Step 3 ───────────────────────────────────────────────────────────

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text with '..' suffix if it exceeds max_len."""
        return (text[: max_len - 2].rstrip() + "..") if len(text) > max_len else text

    def prompt(self, toolname: str, candidate: AquaAsset) -> str:
        """Show tool details and ask for install confirmation."""
        url_display = self._truncate(candidate.url, 40)
        row: dict = {
            "Tool": toolname,
            "Version": candidate.version,
            "File": self._truncate(candidate.name, 40),
            "URL": f"[link={candidate.url}]{url_display}[/link]",
        }
        if candidate.description:
            row["Description"] = self._truncate(candidate.description, 80)
        show_table(
            data=[row],
            title=f"Install {toolname} (via mise/aqua)",
            no_wrap=False,
        )
        pprint("[color(34)]Install this tool (Y/n): ", end="")
        return input().strip().lower() or "y"

    # ── Step 4 ───────────────────────────────────────────────────────────

    def install(
        self,
        candidate: AquaAsset,
        toolname: str,
        temp_dir: str,
        local: bool,
    ) -> bool:
        logger.info(f"Downloading {candidate.url}")
        try:
            extract_url(candidate.url, temp_dir)
        except Exception as e:
            logger.error(f"Download/extract failed: {e}")
            return False

        mkdir(dest)
        if not install_bin(src=temp_dir, dest=dest, local=local, name=toolname):
            logger.error(f"Failed to install binary for '{toolname}'")
            return False
        return True

    # ── Step 5 ───────────────────────────────────────────────────────────

    def save_state(self, key: str, result: Release) -> None:
        save_state(key, result)

    # ── Template method ──────────────────────────────────────────────────

    def get(
        self,
        version: str = "",
        local: bool = True,
        prompt: bool = False,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        toolname = name or self.toolname

        # Step 1
        candidates = self.resolve(version=version)
        if not candidates:
            return

        # Step 2
        asset = self.select(candidates)
        if asset is None:
            return

        # Step 3
        if prompt:
            decision = self.prompt(toolname, asset)
            if decision != "y":
                return
            pprint("\n[magenta]Downloading...[/magenta]")

        # Step 4
        at = TemporaryDirectory(prefix=f"dn_{toolname}_")
        if not self.install(asset, toolname=toolname, temp_dir=at.name, local=local):
            return

        # Step 5
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        release_asset = ReleaseAssets(
            name=asset.name,
            browser_download_url=asset.url,
            content_type="application/octet-stream",
            size=0,
            download_count=0,
            created_at=now_str,
            updated_at=now_str,
            id=0,
            node_id="",
            state="uploaded",
        )
        release = Release(
            url=f"https://github.com/{asset.owner}/{asset.repo}",
            name=toolname,
            tag_name=asset.version,
            prerelease=False,
            published_at=now_str,
            assets=[release_asset],
            description=asset.description or "Installed via mise/aqua registry",
        )
        release.hold_update = bool(version)

        state_key = f"{PROVIDER_STATE_KEY_PREFIXES['mise']}{self.toolname}#{toolname}"
        self.save_state(state_key, release)
