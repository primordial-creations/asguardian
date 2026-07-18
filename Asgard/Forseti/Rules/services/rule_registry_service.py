"""
Rule Registry Service - register and query rules by metadata predicate.

The registry is the single source of truth for rule ids and metadata
(DEEPTHINK_05 Unified Rule Registry). Executable rules wrap check
functions; metadata-only entries describe legacy validator checks that
have not yet been converted to registry execution but still need stable
ids, severities and rationales for reporting.
"""

from typing import Any, Callable, Iterable, Optional

from Asgard.Forseti.Reporting.models.finding_models import Finding
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
)
from Asgard.Forseti.Rules.models.rule_models import RuleMeta

CheckFunction = Callable[[dict[str, Any]], Iterable[Finding]]


class Rule:
    """A registered rule: metadata plus an optional check callable."""

    def __init__(self, meta: RuleMeta, check: Optional[CheckFunction] = None):
        self.meta = meta
        self._check = check

    @property
    def executable(self) -> bool:
        """Whether this rule has an attached check function."""
        return self._check is not None

    def check(self, document: dict[str, Any]) -> list[Finding]:
        """Run the rule against a parsed document."""
        if self._check is None:
            return []
        return list(self._check(document))


class RuleRegistry:
    """Registry of rules, queryable by metadata predicates."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._legacy_index: dict[tuple[SchemaFormat, str], str] = {}

    def register(self, meta: RuleMeta, check: Optional[CheckFunction] = None) -> Rule:
        """Register a rule; raises on duplicate rule_id."""
        if meta.rule_id in self._rules:
            raise ValueError(f"Duplicate rule id: {meta.rule_id}")
        rule = Rule(meta, check)
        self._rules[meta.rule_id] = rule
        for fmt in meta.formats:
            for legacy in meta.legacy_ids:
                self._legacy_index[(fmt, legacy)] = meta.rule_id
        return rule

    def get(self, rule_id: str) -> Optional[Rule]:
        """Look up a rule by id."""
        return self._rules.get(rule_id)

    def resolve_legacy(self, fmt: SchemaFormat, legacy_id: str) -> Optional[Rule]:
        """Resolve a pre-registry rule string to its registered rule."""
        rule_id = self._legacy_index.get((fmt, legacy_id))
        return self._rules.get(rule_id) if rule_id else None

    def all_rules(self) -> list[Rule]:
        """All registered rules, sorted by rule id."""
        return [self._rules[k] for k in sorted(self._rules)]

    def query(
        self,
        *,
        fmt: Optional[SchemaFormat] = None,
        max_cost: Optional[Cost] = None,
        confidence: Optional[Confidence] = None,
        category: Optional[RuleCategory] = None,
        predicate: Optional[Callable[[RuleMeta], bool]] = None,
    ) -> list[Rule]:
        """Select rules matching all supplied metadata predicates."""
        selected: list[Rule] = []
        for rule in self.all_rules():
            meta = rule.meta
            if fmt is not None and fmt not in meta.formats:
                continue
            if max_cost is not None and meta.cost.rank > max_cost.rank:
                continue
            if confidence is not None and meta.confidence != confidence:
                continue
            if category is not None and meta.category != category:
                continue
            if predicate is not None and not predicate(meta):
                continue
            selected.append(rule)
        return selected


default_registry = RuleRegistry()


def register_rule(meta: RuleMeta, registry: Optional[RuleRegistry] = None):
    """Decorator registering a check function under `meta`."""

    def decorator(fn: CheckFunction) -> CheckFunction:
        (registry or default_registry).register(meta, fn)
        return fn

    return decorator


def get_default_registry() -> RuleRegistry:
    """Return the process-wide default registry with builtin rules loaded."""
    # Imported lazily so module import order cannot create cycles.
    from Asgard.Forseti.Rules.services import _builtin_rules  # noqa: F401

    return default_registry
