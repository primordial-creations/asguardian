"""
Forseti Rules - unified rule registry, validation profiles and governance.

Provides metadata-tagged rules with stable namespaced ids, built-in
validation profiles (ide / pre-commit / ci / audit), inline suppressions
with mandatory reasons, finding baselines and compatibility epoch waivers.
"""

RULESET_VERSION = "1.0.0"

from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
    Target,
)
from Asgard.Forseti.Rules.models.rule_models import (
    BaselineEntry,
    ForsetiConfig,
    PathOverride,
    Profile,
    RuleMeta,
    SuppressionEntry,
    WaiverEntry,
)
# Service symbols are exposed lazily (PEP 562) so that importing
# Rules.models from Reporting.models does not create an import cycle
# (Reporting.models <- Rules.services <- Reporting.models).
_LAZY_EXPORTS = {
    "Rule": "Asgard.Forseti.Rules.services.rule_registry_service",
    "RuleRegistry": "Asgard.Forseti.Rules.services.rule_registry_service",
    "default_registry": "Asgard.Forseti.Rules.services.rule_registry_service",
    "get_default_registry": "Asgard.Forseti.Rules.services.rule_registry_service",
    "register_rule": "Asgard.Forseti.Rules.services.rule_registry_service",
    "BUILTIN_PROFILES": "Asgard.Forseti.Rules.services.profile_service",
    "effective_severity": "Asgard.Forseti.Rules.services.profile_service",
    "load_config": "Asgard.Forseti.Rules.services.profile_service",
    "resolve_profile": "Asgard.Forseti.Rules.services.profile_service",
    "select_rules": "Asgard.Forseti.Rules.services.profile_service",
    "BaselineService": "Asgard.Forseti.Rules.services.baseline_service",
    "WaiverService": "Asgard.Forseti.Rules.services.waiver_service",
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        module = importlib.import_module(_LAZY_EXPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module 'Asgard.Forseti.Rules' has no attribute {name!r}")

__all__ = [
    "RULESET_VERSION",
    "BUILTIN_PROFILES",
    "BaselineEntry",
    "BaselineService",
    "Confidence",
    "Cost",
    "ForsetiConfig",
    "PathOverride",
    "Profile",
    "Rule",
    "RuleCategory",
    "RuleMeta",
    "RuleRegistry",
    "SchemaFormat",
    "Severity",
    "SuppressionEntry",
    "Target",
    "WaiverEntry",
    "WaiverService",
    "default_registry",
    "effective_severity",
    "get_default_registry",
    "load_config",
    "register_rule",
    "resolve_profile",
    "select_rules",
]
