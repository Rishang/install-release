"""Provider-agnostic helpers for installation and state management."""

from InstallRelease.helper.install import extract_url, install_bin, _EXEC_PATTERN
from InstallRelease.helper.state import load_state, save_state
from InstallRelease.pkgs.main import (
    detect_package_type_from_asset_name,
    detect_package_type_from_os_release,
)

__all__ = [
    "extract_url",
    "install_bin",
    "detect_package_type_from_asset_name",
    "detect_package_type_from_os_release",
    "save_state",
    "load_state",
    "_EXEC_PATTERN",
]
