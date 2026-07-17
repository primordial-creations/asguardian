"""
Tests for the expanded OpenAPI lint ruleset (plan 03): structure, docs,
style, semantics, security (OWASP), examples and lifecycle rules.
"""

import pytest

from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.services.rule_registry_service import get_default_registry


def run_rule(rule_id: str, document: dict) -> list:
    rule = get_default_registry().get(rule_id)
    assert rule is not None, f"rule {rule_id} not registered"
    assert rule.executable, f"rule {rule_id} has no check function"
    return rule.check(document)


def minimal_spec(**overrides) -> dict:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0.0"},
        "paths": {},
    }
    spec.update(overrides)
    return spec


class TestRegistryDiscipline:
    def test_openapi_rule_count_meets_spectral_parity(self):
        rules = get_default_registry().query(fmt=SchemaFormat.OPENAPI)
        assert len(rules) >= 60

    def test_heuristic_rules_never_error(self):
        for rule in get_default_registry().all_rules():
            if rule.meta.confidence == Confidence.HEURISTIC:
                assert rule.meta.severity != Severity.ERROR, rule.meta.rule_id

    def test_security_rules_all_registered(self):
        expected = {
            "sec.auth.scheme-defined", "sec.auth.no-http-basic",
            "sec.auth.no-apikey-in-query", "sec.transport.https-only",
            "sec.bopla.additional-properties", "sec.dos.bounded-strings",
            "sec.dos.bounded-arrays", "sec.dos.bounded-integers",
            "sec.dos.pagination-required", "sec.bola.uuid-ids",
            "sec.info.no-verbose-errors",
        }
        registered = {
            r.meta.rule_id for r in get_default_registry().query(
                fmt=SchemaFormat.OPENAPI, category=RuleCategory.SECURITY
            )
        }
        assert expected <= registered

    def test_clean_spec_produces_no_error_findings(self):
        spec = minimal_spec(paths={
            "/things": {"get": {"responses": {"200": {"description": "ok"}}}},
        })
        for rule in get_default_registry().query(fmt=SchemaFormat.OPENAPI):
            if not rule.executable:
                continue
            for finding in rule.check(spec):
                assert finding.severity != Severity.ERROR, (
                    f"{finding.rule_id}: {finding.message}"
                )


