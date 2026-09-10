"""L3 contracts for public technical-debt value models.

These models cross analyzer, report, and configuration boundaries.  The
contracts pin their wire shapes, declared constrained inputs, computed effort
values, enum encoding, and isolation of mutable state.
"""

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.models.debt_models import (
    EffortInterval,
    EffortModels,
    FileFriction,
    InterestRates,
    RemediationFunction,
    ROIAnalysis,
    TimeHorizon,
    TimeProjection,
)


def _property_types(model):
    """Return each public field's JSON-schema type."""
    return {
        name: definition.get("type")
        for name, definition in model.model_json_schema()["properties"].items()
    }


class TestRemediationFunctionContract:
    def test_schema_pins_every_public_field_type_and_function_kind(self):
        schema = RemediationFunction.model_json_schema()

        assert _property_types(RemediationFunction) == {
            "kind": "string",
            "base_minutes": "number",
            "coefficient_minutes": "number",
            "unit": "string",
            "batchability": "number",
            "discount_floor": "number",
        }
        assert schema["properties"]["kind"]["enum"] == [
            "constant",
            "linear",
            "linear_with_offset",
        ]

    def test_defaults_have_an_explicit_wire_shape(self):
        assert RemediationFunction().model_dump(mode="json") == {
            "kind": "constant",
            "base_minutes": 0.0,
            "coefficient_minutes": 0.0,
            "unit": "issue",
            "batchability": 0.5,
            "discount_floor": 0.0,
        }

    def test_custom_linear_function_round_trips(self):
        payload = {
            "kind": "linear_with_offset",
            "base_minutes": 20.0,
            "coefficient_minutes": 7.5,
            "unit": "complexity_point",
            "batchability": 0.8,
            "discount_floor": 0.25,
        }

        assert RemediationFunction.model_validate(payload).model_dump(mode="json") == payload

    @pytest.mark.parametrize("field", ["base_minutes", "coefficient_minutes"])
    def test_rejects_negative_cost_components(self, field):
        with pytest.raises(ValidationError):
            RemediationFunction(**{field: -0.01})

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("batchability", -0.01),
            ("batchability", 1.01),
            ("discount_floor", -0.01),
            ("discount_floor", 1.01),
        ],
    )
    def test_rejects_factors_outside_the_closed_unit_interval(self, field, value):
        with pytest.raises(ValidationError):
            RemediationFunction(**{field: value})

    @pytest.mark.parametrize("kind", ["constant", "linear", "linear_with_offset"])
    def test_accepts_every_documented_function_kind(self, kind):
        assert RemediationFunction(kind=kind).kind == kind

    def test_rejects_unknown_function_kind(self):
        with pytest.raises(ValidationError):
            RemediationFunction(kind="quadratic")


class TestEffortIntervalContract:
    def test_schema_pins_every_public_field_type_and_confidence_value(self):
        schema = EffortInterval.model_json_schema()

        assert _property_types(EffortInterval) == {
            "low_minutes": "number",
            "high_minutes": "number",
            "confidence": "string",
            "width_reason": "string",
        }
        assert schema["properties"]["confidence"]["enum"] == ["high", "medium", "low"]

    def test_defaults_and_computed_midpoints_are_stable(self):
        interval = EffortInterval()

        assert interval.model_dump(mode="json") == {
            "low_minutes": 0.0,
            "high_minutes": 0.0,
            "confidence": "medium",
            "width_reason": "",
        }
        assert interval.midpoint_minutes == 0.0
        assert interval.midpoint_hours == 0.0

    def test_interval_round_trips_and_exposes_minutes_and_hours(self):
        payload = {
            "low_minutes": 30.0,
            "high_minutes": 150.0,
            "confidence": "low",
            "width_reason": "The repository history is incomplete.",
        }
        interval = EffortInterval.model_validate(payload)

        assert interval.model_dump(mode="json") == payload
        assert interval.midpoint_minutes == 90.0
        assert interval.midpoint_hours == 1.5

    @pytest.mark.parametrize("field", ["low_minutes", "high_minutes"])
    def test_rejects_negative_effort_bounds(self, field):
        with pytest.raises(ValidationError):
            EffortInterval(**{field: -1.0})

    def test_rejects_unknown_confidence(self):
        with pytest.raises(ValidationError):
            EffortInterval(confidence="unknown")


class TestFileFrictionContract:
    def test_schema_requires_integer_counters(self):
        assert _property_types(FileFriction) == {
            "churn_commits_90d": "integer",
            "distinct_authors_12m": "integer",
            "bugfix_commits_12m": "integer",
        }

    def test_defaults_are_zero_and_custom_values_round_trip(self):
        assert FileFriction().model_dump(mode="json") == {
            "churn_commits_90d": 0,
            "distinct_authors_12m": 0,
            "bugfix_commits_12m": 0,
        }
        assert FileFriction(
            churn_commits_90d=17,
            distinct_authors_12m=4,
            bugfix_commits_12m=3,
        ).model_dump(mode="json") == {
            "churn_commits_90d": 17,
            "distinct_authors_12m": 4,
            "bugfix_commits_12m": 3,
        }

    @pytest.mark.parametrize(
        "field",
        ["churn_commits_90d", "distinct_authors_12m", "bugfix_commits_12m"],
    )
    def test_rejects_negative_counters(self, field):
        with pytest.raises(ValidationError):
            FileFriction(**{field: -1})


