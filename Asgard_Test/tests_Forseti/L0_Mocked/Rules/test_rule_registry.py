"""Tests for the Forseti rule registry (plan 02)."""

import pytest

from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.models.rule_models import RuleMeta
from Asgard.Forseti.Rules.services.rule_registry_service import (
    RuleRegistry,
    get_default_registry,
)


def _meta(rule_id="test.rule", **overrides) -> RuleMeta:
    base = dict(
        rule_id=rule_id,
        formats={SchemaFormat.OPENAPI},
        cost=Cost.ON,
        confidence=Confidence.DETERMINISTIC,
        severity=Severity.ERROR,
        category=RuleCategory.STRUCTURE,
    )
    base.update(overrides)
    return RuleMeta(**base)


class TestRuleMetaDiscipline:
    def test_heuristic_rules_may_never_be_error(self):
        with pytest.raises(ValueError):
            _meta(confidence=Confidence.HEURISTIC, severity=Severity.ERROR)

    def test_heuristic_warning_is_allowed(self):
        meta = _meta(confidence=Confidence.HEURISTIC, severity=Severity.WARNING)
        assert meta.severity == Severity.WARNING

    def test_core_rules_must_be_deterministic(self):
        with pytest.raises(ValueError):
            _meta(core=True, confidence=Confidence.HEURISTIC, severity=Severity.WARNING)


class TestRegistryQueries:
    def test_duplicate_rule_id_rejected(self):
        registry = RuleRegistry()
        registry.register(_meta())
        with pytest.raises(ValueError):
            registry.register(_meta())

    def test_query_by_format(self):
        registry = RuleRegistry()
        registry.register(_meta("a", formats={SchemaFormat.OPENAPI}))
        registry.register(_meta("b", formats={SchemaFormat.AVRO}))
        assert [r.meta.rule_id for r in registry.query(fmt=SchemaFormat.AVRO)] == ["b"]

    def test_query_by_max_cost(self):
        registry = RuleRegistry()
        registry.register(_meta("cheap", cost=Cost.O1))
        registry.register(_meta("linear", cost=Cost.ON))
        registry.register(_meta("net", cost=Cost.NETWORK))
        ids = [r.meta.rule_id for r in registry.query(max_cost=Cost.ON)]
        assert ids == ["cheap", "linear"]

    def test_query_by_confidence(self):
        registry = RuleRegistry()
        registry.register(_meta("det"))
        registry.register(_meta("heur", confidence=Confidence.HEURISTIC,
                                severity=Severity.INFO))
        ids = [r.meta.rule_id for r in registry.query(confidence=Confidence.DETERMINISTIC)]
        assert ids == ["det"]

    def test_legacy_resolution_is_per_format(self):
        registry = RuleRegistry()
        registry.register(_meta("oas.x", legacy_ids={"required-field"}))
        assert registry.resolve_legacy(SchemaFormat.OPENAPI, "required-field").meta.rule_id == "oas.x"
        assert registry.resolve_legacy(SchemaFormat.AVRO, "required-field") is None


class TestDefaultRegistry:
    def test_builtin_rules_loaded(self):
        registry = get_default_registry()
        assert registry.get("oas.lifecycle.deprecated-operation") is not None
        assert registry.get("oas.structure.required-field").meta.core is True

    def test_deprecated_operation_is_info_not_error(self):
        meta = get_default_registry().get("oas.lifecycle.deprecated-operation").meta
        assert meta.severity == Severity.INFO
        assert meta.category == RuleCategory.LIFECYCLE

    def test_no_registered_heuristic_rule_is_error(self):
        for rule in get_default_registry().all_rules():
            if rule.meta.confidence == Confidence.HEURISTIC:
                assert rule.meta.severity != Severity.ERROR, rule.meta.rule_id

    def test_deprecated_check_yields_info_findings(self):
        registry = get_default_registry()
        rule = registry.get("oas.lifecycle.deprecated-operation")
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1"},
            "paths": {"/old": {"get": {"deprecated": True,
                                        "responses": {"200": {"description": "OK"}}}}},
        }
        findings = rule.check(spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.INFO
