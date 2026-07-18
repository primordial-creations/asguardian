"""Avro adapter (RESEARCH_02 semantics) and Protobuf adapter (RESEARCH_14)."""

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    AbstractViolation,
    CompatMode,
    TierVerdict,
)
from Asgard.Forseti.Compatibility.services._avro_adapter import (
    build_named_type_registry,
    diff_avro,
    resolve_named_types,
)
from Asgard.Forseti.Compatibility.services._protobuf_adapter import (
    diff_protobuf,
    wire_compatible,
)
from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufEnum,
    ProtobufField,
    ProtobufMessage,
    ProtobufSchema,
    ProtobufService,
)


def record(fields):
    return {"type": "record", "name": "User", "fields": fields}


class TestAvroAdapter:
    def test_removed_field_with_default_is_compatible_plus_hazard(self):
        """RESEARCH_02: removed-field-with-default = COMPATIBLE + hazard text."""
        old = record([{"name": "a", "type": "string"},
                      {"name": "b", "type": "int", "default": 0}])
        new = record([{"name": "a", "type": "string"}])
        changes = diff_avro(old, new, CompatMode.BACKWARD)
        assert len(changes) == 1
        assert changes[0].rule_id == "AVRO-FIELD-REMOVED"
        assert changes[0].impact.structural == TierVerdict.PASS
        assert changes[0].impact.semantic == TierVerdict.HAZARD

    def test_added_field_without_default_breaks_backward(self):
        old = record([{"name": "a", "type": "string"}])
        new = record([{"name": "a", "type": "string"},
                      {"name": "b", "type": "int"}])
        changes = diff_avro(old, new, CompatMode.BACKWARD)
        assert any(c.rule_id == "AVRO-FIELD-ADDED-NO-DEFAULT"
                   and c.impact.structural == TierVerdict.FAIL for c in changes)

    def test_added_field_with_default_is_semantic_hazard(self):
        old = record([{"name": "a", "type": "string"}])
        new = record([{"name": "a", "type": "string"},
                      {"name": "b", "type": "int", "default": 0}])
        changes = diff_avro(old, new, CompatMode.BACKWARD)
        assert [c.rule_id for c in changes] == ["AVRO-FIELD-ADDED-DEFAULT"]
        assert changes[0].impact.semantic == TierVerdict.HAZARD
        assert changes[0].mitigation  # operational-directive wording present

    def test_int_to_long_promotion_ok_backward_not_forward(self):
        old = record([{"name": "a", "type": "int"}])
        new = record([{"name": "a", "type": "long"}])
        backward = diff_avro(old, new, CompatMode.BACKWARD)
        assert not any(c.impact.structural == TierVerdict.FAIL for c in backward)
        forward = diff_avro(old, new, CompatMode.FORWARD)
        assert any(c.rule_id == "AVRO-TYPE-INCOMPATIBLE" for c in forward)

    def test_full_mode_catches_both_directions(self):
        old = record([{"name": "a", "type": "int"}])
        new = record([{"name": "a", "type": "long"}])
        full = diff_avro(old, new, CompatMode.FULL)
        assert any(c.rule_id == "AVRO-TYPE-INCOMPATIBLE" for c in full)

    def test_named_type_registry_and_resolution(self):
        address = {"type": "record", "name": "Address",
                   "fields": [{"name": "city", "type": "string"}]}
        schema = record([{"name": "home", "type": address},
                         {"name": "work", "type": "Address"}])
        registry = build_named_type_registry(schema)
        assert "Address" in registry
        resolved = resolve_named_types(schema, registry)
        assert resolved["fields"][1]["type"]["type"] == "record"

    def test_named_type_reference_diff(self):
        """A change inside a named type referenced by string is detected."""
        address_v1 = {"type": "record", "name": "Address",
                      "fields": [{"name": "city", "type": "string"}]}
        address_v2 = {"type": "record", "name": "Address",
                      "fields": [{"name": "city", "type": "string"},
                                 {"name": "zip", "type": "string"}]}
        old = record([{"name": "home", "type": address_v1},
                      {"name": "work", "type": "Address"}])
        new = record([{"name": "home", "type": address_v2},
                      {"name": "work", "type": "Address"}])
        changes = diff_avro(old, new, CompatMode.BACKWARD)
        assert any(c.rule_id == "AVRO-FIELD-ADDED-NO-DEFAULT" for c in changes)

    def test_enum_symbol_removed(self):
        old = {"type": "enum", "name": "E", "symbols": ["A", "B"]}
        new = {"type": "enum", "name": "E", "symbols": ["A"]}
        changes = diff_avro(old, new, CompatMode.BACKWARD)
        assert any(c.rule_id == "AVRO-ENUM-SYMBOL-REMOVED" for c in changes)


