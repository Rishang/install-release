from types import SimpleNamespace

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


def _stub_bin_and_pkg_upgrades(monkeypatch) -> tuple[list, list]:
    """One outdated binary and one outdated package; returns (installs, sudo calls)."""

    def state_entry(is_pkg: bool) -> SimpleNamespace:
        return SimpleNamespace(
            is_package=is_pkg,
            hold_update=False,
            tag_name="v1",
            docker_opts=None,
            published_dt=lambda: 1,
        )

    state = {
        "https://github.com/o/bin#bin": state_entry(False),
        "https://github.com/o/pkg#pkg": state_entry(True),
    }
    latest = SimpleNamespace(tag_name="v2", published_dt=lambda: 2)
    installs, sudo_calls = [], []
    monkeypatch.setattr(cli_interact.cache, "state", state)
    monkeypatch.setattr(cli_interact, "state_info", lambda: None)
    monkeypatch.setattr(
        cli_interact,
        "get_repo_info",
        lambda url: SimpleNamespace(repo_url=url, release=lambda **kw: [latest]),
    )
    monkeypatch.setattr(
        cli_interact,
        "sh",
        lambda cmd, **kw: sudo_calls.append(cmd) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        cli_interact,
        "get",
        lambda url, name, pkg, **kw: installs.append((name, pkg)),
    )
    return installs, sudo_calls


def test_upgrade_installs_binaries_then_packages(monkeypatch):
    installs, sudo_calls = _stub_bin_and_pkg_upgrades(monkeypatch)

    result = CliRunner().invoke(cli.app, ["upgrade", "--yes"])

    assert result.exit_code == 0
    assert installs == [("bin", False), ("pkg", True)]
    assert len(sudo_calls) == 1


def test_upgrade_prompts_packages_separately(monkeypatch):
    installs, _ = _stub_bin_and_pkg_upgrades(monkeypatch)

    result = CliRunner().invoke(cli.app, ["upgrade"], input="n\ny\n")

    assert result.exit_code == 0
    assert installs == [("pkg", True)]


def test_upgrade_declining_packages_skips_sudo(monkeypatch):
    installs, sudo_calls = _stub_bin_and_pkg_upgrades(monkeypatch)

    result = CliRunner().invoke(cli.app, ["upgrade"], input="y\nn\n")

    assert result.exit_code == 0
    assert installs == [("bin", False)]
    assert sudo_calls == []


def test_upgrade_enter_means_yes(monkeypatch):
    installs, _ = _stub_bin_and_pkg_upgrades(monkeypatch)

    result = CliRunner().invoke(cli.app, ["upgrade"], input="\n\n")

    assert result.exit_code == 0
    assert installs == [("bin", False), ("pkg", True)]


def test_upgrade_pkg_flag_prompts_once_for_packages_only(monkeypatch):
    installs, sudo_calls = _stub_bin_and_pkg_upgrades(monkeypatch)

    result = CliRunner().invoke(cli.app, ["upgrade", "--pkg"], input="y\n")

    assert result.exit_code == 0
    assert installs == [("pkg", True)]
    assert len(sudo_calls) == 1
    assert result.output.count("(Y/n)") == 1
