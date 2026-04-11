"""Mise registry + Aqua registry resolution."""

import tomllib
from typing import Optional

import requests
import yaml

from InstallRelease.providers.mise.schemas import AquaAsset, MiseToolInfo
from InstallRelease.utils import logger, pprint

from InstallRelease.providers.mise.config import (
    _MISE_REGISTRY_BASE,
    _AQUA_REGISTRY_BASE,
    _current_os,
    _current_arch,
    _trim_v,
)


def _expand_template(
    template: str, version: str, os_name: str, arch: str, fmt: str
) -> str:
    """Expand aqua Go-template variables in an asset filename string."""
    result = template
    result = result.replace("{{trimV .Version}}", _trim_v(version))
    result = result.replace("{{.Version}}", version)
    result = result.replace("{{.OS}}", os_name)
    result = result.replace("{{.Arch}}", arch)
    result = result.replace("{{.Format}}", fmt)
    return result


def get_mise_toml(toolname: str) -> dict:
    """Fetch and parse the mise registry TOML for *toolname*."""
    url = f"{_MISE_REGISTRY_BASE}/{toolname}.toml"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return tomllib.loads(response.text)


def get_aqua_registry_yaml(aqua_path: str) -> dict:
    """Fetch and parse the aqua registry YAML for the given aqua path."""
    url = f"{_AQUA_REGISTRY_BASE}/{aqua_path}/registry.yaml"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return yaml.safe_load(response.text)


def get_backend(toolname: str) -> Optional[MiseToolInfo]:
    """Return mise registry info for the first aqua backend.

    Returns ``None`` if no aqua backend is declared or the tool is not found.
    """
    try:
        data = get_mise_toml(toolname)
    except Exception:
        return None

    description = data.get("description", "")

    for backend in data.get("backends", []):
        if backend.startswith("aqua:"):
            path = backend[len("aqua:") :]
            parts = path.split("/")
            if len(parts) >= 2:
                return MiseToolInfo(
                    owner=parts[0],
                    repo=parts[1],
                    aqua_path=path,
                    description=description,
                )
    return None


def _pick_latest_override(pkg: dict) -> Optional[dict]:
    """Return the version_override with constraint ``"true"`` (latest template).

    Aqua uses ``"true"`` as the catch-all / latest-version constraint.
    """
    for override in reversed(pkg.get("version_overrides", [])):
        if str(override.get("version_constraint", "")).strip() == "true":
            return override
    return None


def resolve_download_url(
    toolname: str,
    version: str,
    *,
    os_name: Optional[str] = None,
    arch: Optional[str] = None,
) -> Optional[AquaAsset]:
    """Resolve the download URL for *toolname* at *version* via the aqua registry.

    Args:
        toolname: Tool name as it appears in the mise registry (e.g. ``"fzf"``).
        version:  Version tag (e.g. ``"v0.55.0"``).
        os_name:  Override detected OS (useful for tests / cross-resolution).
        arch:     Override detected architecture.

    Returns:
        An ``AquaAsset`` with the expanded download URL, or ``None`` on failure.
    """
    backend = get_backend(toolname)
    if backend is None:
        return None

    owner, repo = backend.owner, backend.repo
    description = backend.description

    try:
        registry = get_aqua_registry_yaml(backend.aqua_path)
    except Exception:
        return None

    packages = registry.get("packages", [])
    if not packages:
        return None

    pkg = packages[0]
    os_name = os_name or _current_os()
    arch = arch or _current_arch()
    pkg_type = pkg.get("type", "github_release")

    if pkg_type == "github_release":
        pprint(
            f"\n[bold cyan]💡 [yellow]{toolname}[/yellow] uses GitHub releases. "
            f"Install directly with: [green]ir get https://github.com/{owner}/{repo}[/green][/bold cyan]\n"
        )
        return None
    elif pkg_type != "http":
        logger.info(
            f"Skipping unsupported aqua package type '{pkg_type}' for {toolname}"
        )
        return None

    override = _pick_latest_override(pkg)

    # ── type: http ─────────────────────────────────────────────────────────
    # The package declares a full URL template rather than a GitHub asset name.
    # The override may narrow the URL, but if absent the pkg-level url is used.
    if pkg_type == "http":
        url_template = pkg.get("url", "")
        if override:
            url_template = override.get("url", url_template)
        if not url_template:
            return None
        fmt = (
            override.get("format", pkg.get("format", "zip"))
            if override
            else pkg.get("format", "zip")
        )
        download_url = _expand_template(url_template, version, os_name, arch, fmt)
        filename = download_url.split("/")[-1]
        return AquaAsset(
            url=download_url,
            name=filename,
            version=version,
            fmt=fmt,
            owner=owner,
            repo=repo,
            description=description,
        )

    # ── type: github_release (default) ─────────────────────────────────────
    if override:
        asset_template = override.get("asset", pkg.get("asset", ""))
        fmt = override.get("format", pkg.get("format", "tar.gz"))
        for os_override in override.get("overrides", []):
            if os_override.get("goos") == os_name:
                fmt = os_override.get("format", fmt)
    else:
        asset_template = pkg.get("asset", "")
        fmt = pkg.get("format", "tar.gz")

    if not asset_template:
        return None

    filename = _expand_template(asset_template, version, os_name, arch, fmt)
    download_url = (
        f"https://github.com/{owner}/{repo}/releases/download/{version}/{filename}"
    )

    return AquaAsset(
        url=download_url,
        name=filename,
        version=version,
        fmt=fmt,
        owner=owner,
        repo=repo,
        description=description,
    )
