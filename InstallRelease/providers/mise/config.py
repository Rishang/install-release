import platform

_OS_MAP = {
    "linux": "linux",
    "darwin": "darwin",
    "windows": "windows",
}

_ARCH_MAP = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "armv7l": "arm",
    "i386": "386",
    "i686": "386",
}

_MISE_REGISTRY_BASE = (
    "https://raw.githubusercontent.com/jdx/mise/refs/heads/main/registry"
)
_AQUA_REGISTRY_BASE = (
    "https://raw.githubusercontent.com/aquaproj/aqua-registry/main/pkgs"
)


def _current_os() -> str:
    return _OS_MAP.get(platform.system().lower(), platform.system().lower())


def _current_arch() -> str:
    return _ARCH_MAP.get(platform.machine().lower(), platform.machine().lower())


def _trim_v(version: str) -> str:
    return version.lstrip("v")
