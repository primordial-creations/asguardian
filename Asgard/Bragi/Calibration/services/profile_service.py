"""
Language Profile Service (Plan 05 Phase A).

Loader for the YAML profile plane with the documented fallback chain:

    project override (`.asgard_cache/bragi_local_profile.yaml`, Phase B)
        -> language profile (`Bragi/Calibration/profiles/<language>.yaml`)
        -> generic defaults (`Bragi/Calibration/profiles/generic.yaml`)

Missing profile -> generic defaults, never KeyError. Individual missing
thresholds fall through the same chain independently (a local profile that
only overrides `cyclomatic_complexity` still inherits everything else from
the language profile).
"""

from pathlib import Path
from typing import Dict, Optional

import yaml

from Asgard.Bragi.Calibration.models.calibration_models import (
    LanguageProfile,
    ThresholdSpec,
)

_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
_GENERIC_LANGUAGE = "generic"
LOCAL_PROFILE_RELATIVE_PATH = Path(".asgard_cache") / "bragi_local_profile.yaml"


def _load_yaml_profile(path: Path) -> Optional[LanguageProfile]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return LanguageProfile(**data)


class LanguageProfileService:
    """
    Resolves per-language thresholds through the fallback chain.

    Usage:
        service = LanguageProfileService(project_path=Path("."))
        cc_warn = service.threshold("python", "cyclomatic_complexity").warn
        wmc = service.scalar("python", "wmc")
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        profiles_dir: Optional[Path] = None,
    ):
        self.project_path = Path(project_path or Path.cwd())
        self.profiles_dir = profiles_dir or _PROFILES_DIR
        self._cache: Dict[str, LanguageProfile] = {}
        self._generic = self._load_language(_GENERIC_LANGUAGE) or LanguageProfile(
            language=_GENERIC_LANGUAGE, provenance="in-code fallback (no generic.yaml found)"
        )
        self._local: Optional[LanguageProfile] = self._load_local_override()

    def _load_language(self, language: str) -> Optional[LanguageProfile]:
        if language in self._cache:
            return self._cache[language]
        path = self.profiles_dir / f"{language}.yaml"
        profile = _load_yaml_profile(path)
        if profile is not None:
            self._cache[language] = profile
        return profile

    def _load_local_override(self) -> Optional[LanguageProfile]:
        return _load_yaml_profile(self.project_path / LOCAL_PROFILE_RELATIVE_PATH)

    def resolve(self, language: str) -> LanguageProfile:
        """
        Merged profile for a language: local override values win, then the
        language profile, then generic defaults. Never raises - an unknown
        language returns the generic profile relabeled.
        """
        language_profile = self._load_language(language) or LanguageProfile(
            language=language, provenance="no dedicated profile; using generic defaults"
        )

        merged_thresholds = dict(self._generic.thresholds)
        merged_thresholds.update(language_profile.thresholds)
        merged_scalars = dict(self._generic.scalar_thresholds)
        merged_scalars.update(language_profile.scalar_thresholds)
        merged_severity = dict(self._generic.severity_confidence)
        merged_severity.update(language_profile.severity_confidence)
        category_weights = language_profile.category_weights or self._generic.category_weights
        provenance = language_profile.provenance or self._generic.provenance

        if self._local is not None:
            merged_thresholds.update(self._local.thresholds)
            merged_scalars.update(self._local.scalar_thresholds)
            merged_severity.update(self._local.severity_confidence)
            if self._local.category_weights:
                category_weights = self._local.category_weights
            provenance = self._local.provenance or provenance

        return LanguageProfile(
            language=language,
            provenance=provenance,
            thresholds=merged_thresholds,
            scalar_thresholds=merged_scalars,
            severity_confidence=merged_severity,
            category_weights=category_weights,
        )

    def threshold(self, language: str, metric_id: str) -> ThresholdSpec:
        """Resolve a warn/fail threshold, falling through to generic defaults."""
        profile = self.resolve(language)
        if metric_id in profile.thresholds:
            return profile.thresholds[metric_id]
        if metric_id in self._generic.thresholds:
            return self._generic.thresholds[metric_id]
        raise KeyError(f"No threshold '{metric_id}' in any profile (language={language})")

    def scalar(self, language: str, metric_id: str, default: Optional[float] = None) -> Optional[float]:
        """Resolve a scalar threshold; returns `default` (None by default) when absent anywhere."""
        profile = self.resolve(language)
        if metric_id in profile.scalar_thresholds:
            return profile.scalar_thresholds[metric_id]
        return self._generic.scalar_thresholds.get(metric_id, default)
