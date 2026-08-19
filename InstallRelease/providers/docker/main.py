from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from InstallRelease.config import dest
from InstallRelease.helper import save_state
from InstallRelease.providers.base import PROVIDER_STATE_KEY_PREFIXES, InteractProvider
from InstallRelease.providers.docker.config import WRAPPER_TEMPLATE
from InstallRelease.providers.docker.schemas import DockerImage
from InstallRelease.providers.git.schemas import Release
from InstallRelease.utils import logger, mkdir, pprint, show_table


def _get_local_digest(cli_ref: str) -> str:
    """Return the sha256 RepoDigest for a locally cached image, or empty string."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", cli_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = result.stdout.strip()
    # RepoDigest format: "image@sha256:abc123..." — extract the digest part
    # Returns "<no value>" when the image has no RepoDigest (e.g. locally built)
    if not raw or raw == "<no value>" or "@" not in raw:
        return ""
    return raw.split("@")[-1]


def _get_remote_digest(cli_ref: str) -> str:
    """Return the manifest digest from the registry, or empty string on failure.

    Uses the docker CLI so any registry and any configured credentials work.
    """
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", cli_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Digest:"):
            return line.split(":", 1)[1].strip()
    logger.debug(f"Remote digest check failed for {cli_ref}: {result.stderr.strip()}")
    return ""


def needs_update(image: str, tag: str, force: bool = False) -> bool:
    """Return True if the Docker image should be re-pulled.

    Pinned (non-latest) tags never auto-upgrade unless --force.
    For latest: compares local RepoDigest against the remote manifest digest.
    """
    if force:
        return True
    if tag != "latest":
        return False
    cli_ref = DockerImage(image=image, tag=tag).cli_ref
    local = _get_local_digest(cli_ref)
    if not local:
        return True  # not cached locally (or built locally) → pull
    remote = _get_remote_digest(cli_ref)
    # unknown remote (registry error, rate limit, no network) → keep what we have
    return bool(remote) and local != remote


def _get_entrypoint(cli_ref: str) -> list[str]:
    """Return the ENTRYPOINT of a pulled image, or empty list if none is set."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Entrypoint}}", cli_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = result.stdout.strip()
    if not raw or raw == "null":
        return []
    try:
        return json.loads(raw) or []
    except json.JSONDecodeError:
        return []


def _split_image_tag(ref: str) -> tuple[str, str]:
    """Split an image reference into (image, tag); default tag is 'latest'."""
    colon = ref.rfind(":")
    if colon > -1:
        return ref[:colon], ref[colon + 1 :]
    return ref, "latest"


class DockerInteractProvider(InteractProvider):
    """InteractProvider that wraps a Docker image as a local CLI tool.

    Writes a shell script to dest/<toolname> that proxies all invocations
    through `docker run`, mounting the current directory into the container.

    Steps
    -----
    1. resolve    → return the target tag(s) (given version or image default)
    2. select     → build a DockerImage for the chosen tag
    3. prompt     → show image details and confirm
    4. install    → docker pull + write executable wrapper script
    5. save_state → persist to cache as a Release
    """

    def __init__(self, image_ref: str) -> None:
        """Accept image_ref without the docker:// prefix, e.g. 'hashicorp/terraform:1.7.0'."""
        image, tag = _split_image_tag(image_ref)
        if "/" not in image:
            image = f"library/{image}"
        self._image = DockerImage(image=image, tag=tag)

    # ── Step 1 ───────────────────────────────────────────────────────────

    def resolve(self, version: str = "", pre_release: bool = False) -> list[str]:
        """Return the tag to install: given version or the image's default tag."""
        return [version] if version else [self._image.tag]

    # ── Step 2 ───────────────────────────────────────────────────────────

    def select(self, candidates: list[str], **hints: Any) -> DockerImage | None:
        """Build a DockerImage for the first candidate tag."""
        if not candidates:
            return None
        return DockerImage(image=self._image.image, tag=candidates[0])

    # ── Step 3 ───────────────────────────────────────────────────────────

    def prompt(self, toolname: str, candidate: DockerImage) -> str:
        """Display image info and ask for install confirmation."""
        show_table(
            data=[{"Tool": toolname, "Image": candidate.image, "Tag": candidate.tag}],
            title=f"Install {toolname} (via Docker)",
        )
        pprint("[color(34)]Install selected tool [Y/n]: ", end="")
        return input().strip().lower() or "y"

    # ── Step 4 ───────────────────────────────────────────────────────────

    def install(
        self, candidate: DockerImage, toolname: str, temp_dir: str, local: bool
    ) -> bool:
        """Pull the Docker image and write an executable wrapper script to dest."""
        pprint(f"[cyan]Pulling {candidate.cli_ref}...[/cyan]")
        result = subprocess.run(["docker", "pull", candidate.cli_ref], check=False)
        if result.returncode != 0:
            logger.error(f"docker pull failed for {candidate.cli_ref}")
            return False

        mkdir(dest)
        script_path = os.path.join(dest, toolname)
        entrypoint = _get_entrypoint(candidate.cli_ref)
        # Images without ENTRYPOINT need the command name prepended explicitly
        args = '"$@"' if entrypoint else f'{toolname} "$@"'
        with open(script_path, "w") as f:
            f.write(WRAPPER_TEMPLATE.format(ref=candidate.cli_ref, args=args))
        os.chmod(script_path, 0o755)
        logger.info(f"Installed wrapper: {script_path}")
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
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Orchestrate the full install flow: resolve -> select -> prompt -> install -> save."""
        toolname = name or self._image.name

        # Step 1
        candidates = self.resolve(version=version)

        # Step 2
        image = self.select(candidates)
        if image is None:
            return

        # Step 3
        if prompt:
            decision = self.prompt(toolname, image)
            if decision != "y":
                return
            pprint("\n[magenta]Pulling image...[/magenta]")

        # Step 4
        if not self.install(image, toolname=toolname, temp_dir="", local=local):
            return

        # Step 5
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        release = Release(
            url=f"docker@{image.cli_image}",  # user-facing format shown by ir ls
            name=toolname,
            tag_name=image.tag,
            prerelease=False,
            published_at=now_str,
            assets=[],
            description=f"Docker image wrapper: {image.cli_ref}",
        )
        # Pin hold_update for any non-latest tag so upgrade skips them
        release.hold_update = image.tag != "latest"

        state_key = f"{PROVIDER_STATE_KEY_PREFIXES['docker']}{image.image}#{toolname}"
        self.save_state(state_key, release)
