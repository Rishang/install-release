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

    def _query_package_name(self, source: str) -> str | None:
        """Query the package name embedded in a .deb file using dpkg-deb."""
        result = sh(f"dpkg-deb -f {source} Package")
        if result.returncode == 0 and result.stdout:
            return "".join(result.stdout).strip()
        return None

    def _extract_package(self, source: str) -> Path | None:
        """
        Locate and validate the .deb file, resolving the actual package name
        from its metadata into `self.package_name`.
        """
        source_path = self.validate_source(source, ".deb")
        if not source_path:
            return None
        actual_name = self._query_package_name(str(source_path))
        if actual_name:
            logger.debug(f"DEB package name from metadata: {actual_name}")
            self.package_name = actual_name
        return source_path

    def install(self, source: str) -> str | None:
        """
        Install the .deb package using apt/dpkg.
        Returns the actual package name registered in the dpkg database.
        """
        source_path = self._extract_package(source)
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
