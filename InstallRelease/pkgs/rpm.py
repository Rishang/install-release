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
        return self._extract_package_base(source, ".rpm", "RPM")

    def install(self, source: str) -> str | None:
        """
        Install the .rpm package using dnf/yum/rpm.
        Returns the actual package name registered in the RPM database.
        """
        source_path = self._extract_package(source)
        if not source_path:
            return None

        logger.debug(f"Installing RPM package: {source_path}")

        for cmd in [
            f"sudo dnf install -y {source_path}",
            f"sudo yum install -y {source_path}",
            f"sudo rpm -ivh {source_path}",
        ]:
            result = sh(cmd, interactive=True)
            if result.returncode == 0:
                break
        else:
            logger.error(f"Failed to install RPM package: {result.stderr}")
            return None

        logger.debug(f"RPM package installed: {self.package_name}")
        return self.package_name

    def uninstall(self) -> bool:
        """
        Uninstall the .rpm package using dnf/yum/rpm.
        """
        logger.debug(f"Uninstalling RPM package: {self.package_name}")

        for cmd in [
            f"sudo dnf remove -y {self.package_name}",
            f"sudo yum remove -y {self.package_name}",
            f"sudo rpm -e {self.package_name}",
        ]:
            result = sh(cmd, interactive=True)
            if result.returncode == 0:
                break
        else:
            logger.error(f"Failed to uninstall: {result.stderr}")
            return False

        logger.debug(f"RPM package uninstalled: {self.package_name}")
        return True
