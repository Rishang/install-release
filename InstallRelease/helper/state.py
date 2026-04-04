"""Provider-agnostic state management helpers.

All providers use the same cache backend (``InstallRelease.config.cache``).
This module wraps the raw cache calls so individual providers don't need to
import config directly just for persistence.
"""

from __future__ import annotations

from typing import Optional

from InstallRelease.config import cache
from InstallRelease.providers.git.schemas import Release


def save_state(key: str, release: Release) -> None:
    """Persist *release* under *key* and flush the cache to disk."""
    cache.set(key, release)
    cache.save()


def load_state(key: str) -> Optional[Release]:
    """Return the cached ``Release`` for *key*, or ``None`` if not found."""
    return cache.get(key)
