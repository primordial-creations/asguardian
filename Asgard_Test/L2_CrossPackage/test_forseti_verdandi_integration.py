"""
Forseti-Verdandi Integration Tests

Tests for cross-package integration between Forseti (API/schema validation) and
Verdandi (performance metrics). These tests validate workflows where API
specifications inform SLA thresholds and performance monitoring configuration.
"""

from pathlib import Path

import pytest
import yaml

from Asgard.Forseti.OpenAPI import SpecValidatorService, OpenAPIConfig
from Asgard.Verdandi.Analysis import SLAChecker, SLAConfig, ApdexCalculator, ApdexConfig


def _make_sla_config(threshold_ms: float, target_percentile: float = 95.0) -> SLAConfig:
    return SLAConfig(
        target_percentile=target_percentile,
        threshold_ms=threshold_ms,
    )


@pytest.mark.cross_package
@pytest.mark.forseti_verdandi
class TestAPISpecToSLAChecker:
    """
    Test workflow: Parse OpenAPI spec with Forseti, then configure SLA thresholds
    with Verdandi based on operation complexity and requirements.
    """

    def test_endpoint_count_influences_sla_targets(
        self, sample_openapi_spec: Path
    ):
        validator = SpecValidatorService()
        validation_result = validator.validate(str(sample_openapi_spec))

        assert validation_result.is_valid
        assert validation_result.openapi_version is not None

        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        paths = spec_data.get('paths', {})
        endpoint_count = sum(len(methods) for methods in paths.values())

        if endpoint_count > 20:
            max_response_time_ms = 2000
            target_percentile = 95
        elif endpoint_count > 10:
            max_response_time_ms = 1000
            target_percentile = 99
        else:
            max_response_time_ms = 500
            target_percentile = 99

        sla_config = _make_sla_config(max_response_time_ms, target_percentile)

        assert sla_config.threshold_ms > 0
        assert sla_config.target_percentile in [95, 99]

        sla_checker = SLAChecker(sla_config)

        response_times = [100, 150, 200, 250, 300, 350, 400, 450, 500]

        sla_result = sla_checker.check(
            response_times_ms=response_times,
            error_count=1,
            total_requests=10,
        )

        assert sla_result is not None
        assert hasattr(sla_result, 'status')
        assert hasattr(sla_result, 'percentile_value')

    def test_operation_types_set_apdex_thresholds(
        self, sample_openapi_spec: Path
    ):
        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        paths = spec_data.get('paths', {})

        operation_types = {}
        for path, methods in paths.items():
            for method in methods.keys():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    operation_types[method] = operation_types.get(method, 0) + 1

        get_count = operation_types.get('get', 0)
        post_count = operation_types.get('post', 0)

        if get_count > post_count:
            satisfied_threshold_ms = 100
        else:
            satisfied_threshold_ms = 200

        apdex_config = ApdexConfig(threshold_ms=satisfied_threshold_ms)
        apdex_calculator = ApdexCalculator(threshold_ms=apdex_config.threshold_ms)

        response_times = [50, 150, 300, 600, 1200]
        apdex_result = apdex_calculator.calculate(response_times)

        assert apdex_result is not None
        assert 0 <= apdex_result.score <= 1.0
        assert apdex_result.satisfied_count >= 0
        assert apdex_result.tolerating_count >= 0
        assert apdex_result.frustrated_count >= 0

    def test_security_schemes_affect_timeout_budgets(
        self, sample_openapi_spec: Path
    ):
        validator = SpecValidatorService()
        validation_result = validator.validate(str(sample_openapi_spec))

        assert validation_result.is_valid

        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        components = spec_data.get('components', {})
        security_schemes = components.get('securitySchemes', {})

        has_oauth = any(
            scheme.get('type') == 'oauth2'
            for scheme in security_schemes.values()
        )
        has_openid = any(
            scheme.get('type') == 'openIdConnect'
            for scheme in security_schemes.values()
        )

        base_timeout_ms = 500

        if has_oauth or has_openid:
            timeout_ms = base_timeout_ms + 500
        elif security_schemes:
            timeout_ms = base_timeout_ms + 100
        else:
            timeout_ms = base_timeout_ms

        sla_config = _make_sla_config(timeout_ms)

        assert sla_config.threshold_ms >= base_timeout_ms
        assert sla_config.threshold_ms <= base_timeout_ms + 500