class TestStructureRules:
    def test_broken_ref_detected(self):
        spec = minimal_spec(paths={"/a": {"get": {"responses": {"200": {
            "description": "ok",
            "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/Missing"},
            }},
        }}}}})
        findings = run_rule("oas.structure.no-broken-refs", spec)
        assert len(findings) == 1
        assert "Missing" in findings[0].message

    def test_valid_ref_not_flagged_and_cycle_safe(self):
        spec = minimal_spec(components={"schemas": {
            "A": {"$ref": "#/components/schemas/B"},
            "B": {"$ref": "#/components/schemas/A"},
        }})
        assert run_rule("oas.structure.no-broken-refs", spec) == []

    def test_duplicate_operation_id(self):
        op = {"operationId": "dup", "responses": {"200": {"description": "ok"}}}
        spec = minimal_spec(paths={"/a": {"get": dict(op)}, "/b": {"get": dict(op)}})
        findings = run_rule("oas.structure.operation-id-unique", spec)
        assert len(findings) == 1

    def test_duplicate_parameters(self):
        spec = minimal_spec(paths={"/a": {"get": {
            "parameters": [
                {"name": "q", "in": "query"},
                {"name": "q", "in": "query"},
            ],
            "responses": {"200": {"description": "ok"}},
        }}})
        assert len(run_rule("oas.structure.no-duplicate-parameters", spec)) == 1

    def test_equivalent_paths(self):
        spec = minimal_spec(paths={
            "/users/{id}": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/users/{userId}": {"get": {"responses": {"200": {"description": "ok"}}}},
        })
        assert len(run_rule("oas.structure.no-equivalent-paths", spec)) == 1

    def test_invalid_status_code(self):
        spec = minimal_spec(paths={"/a": {"get": {"responses": {
            "0200": {"description": "bad"},
            "2XX": {"description": "range ok"},
            "default": {"description": "ok"},
        }}}})
        findings = run_rule("oas.structure.valid-status-codes", spec)
        assert len(findings) == 1
        assert "0200" in findings[0].message

    def test_unused_component_reported_as_info(self):
        spec = minimal_spec(components={"schemas": {"Orphan": {"type": "object"}}})
        findings = run_rule("oas.structure.no-unused-components", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.INFO


class TestDescriptionEntropy:
    @pytest.mark.parametrize("name,description,expected_ok", [
        ("billingAddress", "The billing address", False),          # tautology
        ("billingAddress",
         "Postal address used on invoices; ISO country code required", True),
        ("status", "TODO", False),                                  # stop word
        ("status", "TBD", False),
        ("count", "n/a", False),
        ("count", "short", False),                                  # too short
        ("userEmail",
         "Primary contact address; must be verified before login", True),
    ])
    def test_description_quality_table(self, name, description, expected_ok):
        from Asgard.Forseti.OpenAPI.rules import description_quality
        ok, _reason = description_quality(name, description)
        assert ok is expected_ok

    def test_entropy_rule_flags_tautology(self):
        spec = minimal_spec(components={"schemas": {"Invoice": {
            "type": "object",
            "properties": {"billingAddress": {
                "type": "string", "description": "The billing address",
            }},
        }}})
        findings = run_rule("oas.docs.non-trivial-description", spec)
        assert len(findings) == 1
        assert "tautology" in findings[0].message


class TestSemanticsRules:
    def test_get_with_body_flagged(self):
        spec = minimal_spec(paths={"/a": {"get": {
            "requestBody": {"content": {"application/json": {"schema": {}}}},
            "responses": {"200": {"description": "ok"}},
        }}})
        assert len(run_rule("oas.semantics.get-no-request-body", spec)) == 1

    def test_204_with_content_flagged(self):
        spec = minimal_spec(paths={"/a": {"delete": {"responses": {"204": {
            "description": "gone",
            "content": {"application/json": {"schema": {}}},
        }}}}})
        assert len(run_rule("oas.semantics.204-no-content-body", spec)) == 1

    def test_financial_float_hint(self):
        spec = minimal_spec(components={"schemas": {"Order": {
            "type": "object",
            "properties": {"totalPrice": {"type": "number"}},
        }}})
        findings = run_rule("oas.semantics.financial-float", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HINT

    def test_enum_type_mismatch_is_error(self):
        spec = minimal_spec(components={"schemas": {"S": {
            "type": "integer", "enum": [1, "two", 3],
        }}})
        findings = run_rule("oas.semantics.enum-values-match-type", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.ERROR

    def test_cross_schema_type_divergence(self):
        spec = minimal_spec(components={"schemas": {
            "A": {"type": "object", "properties": {"age": {"type": "integer"}}},
            "B": {"type": "object", "properties": {"age": {"type": "string"}}},
        }})
        assert len(run_rule("oas.semantics.cross-schema-type-consistency", spec)) == 1


VULNERABLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Vulnerable", "version": "1.0.0"},
    "servers": [{"url": "http://api.example.com"}],
    "components": {"securitySchemes": {
        "basic": {"type": "http", "scheme": "basic"},
        "key": {"type": "apiKey", "in": "query", "name": "api_key"},
    }},
    "paths": {
        "/items/{itemId}": {"get": {
            "parameters": [{"name": "itemId", "in": "path", "required": True,
                            "schema": {"type": "integer"}}],
            "responses": {
                "200": {"description": "ok"},
                "500": {"description": "err", "content": {"application/json": {
                    "schema": {"type": "object", "properties": {
                        "stacktrace": {"type": "string"},
                    }},
                }}},
            },
        }},
        "/items": {
            "get": {"responses": {"200": {
                "description": "ok",
                "content": {"application/json": {"schema": {
                    "type": "array", "items": {"type": "string"},
                }}},
            }}},
            "post": {
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string",
                                                            "maxLength": 10}},
                        "quantity": {"type": "integer"},
                    },
                }}}},
                "responses": {"201": {"description": "created"}},
            },
        },
    },
}


