"""
RPM package (.rpm) installer.
"""

from pathlib import Path

from InstallRelease.utils import logger, sh
from InstallRelease.pkgs.base import PackageInstallerABC


class RpmPackage(PackageInstallerABC):
    """Installer for RPM packages (.rpm)."""

    def __init__(self, name: str):
        super().__init__(name)
        self.package_name = name

    def _query_package_name(self, source: str) -> str | None:
        """Query the package name embedded in a .rpm file using rpm -qp."""
        result = sh(f"rpm -qp --queryformat '%{{NAME}}' {source}")
        if result.returncode == 0 and result.stdout:
            return "".join(result.stdout).strip()
        return None

    def _extract_package(self, source: str) -> Path | None:
        """
        Locate and validate the .rpm file, resolving the actual package name
        from its metadata into `self.package_name`.
        """
        source_path = self.validate_source(source, ".rpm")
        if not source_path:
            return None
        actual_name = self._query_package_name(str(source_path))
        if actual_name:
            logger.debug(f"RPM package name from metadata: {actual_name}")
            self.package_name = actual_name
        return source_path

    def install(self, source: str) -> str | None:
        """
        Install the .rpm package using dnf/yum/rpm.
        Returns the actual package name registered in the RPM database.
        """
        source_path = self._extract_package(source)
        if not source_path:
            return None

        logger.debug(f"Installing RPM package: {source_path}")

        # Try dnf first (Fedora/RHEL 8+)
        result = sh(f"sudo dnf install -y {source_path}", interactive=True)

        if result.returncode != 0:
            logger.debug("dnf not available, trying yum...")
            # Fallback to yum (older RHEL/CentOS)
            result = sh(f"sudo yum install -y {source_path}", interactive=True)

            if result.returncode != 0:
                logger.debug("yum failed, trying rpm...")
                # Fallback to rpm (no dependency resolution)
                result = sh(f"sudo rpm -ivh {source_path}", interactive=True)

                if result.returncode != 0:
                    logger.error(f"Failed to install RPM package: {result.stderr}")
                    return None

        logger.debug(f"RPM package installed: {self.package_name}")
        return self.package_name

    def uninstall(self) -> bool:
        """
        Uninstall the .rpm package using dnf/yum/rpm.
        """
        logger.debug(f"Uninstalling RPM package: {self.package_name}")

        # Try dnf first
        result = sh(f"sudo dnf remove -y {self.package_name}", interactive=True)

        if result.returncode != 0:
            logger.debug("dnf not available, trying yum...")
            # Fallback to yum
            result = sh(f"sudo yum remove -y {self.package_name}", interactive=True)

            if result.returncode != 0:
                logger.debug("yum failed, trying rpm...")
                # Fallback to rpm
                result = sh(f"sudo rpm -e {self.package_name}", interactive=True)

                if result.returncode != 0:
                    logger.error(f"Failed to uninstall: {result.stderr}")
                    return False

        logger.debug(f"RPM package uninstalled: {self.package_name}")
        return True
