"""
This module is for installing Linux AppImages.
"""

import configparser
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from InstallRelease.pkgs.base import PackageInstallerABC
from InstallRelease.utils import logger

ENTRY = "Desktop Entry"
# One Exec= token: a run of "quoted strings" and non-space chars, e.g. --opt="a b".
_EXEC_TOKEN = re.compile(r'(?:"(?:[^"\\]|\\.)*"|[^\s"])+')
# Characters that force an Exec= argument to be quoted (desktop entry spec).
_EXEC_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")
_ENV_OPTS_WITH_ARG = {"-u", "--unset", "-C", "--chdir"}


def desktop_parser() -> configparser.RawConfigParser:
    """A parser for .desktop files: keeps key casing, leaves %U etc. alone."""
    config = configparser.RawConfigParser(strict=False, interpolation=None)
    config.optionxform = str  # preserve key casing (Name, Exec, etc.)
    return config


def _exec_quote(arg: str) -> str:
    """Quote one argument for an Exec= value per the desktop entry spec."""
    arg = arg.replace("%", "%%")
    if not any(c in _EXEC_RESERVED for c in arg):
        return arg
    # The file's string escaping (\\ -> \) applies before Exec quoting
    # (\" -> "), so a literal backslash takes four and " ` $ take two.
    arg = arg.replace("\\", "\\" * 4)
    for c in '"`$':
        arg = arg.replace(c, "\\\\" + c)
    return f'"{arg}"'


def _point_exec_at(exec_val: str, appimage: str, no_sandbox: bool) -> str:
    """
    Replace the program in an Exec= value with the (already quoted) AppImage,
    keeping any `env ...` prefix and the app's arguments verbatim.
    """
    tokens = list(_EXEC_TOKEN.finditer(exec_val))
    words = [t.group().replace('"', "") for t in tokens]  # for matching only
    i = 0
    if words and Path(words[0]).name == "env":
        i = 1
        while i < len(words) and (words[i].startswith("-") or "=" in words[i]):
            i += 2 if words[i] in _ENV_OPTS_WITH_ARG else 1

    if i >= len(tokens):
        prefix, rest = "", ""
    else:
        prefix, rest = exec_val[: tokens[i].start()], exec_val[tokens[i].end() :]
        if Path(words[i]).name in ("sh", "bash"):
            # shortcut: shell-wrapped commands aren't parsed, so the app gets
            # no args; parse the -c string if an AppImage ever needs them.
            rest = ""

    sandbox = " --no-sandbox" if no_sandbox and "--no-sandbox" not in rest else ""
    return f"{prefix}{appimage}{sandbox}{rest}"


def _point_entry_at(
    config: configparser.RawConfigParser, appimage: str, icon: str, no_sandbox: bool
) -> None:
    """Point every Exec= and Icon= of a desktop entry at the installed files."""
    # D-Bus activation looks up the app by its own desktop-file name, which
    # differs from ours, and TryExec names a binary that isn't on PATH.
    config.remove_option(ENTRY, "DBusActivatable")
    config.remove_option(ENTRY, "TryExec")
    for section in config.sections():
        if section == ENTRY or config.has_option(section, "Exec"):
            exec_val = config.get(section, "Exec", fallback="")
            exec_val = _point_exec_at(exec_val, appimage, no_sandbox)
            config.set(section, "Exec", exec_val)
        if section == ENTRY or config.has_option(section, "Icon"):
            config.set(section, "Icon", icon)


def _load_internal_entry(extracted_dir: Path) -> configparser.RawConfigParser | None:
    """
    Parse the AppImage's own .desktop file (at the squashfs root, per the
    AppImage spec). Returns None if there is none or it can't be parsed.
    """
    for f in sorted(extracted_dir.glob("*.desktop")):
        config = desktop_parser()
        try:
            config.read(f, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError) as e:
            logger.debug(f"Could not parse {f.name}: {e}")
            continue
        if config.has_section(ENTRY):
            logger.debug(f"Using internal desktop file: {f.name}")
            # Without StartupWMClass, desktops match windows by desktop-file
            # name (the Wayland app-id); ours is renamed, so pin that name.
            if not config.get(ENTRY, "StartupWMClass", fallback="").strip():
                config.set(ENTRY, "StartupWMClass", f.stem)
            return config

    logger.debug("No internal .desktop file found")
    return None


