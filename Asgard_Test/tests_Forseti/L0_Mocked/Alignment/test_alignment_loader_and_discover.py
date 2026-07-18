"""L0 tests for the alignment loader (config -> IR -> findings) and the
`align discover` name-heuristic wizard (plan 07 phases 3/4)."""

import json

import pytest
import yaml

from Asgard.Forseti.Alignment.models.alignment_models import AlignmentConfig
from Asgard.Forseti.Alignment.services._discover_helpers import discover, strip_suffix, write_config
from Asgard.Forseti.Alignment.services.alignment_loader_service import (
    build_ir_record,
    check_config,
    infer_format,
    load_config,
)

OPENAPI_DOC = {
    "openapi": "3.0.0",
    "info": {"title": "x", "version": "1"},
    "paths": {},
    "components": {
        "schemas": {
            "OrderResponse": {
                "type": "object",
                "required": ["orderId"],
                "properties": {
                    "orderId": {"type": "string"},
                    "status": {"type": "string", "enum": ["PENDING", "SHIPPED"]},
                },
            }
        }
    },
}

AVRO_DOC = {
    "type": "record",
    "name": "Order",
    "fields": [
        {"name": "order_id", "type": "string"},
        {"name": "status", "type": {"type": "enum", "name": "Status", "symbols": ["PENDING", "SHIPPED", "CANCELLED"]}},
    ],
}


@pytest.fixture
def fixture_dir(tmp_path):
    (tmp_path / "openapi.yaml").write_text(yaml.safe_dump(OPENAPI_DOC), encoding="utf-8")
    (tmp_path / "order.avsc").write_text(json.dumps(AVRO_DOC), encoding="utf-8")
    return tmp_path


class TestInferFormat:
    def test_extension_based(self):
        from Asgard.Forseti.Alignment.models.alignment_models import EntitySource

        assert infer_format(EntitySource(file="x.avsc")) == "avro"
        assert infer_format(EntitySource(file="x.proto")) == "protobuf"
        assert infer_format(EntitySource(file="x.graphql")) == "graphql"
        assert infer_format(EntitySource(file="x.sql")) == "sql"
        assert infer_format(EntitySource(file="x.yaml")) == "openapi"

    def test_explicit_override_wins(self):
        from Asgard.Forseti.Alignment.models.alignment_models import EntitySource

        assert infer_format(EntitySource(file="x.yaml", format="avro")) == "avro"


class TestBuildIRRecord:
    def test_openapi_schema_by_name(self, fixture_dir):
        from Asgard.Forseti.Alignment.models.alignment_models import EntitySource

        record = build_ir_record(EntitySource(file="openapi.yaml", schema_name="OrderResponse"), base_dir=str(fixture_dir))
        assert record.name == "OrderResponse" or len(record.fields) == 2

    def test_avro(self, fixture_dir):
        from Asgard.Forseti.Alignment.models.alignment_models import EntitySource

        record = build_ir_record(EntitySource(file="order.avsc"), base_dir=str(fixture_dir))
        assert record.name == "Order"
        assert len(record.fields) == 2


class TestCheckConfig:
    def test_end_to_end_two_source_entity(self, fixture_dir):
        config = AlignmentConfig.model_validate(
            {
                "entities": {
                    "Order": {
                        "sources": [
                            {"file": "openapi.yaml", "schema_name": "OrderResponse"},
                            {"file": "order.avsc"},
                        ],
                        "direction": [{"from": "order.avsc", "to": "openapi.yaml"}],
                    }
                }
            }
        )
        findings, report = check_config(config, base_dir=str(fixture_dir))
        assert "Order" in report.entities_checked
        # status: Avro superset enum (producer) -> OpenAPI subset (consumer) is fine (subset OK);
        # order_id vs orderId -> lexical divergence INFO.
        rule_ids = {f.rule_id for f in findings}
        assert "align.lexical-divergence" in rule_ids

    def test_entity_filter(self, fixture_dir):
        config = AlignmentConfig.model_validate(
            {
                "entities": {
                    "Order": {"sources": [{"file": "openapi.yaml", "schema_name": "OrderResponse"}]},
                    "Other": {"sources": [{"file": "order.avsc"}]},
                }
            }
        )
        _findings, report = check_config(config, base_dir=str(fixture_dir), entity_filter="Order")
        assert report.entities_checked == ["Order"]


class TestLoadConfig:
    def test_round_trip(self, tmp_path):
        config = AlignmentConfig.model_validate(
            {"entities": {"Order": {"sources": [{"file": "a.yaml"}]}}}
        )
        path = tmp_path / "alignment-config.yaml"
        write_config(config, str(path))
        loaded = load_config(str(path))
        assert "Order" in loaded.entities


class TestDiscover:
    def test_strip_suffix(self):
        assert strip_suffix("OrderEvent") == "Order"
        assert strip_suffix("OrderResponse") == "Order"
        assert strip_suffix("Order") == "Order"

    def test_discover_groups_cross_format_entities(self, fixture_dir):
        config = discover([str(fixture_dir / "openapi.yaml"), str(fixture_dir / "order.avsc")])
        # OrderResponse -> Order (openapi), Order -> Order (avro): should group.
        assert "Order" in config.entities
        assert len(config.entities["Order"].sources) == 2

    def test_discover_ignores_single_format_entities(self, tmp_path):
        (tmp_path / "solo.avsc").write_text(json.dumps(AVRO_DOC), encoding="utf-8")
        config = discover([str(tmp_path / "solo.avsc")])
        assert config.entities == {}
