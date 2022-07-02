from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, fields, field

# locals
from InstallRelease.constants import platform_words

_platform_words = platform_words()


exception_compressed_mime_type = [
    "application/x-7z-compressed",
]


@dataclass
class OsInfo:
    architecture: List[str]
    platform: str
    platform_words: List[str]


@dataclass
class GithubRepoInfo:
    name: str
    full_name: str
    html_url: str
    description: str
    language: str
    stargazers_count: int

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


@dataclass
class GithubReleaseAssets:
    browser_download_url: str
    content_type: str
    created_at: str
    download_count: int
    id: int
    name: str
    node_id: str
    size: int
    state: str
    updated_at: str

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    def __post_init__(self):
        self.updated_at_dt = datetime.strptime(self.created_at, "%Y-%m-%dT%XZ")

    def size_mb(self) -> float:
        return float(str(self.size / 1000000)[:4])


@dataclass
class GithubRelease:
    url: str
    name: str
    tag_name: str
    # author: dict
    # target_commitish: str
    # draft: bool
    prerelease: bool
    published_at: str
    assets: List[GithubReleaseAssets]
    # install_path: Optional[str] = field(default_factory=str)

    def __post_init__(self):
        self.assets = [GithubReleaseAssets(**a) for a in self.assets]

    def published_dt(self):
        return datetime.strptime(self.published_at, "%Y-%m-%dT%H:%M:%SZ")


# ---------- Type Aliases ----------- #

TypeState = Dict[str, GithubRelease]