class AppImage(PackageInstallerABC):
    def __init__(
        self,
        name: str,
        desktop_entry_path: str | None = None,
        icon_path: str | None = None,
        appimage_path: str | None = None,
    ):
        super().__init__(name)

        current_platform = platform.system().lower()

        if current_platform == "linux":
            apps_base = Path.home() / ".local" / "share" / "applications"
            icons_base = Path.home() / ".local" / "share" / "icons"
        else:
            apps_base = Path.home()
            icons_base = Path.home()

        self.desktop_entry_path: Path = (
            Path(desktop_entry_path)
            if desktop_entry_path
            else apps_base / f"{self.name}.desktop"
        )
        self.icon_path: Path = (
            Path(icon_path) if icon_path else icons_base / f"{self.name}.png"
        )
        self.appimage_path: Path = (
            Path(appimage_path)
            if appimage_path
            else Path.home()
            / ".local"
            / "share"
            / "appimages"
            / f"{self.name}.appimage"
        )

    @property
    def package_name(self) -> str:
        return self.name

    def _query_package_name(self, source: str) -> str | None:
        """AppImages have no package-manager name; name is set at construction time."""
        return None

    def _extract_package(self, source: str) -> Path | None:
        """
        Locate and validate the .AppImage file.
        """
        return self.validate_source(source, ".AppImage")

    def install(self, source: str) -> Path | None:
        """
        Install the AppImage.
        """
        source_path = self._extract_package(source)
        if not source_path:
            return None

        dest_path = self.appimage_path.resolve()
        logger.debug(f"Installing AppImage from: {source_path}")

        if source_path != dest_path:
            self.ensure_directory(dest_path.parent)
            shutil.copy2(source_path, dest_path)
            logger.debug(f"Copied AppImage to: {dest_path}")

        dest_path.chmod(0o755)
        self.desktop_entry()

        logger.debug(f"AppImage installed to: {self.appimage_path}")
        return self.appimage_path.resolve()

    def uninstall(self) -> bool:
        """
        Uninstall the AppImage.
        """
        logger.debug(f"Uninstalling AppImage: {self.name}")
        try:
            self.desktop_entry(remove=True)
            self.appimage_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall: {e}")
            return False

    def desktop_entry(self, remove: bool = False):
        """
        Create or remove a desktop entry for the AppImage.
        """
        if remove:
            logger.debug(f"Removing desktop entry and icon for: {self.name}")
            self.desktop_entry_path.unlink(missing_ok=True)
            self.icon(remove=True)
            return

        logger.debug(f"Creating desktop entry: {self.desktop_entry_path}")

        appimage_abs_path = self.appimage_path.resolve()
        extracted_dir = self._appimage_extract(appimage_abs_path)

        # default to False so non-Electron apps don't get --no-sandbox.
        needs_no_sandbox = False
        internal_entry: configparser.RawConfigParser | None = None

        if extracted_dir and extracted_dir.exists():
            try:
                needs_no_sandbox = self._needs_no_sandbox(extracted_dir)
                internal_entry = _load_internal_entry(extracted_dir)

                # Copy icon while we still have the extracted dir.
                icon_file = self._find_icon(extracted_dir)
                if icon_file:
                    logger.debug(f"Found icon: {icon_file}")
                    self.ensure_directory(self.icon_path.parent)
                    shutil.copy2(icon_file, self.icon_path)
                    logger.debug(f"Icon copied to: {self.icon_path}")
                else:
                    logger.warning(
                        f"No icon found in extracted AppImage for: {self.name}"
                    )
            finally:
                shutil.rmtree(extracted_dir.parent, ignore_errors=True)
        else:
            logger.warning(
                f"Could not extract AppImage for inspection: {appimage_abs_path}"
            )

        if internal_entry:
            # Reuse the app's own entry (Name, Categories, Keywords, MimeType,
            # Actions, StartupWMClass, ...), pointed at the installed files.
            config = internal_entry
        else:
            config = desktop_parser()
            config[ENTRY] = {
                "Name": self.name,
                "Type": "Application",
                "Categories": "Utility;",
                "StartupWMClass": self.name,
            }
        _point_entry_at(
            config,
            _exec_quote(str(self.appimage_path)),
            str(self.icon_path),
            needs_no_sandbox,
        )

        self.ensure_directory(self.desktop_entry_path.parent)
        with open(self.desktop_entry_path, "w", encoding="utf-8") as f:
            config.write(f, space_around_delimiters=False)

    def icon(self, remove: bool = False):
        """
        Remove the icon file. Installation is now handled inside desktop_entry()
        to avoid extracting the AppImage a second time.
        """
        if remove:
            logger.debug(f"Removing icon: {self.icon_path}")
            self.icon_path.unlink(missing_ok=True)

    def _appimage_extract(self, appimage_path: Path) -> Path | None:
        """
        Extract the AppImage to a temporary directory.
        Returns path to the extracted squashfs-root, or None on failure.
        The caller is responsible for removing the returned path's *parent*
        (the temp dir) when finished.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{self.name}_extract_"))
        logger.debug(f"Created temporary extraction directory: {temp_dir}")

        try:
            appimage_path.chmod(0o755)
            logger.debug(f"Extracting AppImage: {appimage_path}")

            result = subprocess.run(
                [str(appimage_path), "--appimage-extract"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.error(f"Failed to extract AppImage: {result.stderr}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            squashfs_root = temp_dir / "squashfs-root"
            if not squashfs_root.exists():
                logger.error("Extraction succeeded but squashfs-root not found.")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            return squashfs_root

        except Exception as e:
            logger.error(f"Error extracting AppImage: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def _needs_no_sandbox(self, extracted_dir: Path) -> bool:
        """
        Check extracted AppImage contents to see if the app likely needs
        --no-sandbox (e.g. Electron-based apps on Linux).
        """
        # Electron: app.asar under resources
        if (extracted_dir / "resources" / "app.asar").is_file():
            logger.debug("Detected Electron app (app.asar), will use --no-sandbox")
            return True

        # Electron/Chromium: electron binary or chrome-sandbox
        for name in ("electron", "chrome-sandbox"):
            for parent in (extracted_dir, extracted_dir / "usr" / "bin"):
                if (parent / name).exists():
                    logger.debug(
                        f"Detected Electron/Chromium ({name}), will use --no-sandbox"
                    )
                    return True

        # Any .asar in resources (other Electron layouts)
        resources = extracted_dir / "resources"
        if resources.is_dir():
            if any(p.suffix == ".asar" for p in resources.iterdir()):
                logger.debug("Detected .asar in resources, will use --no-sandbox")
                return True

        logger.debug("No Electron/sandbox indicators, Exec will not use --no-sandbox")
        return False

    def _find_icon(self, extracted_dir: Path) -> Path | None:
        """
        Find an icon file in the extracted AppImage directory.
        """
        # .DirIcon is the AppImage standard — validate it's actually a file.
        dir_icon = extracted_dir / ".DirIcon"
        if dir_icon.is_file():
            return dir_icon

        icon_extensions = (".png", ".svg", ".xpm", ".jpg", ".jpeg")
        search_paths = [
            extracted_dir / "usr" / "share" / "icons",
            extracted_dir / "usr" / "share" / "pixmaps",
            extracted_dir,
        ]

        preferred_icon: Path | None = None
        any_icon: Path | None = None

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for root, dirs, files in os.walk(search_path):
                root_path = Path(root)
                depth = len(root_path.relative_to(search_path).parts)

                # was `>= 3`, which skipped scanning files at depth 3.
                #      Changed to `> 3` so all three levels below root are scanned.
                if depth > 3:
                    dirs.clear()
                    continue

                for file in files:
                    if file.lower().endswith(icon_extensions):
                        file_path = root_path / file
                        if any_icon is None:
                            any_icon = file_path
                        if self.name.lower() in file.lower():
                            preferred_icon = file_path
                            break

                if preferred_icon:
                    break

            if preferred_icon:
                break

        return preferred_icon or any_icon
