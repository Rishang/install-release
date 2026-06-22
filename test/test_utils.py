from __future__ import annotations

import io

from rich.console import Console

from InstallRelease import utils


class _FakeResponse:
    def __init__(self) -> None:
        self.closed = False
        self.iterated_chunk_size: int | None = None
        self.headers = {"content-length": "6"}
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1024 * 1024):
        self.iterated_chunk_size = chunk_size
        yield b"ab"
        yield b"cd"
        yield b"ef"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    @property
    def content(self):
        raise AssertionError(
            "download() should stream chunks instead of reading content"
        )


def test_download_streams_to_disk_and_uses_timeout(tmp_path, monkeypatch):
    fake_response = _FakeResponse()
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_response

    monkeypatch.setattr(utils.requests_session, "get", fake_get)
    monkeypatch.setattr(
        utils, "console", Console(file=io.StringIO(), force_terminal=False)
    )

    output = utils.download(
        "https://example.com/helm-v4.2.0-linux-amd64.tar.gz", str(tmp_path)
    )

    assert output == f"{tmp_path}/helm-v4.2.0-linux-amd64.tar.gz"
    assert (tmp_path / "helm-v4.2.0-linux-amd64.tar.gz").read_bytes() == b"abcdef"
    assert captured["url"] == "https://example.com/helm-v4.2.0-linux-amd64.tar.gz"
    assert captured["kwargs"]["stream"] is True
    assert captured["kwargs"]["timeout"] == utils.REQUEST_TIMEOUT
    assert fake_response.iterated_chunk_size == utils.DOWNLOAD_CHUNK_SIZE
    assert fake_response.closed is True
