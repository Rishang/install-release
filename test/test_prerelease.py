import logging
from datetime import datetime, timezone

from InstallRelease import cli_interact
from InstallRelease.providers.git.base import RepoInfo, get_release
from InstallRelease.providers.git.main import GitInteractProvider
from InstallRelease.providers.git.schemas import Release, ReleaseAssets
from InstallRelease.providers.mise.main import MiseInteractProvider


def _make_asset(name: str = "tool-linux-x86_64.tar.gz") -> ReleaseAssets:
    return ReleaseAssets(
        name=name,
        browser_download_url=f"https://example.com{name}",
        content_type="application/gzip",
        size=1024,
        download_count=1,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        id=1,
        node_id="node1",
        state="uploaded",
    )


def _make_release(
    tag: str,
    prerelease: bool,
    assets: list[ReleaseAssets],
    published_at: str = "2026-01-01T00:00:00Z",
) -> Release:
    return Release(
        url="https://github.com",
        name="repo",
        tag_name=tag,
        prerelease=prerelease,
        published_at=published_at,
        assets=assets,
    )


def test_get_release_skips_prerelease_by_default(caplog):
    pre = _make_release("v2.0.0-beta.1", prerelease=True, assets=[_make_asset()])
    with caplog.at_level(logging.WARNING):
        result = get_release([pre], "https://github.com", pre_release=False)

    assert result is False
    warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == ["No suitable release found (non-prerelease with assets)"]


def test_get_release_selects_prerelease_when_enabled():
    asset = _make_asset("repo-linux-x86_64.tar.gz")
    pre = _make_release("v2.0.0-beta.1", prerelease=True, assets=[asset])

    result = get_release([pre], "https://github.com", pre_release=True)

    assert result == asset


def test_get_release_prerelease_enabled_no_assets_logs_once(caplog):
    pre = _make_release("v2.0.0-beta.1", prerelease=True, assets=[])
    with caplog.at_level(logging.WARNING):
        result = get_release([pre], "https://github.com", pre_release=True)

    assert result is False
    warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == ["No suitable release found (with assets)"]


def test_git_provider_select_passes_pre_release_config(monkeypatch):
    class DummyRepo(RepoInfo):
        repo_url = "https://github.com"
        repo_name = "repo"
        owner = "owner"

        def _req(self, url: str):
            return {}

        def release(self, tag_name: str = "", pre_release: bool = False):
            return []

    asset = _make_asset("repo-linux-x86_64.tar.gz")
    pre = _make_release("v2.0.0-beta.1", prerelease=True, assets=[asset])

    monkeypatch.setattr(
        "InstallRelease.providers.git.main.pre_release_enabled", lambda: True
    )
    provider = GitInteractProvider(DummyRepo())

    assert provider.select([pre]) == asset


def test_mise_get_passes_pre_release_config(monkeypatch):
    captured = []
    monkeypatch.setattr(
        "InstallRelease.providers.mise.main.pre_release_enabled", lambda: True
    )
    provider = MiseInteractProvider("ripgrep")

    def fake_resolve(version: str = "", pre_release: bool = False):
        captured.append((version, pre_release))
        return []

    monkeypatch.setattr(provider, "resolve", fake_resolve)
    provider.get()

    assert captured == [("", True)]


def test_mise_upgrade_passes_pre_release_config(monkeypatch):
    captured = []
    old_release = _make_release(
        "v1.0.0",
        prerelease=False,
        assets=[],
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    )
    monkeypatch.setattr(cli_interact, "pre_release_enabled", lambda: True)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(cli_interact.cache, "state", {"mise:ripgrep#ripgrep": old_release})
    monkeypatch.setattr(
        cli_interact,
        "threads",
        lambda task, data, **kwargs: [task(k) for k in data],
    )

    def fake_resolve(self, version: str = "", pre_release: bool = False):
        captured.append(pre_release)
        return []

    monkeypatch.setattr(MiseInteractProvider, "resolve", fake_resolve)
    cli_interact.upgrade(skip_prompt=True)

    assert captured == [True]
