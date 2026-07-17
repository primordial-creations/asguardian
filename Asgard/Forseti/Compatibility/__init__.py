"""
Forseti Compatibility - the unified compatibility engine (plan 01).

One engine for all schema formats: format parsers stay format-specific,
classification (input contravariance / output covariance), tiering
(structural / semantic / empirical), scoring (0-100 with Blast Radius
Receipt) and transitive modes are shared.
"""

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    AbstractViolation,
    CompatMode,
    CompatStatus,
    Direction,
    EmpiricalVerdict,
    TierVerdict,
)
from Asgard.Forseti.Compatibility.models.compat_models import (
    CompatReport,
    ImpactAssessment,
    TelemetrySource,
    UnifiedChange,
    UsageStats,
)
from Asgard.Forseti.Compatibility.models.legacy_models import LegacyBreakingChange


def __getattr__(name: str):
    """Lazily import the engine so format modules can import our models
    without creating an import cycle."""
    if name in ("CompatEngineService", "JsonFileTelemetrySource"):
        from Asgard.Forseti.Compatibility.services import compat_engine_service
        return getattr(compat_engine_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AbstractViolation",
    "CompatEngineService",
    "CompatMode",
    "CompatReport",
    "CompatStatus",
    "Direction",
    "EmpiricalVerdict",
    "ImpactAssessment",
    "JsonFileTelemetrySource",
    "TelemetrySource",
    "TierVerdict",
    "UnifiedChange",
    "UsageStats",
]