def proto_schema(fields=None, services=None, enums=None, **msg_kw):
    messages = []
    if fields is not None:
        messages = [ProtobufMessage(name="M", fields=fields, **msg_kw)]
    return ProtobufSchema(syntax="proto3", messages=messages,
                          services=services or [], enums=enums or [])


class TestProtobufAdapter:
    def test_wire_group_membership(self):
        assert wire_compatible("int32", "uint64")   # varint group
        assert wire_compatible("string", "bytes")
        assert wire_compatible("fixed64", "sfixed64")
        assert not wire_compatible("int32", "sint32")
        assert not wire_compatible("int32", "string")

    def test_wire_compatible_type_change_is_hazard_not_fail(self):
        old = proto_schema([ProtobufField(name="a", number=1, type="int32")])
        new = proto_schema([ProtobufField(name="a", number=1, type="uint64")])
        changes = diff_protobuf(old, new)
        assert [c.rule_id for c in changes] == ["PROTO-FIELD-TYPE-WIRE-COMPATIBLE"]
        assert changes[0].impact.structural == TierVerdict.PASS
        assert changes[0].impact.semantic == TierVerdict.HAZARD

    def test_cross_group_type_change_fails(self):
        old = proto_schema([ProtobufField(name="a", number=1, type="int32")])
        new = proto_schema([ProtobufField(name="a", number=1, type="string")])
        changes = diff_protobuf(old, new)
        assert changes[0].rule_id == "PROTO-FIELD-TYPE-CHANGED"
        assert changes[0].impact.structural == TierVerdict.FAIL

    def test_field_rename_is_wire_pass_source_hazard(self):
        """RESEARCH_14: field rename => wire PASS + source/JSON HAZARD."""
        old = proto_schema([ProtobufField(name="a", number=1, type="int32")])
        new = proto_schema([ProtobufField(name="b", number=1, type="int32")])
        changes = diff_protobuf(old, new)
        renamed = [c for c in changes if c.rule_id == "PROTO-FIELD-RENAMED"]
        assert len(renamed) == 1
        assert renamed[0].impact.structural == TierVerdict.PASS
        assert renamed[0].impact.semantic == TierVerdict.HAZARD

    def test_field_removed_without_reservation_is_hazard(self):
        old = proto_schema([ProtobufField(name="a", number=1, type="int32")])
        new = proto_schema([])
        changes = diff_protobuf(old, new)
        assert changes[0].rule_id == "PROTO-FIELD-REMOVED-UNRESERVED"
        assert changes[0].impact.semantic == TierVerdict.FAIL

    def test_field_removed_with_reservation_is_mild_hazard(self):
        old = proto_schema([ProtobufField(name="a", number=1, type="int32")])
        new = proto_schema([], reserved_numbers=[1])
        changes = diff_protobuf(old, new)
        assert changes[0].rule_id == "PROTO-FIELD-REMOVED-RESERVED"
        assert changes[0].impact.semantic == TierVerdict.HAZARD

    def test_rpc_removed_is_routing_break(self):
        """RESEARCH_14: method rename == remove+add => routing FAIL."""
        old_service = ProtobufService(name="S", rpcs={
            "Get": {"input": "Req", "output": "Res",
                    "input_stream": "false", "output_stream": "false"}})
        new_service = ProtobufService(name="S", rpcs={
            "Fetch": {"input": "Req", "output": "Res",
                      "input_stream": "false", "output_stream": "false"}})
        changes = diff_protobuf(proto_schema(services=[old_service]),
                                proto_schema(services=[new_service]))
        rpc = [c for c in changes if c.rule_id == "PROTO-RPC-REMOVED"]
        assert len(rpc) == 1
        assert rpc[0].abstract_violation == AbstractViolation.ROUTING_BREAK
        assert rpc[0].impact.structural == TierVerdict.FAIL

    def test_unary_to_server_streaming_fails(self):
        old_service = ProtobufService(name="S", rpcs={
            "Get": {"input": "Req", "output": "Res",
                    "input_stream": "false", "output_stream": "false"}})
        new_service = ProtobufService(name="S", rpcs={
            "Get": {"input": "Req", "output": "Res",
                    "input_stream": "false", "output_stream": "true"}})
        changes = diff_protobuf(proto_schema(services=[old_service]),
                                proto_schema(services=[new_service]))
        assert [c.rule_id for c in changes] == ["PROTO-RPC-STREAMING-CHANGED"]
        assert changes[0].abstract_violation == AbstractViolation.ROUTING_BREAK

    def test_enum_value_number_change_fails(self):
        old = proto_schema(enums=[ProtobufEnum(name="E", values={"A": 0, "B": 1})])
        new = proto_schema(enums=[ProtobufEnum(name="E", values={"A": 0, "B": 2})])
        changes = diff_protobuf(old, new)
        assert any(c.rule_id == "PROTO-ENUM-VALUE-NUMBER-CHANGED" for c in changes)
