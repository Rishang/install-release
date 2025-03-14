from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, fields, field

# locals
from InstallRelease.constants import platform_words

_platform_words = platform_words()


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
    prerelease: bool
    published_at: str
    assets: List[GithubReleaseAssets]
    hold_update: Optional[bool] = field(default=False)
    # author: dict
    # draft: bool
    # target_commitish: str

    def __post_init__(self):
        self.assets = [GithubReleaseAssets(**a) for a in self.assets]

    def published_dt(self):
        return datetime.strptime(self.published_at, "%Y-%m-%dT%H:%M:%SZ")


# GitLab data classes - moved above TypeState to fix the reference error
@dataclass
class GitlabRepoInfo:
    name: str
    path_with_namespace: str
    web_url: str
    description: str
    star_count: int

    # Map GitLab fields to be compatible with GitHub fields
    @property
    def full_name(self):
        return self.path_with_namespace

    @property
    def html_url(self):
        return self.web_url

    @property
    def stargazers_count(self):
        return self.star_count

    @property
    def language(self):
        return "unknown"  # GitLab API doesn't provide this directly

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


@dataclass
class GitlabReleaseAssets:
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
class GitlabRelease:
    url: str
    name: str
    tag_name: str
    prerelease: bool
    published_at: str
    assets: List[GitlabReleaseAssets]
    hold_update: Optional[bool] = field(default=False)

    def __post_init__(self):
        self.assets = [GitlabReleaseAssets(**a) for a in self.assets]

    def published_dt(self):
        return datetime.strptime(self.published_at, "%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ToolConfig:
    token: Optional[str] = field(default_factory=str)
    path: Optional[str] = field(default_factory=str)
    pre_release: Optional[bool] = field(default=False)


class irKey:
    def __init__(self, value):
        self.name = value.split("#")[-1]
        self.url = value.split("#")[0]


# ---------- Type Aliases ----------- #

TypeState = Dict[str, Union[GithubRelease, GitlabRelease]]
