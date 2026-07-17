"""
Official JSON-Schema-Test-Suite parity tests.

Runs a vendored, curated subset of the official test suite (draft-07 and
2020-12) against the compiled validation engine and asserts pass/fail parity.
Fixtures: Asgard_Test/tests_Forseti/fixtures/jsonschema_suite/.
"""

import json
from pathlib import Path

import pytest

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig
from Asgard.Forseti.JSONSchema.services.schema_compiler_service import SchemaCompilerService

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "jsonschema_suite"


def _load_cases(filename: str, dialect: str):
    cases = []
    for group in json.loads((FIXTURES / filename).read_text(encoding="utf-8")):
        for test in group["tests"]:
            cases.append(pytest.param(
                group["schema"], test["data"], test["valid"], dialect,
                id=f"{dialect}::{group['description']}::{test['description']}",
            ))
    return cases


DRAFT7_CASES = _load_cases("draft7.json", "draft-07")
DRAFT2020_CASES = _load_cases("draft2020.json", "2020-12")


def _compiler():
    # Suite semantics: format is annotation-only; additionalProperties always
    # enforced (strict_mode maps to spec behavior).
    return SchemaCompilerService(JSONSchemaConfig(strict_mode=True, check_formats=False))


class TestDraft7SuiteParity:
    @pytest.mark.parametrize("schema,data,expected_valid,dialect", DRAFT7_CASES)
    def test_case(self, schema, data, expected_valid, dialect):
        compiled = _compiler().compile(schema, dialect=dialect)
        errors = compiled.validate(data)
        assert (not errors) is expected_valid, (
            f"expected valid={expected_valid}, errors={[e.message for e in errors]}"
        )


class TestDraft2020SuiteParity:
    @pytest.mark.parametrize("schema,data,expected_valid,dialect", DRAFT2020_CASES)
    def test_case(self, schema, data, expected_valid, dialect):
        compiled = _compiler().compile(schema, dialect=dialect)
        errors = compiled.validate(data)
        assert (not errors) is expected_valid, (
            f"expected valid={expected_valid}, errors={[e.message for e in errors]}"
        )


def test_suite_size_floor():
    """The vendored subset should stay reasonably broad."""
    assert len(DRAFT7_CASES) + len(DRAFT2020_CASES) >= 250
