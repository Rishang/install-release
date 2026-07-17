from __future__ import annotations

import pytest

from InstallRelease.providers.base import Provider
from InstallRelease.providers.git import forgejo
from InstallRelease.providers.git.main import _PROVIDER_CLASSES
from InstallRelease.providers.git.schemas import Release


def test_codeberg_resolves_to_codeberg_provider():
    assert Provider.resolve_provider("https://codeberg.org/forgejo/forgejo") == (
        "codeberg"
    )
    assert "codeberg" in _PROVIDER_CLASSES


def test_forgejo_iso_offset_date_is_parsed():
    """Forgejo/Gitea emit ISO 8601 timestamps with a numeric tz offset."""
    release = Release(
        url="https://codeberg.org/o/r",
        name="r",
        tag_name="v1.0.0",
        prerelease=False,
        published_at="2026-06-10T08:11:24+02:00",
        assets=[],
    )
    dt = release.published_dt()
    assert (dt.year, dt.month, dt.day) == (2026, 6, 10)


def test_forgejo_info_builds_api_base_and_maps_stars(monkeypatch):
    """API base is derived from the repo host; stars_count -> stargazers_count."""
    captured: dict[str, object] = {}

    def fake_req(self, url):
        captured["url"] = url
        return {
            "name": "r",
            "full_name": "o/r",
            "html_url": "https://codeberg.org/o/r",
            "description": "demo",
            "stars_count": 42,
        }

    monkeypatch.setattr(forgejo.ForgejoInfo, "_req", fake_req)

    repo = forgejo.ForgejoInfo("https://codeberg.org/o/r", token="t")

    assert repo.api == "https://codeberg.org/api/v1/repos/o/r"
    assert captured["url"] == repo.api
    assert repo.owner == "o" and repo.repo_name == "r"
    assert repo.info is not None
    assert repo.info.stargazers_count == 42


def test_self_hosted_forgejo_host_is_honoured(monkeypatch):
    monkeypatch.setattr(
        forgejo.ForgejoInfo,
        "_req",
        lambda self, url: {"name": "r", "full_name": "o/r", "stars_count": 0},
    )
    repo = forgejo.ForgejoInfo("https://git.example.com/o/r")
    assert repo.api == "https://git.example.com/api/v1/repos/o/r"


def test_forgejo_rejects_malformed_url(monkeypatch):
    from InstallRelease.providers.git.base import UnsupportedRepositoryError

    with pytest.raises(UnsupportedRepositoryError):
        forgejo.ForgejoInfo("not-a-url")
