from dataclasses import dataclass, field
from typing import NamedTuple


@dataclass
class ToolConfig:
    token: str | None = field(default_factory=str)
    gitlab_token: str | None = field(default_factory=str)
    codeberg_token: str | None = field(default_factory=str)
    path: str | None = field(default_factory=str)
    pre_release: bool | None = field(default=False)


class irKey(NamedTuple):
    url: str
    name: str

    @classmethod
    def parse(cls, value: str) -> "irKey":
        if "#" not in value:
            raise ValueError(f"Invalid key format (missing '#'): {value}")
        url, _, name = value.rpartition("#")
        return cls(url=url, name=name)
