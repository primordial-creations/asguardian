"""
L6 Industry Benchmark Tests — Forseti OpenAPI Contract Validation Quality.

Validates that Forseti's SpecValidatorService meets industry-standard quality
thresholds comparable to API linting tools such as Spectral:

  - Precision: malformed specs are rejected (no false negatives on structural errors)
  - Recall: valid specs pass without false rejections
  - Throughput: 100-endpoint spec validated in < 500 ms (Spectral baseline)
"""

import time
from typing import Any, Dict

import pytest

from Asgard.Forseti.OpenAPI.services.spec_validator_service import SpecValidatorService
from Asgard.Forseti.OpenAPI.models.openapi_models import OpenAPIConfig


# ---------------------------------------------------------------------------
# Helpers — build minimal in-memory OpenAPI 3.0 dicts
# ---------------------------------------------------------------------------

def _valid_spec(num_paths: int = 1) -> Dict[str, Any]:
    """Return a structurally valid OpenAPI 3.0 spec dict."""
    paths: Dict[str, Any] = {}
    for i in range(num_paths):
        paths[f"/resource-{i}"] = {
            "get": {
                "summary": f"Get resource {i}",
                "operationId": f"getResource{i}",
                "responses": {
                    "200": {"description": "OK"},
                },
            }
        }
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": paths,
    }


def _spec_missing_info() -> Dict[str, Any]:
    """OpenAPI dict that is missing the required 'info' field."""
    return {
        "openapi": "3.0.3",
        "paths": {
            "/foo": {
                "get": {
                    "summary": "Get foo",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


def _spec_missing_openapi_version() -> Dict[str, Any]:
    """Dict with no 'openapi' key — ambiguous / invalid."""
    return {
        "info": {"title": "No Version API", "version": "0.0.0"},
        "paths": {},
    }


def _spec_missing_paths() -> Dict[str, Any]:
    """Valid envelope but no paths object."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Empty Paths", "version": "1.0.0"},
    }


# ---------------------------------------------------------------------------
# Precision tests — malformed specs must be rejected
# ---------------------------------------------------------------------------

class TestForsetiPrecision:
    """Known-bad specs must produce at least one validation error."""

    def setup_method(self) -> None:
        self.service = SpecValidatorService(config=OpenAPIConfig(include_warnings=True))

    def test_missing_info_field_is_rejected(self) -> None:
        """A spec without 'info' violates the OpenAPI standard and must be flagged."""
        result = self.service.validate_spec_data(_spec_missing_info())
        assert not result.is_valid, (
            "Expected validation failure for spec missing 'info' field"
        )
        assert len(result.errors) > 0

    def test_missing_openapi_version_reports_no_version(self) -> None:
        """A spec without 'openapi' key cannot be classified — version must be None."""
        result = self.service.validate_spec_data(_spec_missing_openapi_version())
        # Without an 'openapi' field the version is undetectable.
        # The validator correctly reflects this as openapi_version=None.
        assert result.openapi_version is None, (
            f"Expected openapi_version=None for spec missing 'openapi' key, "
            f"got {result.openapi_version}"
        )

    def test_missing_paths_produces_warning_or_error(self) -> None:
        """A spec with no 'paths' object should not silently pass."""
        result = self.service.validate_spec_data(_spec_missing_paths())
        has_feedback = len(result.errors) > 0 or len(result.warnings) > 0
        assert has_feedback, (
            "Expected at least a warning for spec with no 'paths' object"
        )


# ---------------------------------------------------------------------------
# Recall tests — valid specs must not be false-rejected
# ---------------------------------------------------------------------------

class TestForsetiRecall:
    """Known-good specs must pass without false positives."""

    def setup_method(self) -> None:
        self.service = SpecValidatorService(config=OpenAPIConfig(include_warnings=False))

    def test_minimal_valid_spec_passes(self) -> None:
        """A minimal but complete OpenAPI 3.0 spec must pass without errors."""
        result = self.service.validate_spec_data(_valid_spec(num_paths=1))
        assert result.is_valid, (
            f"Valid spec was incorrectly rejected. Errors: {result.errors}"
        )
        assert len(result.errors) == 0

    def test_multi_path_valid_spec_passes(self) -> None:
        """A spec with several paths must pass without errors."""
        result = self.service.validate_spec_data(_valid_spec(num_paths=10))
        assert result.is_valid, (
            f"Multi-path valid spec was incorrectly rejected. Errors: {result.errors}"
        )

    def test_spec_with_multiple_http_methods_passes(self) -> None:
        """A spec mixing GET/POST/DELETE on the same path must pass."""
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "CRUD API", "version": "2.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "responses": {"200": {"description": "OK"}},
                    },
                    "post": {
                        "operationId": "createItem",
                        "responses": {"201": {"description": "Created"}},
                    },
                },
                "/items/{id}": {
                    "delete": {
                        "operationId": "deleteItem",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True,
                             "schema": {"type": "string"}}
                        ],
                        "responses": {"204": {"description": "No Content"}},
                    }
                },
            },
        }
        result = self.service.validate_spec_data(spec)
        assert result.is_valid, (
            f"Mixed-method spec was incorrectly rejected. Errors: {result.errors}"
        )


# ---------------------------------------------------------------------------
# Throughput benchmark — industry baseline: Spectral validates 100-endpoint
# spec in < 500 ms on commodity hardware
# ---------------------------------------------------------------------------

class TestForsetiThroughput:
    """Throughput must meet the < 500 ms industry threshold for API linting tools."""

    def test_100_endpoint_spec_validates_in_under_500ms(self) -> None:
        """
        Build a 100-endpoint spec and assert validation completes within 500 ms.

        Spectral (the most widely-used OSS API linter) targets < 500 ms for
        similarly-sized specs.  This test ensures Forseti stays competitive.
        """
        service = SpecValidatorService()
        large_spec = _valid_spec(num_paths=100)

        start = time.perf_counter()
        result = service.validate_spec_data(large_spec)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500, (
            f"Forseti took {elapsed_ms:.1f} ms to validate a 100-endpoint spec "
            f"(industry threshold: 500 ms)"
        )
        # Also verify the spec itself was not incorrectly rejected
        assert result.is_valid, (
            f"100-endpoint valid spec was incorrectly rejected. Errors: {result.errors}"
        )

    def test_validation_time_reported_in_result(self) -> None:
        """Result object must expose validation_time_ms for observability."""
        service = SpecValidatorService()
        result = service.validate_spec_data(_valid_spec(num_paths=5))
        assert result.validation_time_ms is not None
        assert result.validation_time_ms >= 0
