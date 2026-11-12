from __future__ import annotations

from pathlib import Path

import pytest

from InstallRelease.pkgs.app_images import (
    ENTRY,
    AppImage,
    _exec_quote,
    _point_exec_at,
    desktop_parser,
)

GHOSTTY_DESKTOP = """\
[Desktop Entry]
Name=Ghostty
Type=Application
TryExec=ghostty
Exec=ghostty --gtk-single-instance=true
Icon=com.mitchellh.ghostty
Categories=System;TerminalEmulator;
Keywords=terminal;tty;pty;
StartupWMClass=com.mitchellh.ghostty
DBusActivatable=true
Actions=new-window;

[Desktop Action new-window]
Name=New Window
Exec=ghostty --gtk-single-instance=true
Icon=window-new
"""

ELECTRON_DESKTOP = """\
[Desktop Entry]
Name=Obsidian
Type=Application
Exec=env FOO=1 AppRun --no-sandbox %U
MimeType=x-scheme-handler/obsidian;
"""


def _install_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    desktop: str | None,
    electron: bool = False,
):
    root = tmp_path / "extract" / "squashfs-root"
    root.mkdir(parents=True)
    if desktop is not None:
        (root / "md.obsidian.Obsidian.desktop").write_text(desktop)
    if electron:
        (root / "resources").mkdir()
        (root / "resources" / "app.asar").write_text("")
    (root / ".DirIcon").write_bytes(b"png")

    app = AppImage(
        "app-appimage",
        desktop_entry_path=str(tmp_path / "out" / "app.desktop"),
        icon_path=str(tmp_path / "icons" / "app.png"),
        appimage_path=str(tmp_path / "bin" / "app.appimage"),
    )
    monkeypatch.setattr(app, "_appimage_extract", lambda _path: root)
    app.desktop_entry()

    config = desktop_parser()
    config.read(app.desktop_entry_path)
    return app, config


def test_reuses_internal_desktop_entry(tmp_path, monkeypatch):
    app, config = _install_entry(tmp_path, monkeypatch, GHOSTTY_DESKTOP)
    entry = config[ENTRY]
    exe = str(app.appimage_path)

    assert entry["Name"] == "Ghostty"
    assert entry["Categories"] == "System;TerminalEmulator;"
    assert entry["Keywords"] == "terminal;tty;pty;"
    assert entry["StartupWMClass"] == "com.mitchellh.ghostty"
    assert entry["Exec"] == f"{exe} --gtk-single-instance=true"
    assert entry["Icon"] == str(app.icon_path)
    assert "TryExec" not in entry
    assert "DBusActivatable" not in entry
    action = config["Desktop Action new-window"]
    assert action["Exec"] == f"{exe} --gtk-single-instance=true"
    assert action["Icon"] == str(app.icon_path)
    assert app.icon_path.read_bytes() == b"png"


def test_electron_env_exec_and_wm_class_fallback(tmp_path, monkeypatch):
    app, config = _install_entry(tmp_path, monkeypatch, ELECTRON_DESKTOP, electron=True)
    entry = config[ENTRY]

    # env prefix kept, AppRun replaced, --no-sandbox not duplicated, %U kept.
    assert entry["Exec"] == f"env FOO=1 {app.appimage_path} --no-sandbox %U"
    # No StartupWMClass: pinned to the internal desktop-file name (app-id).
    assert entry["StartupWMClass"] == "md.obsidian.Obsidian"
    assert entry["MimeType"] == "x-scheme-handler/obsidian;"


def test_minimal_entry_without_internal_desktop(tmp_path, monkeypatch):
    app, config = _install_entry(tmp_path, monkeypatch, None)
    entry = config[ENTRY]

    assert entry["Name"] == "app-appimage"
    assert entry["Exec"] == str(app.appimage_path)
    assert entry["StartupWMClass"] == "app-appimage"
    assert entry["Icon"] == str(app.icon_path)


@pytest.mark.parametrize(
    ("exec_val", "no_sandbox", "expected"),
    [
        ('"/opt/My App/bin" --title="a  b" %U', False, 'APP --title="a  b" %U'),
        ("env -u X FOO=1 foo %F", False, "env -u X FOO=1 APP %F"),
        ('sh -c "foo --bar"', False, "APP"),
        ("AppRun --no-sandbox %U", True, "APP --no-sandbox %U"),
        ("foo %U", True, "APP --no-sandbox %U"),
        ("", False, "APP"),
    ],
)
def test_point_exec_at(exec_val, no_sandbox, expected):
    assert _point_exec_at(exec_val, "APP", no_sandbox) == expected


def test_exec_quote():
    assert _exec_quote("/home/u/app.appimage") == "/home/u/app.appimage"
    assert _exec_quote("/home/my u/50%/$a") == r'"/home/my u/50%%/\\$a"'
