"""L0 tests for the Protobuf/GraphQL/SQL -> IR adapters (plan 07 phase 2/3)."""

import pytest

from Asgard.Forseti.Alignment.models.ir_models import TypeClass
from Asgard.Forseti.Alignment.services._ir_graphql_helpers import graphql_sdl_to_ir_record
from Asgard.Forseti.Alignment.services._ir_protobuf_helpers import protobuf_schema_to_ir_record
from Asgard.Forseti.Alignment.services._ir_sql_helpers import sql_table_to_ir_record
from Asgard.Forseti.Alignment.services.ir_builder_service import IRBuilderService
from Asgard.Forseti.Database.services.schema_analyzer_service import SchemaAnalyzerService
from Asgard.Forseti.GraphQL.utilities._graphql_parse_utils import parse_sdl
from Asgard.Forseti.Protobuf.services.protobuf_validator_service import ProtobufValidatorService

PROTO_SOURCE = """
syntax = "proto3";
package acme.orders;

enum Status {
  PENDING = 0;
  SHIPPED = 1;
}

message Order {
  string order_id = 1;
  double total = 2;
  Status status = 3;
  optional string notes = 4;
}
"""

GRAPHQL_SOURCE = """
type Order {
  orderId: ID!
  total: Float!
  status: Status!
  notes: String
}

enum Status {
  PENDING
  SHIPPED
}
"""

SQL_SOURCE = """
CREATE TABLE orders (
  order_id VARCHAR(36) NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  status VARCHAR(20) NOT NULL,
  notes TEXT
);
"""


class TestProtobufAdapter:
    def _schema(self):
        result = ProtobufValidatorService().validate_content(PROTO_SOURCE)
        return result.parsed_schema

    def test_field_names_and_optional(self):
        record = protobuf_schema_to_ir_record(self._schema(), "Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["order_id"].required is True
        assert by_name["notes"].nullable is True

    def test_enum_symbols_captured(self):
        record = protobuf_schema_to_ir_record(self._schema(), "Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["status"].type.type_class == TypeClass.ENUM
        assert set(by_name["status"].type.enum_symbols) == {"PENDING", "SHIPPED"}

    def test_lexical_tokens_normalized(self):
        record = protobuf_schema_to_ir_record(self._schema(), "Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["order_id"].lexical_tokens == ("order", "id")

    def test_missing_message_raises(self):
        with pytest.raises(ValueError):
            protobuf_schema_to_ir_record(self._schema(), "NoSuchMessage")

    def test_ir_builder_service_dispatch(self):
        record = IRBuilderService().build_protobuf(self._schema(), "Order")
        assert record.name == "Order"
        assert len(record.fields) == 4


class TestGraphQLAdapter:
    def _parsed(self):
        return parse_sdl(GRAPHQL_SOURCE)

    def test_non_null_maps_to_required(self):
        record = graphql_sdl_to_ir_record(self._parsed(), "Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["orderId"].required is True
        assert by_name["notes"].nullable is True

    def test_enum_symbols_captured(self):
        record = graphql_sdl_to_ir_record(self._parsed(), "Order")
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["status"].type.type_class == TypeClass.ENUM
        assert set(by_name["status"].type.enum_symbols) == {"PENDING", "SHIPPED"}

    def test_missing_type_raises(self):
        with pytest.raises(ValueError):
            graphql_sdl_to_ir_record(self._parsed(), "NoSuchType")

    def test_ir_builder_service_dispatch(self):
        record = IRBuilderService().build_graphql(self._parsed(), "Order")
        assert record.name == "Order"
        assert len(record.fields) == 4


class TestSQLAdapter:
    def _table(self):
        schema = SchemaAnalyzerService().analyze_sql(SQL_SOURCE)
        return schema.tables[0]

    def test_nullable_column_detected(self):
        record = sql_table_to_ir_record(self._table())
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["notes"].nullable is True
        assert by_name["order_id"].nullable is False

    def test_decimal_type_mapped(self):
        record = sql_table_to_ir_record(self._table())
        by_name = {f.raw_name: f for f in record.fields}
        assert by_name["total"].type.type_class == TypeClass.DECIMAL

    def test_ir_builder_service_dispatch(self):
        record = IRBuilderService().build_sql(self._table())
        assert record.name == "orders"
        assert len(record.fields) == 4
