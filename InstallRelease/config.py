"""
This module handles the configuration of the tool.
"""

import os
from InstallRelease.state import State, platform_path
from InstallRelease.schemas import ToolConfig
from InstallRelease.providers.git.schemas import Release
from InstallRelease.utils import logger

HOME = os.path.expanduser("~")

_PATHS = {
    "linux": {
        "state": f"{HOME}/.config/install_release/state.json",
        "config": f"{HOME}/.config/install_release/config.json",
        "bin": f"{HOME}/bin",
    },
    "darwin": {
        "state": f"{HOME}/Library/.config/install_release/state.json",
        "config": f"{HOME}/Library/.config/install_release/config.json",
        "bin": f"{HOME}/bin",
    },
}

state_path = {k: v["state"] for k, v in _PATHS.items()}
config_path = {k: v["config"] for k, v in _PATHS.items()}
bin_path = {k: v["bin"] for k, v in _PATHS.items()}

if os.environ.get("installState", "") == "test":
    temp_dir = "../temp"
    __spath = {
        "state_path": f"{temp_dir}/temp-state.json",
        "config_path": f"{temp_dir}/temp-config.json",
    }
    logger.info(f"installState={os.environ.get('installState')}")
else:
    __spath = {"state_path": "", "config_path": ""}


cache = State(
    file_path=platform_path(paths=state_path, alt=__spath["state_path"]),
    obj=Release,
)

cache_config = State(
    file_path=platform_path(paths=config_path, alt=__spath["config_path"]),
    obj=ToolConfig,
)


def load_config() -> ToolConfig:
    """
    Load config from cache_config

    Returns:
        The loaded configuration object or a new one if not found
    """
    _config = cache_config.state.get("config")

    if _config is not None and isinstance(_config, ToolConfig):
        return _config
    else:
        new_config = ToolConfig()
        cache_config.set("config", new_config)
        cache_config.save()
        return new_config


config: ToolConfig = load_config()


def pre_release_enabled() -> bool:
    """Return whether pre-release versions are enabled in the tool config."""
    return bool(config.pre_release)


# Handle the path, ensuring it's a string
config_path_str = str(config.path) if config.path is not None else ""
dest = platform_path(paths=bin_path, alt=config_path_str)
