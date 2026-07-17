"""Git / GitHub / GitLab release-related dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime

from InstallRelease.utils import FilterDataclass

_valid_install_methods = ["binary", "package"]
_valid_package_types = ["deb", "rpm", "AppImage", "binary"]


@dataclass
class RepositoryInfo:
    name: str = ""
    full_name: str = ""
    html_url: str = ""
    description: str = ""
    language: str = ""
    stargazers_count: int = 0


@dataclass
class ReleaseAssets:
    browser_download_url: str = ""
    content_type: str = ""
    created_at: str = ""
    download_count: int = 0
    id: int = 0
    name: str = ""
    node_id: str = ""
    size: int = 0
    state: str = ""
    updated_at: str = ""

    def size_mb(self) -> float:
        return round(self.size / 1_000_000, 2)


@dataclass
class Release:
    url: str
    name: str
    tag_name: str
    prerelease: bool
    published_at: str
    assets: list[ReleaseAssets]
    description: str | None = field(default=None)
    hold_update: bool | None = field(default=False)
    custom_release_words: list[str] | None = field(default=None)
    package_type: str | None = field(
        default="binary"
    )  # "deb", "rpm", "AppImage", "binary"
    install_method: str | None = field(default="binary")  # "binary" or "package"
    package_name: str | None = field(default=None)

    def __post_init__(self):
        if self.package_type and self.package_type.lower() == "appimage":
            self.package_type = "AppImage"
        if self.install_method and self.install_method not in _valid_install_methods:
            raise ValueError(f"Unsupported install method: {self.install_method}")
        if self.package_type and self.package_type not in _valid_package_types:
            raise ValueError(f"Unsupported package type: {self.package_type}")

        processed_assets = []
        for a in self.assets:
            if isinstance(a, ReleaseAssets):
                processed_assets.append(a)
            elif isinstance(a, dict):
                processed_assets.append(FilterDataclass(a, obj=ReleaseAssets))
            else:
                raise TypeError(f"Unsupported asset type: {type(a)}")
        self.assets = processed_assets

    @property
    def is_package(self) -> bool:
        return self.install_method == "package"

    def published_dt(self):
        # GitHub uses Z-suffixed UTC; Forgejo/Gitea use ISO 8601 with a numeric
        # timezone offset (e.g. "+02:00"). Try the fast strptime paths first,
        # then fall back to fromisoformat for offset-aware timestamps.
        for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
            try:
                return datetime.strptime(self.published_at, fmt)
            except ValueError:
                continue

        try:
            # Python 3.10's fromisoformat doesn't accept a 'Z' suffix; normalise it.
            return datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
        except ValueError:
            pass

        raise ValueError(f"Cannot parse date: {self.published_at}")


TypeState = dict[str, Release]
