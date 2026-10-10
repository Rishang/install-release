from unittest.mock import MagicMock
from typer.testing import CliRunner

from InstallRelease import cli, cli_interact
from InstallRelease.providers.docker.main import DockerInteractProvider
from InstallRelease.providers.docker.schemas import DockerImage
from InstallRelease.providers.git.schemas import Release


def test_docker_interact_provider_get_passes_docker_opts(monkeypatch, tmp_path):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint", lambda ref: ["/entrypoint"]
    )
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", mock_run)

    saved_state = {}
    monkeypatch.setattr(
        DockerInteractProvider,
        "save_state",
        lambda self, key, release: saved_state.update({key: release}),
    )

    provider = DockerInteractProvider("alpine:3.19")
    provider.get(
        name="alpine-custom",
        prompt=False,
        docker_opts="-v /host/path:/container/path:ro",
    )

    wrapper_path = dest_dir / "alpine-custom"
    assert wrapper_path.exists()
    content = wrapper_path.read_text()
    assert "-v /host/path:/container/path:ro" in content
    assert 'docker run --rm -i $termflag -v "${PWD}:/tmp/cmd" -w /tmp/cmd -v /host/path:/container/path:ro' in content

    # Check state was stored with docker_opts
    key = "docker:library/alpine#alpine-custom"
    assert key in saved_state
    assert saved_state[key].docker_opts == "-v /host/path:/container/path:ro"


def test_docker_interact_provider_empty_docker_opts_removes(monkeypatch, tmp_path):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint", lambda ref: ["/entrypoint"]
    )
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=MagicMock(returncode=0)))

    saved_state = {}
    monkeypatch.setattr(
        DockerInteractProvider,
        "save_state",
        lambda self, key, release: saved_state.update({key: release}),
    )

    provider = DockerInteractProvider("alpine:3.19")
    provider.get(
        name="alpine-custom",
        prompt=False,
        docker_opts="",
    )

    wrapper_path = dest_dir / "alpine-custom"
    content = wrapper_path.read_text()
    assert 'docker run --rm -i $termflag -v "${PWD}:/tmp/cmd" -w /tmp/cmd  alpine:3.19' in content
    assert saved_state["docker:library/alpine#alpine-custom"].docker_opts == ""


def test_cli_get_passes_docker_opts_to_get_function(monkeypatch):
    captured_args = {}

    def fake_get(url, **kwargs):
        captured_args["url"] = url
        captured_args.update(kwargs)

    monkeypatch.setattr(cli, "_get", fake_get)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["get", "docker@alpine:latest", "--name", "my-alpine", "--docker-opts", "-v /data:/data", "-y"],
    )

    assert result.exit_code == 0
    assert captured_args["url"] == "docker@alpine"
    assert captured_args["docker_opts"] == "-v /data:/data"
    assert captured_args["name"] == "my-alpine"


def test_upgrade_preserves_docker_opts(monkeypatch):
    existing_release = Release(
        url="docker@alpine",
        name="alpine",
        tag_name="3.19",
        prerelease=False,
        published_at="2024-01-01T00:00:00Z",
        assets=[],
        docker_opts="-v /shared:/shared",
    )
    state = {"docker://library/alpine#alpine": existing_release}

    monkeypatch.setattr(cli_interact.cache, "state", state)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(cli_interact, "docker_needs_update", lambda *args, **kwargs: True)

    upgraded_call = {}

    def fake_get(url, **kwargs):
        upgraded_call["url"] = url
        upgraded_call.update(kwargs)

    monkeypatch.setattr(cli_interact, "get", fake_get)

    cli_interact.upgrade(name="alpine", skip_prompt=True, force=True)

    assert upgraded_call.get("docker_opts") == "-v /shared:/shared"
    assert upgraded_call.get("name") == "alpine"
