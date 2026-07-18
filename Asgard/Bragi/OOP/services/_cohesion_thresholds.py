"""Cohesion/coupling thresholds sourced from the ``Shared/Profiles`` plane.

Per ``_Docs/Planning/Heimdall/05_Cohesion_Coupling.md``: "Thresholds into
``Shared/Profiles`` builtin profiles (`Asgard Way - Python`: CBO 20, LCOM4 1,
WMC 20; Strict: CBO 12)." This module is the single place that resolves a
:class:`~Asgard.Shared.Profiles.models.profile_models.QualityProfile` (or the
absence of one) into concrete CBO/LCOM4/RFC/WMC numbers, so
``cir_metrics.py``, ``cohesion_analyzer.py``, and ``coupling_analyzer.py``
share one source of truth instead of each hardcoding its own constant.
"""
from dataclasses import dataclass
from typing import Optional

# Defaults mirror the "Asgard Way - Python" builtin profile and are used
# whenever no profile is supplied (zero-config path).
DEFAULT_CBO_THRESHOLD = 20.0
DEFAULT_LCOM4_THRESHOLD = 1.0
DEFAULT_RFC_THRESHOLD = 50.0
DEFAULT_WMC_THRESHOLD = 20.0

_RULE_IDS = {
    "cbo": "architecture.cohesion.cbo",
    "lcom4": "architecture.cohesion.lcom4",
    "rfc": "architecture.cohesion.rfc",
    "wmc": "architecture.cohesion.wmc",
}


@dataclass(frozen=True)
class CohesionThresholds:
    cbo: float = DEFAULT_CBO_THRESHOLD
    lcom4: float = DEFAULT_LCOM4_THRESHOLD
    rfc: float = DEFAULT_RFC_THRESHOLD
    wmc: float = DEFAULT_WMC_THRESHOLD


def thresholds_from_profile(profile=None) -> CohesionThresholds:
    """Resolve :class:`CohesionThresholds` from a
    :class:`~Asgard.Shared.Profiles.models.profile_models.QualityProfile`.

    Falls back to the documented "Asgard Way - Python" defaults for any
    rule not present/enabled in *profile* (including when *profile* is
    ``None`` — the zero-config case per the uplift's general-purpose-first
    mandate).
    """
    if profile is None:
        return CohesionThresholds()

    values = {}
    for key, rule_id in _RULE_IDS.items():
        rule = profile.get_rule(rule_id) if hasattr(profile, "get_rule") else None
        default = getattr(CohesionThresholds(), key)
        if rule is not None and getattr(rule, "enabled", True) and rule.threshold is not None:
            values[key] = float(rule.threshold)
        else:
            values[key] = default

    return CohesionThresholds(**values)


def resolve_thresholds(profile_name: Optional[str] = None) -> CohesionThresholds:
    """Look up *profile_name* via :class:`ProfileManager` and resolve
    thresholds. Returns defaults if the profile can't be found/loaded —
    this must never raise, since cohesion analysis has to keep working on a
    fresh repo with zero profile configuration."""
    if not profile_name:
        return CohesionThresholds()
    try:
        from Asgard.Shared.Profiles.services.profile_manager import ProfileManager  # noqa: PLC0415
        manager = ProfileManager()
        profile = manager.get_effective_profile(profile_name)
        return thresholds_from_profile(profile)
    except Exception:
        return CohesionThresholds()
