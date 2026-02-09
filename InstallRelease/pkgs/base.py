"""
Base class for package installers using ABC.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from InstallRelease.utils import logger


class PackageInstallerABC(ABC):
    """Abstract base class for package installers."""

    def __init__(self, name: str):
        """
        Initialize the package installer.

        Args:
            name: Name of the package/application
        """
        logger.debug(f"Initializing {self.__class__.__name__}: {name}")
        self.name = name

    @abstractmethod
    def install(self, source: str) -> Path | None:
        """
        Install the package from source.

        Args:
            source: Path to the source package file

        Returns:
            Path to the installed package, or None if failed
        """
        pass

    @abstractmethod
    def uninstall(self) -> bool:
        """
        Uninstall the package.

        Returns:
            True if successful, False otherwise
        """
        pass

    def validate_source(self, source: str, extension: str) -> Path | None:
        """
        Validate the source file exists and has the correct extension.

        Args:
            source: Path to the source file
            extension: Expected file extension (e.g., '.AppImage', '.deb')

        Returns:
            Resolved Path object if valid, None otherwise
        """
        source_path = Path(source).resolve()

        if not source_path.exists():
            logger.error(f"Source file does not exist: {source_path}")
            return None

        if not source_path.name.endswith(extension):
            logger.error(
                f"Source file does not have {extension} extension: {source_path}"
            )
            return None

        return source_path

    def ensure_directory(self, path: Path) -> None:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Path to the directory
        """
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {path}")
