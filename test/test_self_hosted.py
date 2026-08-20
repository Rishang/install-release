from __future__ import annotations

import pytest

from InstallRelease.providers.base import Provider
from InstallRelease.providers.git import forgejo, gitlab
from InstallRelease.providers.git.base import (
    UnsupportedRepositoryError,
    split_prefixed_url,
)
from InstallRelease.providers.git.main import _PROVIDER_CLASSES, host_token
from InstallRelease.schemas import ToolConfig


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        ("gitlab@gitlab.example.com/g/tool", "gitlab_self"),
        ("forgejo@git.example.com/o/r", "forgejo_self"),
        ("https://gitlab.com/o/r", "gitlab"),
        ("https://codeberg.org/o/r", "codeberg"),
    ],
)
def test_prefix_resolves_to_provider(url, provider):
    assert Provider.resolve_provider(url) == provider
    assert provider in _PROVIDER_CLASSES


def test_split_prefixed_url_keeps_subgroups():
    assert split_prefixed_url("gitlab@host/g/sub/tool", "gitlab@") == (
        "host",
        "g/sub/tool",
    )


@pytest.mark.parametrize("url", ["gitlab@host/tool", "gitlab@host", "gitlab@/o/r"])
def test_split_prefixed_url_rejects_malformed(url):
    with pytest.raises(UnsupportedRepositoryError):
        split_prefixed_url(url, "gitlab@")


def _fake_req(captured):
    def fake_req(self, url):
        captured["url"] = url
        return {"name": "r", "full_name": "o/r", "web_url": "", "star_count": 1}

    return fake_req


@pytest.mark.parametrize(
    ("cls", "url", "api"),
    [
        (
            gitlab.SelfHostedGitlabInfo,
            "gitlab@gitlab.example.com/g/sub/tool",
            "https://gitlab.example.com/api/v4/projects/g%2Fsub%2Ftool",
        ),
        (
            gitlab.GitlabInfo,
            "https://gitlab.com/o/r",
            "https://gitlab.com/api/v4/projects/o%2Fr",
        ),
    ],
)
def test_gitlab_api_base(monkeypatch, cls, url, api):
    captured: dict[str, object] = {}
    monkeypatch.setattr(gitlab.GitlabInfo, "_req", _fake_req(captured))
    repo = cls(url)
    assert repo.api == api
    assert captured["url"] == api
    # the prefixed form must round-trip, upgrade re-resolves the provider from it
    assert repo.repo_url == url


def test_gitlab_self_hosted_asset_fallback_uses_host(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(gitlab.GitlabInfo, "_req", _fake_req(captured))
    repo = gitlab.SelfHostedGitlabInfo("gitlab@gitlab.example.com/g/sub/tool")
    assert repo.host == "gitlab.example.com"
    assert repo.project_path == "g/sub/tool"
    assert repo.repo_name == "tool"


@pytest.mark.parametrize(
    ("cls", "url", "api"),
    [
        (
            forgejo.SelfHostedForgejoInfo,
            "forgejo@git.example.com/o/r",
            "https://git.example.com/api/v1/repos/o/r",
        ),
        (
            forgejo.ForgejoInfo,
            "https://codeberg.org/o/r",
            "https://codeberg.org/api/v1/repos/o/r",
        ),
    ],
)
def test_forgejo_api_base(monkeypatch, cls, url, api):
    captured: dict[str, object] = {}
    monkeypatch.setattr(forgejo.ForgejoInfo, "_req", _fake_req(captured))
    repo = cls(url)
    assert repo.api == api
    assert repo.repo_url == url


def test_flat_token_string_migrates_to_host_map():
    from InstallRelease.config import _migrate_host_tokens

    cfg = ToolConfig(gitlab_token="glpat-x", codeberg_token="cb-x")  # type: ignore[arg-type]
    assert _migrate_host_tokens(cfg) is True
    assert cfg.gitlab_token == {"gitlab.com": "glpat-x"}
    assert cfg.codeberg_token == {"codeberg.org": "cb-x"}
    # already migrated -> no rewrite
    assert _migrate_host_tokens(cfg) is False


def test_host_token_registers_unseen_host(monkeypatch):
    from InstallRelease.providers.git import main

    monkeypatch.setattr(main.cache_config, "save", lambda: None)
    tokens = {"gitlab.com": "glpat-x"}
    assert host_token(tokens, "gitlab.example.com") == ""
    assert tokens == {"gitlab.com": "glpat-x", "gitlab.example.com": ""}
    assert host_token(tokens, "gitlab.com") == "glpat-x"
