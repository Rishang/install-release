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
        self.desktop_entry_path.write_text(
            f"[Desktop Entry]\nName={self.name}\nExec={self.appimage_path}\nIcon={self.icon_path}\nType=Application\nCategories=Utility;"
        )
        self.icon()

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

        # Convert to absolute path to avoid issues with cd
        appimage_abs_path = self.appimage_path.resolve()

        # Create a temporary directory for extraction
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{self.name}_extract_"))
        logger.debug(f"Created temporary extraction directory: {temp_dir}")

        try:
            # Make AppImage executable
            appimage_abs_path.chmod(0o755)

            # Extract AppImage
            logger.debug(f"Extracting AppImage: {appimage_abs_path}")
            result = sh(f"cd {temp_dir} && {appimage_abs_path} --appimage-extract")

            if result.returncode != 0:
                logger.error(f"Failed to extract AppImage: {result.stderr}")
                return None

            # Look for icon files in the extracted directory
            extracted_dir = temp_dir / "squashfs-root"
            icon_file = self._find_icon(extracted_dir)

            if icon_file:
                logger.debug(f"Found icon: {icon_file}")
                # Copy icon to the destination
                shutil.copy2(icon_file, self.icon_path)
                logger.debug(f"Icon copied to: {self.icon_path}")
                return str(self.icon_path)

        except Exception as e:
            logger.error(f"Error generating icon: {e}")
            return None
        finally:
            # Clean up extracted directory
            if temp_dir.exists():
                logger.debug(f"Removing temporary directory: {temp_dir}")
                shutil.rmtree(temp_dir)

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
