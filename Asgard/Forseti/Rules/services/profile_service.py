"""
Profile Service - built-in validation profiles and `.forseti.yaml` loading.

Built-in profile semantics (DEEPTHINK_05 / DEEPTHINK_11):

| Profile    | Rule selector                     | Budget | Bailout    | Blocking |
|------------|-----------------------------------|--------|------------|----------|
| ide        | all                               | 200 ms | fail-open  | never    |
| pre-commit | cost<=O(N), deterministic only    | 2 s    | fail-open  | soft     |
| ci         | all                               | 30 s   | fail-closed| hard     |
| audit      | all                               | none   | fail-closed| report   |

Core rules can never be disabled or downgraded by any profile.
"""

import fnmatch
from pathlib import Path
from typing import Optional

import yaml

from Asgard.Forseti.Rules.models._rule_base_models import Cost, Severity
from Asgard.Forseti.Rules.models.rule_models import ForsetiConfig, PathOverride, Profile, RuleMeta
from Asgard.Forseti.Rules.services.rule_registry_service import Rule, RuleRegistry

CONFIG_FILENAME = ".forseti.yaml"

BUILTIN_PROFILES: dict[str, Profile] = {
    "ide": Profile(
        name="ide", max_cost=Cost.NETWORK, budget_ms=200, fail_open=True, blocking="never",
    ),
    "pre-commit": Profile(
        name="pre-commit", max_cost=Cost.ON, deterministic_only=True,
        budget_ms=2000, fail_open=True, blocking="soft",
    ),
    "ci": Profile(
        name="ci", max_cost=Cost.NETWORK, budget_ms=30000, fail_open=False, blocking="hard",
    ),
    "audit": Profile(
        name="audit", max_cost=Cost.NETWORK, budget_ms=None, fail_open=False, blocking="report",
    ),
}


def load_config(path: Optional[str | Path] = None) -> Optional[ForsetiConfig]:
    """Load `.forseti.yaml` from `path` (file or directory). None if absent."""
    if path is None:
        candidate = Path.cwd() / CONFIG_FILENAME
    else:
        candidate = Path(path)
        if candidate.is_dir():
            candidate = candidate / CONFIG_FILENAME
    if not candidate.is_file():
        return None
    raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    overrides = [PathOverride(**entry) for entry in raw.get("overrides", []) or []]
    return ForsetiConfig(
        version=raw.get("version", 1),
        ruleset_version=raw.get("ruleset_version"),
        profile=raw.get("profile", "ci"),
        rules={str(k): str(v) for k, v in (raw.get("rules") or {}).items()},
        overrides=overrides,
    )


def resolve_profile(
    name: Optional[str] = None,
    config: Optional[ForsetiConfig] = None,
) -> Profile:
    """Resolve a profile by name, merging config-file rule overrides."""
    profile_name = name or (config.profile if config else "ci")
    base = BUILTIN_PROFILES.get(profile_name)
    if base is None:
        base = BUILTIN_PROFILES["ci"].model_copy(update={"name": profile_name})
    profile = base.model_copy(deep=True)
    if config:
        profile.rule_overrides = dict(config.rules)
        profile.path_overrides = list(config.overrides)
    return profile


def select_rules(registry: RuleRegistry, profile: Profile, fmt=None) -> list[Rule]:
    """Select the executable rule set for a profile."""
    from Asgard.Forseti.Rules.models._rule_base_models import Confidence

    rules = registry.query(
        fmt=fmt,
        max_cost=profile.max_cost,
        confidence=Confidence.DETERMINISTIC if profile.deterministic_only else None,
    )
    return [r for r in rules if effective_severity(r.meta, profile) is not None or r.meta.core]


def _match_override(rule_id: str, overrides: dict[str, str]) -> Optional[str]:
    """Find the override value matching a rule id (exact wins over glob)."""
    if rule_id in overrides:
        return overrides[rule_id]
    for pattern, value in overrides.items():
        if fnmatch.fnmatch(rule_id, pattern):
            return value
    return None


def effective_severity(
    meta: RuleMeta,
    profile: Profile,
    file_path: Optional[str] = None,
) -> Optional[Severity]:
    """
    Resolve the effective severity of a rule under a profile.

    Returns None when the rule is disabled. Core rules ignore any attempt
    to disable or downgrade them; overrides may only strengthen severity
    for core rules (never weaken — DEEPTHINK_02 Inviolable Core).
    """
    override = _match_override(meta.rule_id, profile.rule_overrides)
    if file_path:
        for path_override in profile.path_overrides:
            if fnmatch.fnmatch(file_path, path_override.path):
                scoped = _match_override(meta.rule_id, path_override.rules)
                if scoped is not None:
                    override = scoped
    if override is None:
        return meta.severity
    value = override.strip().lower()
    if value in ("off", "false", "disabled", "none"):
        return None if not meta.core else meta.severity
    try:
        candidate = Severity(value)
    except ValueError:
        return meta.severity
    if meta.core and candidate.rank < meta.severity.rank:
        return meta.severity
    # Heuristic rules can never be promoted to ERROR (DEEPTHINK_10).
    from Asgard.Forseti.Rules.models._rule_base_models import Confidence

    if meta.confidence == Confidence.HEURISTIC and candidate == Severity.ERROR:
        return Severity.WARNING
    return candidate
