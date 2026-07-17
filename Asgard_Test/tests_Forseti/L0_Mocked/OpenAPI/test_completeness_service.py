"""
Tests for the OpenAPI completeness service (plan 03): 4-vector matrix,
gated maturity tiers, tier demotion, and dx/secops profiles.
"""

import copy

import pytest

from Asgard.Forseti.OpenAPI.models.completeness_models import MaturityTier
from Asgard.Forseti.OpenAPI.services.completeness_service import CompletenessService


def _op(description: str, extra_responses: dict | None = None, **kwargs) -> dict:
    responses = {
        "200": {"description": "The requested resource, fully populated"},
        "400": {"description": "Request was malformed or failed validation",
                "content": {"application/problem+json": {"schema": {
                    "$ref": "#/components/schemas/Problem"}}}},
        "500": {"description": "Unexpected internal failure; retry later",
                "content": {"application/problem+json": {"schema": {
                    "$ref": "#/components/schemas/Problem"}}},
                "headers": {"Retry-After": {"schema": {"type": "integer"}}}},
    }
    responses.update(extra_responses or {})
    operation = {"description": description, "responses": responses}
    operation.update(kwargs)
    return operation


def comprehensive_spec() -> dict:
    """A spec engineered to hit the COMPREHENSIVE tier."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Payments", "version": "2.1.0"},
        "security": [{"bearer": []}],
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "Problem": {
                    "type": "object",
                    "description": "RFC 7807 problem document for all errors",
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string", "format": "uri",
                                 "description": "URI identifying the problem class"},
                        "title": {"type": "string", "maxLength": 200,
                                  "description": "Short human-readable summary line"},
                        "status": {"type": "integer", "minimum": 100,
                                   "maximum": 599,
                                   "description": "HTTP status code for this occurrence"},
                    },
                    "example": {"type": "https://errors.example.com/invalid",
                                "title": "Request failed validation",
                                "status": 400},
                },
                "Payment": {
                    "type": "object",
                    "description": "A single settled or pending payment record",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string", "format": "uuid",
                               "description": "Server-assigned opaque payment identifier"},
                        "amountMinor": {"type": "integer", "minimum": 0,
                                        "description": "Amount in minor currency units (cents)"},
                    },
                    "example": {"id": "3d5a0e5e-0000-4000-8000-000000000000",
                                "amountMinor": 1250},
                },
            },
        },
        "paths": {
            "/payments": {"get": _op(
                "List payments visible to the caller, most recent first",
                parameters=[{
                    "name": "limit", "in": "query",
                    "description": "Maximum number of records returned per page",
                    "schema": {"type": "integer", "minimum": 1, "maximum": 100},
                }],
                extra_responses={"200": {
                    "description": "One page of payment records for the caller",
                    "content": {"application/json": {"schema": {
                        "type": "array", "maxItems": 100,
                        "items": {"$ref": "#/components/schemas/Payment"},
                    }}},
                }, "429": {"description": "Rate limit exceeded; consult Retry-After"}},
            )},
        },
    }


class TestTierAssignment:
    def test_comprehensive_fixture(self):
        report = CompletenessService().assess_spec_data(comprehensive_spec())
        assert report.tier == MaturityTier.COMPREHENSIVE
        assert report.missing_for_next_tier == []

    def test_empty_spec_is_none_tier(self):
        report = CompletenessService().assess_spec_data({
            "openapi": "3.0.0", "info": {"title": "T", "version": "1"},
            "paths": {"/a": {"get": {"responses": {"200": {"description": "x"}}}}},
        })
        assert report.tier == MaturityTier.NONE
        assert report.missing_for_next_tier  # actionable path shown

    @pytest.mark.parametrize("mutate,floor", [
        # break a BASIC gate -> tier collapses to NONE
        (lambda s: s["components"].pop("securitySchemes"), MaturityTier.NONE),
        # break structural (broken ref) -> NONE
        (lambda s: s["paths"].update({"/x": {"get": {"responses": {"200": {
            "description": "ok", "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/Nope"}}}}}}}}),
         MaturityTier.NONE),
        # break a STANDARD gate (invalid example) -> at most BASIC
        (lambda s: s["components"]["schemas"]["Payment"].update(
            {"example": {"id": 42, "amountMinor": "x"}}), MaturityTier.BASIC),
        # break a COMPREHENSIVE gate (unbounded string) -> at most STANDARD
        (lambda s: [s["components"]["schemas"]["Payment"]["properties"].update(
            {f"note{i}": {"type": "string",
                          "description": "Free-form annotation supplied by the operator"}}
        ) for i in range(3)], MaturityTier.STANDARD),
    ])
    def test_single_gate_mutation_demotes_tier(self, mutate, floor):
        spec = copy.deepcopy(comprehensive_spec())
        mutate(spec)
        report = CompletenessService().assess_spec_data(spec)
        assert report.tier == floor

    def test_gates_are_lowest_common_denominator(self):
        """Failing BASIC can never yield STANDARD, however good other vectors."""
        spec = copy.deepcopy(comprehensive_spec())
        del spec["components"]["securitySchemes"]
        spec.pop("security")
        report = CompletenessService().assess_spec_data(spec)
        assert report.tier == MaturityTier.NONE


class TestVectorsAndProfiles:
    def test_vectors_in_range(self):
        report = CompletenessService().assess_spec_data(comprehensive_spec())
        for value in (report.vector.experiential, report.vector.precision,
                      report.vector.operational, report.vector.structural):
            assert 0.0 <= value <= 1.0
        assert report.vector.structural == 1.0
        assert report.vector.precision > 0.9

    def test_secops_ignores_experiential(self):
        spec = copy.deepcopy(comprehensive_spec())
        # strip all descriptions: dx tier collapses, secops does not care
        spec["paths"]["/payments"]["get"].pop("description")
        for schema in spec["components"]["schemas"].values():
            schema.pop("description", None)
            for prop in schema.get("properties", {}).values():
                prop.pop("description", None)
        service = CompletenessService()
        dx = service.assess_spec_data(spec, profile="dx")
        secops = service.assess_spec_data(spec, profile="secops")
        assert dx.tier == MaturityTier.NONE
        assert secops.tier.rank >= MaturityTier.BASIC.rank

    def test_unknown_profile_rejected(self):
        with pytest.raises(ValueError):
            CompletenessService().assess_spec_data(comprehensive_spec(),
                                                   profile="bogus")

    def test_meets_tier_and_reports(self):
        service = CompletenessService()
        report = service.assess_spec_data(comprehensive_spec())
        assert service.meets_tier(report, MaturityTier.STANDARD)
        text = service.generate_report(report, "text")
        assert "COMPREHENSIVE" in text
        as_json = service.generate_report(report, "json")
        assert '"tier"' in as_json