class TestROIAnalysisContract:
    def test_schema_pins_scalar_and_per_type_roi_values(self):
        schema = ROIAnalysis.model_json_schema()

        assert _property_types(ROIAnalysis) == {
            "overall_roi": "number",
            "roi_by_type": "object",
            "payback_period_months": "number",
            "total_effort_hours": "number",
            "total_benefit": "number",
        }
        assert schema["properties"]["roi_by_type"]["additionalProperties"] == {
            "type": "number"
        }

    def test_rejects_non_string_roi_category_keys(self):
        with pytest.raises(ValidationError):
            ROIAnalysis(roi_by_type={1: 2.5})

    def test_defaults_are_explicit_and_roi_maps_are_isolated(self):
        first, second = ROIAnalysis(), ROIAnalysis()

        assert first.model_dump(mode="json") == {
            "overall_roi": 0.0,
            "roi_by_type": {},
            "payback_period_months": 0.0,
            "total_effort_hours": 0.0,
            "total_benefit": 0.0,
        }
        first.roi_by_type["code"] = 2.5
        assert second.roi_by_type == {}

    def test_complete_analysis_round_trips(self):
        payload = {
            "overall_roi": 2.75,
            "roi_by_type": {"code": 3.5, "test": 1.25},
            "payback_period_months": 4.0,
            "total_effort_hours": 80.0,
            "total_benefit": 220.0,
        }

        assert ROIAnalysis.model_validate(payload).model_dump(mode="json") == payload


class TestTimeProjectionContract:
    def test_schema_pins_numeric_fields_and_the_horizon_enum(self):
        schema = TimeProjection.model_json_schema()

        assert _property_types(TimeProjection) == {
            "current_debt_hours": "number",
            "projected_debt_hours": "number",
            "growth_percentage": "number",
            "time_horizon": None,
        }
        assert schema["properties"]["time_horizon"]["$ref"] == "#/$defs/TimeHorizon"
        horizon_schema = schema["$defs"]["TimeHorizon"]
        assert horizon_schema["type"] == "string"
        assert horizon_schema["enum"] == ["sprint", "quarter", "year"]

    def test_time_horizon_wire_map_is_exact_and_exhaustive(self):
        assert {member.name: member.value for member in TimeHorizon} == {
            "SPRINT": "sprint",
            "QUARTER": "quarter",
            "YEAR": "year",
        }

    def test_defaults_have_quarter_wire_value(self):
        assert TimeProjection().model_dump(mode="json") == {
            "current_debt_hours": 0.0,
            "projected_debt_hours": 0.0,
            "growth_percentage": 0.0,
            "time_horizon": "quarter",
        }

    def test_projection_round_trips_with_enum_wire_value(self):
        payload = {
            "current_debt_hours": 40.0,
            "projected_debt_hours": 52.0,
            "growth_percentage": 30.0,
            "time_horizon": "year",
        }

        projection = TimeProjection.model_validate(payload)
        assert projection.time_horizon == "year"
        assert projection.model_dump(mode="json") == payload

    def test_rejects_unknown_time_horizon(self):
        with pytest.raises(ValidationError):
            TimeProjection(time_horizon="month")


class TestEffortModelsContract:
    def test_schema_requires_numeric_cost_factors(self):
        assert _property_types(EffortModels) == {
            "complexity_reduction_factor": "number",
            "test_coverage_factor": "number",
            "documentation_factor": "number",
            "refactoring_log_factor": "number",
            "dependency_update_hours": "number",
        }

    def test_defaults_match_the_analyzer_cost_model(self):
        assert EffortModels().model_dump(mode="json") == {
            "complexity_reduction_factor": 0.5,
            "test_coverage_factor": 0.1,
            "documentation_factor": 0.25,
            "refactoring_log_factor": 2.0,
            "dependency_update_hours": 2.0,
        }

    def test_custom_cost_model_round_trips(self):
        payload = {
            "complexity_reduction_factor": 0.75,
            "test_coverage_factor": 0.2,
            "documentation_factor": 0.5,
            "refactoring_log_factor": 3.0,
            "dependency_update_hours": 4.0,
        }

        assert EffortModels.model_validate(payload).model_dump(mode="json") == payload


class TestInterestRatesContract:
    def test_schema_requires_numeric_rates(self):
        assert _property_types(InterestRates) == {
            "high_complexity": "number",
            "no_tests": "number",
            "poor_docs": "number",
            "outdated_deps": "number",
            "design_issues": "number",
        }

    def test_defaults_match_the_quarterly_interest_model(self):
        assert InterestRates().model_dump(mode="json") == {
            "high_complexity": 0.10,
            "no_tests": 0.15,
            "poor_docs": 0.05,
            "outdated_deps": 0.20,
            "design_issues": 0.08,
        }

    def test_custom_interest_model_round_trips(self):
        payload = {
            "high_complexity": 0.12,
            "no_tests": 0.18,
            "poor_docs": 0.06,
            "outdated_deps": 0.25,
            "design_issues": 0.09,
        }

        assert InterestRates.model_validate(payload).model_dump(mode="json") == payload
