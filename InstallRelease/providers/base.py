from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from InstallRelease.providers.git.schemas import Release, RepositoryInfo

PROVIDER_STATE_KEY_PREFIXES: dict[str, str] = {
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "mise": "mise:",
    "docker": "docker:",
}


class Provider(ABC):
    """Base class for all tool providers (git, mise, etc.)."""

    repo_url: str = ""
    repo_name: str = ""
    owner: str = ""
    info: "RepositoryInfo | None" = None

    @abstractmethod
    def release(
        self, tag_name: str = "", pre_release: bool = False
    ) -> "list[Release]": ...

    @staticmethod
    def resolve_provider(url: str) -> Optional[str]:
        for name, prefix in PROVIDER_STATE_KEY_PREFIXES.items():
            if url.startswith(prefix):
                return name
        return None


class InteractProvider(ABC):
    """Abstract builder for interactive tool installation.

    Subclasses implement resolve/select/prompt/install/save_state steps;
    get() orchestrates them.
    """

    @abstractmethod
    def resolve(self, version: str = "", pre_release: bool = False) -> list[Any]: ...

    @abstractmethod
    def select(self, candidates: list[Any], **hints: Any) -> Optional[Any]: ...

    @abstractmethod
    def prompt(self, toolname: str, candidate: Any) -> str: ...

    @abstractmethod
    def install(
        self, candidate: Any, toolname: str, temp_dir: str, local: bool
    ) -> bool: ...

    @abstractmethod
    def save_state(self, key: str, result: Any) -> None: ...

    @abstractmethod
    def get(
        self,
        version: str = "",
        local: bool = True,
        prompt: bool = False,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None: ...
