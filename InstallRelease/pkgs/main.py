import glob
import platform
from typing import Optional

from InstallRelease.utils import logger, sh
from InstallRelease.data import _valid_package_types


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

    # Try to detect from /etc/os-release (standard method)
    try:
        with open("/etc/os-release") as f:
            os_release = f.read().lower()

            # Check for Debian-based distros
            if any(
                distro in os_release
                for distro in ["debian", "ubuntu", "mint", "pop", "elementary"]
            ):
                logger.debug(
                    "Detected Debian-based system from /etc/os-release, using .deb packages"
                )
                package_type = "deb"

            # Check for RPM-based distros
            if any(
                distro in os_release
                for distro in [
                    "fedora",
                    "rhel",
                    "centos",
                    "rocky",
                    "alma",
                    "opensuse",
                    "suse",
                ]
            ):
                logger.debug(
                    "Detected RPM-based system from /etc/os-release, using .rpm packages"
                )
                package_type = "rpm"

            # Linux fallback
            if platform.system().lower() == "linux":
                logger.debug("Detected Linux system, using AppImage packages")
                package_type = "AppImage"

    except FileNotFoundError:
        logger.debug(
            "/etc/os-release not found, falling back to package manager detection"
        )

    # Fallback: Check for package manager availability
    # Check for rpm-based first (to avoid false positives on Fedora with dpkg installed)
    if (
        sh("command -v rpm").returncode == 0
        or sh("command -v dnf").returncode == 0
        or sh("command -v yum").returncode == 0
    ):
        logger.debug("Detected RPM package manager, using .rpm packages")
        package_type = "rpm"

    # Check for dpkg/apt (Debian-based)
    elif sh("command -v dpkg").returncode == 0 or sh("command -v apt").returncode == 0:
        logger.debug("Detected Debian package manager, using .deb packages")
        package_type = "deb"

    else:
        # Fallback to AppImage for other Linux distros
        logger.debug("No specific package manager detected, using AppImage")
        package_type = "AppImage"

    if package_type not in _valid_package_types:
        raise ValueError(f"Unsupported package type: {package_type}")

    return package_type


def install_package(
    package_type: str,
    name: str,
    temp_dir: str,
) -> bool:
    """Install a package using the appropriate installer

    Args:
        package_type: Type of package (deb/rpm/appimage)
        name: Name of the package
        temp_dir: Temporary directory for downloads

    Returns:
        True if installation succeeded
    """
    # Find the package file in the temp directory
    package_files = glob.glob(f"{temp_dir}/**/*.{package_type}", recursive=True)

    if not package_files:
        logger.error(f"No .{package_type} file found in {temp_dir}")
        return False

    package_path = package_files[0]
    logger.debug(f"Found package file: {package_path}")

    # Install based on type
    try:
        if package_type == "deb":
            from InstallRelease.pkgs.deb import DebPackage

            installer = DebPackage(name)
            logger.info("Installing DEB package this will need sudo permissions...")
            result = installer.install(package_path)
        elif package_type == "rpm":
            from InstallRelease.pkgs.rpm import RpmPackage

            installer = RpmPackage(name)
            logger.info("Installing RPM package this will need sudo permissions...")
            result = installer.install(package_path)
        elif package_type == "AppImage":
            from InstallRelease.pkgs.app_images import AppImage

            installer = AppImage(name)
            result = installer.install(package_path)
        else:
            logger.error(f"Unsupported package type: {package_type}")
            return False

        return result is not None
    except Exception as e:
        logger.error(f"Failed to install package: {e}")
        return False
