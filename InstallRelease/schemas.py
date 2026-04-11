from typing import NamedTuple, Optional
from dataclasses import dataclass, field


@dataclass
class ToolConfig:
    token: Optional[str] = field(default_factory=str)
    gitlab_token: Optional[str] = field(default_factory=str)
    path: Optional[str] = field(default_factory=str)
    pre_release: Optional[bool] = field(default=False)


class irKey(NamedTuple):
    url: str
    name: str

    @classmethod
    def parse(cls, value: str) -> "irKey":
        if "#" not in value:
            raise ValueError(f"Invalid key format (missing '#'): {value}")
        url, _, name = value.rpartition("#")
        return cls(url=url, name=name)
