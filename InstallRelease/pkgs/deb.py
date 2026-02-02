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

        source_path = source_path.resolve()

        # Use dpkg so the local .deb is always installed (apt may substitute a repo package)
        result = sh(f"sudo dpkg -i {source_path}", interactive=True)

        if result.returncode != 0:
            logger.debug("Fixing dependencies with apt...")
            fix_result = sh("sudo apt-get install -f -y", interactive=True)
            if fix_result.returncode != 0:
                logger.error(f"Failed to install DEB package: {result.stderr}")
                return None

        logger.debug(f"DEB package installed: {self.package_name}")
        return self.package_name

    def uninstall(self) -> bool:
        """
        Uninstall the .deb package using apt/dpkg.
        """
        logger.debug(f"Uninstalling DEB package: {self.package_name}")

        # Try apt remove first
        result = sh(f"sudo apt remove -y {self.package_name}", interactive=True)

        if result.returncode != 0:
            logger.error(f"Failed to uninstall: {result.stderr}")
            # Fallback to dpkg
            result = sh(f"sudo dpkg -r {self.package_name}", interactive=True)
            if result.returncode != 0:
                logger.error(f"dpkg remove also failed: {result.stderr}")
                return False

        logger.debug(f"DEB package uninstalled: {self.package_name}")
        return True