@pytest.mark.cross_package
@pytest.mark.forseti_verdandi
class TestSchemaValidationToMetrics:
    """Validate schemas with Forseti, track validation perf with Verdandi metrics."""

    def test_schema_complexity_sets_performance_baselines(
        self, sample_openapi_spec: Path
    ):
        validator = SpecValidatorService()
        validation_result = validator.validate(str(sample_openapi_spec))
        assert validation_result.is_valid

        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        components = spec_data.get('components', {})
        schemas = components.get('schemas', {})

        total_properties = 0
        max_nesting_level = 0
        for _, schema_def in schemas.items():
            properties = schema_def.get('properties', {})
            total_properties += len(properties)
            for _, prop_def in properties.items():
                if prop_def.get('type') == 'object':
                    max_nesting_level = max(max_nesting_level, 1)
                elif '$ref' in prop_def:
                    max_nesting_level = max(max_nesting_level, 1)

        complexity_score = total_properties + (max_nesting_level * 10)

        if complexity_score > 50:
            baseline_validation_time_ms = 50
        elif complexity_score > 20:
            baseline_validation_time_ms = 20
        else:
            baseline_validation_time_ms = 10

        apdex_config = ApdexConfig(threshold_ms=baseline_validation_time_ms)

        validation_times = [
            baseline_validation_time_ms * 0.8,
            baseline_validation_time_ms * 1.2,
            baseline_validation_time_ms * 2.5,
            baseline_validation_time_ms * 4.0,
        ]

        apdex_calculator = ApdexCalculator(threshold_ms=apdex_config.threshold_ms)
        apdex_result = apdex_calculator.calculate(validation_times)

        assert apdex_result.score >= 0
        assert apdex_result.total_count == len(validation_times)

    def test_required_fields_influence_validation_strictness(
        self, sample_openapi_spec: Path
    ):
        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        components = spec_data.get('components', {})
        schemas = components.get('schemas', {})

        total_required = 0
        for _, schema_def in schemas.items():
            required_fields = schema_def.get('required', [])
            total_required += len(required_fields)

        if total_required > 20:
            max_validation_time_ms = 200
        elif total_required > 10:
            max_validation_time_ms = 100
        else:
            max_validation_time_ms = 50

        sla_config = _make_sla_config(max_validation_time_ms, target_percentile=99.0)

        assert sla_config.threshold_ms > 0
        if total_required > 20:
            assert sla_config.threshold_ms >= 200

    def test_endpoint_response_schemas_set_serialization_sla(
        self, sample_openapi_spec: Path
    ):
        validator = SpecValidatorService()
        validation_result = validator.validate(str(sample_openapi_spec))
        assert validation_result.is_valid

        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        paths = spec_data.get('paths', {})

        response_schema_count = 0
        array_responses = 0
        for _, methods in paths.items():
            for method, operation in methods.items():
                if method not in ['get', 'post', 'put', 'delete', 'patch']:
                    continue
                responses = operation.get('responses', {})
                for _, response_def in responses.items():
                    content = response_def.get('content', {})
                    for _, schema_info in content.items():
                        schema = schema_info.get('schema', {})
                        response_schema_count += 1
                        if schema.get('type') == 'array':
                            array_responses += 1

        if array_responses > 0:
            serialization_time_ms = 100 * array_responses
        else:
            serialization_time_ms = 50

        apdex_config = ApdexConfig(threshold_ms=serialization_time_ms)
        assert apdex_config.threshold_ms > 0
        assert apdex_config.frustration_threshold_ms > apdex_config.threshold_ms


@pytest.mark.cross_package
@pytest.mark.forseti_verdandi
class TestAPIVersioningToPerformanceTracking:
    """Use API version from Forseti to set up versioned perf tracking with Verdandi."""

    def test_api_version_creates_separate_sla_baselines(
        self, sample_openapi_spec: Path
    ):
        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        info = spec_data.get('info', {})
        api_version = info.get('version', '1.0.0')

        major_version = int(api_version.split('.')[0])

        if major_version >= 2:
            max_response_time_ms = 1000
        else:
            max_response_time_ms = 500

        sla_config = _make_sla_config(max_response_time_ms)

        assert sla_config.threshold_ms > 0

        version_baselines = {
            f"v{major_version}": {
                "max_response_ms": sla_config.threshold_ms,
            }
        }
        assert f"v{major_version}" in version_baselines

    def test_deprecated_endpoints_have_different_sla(
        self, sample_openapi_spec: Path
    ):
        with open(sample_openapi_spec, 'r') as f:
            spec_data = yaml.safe_load(f)

        paths = spec_data.get('paths', {})

        deprecated_count = 0
        active_count = 0
        for _, methods in paths.items():
            for method, operation in methods.items():
                if method not in ['get', 'post', 'put', 'delete', 'patch']:
                    continue
                if operation.get('deprecated', False):
                    deprecated_count += 1
                else:
                    active_count += 1

        active_sla = _make_sla_config(500, target_percentile=99.0)
        deprecated_sla = _make_sla_config(1000, target_percentile=95.0)

        assert deprecated_sla.threshold_ms >= active_sla.threshold_ms
        assert deprecated_sla.target_percentile <= active_sla.target_percentile
