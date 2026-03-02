"""
This module handles the configuration of the tool.
"""

import os
from InstallRelease.state import State, platform_path
from InstallRelease.schemas import Release, ToolConfig
from InstallRelease.utils import logger

HOME = os.path.expanduser("~")

__bin_at__ = "bin"
__dir_name__ = "install_release"

__state_at__ = f"{__dir_name__}/state.json"
__config_at__ = f"{__dir_name__}/config.json"


state_path = {
    "linux": f"{HOME}/.config/{__state_at__}",
    "darwin": f"{HOME}/Library/.config/{__state_at__}",
}

config_path = {
    "linux": f"{HOME}/.config/{__config_at__}",
    "darwin": f"{HOME}/Library/.config/{__config_at__}",
}

bin_path = {
    "linux": f"{HOME}/{__bin_at__}",
    "darwin": f"{HOME}/{__bin_at__}",
}

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

# Handle the path, ensuring it's a string
config_path_str = str(config.path) if config.path is not None else ""
dest = platform_path(paths=bin_path, alt=config_path_str)
