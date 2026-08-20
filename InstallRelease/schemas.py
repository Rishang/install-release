from dataclasses import dataclass, field
from typing import NamedTuple

GITLAB_HOST = "gitlab.com"
CODEBERG_HOST = "codeberg.org"


@dataclass
class ToolConfig:
    token: str | None = field(default_factory=str)
    # host -> token, so self-hosted instances carry their own credentials
    gitlab_token: dict[str, str] = field(default_factory=lambda: {GITLAB_HOST: ""})
    codeberg_token: dict[str, str] = field(default_factory=lambda: {CODEBERG_HOST: ""})
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
