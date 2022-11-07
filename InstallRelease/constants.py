import os
import platform


HOME = os.path.expanduser("~")

__bin_at__ = ".release-bin"
__dir_name__ = "install_release"

__state_at__ = f"{__dir_name__}/state.json"
__config_at__ = f"{__dir_name__}/config.json"

_colors = {
    "green": "#8CC265",
    "light_green": "#D0FF5E bold",
    "blue": "#4AA5F0",
    "cyan": "#76F6FF",
    "yellow": "#F0A45D bold",
    "red": "#E8678A",
    "purple": "#8782E9 bold",
}


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


def platform_words() -> list:

    aliases = {
        "x86_64": ["x86", "x64", "amd64", "amd", "x86_64"],
        "aarch64": ["arm64", "aarch64"],
    }

    platform_words = []

    platform_words += [platform.system().lower(), platform.architecture()[0]]

    for alias in aliases:
        if platform.machine().lower() in aliases[alias]:
            platform_words += aliases[alias]

    try:
        sys_alias = platform.platform().split("-")[0].lower()

        if platform.system().lower() != sys_alias:
            platform_words.append(sys_alias)
    except:
        ...

    return platform_words
