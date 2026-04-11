"""Mise / Aqua registry dataclasses."""

from dataclasses import dataclass


@dataclass
class AquaAsset:
    """Resolved download asset from the aqua registry."""

    url: str
    name: str
    version: str
    fmt: str
    owner: str
    repo: str
    description: str = ""


@dataclass
class MiseToolInfo:
    """Resolved mise registry metadata."""

    owner: str
    repo: str
    description: str = ""