class TestSecurityRules:
    """The intentionally-vulnerable fixture must trip every rule id."""

    @pytest.mark.parametrize("rule_id", [
        "sec.auth.scheme-defined",        # operations not covered
        "sec.auth.no-http-basic",
        "sec.auth.no-apikey-in-query",
        "sec.transport.https-only",
        "sec.bopla.additional-properties",
        "sec.dos.bounded-strings",
        "sec.dos.bounded-arrays",
        "sec.dos.bounded-integers",
        "sec.dos.pagination-required",
        "sec.bola.uuid-ids",
        "sec.info.no-verbose-errors",
    ])
    def test_vulnerable_fixture_trips_rule(self, rule_id):
        findings = run_rule(rule_id, VULNERABLE_SPEC)
        assert findings, f"{rule_id} produced no findings"
        for finding in findings:
            assert finding.severity != Severity.ERROR  # gate-friendly set

    def test_https_localhost_exempt(self):
        spec = minimal_spec(servers=[{"url": "http://localhost:8080"}])
        assert run_rule("sec.transport.https-only", spec) == []

    def test_secured_spec_clean(self):
        spec = minimal_spec(
            servers=[{"url": "https://api.example.com"}],
            security=[{"bearer": []}],
            components={"securitySchemes": {
                "bearer": {"type": "http", "scheme": "bearer"},
            }},
            paths={"/a": {"get": {"responses": {"200": {"description": "ok"}}}}},
        )
        for rule_id in ("sec.auth.scheme-defined", "sec.auth.no-http-basic",
                        "sec.transport.https-only"):
            assert run_rule(rule_id, spec) == []


class TestExampleRules:
    def test_invalid_example_flagged(self):
        spec = minimal_spec(components={"schemas": {"User": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}},
            "example": {"id": "not-an-int"},
        }}})
        findings = run_rule("oas.examples.example-matches-schema", spec)
        assert findings
        assert findings[0].severity == Severity.WARNING

    def test_valid_example_passes(self):
        spec = minimal_spec(components={"schemas": {"User": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "example": {"id": 7},
        }}})
        assert run_rule("oas.examples.example-matches-schema", spec) == []

    def test_example_with_ref_resolution(self):
        spec = minimal_spec(
            paths={"/u": {"get": {"responses": {"200": {
                "description": "ok",
                "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/User"},
                    "example": {"id": "wrong"},
                }},
            }}}}},
            components={"schemas": {"User": {
                "type": "object", "properties": {"id": {"type": "integer"}},
            }}},
        )
        assert run_rule("oas.examples.example-matches-schema", spec)

    def test_nullable_shim_for_30(self):
        spec = minimal_spec(components={"schemas": {"S": {
            "type": "object",
            "properties": {"note": {"type": "string", "nullable": True}},
            "example": {"note": None},
        }}})
        assert run_rule("oas.examples.example-matches-schema", spec) == []


class TestLifecycleRules:
    def test_deprecated_needs_sunset(self):
        spec = minimal_spec(paths={"/old": {"get": {
            "deprecated": True,
            "responses": {"200": {"description": "ok"}},
        }}})
        findings = run_rule("oas.lifecycle.deprecated-needs-sunset", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING

    def test_sunset_passed_is_warning_not_error(self):
        spec = minimal_spec(paths={"/old": {"get": {
            "deprecated": True,
            "x-sunset-date": "2000-01-01",
            "x-replaced-by": "/new",
            "responses": {"200": {"description": "ok"}},
        }}})
        findings = run_rule("oas.lifecycle.sunset-passed", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING
        assert run_rule("oas.lifecycle.deprecated-needs-sunset", spec) == []
        assert run_rule("oas.lifecycle.replacement-missing", spec) == []

    def test_replacement_missing_is_info(self):
        spec = minimal_spec(paths={"/old": {"get": {
            "deprecated": True,
            "x-sunset-date": "2099-01-01",
            "responses": {"200": {"description": "ok"}},
        }}})
        findings = run_rule("oas.lifecycle.replacement-missing", spec)
        assert len(findings) == 1
        assert findings[0].severity == Severity.INFO
