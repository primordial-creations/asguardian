"""Golden tests for the directional split (DEEPTHINK_01)."""

import copy

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction, TierVerdict
from Asgard.Forseti.Compatibility.services._openapi_adapter import (
    build_reverse_ref_index,
    diff_openapi,
)


def base_spec():
    return {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "parameters": [{"name": "limit", "in": "query",
                                    "schema": {"type": "integer"}}],
                    "responses": {"200": {"content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/User"}}}}},
                },
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string",
                                     "enum": ["admin", "user"]},
                        },
                    }}}},
                    "responses": {"201": {}},
                },
            },
        },
        "components": {"schemas": {"User": {
            "type": "object",
            "properties": {"id": {"type": "string"},
                           "email": {"type": "string"}},
            "required": ["id"],
        }}},
    }


class TestDirectionalSplit:
    def test_field_removed_in_response_fails(self):
        old = base_spec()
        new = copy.deepcopy(old)
        del new["components"]["schemas"]["User"]["properties"]["email"]
        changes = diff_openapi(old, new)
        removed = [c for c in changes if c.rule_id == "OAS-RES-FIELD-REMOVED"]
        assert removed
        assert all(c.direction == Direction.OUTPUT for c in removed)
        assert all(c.impact.structural == TierVerdict.FAIL for c in removed)

    def test_optional_field_removed_in_request_is_note_not_fail(self):
        """The same removal must FAIL in a response but pass-with-note in a request."""
        old = base_spec()
        new = copy.deepcopy(old)
        del new["paths"]["/users"]["post"]["requestBody"]["content"][
            "application/json"]["schema"]["properties"]["name"]
        changes = diff_openapi(old, new)
        req = [c for c in changes if c.rule_id == "OAS-REQ-FIELD-REMOVED"]
        assert len(req) == 1
        assert req[0].direction == Direction.INPUT
        assert req[0].impact.structural == TierVerdict.PASS
        assert req[0].impact.semantic == TierVerdict.HAZARD
        assert not any(c.rule_id == "OAS-RES-FIELD-REMOVED" for c in changes)

    def test_required_added_to_request_fails(self):
        old = base_spec()
        new = copy.deepcopy(old)
        new["paths"]["/users"]["post"]["requestBody"]["content"][
            "application/json"]["schema"]["required"] = ["role"]
        changes = diff_openapi(old, new)
        assert any(c.rule_id == "OAS-REQ-FIELD-REQUIRED-ADDED"
                   and c.direction == Direction.INPUT for c in changes)

    def test_request_enum_narrowed_fails_response_enum_extended_hazard(self):
        old = base_spec()
        new = copy.deepcopy(old)
        new["paths"]["/users"]["post"]["requestBody"]["content"][
            "application/json"]["schema"]["properties"]["role"]["enum"] = ["user"]
        changes = diff_openapi(old, new)
        narrowed = [c for c in changes if c.rule_id == "OAS-REQ-ENUM-NARROWED"]
        assert len(narrowed) == 1
        assert narrowed[0].old_value == "admin"

    def test_path_and_method_removed_are_routing_breaks(self):
        old = base_spec()
        new = copy.deepcopy(old)
        del new["paths"]["/users"]["post"]
        changes = diff_openapi(old, new)
        assert any(c.rule_id == "OAS-METHOD-REMOVED" for c in changes)
        new2 = copy.deepcopy(old)
        new2["paths"] = {}
        changes2 = diff_openapi(old, new2)
        assert any(c.rule_id == "OAS-PATH-REMOVED" for c in changes2)

    def test_required_parameter_added_fails(self):
        old = base_spec()
        new = copy.deepcopy(old)
        new["paths"]["/users"]["get"]["parameters"].append(
            {"name": "tenant", "in": "header", "required": True})
        changes = diff_openapi(old, new)
        assert any(c.rule_id == "OAS-PARAM-REQUIRED-ADDED" for c in changes)

    def test_identical_specs_produce_no_changes(self):
        old = base_spec()
        assert diff_openapi(old, copy.deepcopy(old)) == []


class TestBlastRadius:
    def test_reverse_ref_index_counts_operations(self):
        spec = base_spec()
        index = build_reverse_ref_index(spec)
        assert index["#/components/schemas/User"] == {"/users/get"}

    def test_schema_removed_blast_radius(self):
        old = base_spec()
        new = copy.deepcopy(old)
        del new["components"]["schemas"]["User"]
        # keep the response ref dangling: schema removal is the change under test
        changes = diff_openapi(old, new)
        removed = [c for c in changes if c.rule_id == "OAS-SCHEMA-REMOVED"]
        assert len(removed) == 1
        assert removed[0].blast_radius == 1
