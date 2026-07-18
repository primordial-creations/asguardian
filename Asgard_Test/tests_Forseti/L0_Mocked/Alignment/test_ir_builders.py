"""L0 tests for the OpenAPI/JSON Schema and Avro -> IR adapters (plan 07 phase 1)."""

from Asgard.Forseti.Alignment.models.ir_models import TypeClass
from Asgard.Forseti.Alignment.services._ir_avro_helpers import avro_schema_to_ir_record
from Asgard.Forseti.Alignment.services._ir_openapi_helpers import openapi_schema_to_ir_record
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService

OPENAPI_ORDER_SCHEMA = {
    "type": "object",
    "required": ["orderId", "total"],
    "properties": {
        "orderId": {"type": "string"},
        "total": {"type": "number", "format": "double"},
        "status": {"type": "string", "enum": ["PENDING", "SHIPPED"]},
        "notes": {"type": ["string", "null"]},
    },
}

AVRO_ORDER_SCHEMA = {
    "type": "record",
    "name": "Order",
    "fields": [
        {"name": "order_id", "type": "string"},
        {"name": "total", "type": "double"},
        {"name": "status", "type": {"type": "enum", "name": "Status", "symbols": ["PENDING", "SHIPPED", "CANCELLED"]}},
        {"name": "notes", "type": ["null", "string"]},
    ],
}


class TestOpenAPIAdapter:
    def test_field_names_and_required(self):
        record = openapi_schema_to_ir_record(OPENAPI_ORDER_SCHEMA, name="Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["orderId"].required is True
        assert by_name["status"].required is False

    def test_nullable_union_type_detected(self):
        record = openapi_schema_to_ir_record(OPENAPI_ORDER_SCHEMA, name="Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["notes"].nullable is True

    def test_enum_symbols_captured(self):
        record = openapi_schema_to_ir_record(OPENAPI_ORDER_SCHEMA, name="Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["status"].type.type_class == TypeClass.ENUM
        assert set(by_name["status"].type.enum_symbols) == {"PENDING", "SHIPPED"}

    def test_lexical_tokens_normalized(self):
        record = openapi_schema_to_ir_record(OPENAPI_ORDER_SCHEMA, name="Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["orderId"].lexical_tokens == ("order", "id")


class TestAvroAdapter:
    def test_union_null_marks_nullable(self):
        record = avro_schema_to_ir_record(AVRO_ORDER_SCHEMA)
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["notes"].nullable is True
        assert by_name["order_id"].nullable is False

    def test_enum_symbols_captured(self):
        record = avro_schema_to_ir_record(AVRO_ORDER_SCHEMA)
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["status"].type.type_class == TypeClass.ENUM
        assert set(by_name["status"].type.enum_symbols) == {"PENDING", "SHIPPED", "CANCELLED"}

    def test_lexical_tokens_match_openapi_camel_case(self):
        avro_record = avro_schema_to_ir_record(AVRO_ORDER_SCHEMA)
        openapi_record = openapi_schema_to_ir_record(OPENAPI_ORDER_SCHEMA, name="Order")
        avro_field = avro_record.field_by_tokens(("order", "id"))
        openapi_field = openapi_record.field_by_tokens(("order", "id"))
        assert avro_field is not None and openapi_field is not None
        assert avro_field.raw_name == "order_id"
        assert openapi_field.raw_name == "orderId"


class TestIRBuilderService:
    def test_dispatches_openapi(self):
        record = IRBuilderService().build(OPENAPI_ORDER_SCHEMA, "openapi", name="Order")
        assert record.name == "Order"
        assert len(record.fields) == 4

    def test_dispatches_avro(self):
        record = IRBuilderService().build(AVRO_ORDER_SCHEMA, "avro")
        assert record.name == "Order"
        assert len(record.fields) == 4

    def test_unsupported_format_raises(self):
        import pytest

        with pytest.raises(ValueError):
            IRBuilderService().build({}, "cobol")
