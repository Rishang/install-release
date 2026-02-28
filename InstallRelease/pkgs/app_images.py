"""
This module is for installing Linux AppImages.
"""

import configparser
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from InstallRelease.pkgs.base import PackageInstallerABC
from InstallRelease.utils import logger


class AppImage(PackageInstallerABC):
    def __init__(
        self,
        name: str,
        desktop_entry_path: str = None,
        icon_path: str = None,
        appimage_path: str = None,
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

    def install(self, source: str) -> Path | None:
        """
        Install the AppImage.
        """
        source_path = self.validate_source(source, ".AppImage")
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

        # extract once, reuse for sandbox detection, pid name, AND icon —
        #      previously extracted twice (once here, once inside icon()).
        appimage_abs_path = self.appimage_path.resolve()
        extracted_dir = self._appimage_extract(appimage_abs_path)

        # default to False (no-sandbox) rather than True when extraction
        #      fails, so non-Electron apps don't get the flag unnecessarily.
        needs_no_sandbox = False
        # pid_name is a local variable; previously it was stored as
        #      instance state via a hidden side effect in desktop_entry().
        pid_name: str | None = None

        if extracted_dir and extracted_dir.exists():
            try:
                needs_no_sandbox = self._needs_no_sandbox(extracted_dir)
                pid_name = self._get_pid_name(extracted_dir)
                logger.debug(f"Detected PID name: {pid_name}")

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
                # cleanup is always done here — previously the caller was
                #      responsible, creating an asymmetric and leak-prone contract.
                shutil.rmtree(extracted_dir.parent, ignore_errors=True)
        else:
            logger.warning(
                f"Could not extract AppImage for inspection: {appimage_abs_path}"
            )

        exec_cmd = (
            f"{self.appimage_path} --no-sandbox"
            if needs_no_sandbox
            else str(self.appimage_path)
        )
        startup_wm_class = pid_name or self.name

        # use configparser to write the .desktop file instead of a raw
        #      string, consistent with how we read it in _get_pid_name().
        config = configparser.RawConfigParser()
        config.optionxform = str  # preserve key casing (Name, Exec, etc.)
        config["Desktop Entry"] = {
            "Name": self.name,
            "Exec": exec_cmd,
            "Icon": str(self.icon_path),
            "Type": "Application",
            "Categories": "Utility;",
            "StartupWMClass": startup_wm_class,
        }
        self.ensure_directory(self.desktop_entry_path.parent)
        with open(self.desktop_entry_path, "w") as f:
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

    def _get_pid_name(self, extracted_dir: Path) -> str | None:
        """
        Detect the actual process name the AppImage launches by reading
        the internal .desktop file's Exec= entry.

        Returns the binary name (e.g. "code", "obsidian") or None if not found.
        """
        for f in extracted_dir.glob("*.desktop"):
            config = configparser.RawConfigParser(strict=False)
            config.read(f)
            exec_val = config.get("Desktop Entry", "Exec", fallback=None)
            if exec_val:
                binary = exec_val.split()[0]
                pid_name = Path(binary).name
                logger.debug(f"Found PID name '{pid_name}' from {f.name}")
                return pid_name

        logger.debug("No internal .desktop file found; could not detect PID name")
        return None

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
