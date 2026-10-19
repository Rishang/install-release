from typer.testing import CliRunner

from InstallRelease import cli, cli_interact


def test_upgrade_accepts_and_filters_by_name(monkeypatch):
    captured = []
    monkeypatch.setattr(
        cli_interact.cache, "state", {"repo#zen": object(), "repo#other": object()}
    )
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(
        cli_interact,
        "threads",
        lambda task, data, **kwargs: captured.extend(data),
    )

    result = CliRunner().invoke(cli.app, ["upgrade", "zen", "--yes"])

    assert result.exit_code == 0
    assert captured == ["repo#zen"]


def test_me_upgrade_keeps_running_binary_name(monkeypatch):
    for argv0, expected in [
        ("/home/u/bin/ir", "ir get https://github.com/Rishang/install-release -n ir"),
        (
            "install-release",
            "install-release get https://github.com/Rishang/install-release -n install-release",
        ),
        (
            "/src/InstallRelease/cli.py",
            "ir get https://github.com/Rishang/install-release -n ir",
        ),
    ]:
        ran = []
        monkeypatch.setattr(cli.sys, "argv", [argv0])
        monkeypatch.setattr(cli.os, "system", ran.append)

        result = CliRunner().invoke(cli.app, ["me", "-U"])

        assert result.exit_code == 0
        assert ran == [expected]
