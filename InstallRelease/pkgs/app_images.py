"""
This module is for installing Linux AppImages.
"""

import os
import shutil
import tempfile
from pathlib import Path
from InstallRelease.utils import logger, sh
from InstallRelease.pkgs.base import PackageInstallerABC
import platform


class AppImage(PackageInstallerABC):
    def __init__(
        self,
        name: str,
        desktop_entry_path: str = None,
        icon_path: str = None,
        appimage_path: str = None,
    ):
        super().__init__(name)
        self.name = name
        self.appimage_path = Path(appimage_path) if appimage_path else None

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

        if not self.appimage_path:
            self.appimage_path = (
                Path.home() / ".local" / "share" / "appimages" / f"{self.name}.appimage"
            )

    def install(self, source: str) -> Path | None:
        """
        Install the AppImage.
        """
        # Validate source file
        source_path = self.validate_source(source, ".AppImage")
        if not source_path:
            return None

        dest_path = self.appimage_path.resolve()
        logger.debug(f"Installing AppImage from: {source_path}")

        # Check if source and destination are the same file
        if source_path == dest_path:
            logger.debug("Source and destination are the same, skipping copy")
        else:
            # Ensure destination directory exists
            self.ensure_directory(dest_path.parent)
            shutil.copy2(source_path, dest_path)
            logger.debug(f"Copied AppImage to: {dest_path}")

        # Make executable
        dest_path.chmod(0o755)

        # Create desktop entry and icon
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
        Create a desktop entry for the AppImage.
        """
        if remove:
            logger.debug(f"Removing desktop entry and icon for: {self.name}")
            # remove the desktop entry
            self.desktop_entry_path.unlink(missing_ok=True)
            # remove the icon
            self.icon(remove=True)
            return

        logger.debug(f"Creating desktop entry: {self.desktop_entry_path}")
        # Extract to detect whether we need --no-sandbox for Exec
        needs_no_sandbox = True
        if self.appimage_path and self.appimage_path.exists():
            appimage_abs_path = self.appimage_path.resolve()
            extracted_dir = self._appimage_extract(appimage_abs_path)
            if extracted_dir and extracted_dir.exists():
                try:
                    needs_no_sandbox = self._needs_no_sandbox(extracted_dir)
                finally:
                    if extracted_dir.parent.exists():
                        shutil.rmtree(extracted_dir.parent)
        exec_cmd = (
            f"{self.appimage_path} --no-sandbox"
            if needs_no_sandbox
            else str(self.appimage_path)
        )
        self.desktop_entry_path.write_text(
            f"[Desktop Entry]\nName={self.name}\nExec={exec_cmd}\nIcon={self.icon_path}\nType=Application\nCategories=Utility;"
        )
        self.icon()

    def _appimage_extract(self, appimage_path: Path) -> Path | None:
        """
        Extract the AppImage to a temporary directory.
        Returns path to the extracted squashfs-root, or None on failure.
        Caller is responsible for cleaning up the parent of the returned path.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{self.name}_extract_"))
        logger.debug(f"Created temporary extraction directory: {temp_dir}")

        try:
            appimage_path.chmod(0o755)
            logger.debug(f"Extracting AppImage: {appimage_path}")
            result = sh(f"cd {temp_dir} && {appimage_path} --appimage-extract")
            if result.returncode != 0:
                logger.error(f"Failed to extract AppImage: {result.stderr}")
                return None
            return temp_dir / "squashfs-root"
        except Exception as e:
            logger.error(f"Error extracting AppImage: {e}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            return None

    def icon(self, remove: bool = False):
        """
        Extract an icon for the AppImage.
        """
        if remove:
            logger.debug(f"Removing icon: {self.icon_path}")
            self.icon_path.unlink(missing_ok=True)
            return

        logger.debug(f"Generating icon: {self.icon_path}")

        if not self.appimage_path or not self.appimage_path.exists():
            logger.error(
                f"AppImage path not set or file does not exist: {self.appimage_path}"
            )
            return None

        appimage_abs_path = self.appimage_path.resolve()
        extracted_dir = self._appimage_extract(appimage_abs_path)
        if not extracted_dir or not extracted_dir.exists():
            return None

        try:
            icon_file = self._find_icon(extracted_dir)
            if icon_file:
                logger.debug(f"Found icon: {icon_file}")
                shutil.copy2(icon_file, self.icon_path)
                logger.debug(f"Icon copied to: {self.icon_path}")
                return str(self.icon_path)
            return None
        except Exception as e:
            logger.error(f"Error generating icon: {e}")
            return None
        finally:
            if extracted_dir.parent.exists():
                logger.debug(f"Removing temporary directory: {extracted_dir.parent}")
                shutil.rmtree(extracted_dir.parent)

    def _needs_no_sandbox(self, extracted_dir: Path) -> bool:
        """
        Check extracted AppImage contents to see if the app likely needs
        --no-sandbox (e.g. Electron-based apps on Linux).
        """
        # Electron: app.asar under resources
        app_asar = extracted_dir / "resources" / "app.asar"
        if app_asar.is_file():
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
            for p in resources.iterdir():
                if p.suffix == ".asar":
                    logger.debug("Detected .asar in resources, will use --no-sandbox")
                    return True
        logger.debug("No Electron/sandbox indicators, Exec will not use --no-sandbox")
        return False

    def _find_icon(self, extracted_dir: Path) -> Path | None:
        """
        Find an icon file in the extracted AppImage directory.
        """
        # Check for .DirIcon (AppImage standard)
        dir_icon = extracted_dir / ".DirIcon"
        if dir_icon.is_file():
            return dir_icon

        icon_extensions = (".png", ".svg", ".xpm", ".jpg", ".jpeg")
        search_paths = [
            extracted_dir / "usr" / "share" / "icons",
            extracted_dir / "usr" / "share" / "pixmaps",
            extracted_dir,
        ]

        preferred_icon = None
        any_icon = None

        # Search for icons (max depth: 3 levels)
        for search_path in search_paths:
            if not search_path.exists():
                continue

            for root, dirs, files in os.walk(search_path):
                root_path = Path(root)
                # Limit search depth
                if len(root_path.relative_to(search_path).parts) >= 3:
                    dirs.clear()  # Stop descending further
                    continue

                for file in files:
                    if file.lower().endswith(icon_extensions):
                        file_path = root_path / file

                        if not any_icon:
                            any_icon = file_path

                        # Prefer icons matching app name
                        if self.name.lower() in file.lower():
                            preferred_icon = file_path
                            break

                if preferred_icon:
                    break

            if preferred_icon:
                break

        return preferred_icon or any_icon
