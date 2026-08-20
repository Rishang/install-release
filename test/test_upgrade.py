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
