import re
import platform
import subprocess
from typing import List, Optional, Tuple, Dict, Any
from InstallRelease.utils import logger, to_words

PLATFORM_ARCH_ALIASES = {
    "x86_64": ["x86", "x64", "amd64", "amd", "x86_64"],
    "aarch64": ["arm64", "aarch64", "arm"],
}

PENALTY_KEYWORDS = {
    "debug",
    ".dbg",
    ".json",
    ".jsonl",
    ".spdx",
    ".txt",
    ".yaml",
    ".yml",
    ".md",
    ".snap",
    ".sha256sum",
    ".sig",
    ".msi",
    ".exe",
}


class ReleaseScorer:
    """Score release names based on platform compatibility"""

    def __init__(
        self, extra_words: Optional[List[str]] = None, disable_penalties: bool = False
    ):
        """Initialize the scorer with platform detection and matching words

        Args:
            extra_words: Additional words to match (e.g., user-specified patterns)
            disable_penalties: Whether to disable penalty/bonus adjustments
        """
        self.platform = platform.system().lower()
        self.architecture = platform.machine().lower()
        self.is_glibc = self._detect_glibc()
        self.extra_words = extra_words or []
        self.disable_penalties = disable_penalties

        # Build weighted patterns (pattern -> weight)
        self.patterns = self._build_patterns()

        logger.debug(
            f"Platform: {self.platform}, Arch: {self.architecture}, glibc: {self.is_glibc}"
        )
        logger.debug(f"Patterns: {self.patterns}")

    def _detect_glibc(self) -> bool:
        """Detect if system uses glibc"""
        try:
            result = subprocess.run(
                ["ldd", "--version"], capture_output=True, text=True, timeout=2
            )
            output = (result.stdout + result.stderr).lower()
            return "glibc" in output or "gnu" in output
        except Exception:
            return False

    def _build_patterns(self) -> Dict[str, float]:
        """Build weighted pattern dictionary

        Returns:
            Dict mapping pattern to weight (higher = more important)
        """
        patterns = {}

        # 1. Operating system (highest priority)
        patterns[self.platform] = 5.0

        # 2. Architecture aliases
        for canonical, aliases in PLATFORM_ARCH_ALIASES.items():
            if self.architecture in aliases:
                for alias in aliases:
                    patterns[alias] = 3.0
                break

        # 3. Bit architecture (lower priority)
        bit_arch = platform.architecture()[0]
        patterns[bit_arch] = 1.0

        # 4. musl for non-glibc systems
        if not self.is_glibc:
            patterns["musl"] = 2.0

        # 5. Archive extensions
        patterns[r"\.(tar|zip|gz|bz2|xz|7z)"] = 2.0

        # 6. User-specified words
        for word in self.extra_words:
            patterns[word] = 2.0

        return patterns

    def score(self, release_name: str) -> float:
        """Score a release name (0-1, higher is better)

        Returns:
            Normalized score between 0 and 1
        """
        name_lower = release_name.lower()

        # Calculate base score from pattern matching
        matched_weight = 0.0
        total_weight = sum(self.patterns.values())

        for pattern, weight in self.patterns.items():
            if re.search(pattern, name_lower):
                matched_weight += weight

        base_score = matched_weight / total_weight if total_weight > 0 else 0.0

        # Apply adjustments if not disabled
        if not self.disable_penalties:
            score = self._adjust_score(base_score, name_lower)
        else:
            score = base_score

        logger.debug(f"'{release_name}': base={base_score:.3f}, final={score:.3f}")
        return score

    def _adjust_score(self, base_score: float, name_lower: str) -> float:
        """Apply penalty and bonus adjustments

        Returns:
            Adjusted score
        """
        score = base_score

        # Penalty: musl on glibc system
        if self.is_glibc and "musl" in name_lower:
            score *= 0.7
            logger.debug(f"Applied musl penalty: {score:.3f}")

        # Bonus: glibc on glibc system
        elif self.is_glibc and any(word in name_lower for word in ["glibc", "gnu"]):
            score *= 1.1
            logger.debug(f"Applied glibc bonus: {score:.3f}")

        # Penalty: debug/unwanted files
        if any(word in name_lower for word in PENALTY_KEYWORDS):
            score *= 0.5
            logger.debug(f"Applied penalty keyword: {score:.3f}")

        return score

    def select_best(
        self, release_names: List[str], min_score: float = 0.2
    ) -> Optional[str]:
        """Select the best matching release

        Args:
            release_names: List of release filenames
            min_score: Minimum acceptable score

        Returns:
            Best matching release name or None
        """
        if not release_names:
            return None

        scored = [(name, self.score(name)) for name in release_names]
        scored.sort(key=lambda x: x[1], reverse=True)

        logger.debug(f"Top 3 scores: {scored[:3]}")

        valid = [item for item in scored if item[1] >= min_score]

        if not valid:
            if len(scored) == 1:
                logger.info(f"Only one asset available, selecting: '{scored[0][0]}'")
                return scored[0][0]
            logger.debug(f"No releases scored above {min_score}")
            return None

        best_name, best_score = valid[0]

        # When penalties disabled with user pattern, find exact word matches
        if self.disable_penalties and self.extra_words:
            extra_words_set = set(word.lower() for word in self.extra_words)

            for name, score in valid:
                release_words = set(to_words(name, ignore_words=["v", "unknown"]))

                # Prefer release that contains all extra words
                if extra_words_set.issubset(release_words):
                    logger.debug(
                        f"Exact word match: '{name}' contains all words {self.extra_words}"
                    )
                    return name

        logger.debug(f"Selected: '{best_name}' (score: {best_score:.3f})")
        return best_name

    def score_multiple(self, release_names: List[str]) -> List[Tuple[str, float]]:
        """Score and sort multiple releases

        Args:
            release_names: List of release filenames

        Returns:
            List of (name, score) tuples, sorted by score descending
        """
        scored = [(name, self.score(name)) for name in release_names]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def get_info(self) -> Dict[str, Any]:
        """Get information about the scorer configuration

        Returns:
            Dictionary with scorer configuration details
        """
        return {
            "platform_words": list(self.patterns.keys()),
            "extra_words": self.extra_words,
            "all_patterns": list(self.patterns.keys()),
            "pattern_weights": self.patterns,
            "is_glibc_system": self.is_glibc,
            "platform": self.platform,
            "architecture": self.architecture,
        }
