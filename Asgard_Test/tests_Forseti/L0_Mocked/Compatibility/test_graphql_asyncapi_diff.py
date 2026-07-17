"""GraphQL and AsyncAPI diff services (plan 01 phase 3 — new capability)."""

from Asgard.Forseti.AsyncAPI.services.asyncapi_diff_service import AsyncAPIDiffService
from Asgard.Forseti.Compatibility.models._compat_base_models import (
    AbstractViolation,
    Direction,
    TierVerdict,
)
from Asgard.Forseti.GraphQL.services.schema_diff_service import GraphQLSchemaDiffService

OLD_SDL = """
type Query {
  user(id: ID!): User
  users(limit: Int): [User]
}

type User {
  id: ID!
  name: String
  email: String
}

enum Role {
  ADMIN
  USER
}

input UserInput {
  name: String
}

union SearchResult = User
"""


class TestGraphQLDiff:
    def setup_method(self):
        self.service = GraphQLSchemaDiffService()

    def test_identical_schemas_no_changes(self):
        assert self.service.diff_sdl(OLD_SDL, OLD_SDL) == []

    def test_field_removed_is_input_contravariance_break(self):
        new = OLD_SDL.replace("  email: String\n", "")
        changes = self.service.diff_sdl(OLD_SDL, new)
        removed = [c for c in changes if c.rule_id == "GQL-FIELD-REMOVED"]
        assert len(removed) == 1
        assert removed[0].location == "User.email"
        assert removed[0].direction == Direction.INPUT
        assert removed[0].abstract_violation == \
            AbstractViolation.INPUT_CONTRAVARIANCE_VIOLATION
        assert removed[0].impact.structural == TierVerdict.FAIL

    def test_type_removed(self):
        new = OLD_SDL.replace("enum Role {\n  ADMIN\n  USER\n}\n", "")
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert any(c.rule_id == "GQL-TYPE-REMOVED" and c.location == "Role"
                   for c in changes)

    def test_enum_value_removed_fails_added_is_hazard(self):
        new = OLD_SDL.replace("  ADMIN\n  USER\n", "  USER\n  GUEST\n")
        changes = self.service.diff_sdl(OLD_SDL, new)
        rule_ids = {c.rule_id for c in changes}
        assert "GQL-ENUM-VALUE-REMOVED" in rule_ids
        assert "GQL-ENUM-VALUE-ADDED" in rule_ids
        added = next(c for c in changes if c.rule_id == "GQL-ENUM-VALUE-ADDED")
        assert added.impact.structural == TierVerdict.PASS

    def test_field_type_changed(self):
        new = OLD_SDL.replace("name: String", "name: Int")
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert any(c.rule_id == "GQL-FIELD-TYPE-CHANGED" for c in changes)

    def test_argument_removed(self):
        new = OLD_SDL.replace("users(limit: Int)", "users")
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert any(c.rule_id == "GQL-ARG-REMOVED"
                   and "limit" in c.location for c in changes)

    def test_required_argument_added(self):
        new = OLD_SDL.replace("users(limit: Int)", "users(limit: Int, tenant: ID!)")
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert any(c.rule_id == "GQL-ARG-REQUIRED-ADDED" for c in changes)

    def test_defaulted_required_argument_is_not_a_break(self):
        new = OLD_SDL.replace("users(limit: Int)", 'users(limit: Int, max: Int! = 10)')
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert not any(c.rule_id == "GQL-ARG-REQUIRED-ADDED" for c in changes)

    def test_required_input_field_added(self):
        new = OLD_SDL.replace("input UserInput {\n  name: String\n}",
                              "input UserInput {\n  name: String\n  org: ID!\n}")
        changes = self.service.diff_sdl(OLD_SDL, new)
        assert any(c.rule_id == "GQL-INPUT-FIELD-REQUIRED-ADDED" for c in changes)

    def test_union_member_removed(self):
        old = OLD_SDL.replace("union SearchResult = User",
                              "union SearchResult = User | Query")
        changes = self.service.diff_sdl(old, OLD_SDL)
        assert any(c.rule_id == "GQL-UNION-MEMBER-REMOVED" for c in changes)


def asyncapi_spec():
    return {
        "asyncapi": "2.6.0",
        "channels": {
            "user/created": {
                "publish": {"message": {"payload": {
                    "type": "object",
                    "properties": {"id": {"type": "string"},
                                   "email": {"type": "string"}},
                }}},
            },
            "user/commands": {
                "subscribe": {"message": {"payload": {
                    "type": "object",
                    "properties": {"action": {"type": "string"}},
                }}},
            },
        },
    }


class TestAsyncAPIDiff:
    def setup_method(self):
        self.service = AsyncAPIDiffService()

    def test_identical_specs_no_changes(self):
        spec = asyncapi_spec()
        assert self.service.diff_specs(spec, asyncapi_spec()) == []

    def test_channel_removed_is_routing_break(self):
        old = asyncapi_spec()
        new = asyncapi_spec()
        del new["channels"]["user/created"]
        changes = self.service.diff_specs(old, new)
        assert [c.rule_id for c in changes] == ["ASYNC-CHANNEL-REMOVED"]
        assert changes[0].abstract_violation == AbstractViolation.ROUTING_BREAK

    def test_publish_payload_field_removed_is_output_violation(self):
        old = asyncapi_spec()
        new = asyncapi_spec()
        del new["channels"]["user/created"]["publish"]["message"]["payload"][
            "properties"]["email"]
        changes = self.service.diff_specs(old, new)
        assert len(changes) == 1
        assert changes[0].rule_id == "ASYNC-MSG-FIELD-REMOVED"
        assert changes[0].direction == Direction.OUTPUT

    def test_subscribe_required_added_is_input_violation(self):
        old = asyncapi_spec()
        new = asyncapi_spec()
        new["channels"]["user/commands"]["subscribe"]["message"]["payload"][
            "required"] = ["action"]
        changes = self.service.diff_specs(old, new)
        assert any(c.rule_id == "ASYNC-MSG-FIELD-REQUIRED-ADDED"
                   and c.direction == Direction.INPUT for c in changes)

    def test_operation_removed(self):
        old = asyncapi_spec()
        new = asyncapi_spec()
        del new["channels"]["user/created"]["publish"]
        changes = self.service.diff_specs(old, new)
        assert any(c.rule_id == "ASYNC-OPERATION-REMOVED" for c in changes)

    def test_message_ref_resolution(self):
        old = asyncapi_spec()
        new = {
            "asyncapi": "2.6.0",
            "channels": {"user/created": {"publish": {"message": {
                "$ref": "#/components/messages/UserCreated"}}},
                "user/commands": old["channels"]["user/commands"]},
            "components": {"messages": {"UserCreated": {"payload": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }}}},
        }
        changes = self.service.diff_specs(old, new)
        assert any(c.rule_id == "ASYNC-MSG-FIELD-REMOVED"
                   and "email" in c.location for c in changes)
