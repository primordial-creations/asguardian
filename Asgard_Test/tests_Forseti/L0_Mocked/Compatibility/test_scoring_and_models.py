"""Scoring, classification and model tests for the unified compat engine."""

import random

import pytest

from Asgard.Forseti.Compatibility import (
    AbstractViolation,
    CompatMode,
    CompatStatus,
    Direction,
    TierVerdict,
    UnifiedChange,
)
from Asgard.Forseti.Compatibility.services._classification_helpers import (
    COMPAT_RULE_TABLE,
    make_change,
)
from Asgard.Forseti.Compatibility.services._scoring_helpers import (
    compute_score,
    compute_status,
    deduction,
    temporal_penalty,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat
from Asgard.Forseti.Rules.services.rule_registry_service import get_default_registry


class TestScoring:
    def test_empty_changes_scores_100(self):
        score, receipt = compute_score([])
        assert score == 100
        assert receipt == []

    def test_score_deducts_per_change(self):
        change = make_change("OAS-RES-FIELD-REMOVED", SchemaFormat.OPENAPI,
                             Direction.OUTPUT, "/a", "removed")
        score, receipt = compute_score([change])
        assert score == 85  # base 15 x temporal 1.0 x blast 1
        assert "OAS-RES-FIELD-REMOVED" in receipt[0]

    def test_avro_temporal_penalty_is_5x(self):
        assert temporal_penalty(SchemaFormat.AVRO) == 5.0
        assert temporal_penalty(SchemaFormat.ASYNCAPI) == 5.0
        assert temporal_penalty(SchemaFormat.PROTOBUF) == 1.5
        assert temporal_penalty(SchemaFormat.OPENAPI) == 1.0

    def test_blast_radius_multiplies(self):
        change = make_change("OAS-SCHEMA-REMOVED", SchemaFormat.OPENAPI,
                             Direction.OUTPUT, "/s", "removed", blast_radius=3)
        assert deduction(change) == 45

    def test_waived_change_deducts_nothing(self):
        change = make_change("OAS-PATH-REMOVED", SchemaFormat.OPENAPI,
                             Direction.INPUT, "/p", "gone")
        change.waived = True
        assert deduction(change) == 0.0
        score, _ = compute_score([change])
        assert score == 100

    def test_score_floor_is_zero(self):
        changes = [
            make_change("ASYNC-CHANNEL-REMOVED", SchemaFormat.ASYNCAPI,
                        Direction.OUTPUT, f"/c{i}", "gone")
            for i in range(5)
        ]
        score, _ = compute_score(changes)
        assert score == 0

    def test_score_is_monotonic(self):
        """Property test: adding a change never increases the score."""
        rng = random.Random(42)
        rule_ids = list(COMPAT_RULE_TABLE)
        changes: list[UnifiedChange] = []
        previous = 100
        for i in range(30):
            rule_id = rng.choice(rule_ids)
            fmt = SchemaFormat.OPENAPI
            changes.append(make_change(rule_id, fmt, Direction.OUTPUT,
                                       f"/loc{i}", "msg",
                                       blast_radius=rng.randint(1, 4)))
            score, _ = compute_score(changes)
            assert score <= previous
            previous = score


class TestStatus:
    def test_structural_fail_fails(self):
        change = make_change("OAS-PATH-REMOVED", SchemaFormat.OPENAPI,
                             Direction.INPUT, "/p", "gone")
        assert compute_status([change]) == CompatStatus.FAILED

    def test_hazard_only_is_conditional(self):
        change = make_change("AVRO-FIELD-ADDED-DEFAULT", SchemaFormat.AVRO,
                             Direction.OUTPUT, "/f", "bridged")
        assert change.impact.structural == TierVerdict.PASS
        assert change.impact.semantic == TierVerdict.HAZARD
        assert compute_status([change]) == CompatStatus.CONDITIONALLY_PASSED

    def test_no_changes_passes(self):
        assert compute_status([]) == CompatStatus.PASSED

    def test_waived_fail_does_not_gate(self):
        change = make_change("OAS-PATH-REMOVED", SchemaFormat.OPENAPI,
                             Direction.INPUT, "/p", "gone")
        change.waived = True
        assert compute_status([change]) == CompatStatus.PASSED


class TestClassificationTable:
    def test_every_rule_has_valid_severity_range(self):
        for rule_id, (violation, structural, semantic, base, desc) in \
                COMPAT_RULE_TABLE.items():
            assert 0 <= base <= 100, rule_id
            assert desc, rule_id
            assert isinstance(violation, AbstractViolation)

    def test_default_bridges_are_never_silently_green(self):
        """DEEPTHINK_01: structural PASS must pair with semantic HAZARD."""
        for rule_id in ("AVRO-FIELD-ADDED-DEFAULT", "AVRO-FIELD-REMOVED",
                        "PROTO-FIELD-RENAMED", "OAS-RES-ENUM-EXTENDED"):
            _, structural, semantic, _, _ = COMPAT_RULE_TABLE[rule_id]
            assert structural == TierVerdict.PASS
            assert semantic == TierVerdict.HAZARD

    def test_unknown_rule_id_raises(self):
        with pytest.raises(KeyError):
            make_change("NOT-A-RULE", SchemaFormat.OPENAPI,
                        Direction.INPUT, "/", "x")


class TestRegistryIntegration:
    def test_compat_rules_registered_with_dotted_ids(self):
        import Asgard.Forseti.Compatibility.services.compat_engine_service  # noqa: F401

        registry = get_default_registry()
        rule = registry.get("avro.compat.field-removed")
        assert rule is not None
        assert "AVRO-FIELD-REMOVED" in rule.meta.legacy_ids

    def test_legacy_resolution(self):
        import Asgard.Forseti.Compatibility.services.compat_engine_service  # noqa: F401

        registry = get_default_registry()
        rule = registry.resolve_legacy(SchemaFormat.PROTOBUF, "PROTO-RPC-REMOVED")
        assert rule is not None
        assert rule.meta.rule_id == "proto.compat.rpc-removed"


class TestCompatMode:
    def test_transitive_flags(self):
        assert CompatMode.BACKWARD_TRANSITIVE.is_transitive
        assert not CompatMode.BACKWARD.is_transitive
        assert CompatMode.FULL_TRANSITIVE.pairwise == CompatMode.FULL
