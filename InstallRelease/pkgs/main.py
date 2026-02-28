import glob
import platform
from typing import Optional
from pathlib import Path
from InstallRelease.utils import logger, sh
from InstallRelease.data import _valid_package_types
from InstallRelease.pkgs.base import PackageInstallerABC
from InstallRelease.pkgs.deb import DebPackage
from InstallRelease.pkgs.rpm import RpmPackage
from InstallRelease.pkgs.app_images import AppImage


def detect_package_type_from_asset_name(name: str) -> Optional[str]:
    """Infer package type from asset filename. Returns None if not a known package."""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext == "appimage":
        ext = "AppImage"
    return ext if ext in _valid_package_types else None


def detect_package_type_from_os_release() -> Optional[str]:
    """Detect the appropriate package type for the current OS"""

    package_type = ""
    system = platform.system().lower()

    if system != "linux":
        logger.warning("Package installation is only supported on Linux")
        return None

    # Try to detect from /etc/os-release
    try:
        with open("/etc/os-release") as f:
            os_release = f.read().lower()

            if any(
                d in os_release
                for d in ["debian", "ubuntu", "mint", "pop", "elementary"]
            ):
                logger.debug("Detected Debian-based system, using .deb packages")
                package_type = "deb"
            elif any(
                d in os_release
                for d in [
                    "fedora",
                    "rhel",
                    "centos",
                    "rocky",
                    "alma",
                    "opensuse",
                    "suse",
                ]
            ):
                logger.debug("Detected RPM-based system, using .rpm packages")
                package_type = "rpm"

    except FileNotFoundError:
        logger.debug(
            "/etc/os-release not found, falling back to package manager detection"
        )

    # Fallback: check package manager availability if not detected yet
    if not package_type:
        if (
            sh("command -v rpm").returncode == 0
            or sh("command -v dnf").returncode == 0
            or sh("command -v yum").returncode == 0
        ):
            logger.debug("Detected RPM package manager, using .rpm packages")
            package_type = "rpm"
        elif (
            sh("command -v dpkg").returncode == 0
            or sh("command -v apt").returncode == 0
        ):
            logger.debug("Detected Debian package manager, using .deb packages")
            package_type = "deb"
        else:
            logger.debug("No specific package manager detected, using AppImage")
            package_type = "AppImage"

    if package_type not in _valid_package_types:
        raise ValueError(f"Unsupported package type: {package_type}")

    return package_type


class PackageInstaller(PackageInstallerABC):
    def __init__(self, name: str, package_type: str = None):
        super().__init__(name)
        self.package_type = (
            package_type if package_type else detect_package_type_from_os_release()
        )
        self.pkgs: dict[str, type[PackageInstallerABC]] = {
            "deb": DebPackage,
            "rpm": RpmPackage,
            "AppImage": AppImage,
        }

    def install(self, source: str) -> Path | None:
        # Find the package file in the temp directory
        package_files = glob.glob(f"{source}/**/*.{self.package_type}", recursive=True)

        if not package_files:
            logger.error(f"No .{self.package_type} file found in {source}")
            return Path.home()

        package_path = package_files[0]
        logger.debug(f"Found package file: {package_path}")

        # Install based on type
        try:
            installer = self.pkgs[self.package_type](self.name)
            logger.info(
                f"Installing {self.package_type} package this might need sudo permissions..."
            )
            result = installer.install(package_path)
            return result
        except Exception as e:
            logger.error(f"Failed to install package: {e}")
            return None

    def uninstall(self) -> None:
        try:
            installer = self.pkgs[self.package_type](self.name)
            _ = installer.uninstall()
        except Exception as e:
            logger.error(f"Failed to uninstall package: {e}")
