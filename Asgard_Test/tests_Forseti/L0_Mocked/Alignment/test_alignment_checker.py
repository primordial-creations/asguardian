"""
L0 golden test for the alignment checker (plan 07 testing notes).

Two sources for one logical `Order` entity, deliberately diverging:
- `total`: Avro int32 (producer) vs OpenAPI int64 (consumer) -> widening,
  fine on that direction but the reverse (int64 producer -> int32
  consumer) is the interesting lossy case, exercised separately.
- `status`: Avro enum superset vs OpenAPI enum subset with a declared
  producer->consumer edge -> CRITICAL enum divergence.
- `notes`: Avro nullable (producer) vs OpenAPI required (consumer) with a
  declared edge -> CRITICAL nullability breach.
- `internal_flag`: only in Avro, listed in ignore_fields -> suppressed.
- `extra_field`: only in OpenAPI, not ignored -> INFO subset divergence.
"""

from Asgard.Forseti.Alignment.services.alignment_checker_service import (
    check_entity_alignment,
)
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService

AVRO_SOURCE = {
    "type": "record",
    "name": "Order",
    "fields": [
        {"name": "order_id", "type": "string"},
        {"name": "status", "type": {"type": "enum", "name": "Status", "symbols": ["PENDING", "SHIPPED", "CANCELLED"]}},
        {"name": "notes", "type": ["null", "string"]},
        {"name": "internal_flag", "type": "boolean"},
    ],
}

OPENAPI_SOURCE = {
    "type": "object",
    "required": ["orderId", "status", "notes"],
    "properties": {
        "orderId": {"type": "string"},
        "status": {"type": "string", "enum": ["PENDING", "SHIPPED"]},
        "notes": {"type": "string"},
        "extra_field": {"type": "string"},
    },
}


def _build_sources():
    builder = IRBuilderService()
    return {
        "kafka/order.avsc": builder.build(AVRO_SOURCE, "avro"),
        "rest/openapi.yaml": builder.build(OPENAPI_SOURCE, "openapi", name="Order"),
    }


class TestAlignmentGolden:
    def test_finding_counts_by_severity(self):
        sources = _build_sources()
        findings = check_entity_alignment(
            "Order",
            sources,
            direction_edges=[("kafka/order.avsc", "rest/openapi.yaml")],
            ignore_fields={"internal_flag"},
        )
        from Asgard.Forseti.Rules.models._rule_base_models import Severity

        errors = [f for f in findings if f.severity == Severity.ERROR]
        infos = [f for f in findings if f.severity == Severity.INFO]

        error_rule_ids = {f.rule_id for f in errors}
        assert "align.nullability-breach" in error_rule_ids
        assert "align.enum-divergence" in error_rule_ids

        info_rule_ids = {f.rule_id for f in infos}
        assert "align.subset-divergence" in info_rule_ids
        # internal_flag must NOT appear as subset-divergence (ignored).
        assert all("internal_flag" not in f.message for f in findings)
        # extra_field must appear.
        assert any("extra_field" in f.message for f in infos)

    def test_ignore_fields_never_suppresses_type_contradiction(self):
        avro = {
            "type": "record",
            "name": "Thing",
            "fields": [{"name": "flag", "type": "string"}],
        }
        openapi = {
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
        }
        builder = IRBuilderService()
        sources = {
            "a.avsc": builder.build(avro, "avro"),
            "b.yaml": builder.build(openapi, "openapi", name="Thing"),
        }
        findings = check_entity_alignment("Thing", sources, ignore_fields={"flag"})
        rule_ids = {f.rule_id for f in findings}
        assert "align.type-contradiction" in rule_ids

    def test_no_direction_edges_uses_symmetric_enum_check(self):
        avro = {
            "type": "record",
            "name": "Thing",
            "fields": [{"name": "status", "type": {"type": "enum", "name": "S", "symbols": ["A", "B"]}}],
        }
        openapi = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["A", "B", "C"]}},
        }
        builder = IRBuilderService()
        sources = {
            "a.avsc": builder.build(avro, "avro"),
            "b.yaml": builder.build(openapi, "openapi", name="Thing"),
        }
        findings = check_entity_alignment("Thing", sources)
        rule_ids = {f.rule_id for f in findings}
        assert "align.enum-divergence" in rule_ids
        # No direction declared, but one side is a strict superset -> INFO, not ERROR.
        from Asgard.Forseti.Rules.models._rule_base_models import Severity

        enum_findings = [f for f in findings if f.rule_id == "align.enum-divergence"]
        assert all(f.severity == Severity.INFO for f in enum_findings)
