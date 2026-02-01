"""
Debian package (.deb) installer.
"""

from pathlib import Path
from InstallRelease.utils import logger, sh
from InstallRelease.pkgs.base import PackageInstallerABC


class DebPackage(PackageInstallerABC):
    """Installer for Debian packages (.deb)."""

    def __init__(self, name: str):
        super().__init__(name)
        self.package_name = name

    def install(self, source: str) -> Path | None:
        """
        Install the .deb package using apt/dpkg.
        """
        # Validate source file
        source_path = self.validate_source(source, ".deb")
        if not source_path:
            return None

        logger.debug(f"Installing DEB package: {source_path}")

        # Use apt to install (handles dependencies)
        result = sh(f"sudo apt install -y {source_path}")

        if result.returncode != 0:
            logger.error(f"Failed to install DEB package: {result.stderr}")
            # Fallback to dpkg
            logger.debug("Trying dpkg fallback...")
            result = sh(f"sudo dpkg -i {source_path}")
            if result.returncode != 0:
                logger.error(f"dpkg also failed: {result.stderr}")
                return None

        logger.debug(f"DEB package installed: {self.package_name}")
        return self.package_name

    def uninstall(self) -> bool:
        """
        Uninstall the .deb package using apt/dpkg.
        """
        logger.debug(f"Uninstalling DEB package: {self.package_name}")

        # Try apt remove first
        result = sh(f"sudo apt remove -y {self.package_name}")

        if result.returncode != 0:
            logger.error(f"Failed to uninstall: {result.stderr}")
            # Fallback to dpkg
            result = sh(f"sudo dpkg -r {self.package_name}")
            if result.returncode != 0:
                logger.error(f"dpkg remove also failed: {result.stderr}")
                return False

        logger.debug(f"DEB package uninstalled: {self.package_name}")
        return True
