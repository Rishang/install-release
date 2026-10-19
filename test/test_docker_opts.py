import logging
from unittest.mock import MagicMock

from typer.testing import CliRunner

from InstallRelease import cli, cli_interact
from InstallRelease.providers.docker.main import DockerInteractProvider
from InstallRelease.providers.git.schemas import Release


def test_docker_interact_provider_get_passes_docker_opts(monkeypatch, tmp_path):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint",
        lambda ref: ["/entrypoint"],
    )
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("InstallRelease.providers.docker.main.subprocess.run", mock_run)

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
    assert (
        'docker run --rm -i $termflag -v "${PWD}:/tmp/cmd" -w /tmp/cmd -v /host/path:/container/path:ro'
        in content
    )

    # Check state was stored with docker_opts
    key = "docker:library/alpine#alpine-custom"
    assert key in saved_state
    assert saved_state[key].docker_opts == "-v /host/path:/container/path:ro"


def test_docker_interact_provider_empty_docker_opts_removes(monkeypatch, tmp_path):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint",
        lambda ref: ["/entrypoint"],
    )
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    saved_state = {}
    monkeypatch.setattr(
        DockerInteractProvider,
        "save_state",
        lambda self, key, release: saved_state.update({key: release}),
    )

    provider = DockerInteractProvider("alpine:3.19")

    # First install with opts
    provider.get(
        name="alpine-custom",
        prompt=False,
        docker_opts="-v /old/path:/old/path",
    )
    wrapper_path = dest_dir / "alpine-custom"
    assert "-v /old/path:/old/path" in wrapper_path.read_text()
    assert (
        saved_state["docker:library/alpine#alpine-custom"].docker_opts
        == "-v /old/path:/old/path"
    )

    # Re-running with empty docker_opts clears it
    provider.get(
        name="alpine-custom",
        prompt=False,
        docker_opts="",
    )

    content = wrapper_path.read_text()
    assert "-v /old/path:/old/path" not in content
    assert "-w /tmp/cmd" in content
    assert "alpine:3.19" in content
    assert saved_state["docker:library/alpine#alpine-custom"].docker_opts == ""


def test_docker_interact_provider_omitted_docker_opts_preserves_stored_opts(
    monkeypatch, tmp_path
):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint",
        lambda ref: ["/entrypoint"],
    )
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    saved_state = {}
    monkeypatch.setattr(
        DockerInteractProvider,
        "save_state",
        lambda self, key, release: saved_state.update({key: release}),
    )
    monkeypatch.setattr(
        DockerInteractProvider,
        "load_state",
        lambda self, key: saved_state.get(key),
    )

    provider = DockerInteractProvider("alpine:3.19")

    # 1. First install with opts
    provider.get(
        name="alpine-custom",
        prompt=False,
        docker_opts="-v /persistent:/persistent",
    )
    wrapper_path = dest_dir / "alpine-custom"
    assert "-v /persistent:/persistent" in wrapper_path.read_text()
    key = "docker:library/alpine#alpine-custom"
    assert saved_state[key].docker_opts == "-v /persistent:/persistent"

    # 2. Re-run without docker_opts (omitted -> defaults to None)
    provider.get(
        name="alpine-custom",
        prompt=False,
    )
    content = wrapper_path.read_text()
    assert "-v /persistent:/persistent" in content
    assert saved_state[key].docker_opts == "-v /persistent:/persistent"


def test_cli_get_defaults_docker_opts_to_none(monkeypatch):
    captured_args = {}

    def fake_get(url, **kwargs):
        captured_args["url"] = url
        captured_args.update(kwargs)

    monkeypatch.setattr(cli, "_get", fake_get)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "get",
            "docker@alpine:latest",
            "-y",
        ],
    )

    assert result.exit_code == 0
    assert captured_args["docker_opts"] is None


def test_cli_get_passes_docker_opts_to_get_function(monkeypatch):
    captured_args = {}

    def fake_get(url, **kwargs):
        captured_args["url"] = url
        captured_args.update(kwargs)

    monkeypatch.setattr(cli, "_get", fake_get)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "get",
            "docker@alpine:latest",
            "--name",
            "my-alpine",
            "--docker-opts",
            "-v /data:/data",
            "-y",
        ],
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
    state = {"docker:library/alpine#alpine": existing_release}

    monkeypatch.setattr(cli_interact.cache, "state", state)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(
        cli_interact, "docker_needs_update", lambda *args, **kwargs: True
    )

    upgraded_call = {}

    def fake_get(url, **kwargs):
        upgraded_call["url"] = url
        upgraded_call.update(kwargs)

    monkeypatch.setattr(cli_interact, "get", fake_get)

    cli_interact.upgrade(name="alpine", skip_prompt=True, force=True)

    assert upgraded_call.get("docker_opts") == "-v /shared:/shared"
    assert upgraded_call.get("name") == "alpine"


