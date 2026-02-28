import re
import platform
import subprocess
from typing import List, Optional, Tuple, Dict, Any
from InstallRelease.utils import logger, to_words

PLATFORM_ARCH_ALIASES = {
    "x86_64": ["x86", "x64", "amd64", "amd", "x86_64"],
    "aarch64": ["arm64", "aarch64", "arm"],
}

PENALTY_SUBSTRINGS = {"debug"}
PENALTY_EXTENSIONS = {
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
    """Score release names based on platform compatibility."""

    def __init__(
        self,
        extra_words: Optional[List[str]] = None,
        disable_adjustments: bool = False,  # FIX: renamed from disable_penalties —
        # the flag suppresses bonuses too, not just penalties.
    ):
        """Initialize the scorer with platform detection and matching words."""
        self.platform = platform.system().lower()
        self.architecture = platform.machine().lower()
        self.is_glibc = self._detect_glibc()
        self.extra_words = extra_words or []
        self.disable_adjustments = disable_adjustments

        self._extra_words_set = {w.lower() for w in self.extra_words}

        # never accidentally treat a plain string as a regex or vice-versa.
        self._plain_patterns: Dict[str, float] = {}
        self._regex_patterns: Dict[str, float] = {}
        self._build_patterns()

        # Total weight is used for normalisation — computed once.
        self._total_weight = sum(self._plain_patterns.values()) + sum(
            self._regex_patterns.values()
        )

        logger.debug(
            f"Platform: {self.platform}, Arch: {self.architecture}, "
            f"glibc: {self.is_glibc}"
        )
        logger.debug(
            f"Plain patterns: {self._plain_patterns}, "
            f"Regex patterns: {self._regex_patterns}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_glibc(self) -> bool:
        """Detect if system uses glibc."""
        try:
            result = subprocess.run(
                ["ldd", "--version"], capture_output=True, text=True, timeout=2
            )
            output = (result.stdout + result.stderr).lower()
            return "glibc" in output or "gnu" in output
        except Exception:
            return False

    def _build_patterns(self) -> None:
        """Populate _plain_patterns and _regex_patterns."""

        # 1. Operating system (highest priority).
        self._plain_patterns[self.platform] = 5.0

        # 2. Architecture aliases.
        for canonical, aliases in PLATFORM_ARCH_ALIASES.items():
            if self.architecture in aliases:
                for alias in aliases:
                    self._plain_patterns[alias] = 3.0
                break
        else:
            # FIX: warn when architecture is unrecognised instead of silently
            # adding no arch patterns and distorting scores.
            logger.warning(
                f"Architecture '{self.architecture}' not found in "
                f"PLATFORM_ARCH_ALIASES; no arch patterns will be applied."
            )

        # 3. musl for non-glibc systems.
        if not self.is_glibc:
            self._plain_patterns["musl"] = 2.0

        # 4. Archive extensions (regex, kept separate from plain patterns).
        self._regex_patterns[r"\.(tar|zip|gz|bz2|xz|7z)"] = 2.0

        # 5. User-specified words (treated as plain strings).
        for word in self.extra_words:
            self._plain_patterns[word] = 2.0

    def _is_penalised(self, name_lower: str) -> bool:
        """Return True if the release name should be penalised."""
        # FIX: check extensions via str.endswith() and substrings separately,
        # preventing extension strings like ".json" from matching mid-filename.
        if any(name_lower.endswith(ext) for ext in PENALTY_EXTENSIONS):
            return True
        if any(kw in name_lower for kw in PENALTY_SUBSTRINGS):
            return True
        return False

    def _match_weight(self, name_lower: str) -> float:
        """Sum weights of all patterns that match name_lower."""
        weight = 0.0
        for pattern, w in self._plain_patterns.items():
            if pattern in name_lower:
                weight += w
        for pattern, w in self._regex_patterns.items():
            if re.search(pattern, name_lower):
                weight += w
        return weight

    def score(self, release_name: str) -> float:
        """Score a release name based on platform compatibility.

        Returns:
            Normalised score between 0.0 and 1.0 (before adjustments).
            Adjustments (penalties/bonuses) may push the value slightly
            outside that range but are bounded to [0, 1] before returning.
        """
        name_lower = release_name.lower()

        base_score = (
            self._match_weight(name_lower) / self._total_weight
            if self._total_weight > 0
            else 0.0
        )

        if not self.disable_adjustments:
            final_score = self._adjust_score(base_score, name_lower)
        else:
            final_score = base_score

        # FIX: clamp to [0, 1] so callers can always rely on the stated range.
        final_score = max(0.0, min(1.0, final_score))

        logger.debug(
            f"'{release_name}': base={base_score:.3f}, final={final_score:.3f}"
        )
        return final_score

    def _adjust_score(self, base_score: float, name_lower: str) -> float:
        """Apply penalty and bonus adjustments to a base score."""
        score = base_score

        if self.is_glibc:
            if "musl" in name_lower:
                score *= 0.7
                logger.debug(f"Applied musl penalty -> {score:.3f}")
            elif any(word in name_lower for word in ("glibc", "gnu")):
                score *= 1.1
                logger.debug(f"Applied glibc bonus -> {score:.3f}")

        # FIX: use the split penalty sets and report the triggering token.
        triggered = next(
            (ext for ext in PENALTY_EXTENSIONS if name_lower.endswith(ext)), None
        ) or next((kw for kw in PENALTY_SUBSTRINGS if kw in name_lower), None)
        if triggered:
            score *= 0.5
            logger.debug(f"Applied penalty for '{triggered}' -> {score:.3f}")

        return score

    def select_best(
        self, release_names: List[str], min_score: float = 0.2
    ) -> Optional[str]:
        """Select the best matching release.

        When ``disable_adjustments`` is True and ``extra_words`` are provided,
        prefers a release whose tokenised name contains *all* extra words over
        the highest-scored candidate.

        When only a single asset exists it is returned regardless of score,
        since there is no alternative.

        Args:
            release_names: List of release filenames.
            min_score: Minimum acceptable score (ignored when only one asset).

        Returns:
            Best matching release name or None.
        """
        if not release_names:
            return None

        scored = self.score_multiple(release_names)
        logger.debug(f"Top 3 scores: {scored[:3]}")

        # FIX: single-asset fallback is now explicit and documented.
        if len(scored) == 1:
            logger.info(f"Only one asset available, selecting: '{scored[0][0]}'")
            return scored[0][0]

        valid = [(name, s) for name, s in scored if s >= min_score]

        if not valid:
            logger.debug(f"No releases scored above {min_score}")
            return None

        best_name, best_score = valid[0]

        # When adjustments are disabled and the caller supplied extra words,
        # prefer an exact full-word match over the raw score winner.
        if self.disable_adjustments and self._extra_words_set:
            for name, _ in valid:
                release_words = set(to_words(name, ignore_words=["v", "unknown"]))
                if self._extra_words_set.issubset(release_words):
                    logger.debug(
                        f"Exact word match: '{name}' contains all words {self.extra_words}"
                    )
                    return name

        logger.debug(f"Selected: '{best_name}' (score: {best_score:.3f})")
        return best_name

    def score_multiple(self, release_names: List[str]) -> List[Tuple[str, float]]:
        """Score and sort multiple releases by descending score.

        Returns:
            List of (name, score) tuples sorted by score descending.
        """
        scored = [(name, self.score(name)) for name in release_names]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def get_info(self) -> Dict[str, Any]:
        """
        Returns:
            Dictionary with platform, architecture, pattern weights, etc.
        """
        all_patterns = {**self._plain_patterns, **self._regex_patterns}
        return {
            "platform_words": list(all_patterns.keys()),
            "extra_words": self.extra_words,
            "all_patterns": list(all_patterns.keys()),
            "pattern_weights": all_patterns,
            "is_glibc_system": self.is_glibc,
            "platform": self.platform,
            "architecture": self.architecture,
        }
