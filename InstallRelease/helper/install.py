"""Provider-agnostic helpers: download, extract, binary detection and install."""

from __future__ import annotations

import glob
import os
import platform
import re
from typing import Optional

from magic.compat import detect_from_filename

from InstallRelease.utils import download, extract, logger, sh

# Matches binary executables and JavaScript files with a node shebang
_EXEC_PATTERN = r"application\/(x-(\w+-)?(executable|binary)|javascript)"


# ── Download + extract ───────────────────────────────────────────────────────


def extract_url(url: str, at: str) -> bool:
    """Download *url* into *at* and extract if it is an archive.

    Returns ``True`` on success; propagates exceptions from ``extract()``.
    """
    path = download(url, at)
    logger.debug(f"Downloaded: {path}")
    if not re.match(_EXEC_PATTERN, detect_from_filename(path).mime_type):
        extract(path=path, at=at)
        logger.debug("Extraction done.")
    return True


# ── Binary finding + installation ────────────────────────────────────────────


def _install_binary(source: str, dest: str, name: str = "", local: bool = True) -> bool:
    """Install a single binary from *source* to *dest*."""
    system = platform.system().lower()
    if system not in ("linux", "darwin"):
        logger.error(f"Unsupported platform: {system}")
        return False

    prefix = "" if local else "sudo "
    target = f"{dest}/{name}" if name else dest
    cmd = f"{prefix}install {source} {target}"

    logger.info(cmd)
    out = sh(cmd)
    if out.returncode != 0:
        logger.error(out.stderr)
        return False
    logger.info(f"[bold green]Installed: {name}[/]", extra={"markup": True})
    return True


def install_bin(
    src: str,
    dest: str,
    local: bool,
    name: Optional[str] = None,
    skip_extensions: Optional[list[str]] = None,
) -> bool:
    """Find the single executable inside *src* and install it to *dest*.

    Args:
        src:              Source directory to search recursively for binaries.
        dest:             Destination directory.
        local:            Install locally (no sudo) when ``True``.
        name:             Rename the binary at the destination.
        skip_extensions:  File extensions to ignore (default: ``["ts"]``).

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    if skip_extensions is None:
        skip_extensions = ["ts"]

    bin_files: list[str] = []

    for file in glob.iglob(f"{src}/**", recursive=True):
        f = detect_from_filename(file)
        if f.name == "directory":
            continue
        if not re.match(_EXEC_PATTERN, f.mime_type):
            continue

        file_ext = os.path.splitext(file)[1].lower().lstrip(".")

        if skip_extensions and file_ext in skip_extensions:
            logger.debug(f"Skipping script file: {file}")
            continue

        if file_ext in ("js", "ts"):
            try:
                with open(file, "rb") as fh:
                    shebang = fh.read(32)
                if b"#!/usr/bin/env node" not in shebang:
                    logger.debug(f"Skipping non-runnable .js (no node shebang): {file}")
                    continue
            except Exception:
                continue

        if not os.access(file, os.X_OK):
            try:
                os.chmod(file, 0o755)
                logger.debug(f"Made file executable: {file}")
            except Exception as e:
                logger.error(f"Failed to make file executable: {e}")
                continue

        bin_files.append(file)

    if len(bin_files) != 1:
        logger.error(f"Expected a single binary, found: {bin_files}")
        return False

    return _install_binary(source=bin_files[0], dest=dest, name=name or "", local=local)
