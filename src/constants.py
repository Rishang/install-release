import platform

_colors = {
    "green": "#8CC265",
    "light_green": "#D0FF5E bold",
    "blue": "#4AA5F0",
    "cyan": "#76F6FF",
    "yellow": "#F0A45D bold",
    "red": "#E8678A",
    "purple": "#8782E9 bold",
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

    return platform_words
