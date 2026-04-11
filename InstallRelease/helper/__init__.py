"""Provider-agnostic helpers for installation and state management."""

from InstallRelease.helper.install import extract_url as extract_url
from InstallRelease.helper.install import install_bin as install_bin
from InstallRelease.helper.install import _EXEC_PATTERN as _EXEC_PATTERN
from InstallRelease.helper.state import load_state as load_state
from InstallRelease.helper.state import save_state as save_state
from InstallRelease.pkgs.main import (
    detect_package_type_from_asset_name as detect_package_type_from_asset_name,
)
from InstallRelease.pkgs.main import (
    detect_package_type_from_os_release as detect_package_type_from_os_release,
)