def test_real_install_and_upgrade_preserves_docker_opts(monkeypatch, tmp_path):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.config.dest", str(dest_dir))
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint",
        lambda ref: ["/entrypoint"],
    )
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    state_dict = {}
    monkeypatch.setattr(cli_interact.cache, "state", state_dict)
    monkeypatch.setattr("InstallRelease.helper.state.cache.state", state_dict)
    monkeypatch.setattr(
        "InstallRelease.helper.state.cache.set",
        lambda k, v: state_dict.update({k: v}),
    )
    monkeypatch.setattr("InstallRelease.helper.state.cache.save", lambda: None)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(
        cli_interact, "docker_needs_update", lambda *args, **kwargs: True
    )

    # 1. Install tool with docker_opts
    cli_interact.get(
        "docker@alpine:latest",
        name="alpine-tool",
        docker_opts="-v /my/data:/data:rw",
        prompt=False,
    )

    # Verify wrapper created with docker_opts
    wrapper_path = dest_dir / "alpine-tool"
    assert wrapper_path.exists()
    assert "-v /my/data:/data:rw" in wrapper_path.read_text()

    # Verify state saved with docker_opts
    key = "docker:library/alpine#alpine-tool"
    assert key in state_dict
    assert state_dict[key].docker_opts == "-v /my/data:/data:rw"

    # 2. Run real upgrade
    cli_interact.upgrade(name="alpine-tool", skip_prompt=True, force=True)

    # Verify regenerated wrapper and state still retain docker_opts
    content = wrapper_path.read_text()
    assert "-v /my/data:/data:rw" in content
    assert state_dict[key].docker_opts == "-v /my/data:/data:rw"


def test_cli_interact_get_omitted_docker_opts_preserves_stored_opts(
    monkeypatch, tmp_path
):
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()
    monkeypatch.setattr("InstallRelease.config.dest", str(dest_dir))
    monkeypatch.setattr("InstallRelease.providers.docker.main.dest", str(dest_dir))
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main._get_entrypoint",
        lambda ref: ["/entrypoint"],
    )
    monkeypatch.setattr(
        "InstallRelease.providers.docker.main.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=0)),
    )

    state_dict = {}
    monkeypatch.setattr(cli_interact.cache, "state", state_dict)
    monkeypatch.setattr("InstallRelease.helper.state.cache.state", state_dict)
    monkeypatch.setattr(
        "InstallRelease.helper.state.cache.set",
        lambda k, v: state_dict.update({k: v}),
    )
    monkeypatch.setattr("InstallRelease.helper.state.cache.save", lambda: None)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)

    # 1. Install tool with docker_opts
    cli_interact.get(
        "docker@alpine:3.19",
        name="alpine-tool",
        docker_opts="-v /persistent:/persistent",
        prompt=False,
    )
    wrapper_path = dest_dir / "alpine-tool"
    assert "-v /persistent:/persistent" in wrapper_path.read_text()
    key = "docker:library/alpine#alpine-tool"
    assert state_dict[key].docker_opts == "-v /persistent:/persistent"

    # 2. Re-run get without docker_opts (e.g. changing tag or reinstalling)
    cli_interact.get(
        "docker@alpine:latest",
        name="alpine-tool",
        prompt=False,
    )
    content = wrapper_path.read_text()
    assert "-v /persistent:/persistent" in content
    assert state_dict[key].docker_opts == "-v /persistent:/persistent"


def test_cli_interact_get_warns_docker_opts_on_non_docker_url(monkeypatch, caplog):
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    fake_provider = MagicMock()
    monkeypatch.setattr(cli_interact, "get_repo_info", lambda url: fake_provider)
    monkeypatch.setattr(
        cli_interact, "GitInteractProvider", MagicMock(return_value=fake_provider)
    )

    with caplog.at_level(logging.WARNING):
        cli_interact.get("https://github.com/example/tool", docker_opts="-v /a:/b")

    assert "--docker-opts is only supported for docker images" in caplog.text
