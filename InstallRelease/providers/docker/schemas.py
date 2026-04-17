from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DockerImage:
    """Parsed Docker image reference with repository path and tag."""

    image: str  # e.g. "hashicorp/terraform" or "library/alpine"
    tag: str  # e.g. "latest" or "1.7.0"

    @property
    def cli_image(self) -> str:
        """Image name without library/ prefix, suitable for docker CLI and display."""
        return (
            self.image[len("library/") :]
            if self.image.startswith("library/")
            else self.image
        )

    @property
    def cli_ref(self) -> str:
        """Full reference for docker CLI: cli_image:tag."""
        return f"{self.cli_image}:{self.tag}"

    @property
    def name(self) -> str:
        return self.image.split("/")[-1]
