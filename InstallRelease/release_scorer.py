import re
import platform
import subprocess
from typing import List, Optional, Tuple, Dict, Any
from InstallRelease.utils import logger


class ReleaseScorer:
    """Simple class to score release names based on platform compatibility"""

    def __init__(self, extra_words: Optional[List[str]] = None, debug: bool = False):
        """Initialize the scorer with platform words and extra matching words

        Args:
            platform_words: List of platform-specific words to match
            extra_words: Additional words to match against
            debug: Whether to print debug information
        """
        self.platform_words = self._platform_words()
        self.extra_words = extra_words or []
        self.debug = debug
        self.is_glibc_system = self._detect_glibc()
        self.platform = platform.system().lower()
        self.architecture = platform.machine()

        # Combine all patterns for matching
        self.all_patterns = self.platform_words + self.extra_words + ["(.tar|.zip)"]

        logger.debug(f"ReleaseScorer initialized with patterns: {self.all_patterns}")
        logger.debug(f"Is glibc system: {self.is_glibc_system}")

    def _platform_words(self) -> list:
        aliases = {
            "x86_64": ["x86", "x64", "amd64", "amd", "x86_64"],
            "aarch64": ["arm64", "aarch64", "arm"],
        }

        words = [platform.system().lower(), platform.architecture()[0]]

        for alias in aliases:
            if platform.machine().lower() in aliases[alias]:
                words += aliases[alias]

        try:
            sys_alias = platform.platform().split("-")[0].lower()

            if platform.system().lower() != sys_alias:
                words.append(sys_alias)
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["ldd", "--version"], capture_output=True, text=True
            )
            output = result.stdout + result.stderr
            if "musl" in output:
                words.append("musl")
            elif "glibc" in output or "GNU libc" in output:
                # Not adding glibc to the words list as this word is not much used in release names
                pass

        except Exception:
            pass

        return words

    def _detect_glibc(self) -> bool:
        """Detect if the system is using glibc"""
        try:
            result = subprocess.run(
                ["ldd", "--version"], capture_output=True, text=True
            )
            output = result.stdout + result.stderr
            return "glibc" in output or "GNU libc" in output
        except Exception:
            return False

    def _calculate_pattern_match_score(self, release_name: str) -> float:
        """Calculate base score based on pattern matching

        Args:
            release_name: Name of the release

        Returns:
            Score between 0 and 1 based on pattern matches
        """
        count = 0
        release_name_lower = release_name.lower()

        for pattern in self.all_patterns:
            if re.search(pattern.lower(), release_name_lower):
                count += 1

        if count == 0:
            return 0.0

        return count / len(self.all_patterns)

    def _apply_penalties_and_bonuses(self, score: float, release_name: str) -> float:
        """Apply penalties and bonuses to the base score

        Args:
            score: Base score from pattern matching
            release_name: Name of the release

        Returns:
            Adjusted score after applying penalties/bonuses
        """
        adjusted_score = score
        release_name_lower = release_name.lower()

        # Apply penalty for musl releases on glibc systems
        if self.is_glibc_system and "musl" in release_name_lower:
            adjusted_score *= 0.8  # 20% penalty
            logger.debug(
                f"Applied musl penalty to '{release_name}': {score} -> {adjusted_score}"
            )

        # Apply bonus for glibc releases on glibc systems
        elif self.is_glibc_system and any(
            word in release_name_lower for word in ["glibc", "gnu"]
        ):
            adjusted_score *= 1.05  # 5% bonus

            logger.debug(
                f"Applied glibc bonus to '{release_name}': {score} -> {adjusted_score}"
            )

        # Apply penalty for debug releases
        if any(word in release_name_lower for word in ["debug", "dbg"]):
            adjusted_score *= 0.8  # 20% penalty

            logger.debug(f"Applied debug penalty to '{release_name}': {adjusted_score}")

        return adjusted_score

    def score(self, release_name: str) -> float:
        """Score a release name

        Args:
            release_name: Name of the release to score

        Returns:
            Score between 0 and 1, higher is better
        """
        base_score = self._calculate_pattern_match_score(release_name)
        final_score = self._apply_penalties_and_bonuses(base_score, release_name)

        logger.debug(
            f"name: '{release_name}', base_score: {base_score}, final_score: {final_score}"
        )

        return final_score

    def score_multiple(self, release_names: List[str]) -> List[Tuple[str, float]]:
        """Score multiple release names

        Args:
            release_names: List of release names to score

        Returns:
            List of tuples (release_name, score) sorted by score descending
        """
        scores = [(name, self.score(name)) for name in release_names]
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def select_best(
        self, release_names: List[str], min_score: float = 0.2
    ) -> Optional[str]:
        """Select the best release name from a list

        Args:
            release_names: List of release names to choose from

        Returns:
            The best release name or None if no valid matches
        """
        if not release_names:
            return None

        scored = self.score_multiple(release_names)

        # Filter out releases with zero score
        valid_scores = [item for item in scored if item[1] > 0]

        if not valid_scores:
            return None

        best_name, best_score = valid_scores[0]

        logger.debug(f"Selected: '{best_name}' with score: {best_score}")
        if best_score < min_score:
            logger.debug(
                f"Warning: Best match has low probability (score: {best_score})"
            )

        return best_name

    def get_info(self) -> Dict[str, Any]:
        """Get information about the scorer configuration

        Returns:
            Dictionary with scorer configuration details
        """
        return {
            "platform_words": self.platform_words,
            "extra_words": self.extra_words,
            "all_patterns": self.all_patterns,
            "is_glibc_system": self.is_glibc_system,
            "platform": self.platform,
            "architecture": self.architecture,
        }
