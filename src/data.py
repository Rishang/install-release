from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, fields, field

# locals
from src.utils import platform_words, logger

_platform_words = platform_words()

logger.debug(msg=("platform_words: ", _platform_words))

exception_compressed_mime_type = [
    "application/x-7z-compressed",
]


@dataclass
class OsInfo:
    architecture: List[str]
    platform: str
    platform_words: List[str]


@dataclass(init=False)
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
        self.size_mb = int(str(self.size / 1000000)[:4])
        self.updated_at_dt = datetime.strptime(self.created_at, "%Y-%m-%dT%XZ")


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
