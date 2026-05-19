"""
Comprehensive L0 Unit Tests for Verdandi SLO Models

Tests all Pydantic models in the SLO module including:
- SLODefinition
- SLIMetric
- ErrorBudget
- BurnRate
- SLOReport
- Enums (SLOType, SLOComplianceStatus)
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from Asgard.Verdandi.SLO.models.slo_models import (
    SLODefinition,
    SLIMetric,
    ErrorBudget,
    BurnRate,
    SLOReport,
    SLOType,
    SLOComplianceStatus,
)


class TestSLOType:
    """Tests for SLOType enum."""

    def test_slo_type_values(self):
        """Test all SLOType enum values."""
        assert SLOType.AVAILABILITY.value == "availability"
        assert SLOType.LATENCY.value == "latency"
        assert SLOType.THROUGHPUT.value == "throughput"
        assert SLOType.ERROR_RATE.value == "error_rate"
        assert SLOType.QUALITY.value == "quality"
        assert SLOType.FRESHNESS.value == "freshness"


class TestSLOComplianceStatus:
    """Tests for SLOComplianceStatus enum."""

    def test_compliance_status_values(self):
        """Test all SLOComplianceStatus enum values."""
        assert SLOComplianceStatus.COMPLIANT.value == "compliant"
        assert SLOComplianceStatus.AT_RISK.value == "at_risk"
        assert SLOComplianceStatus.BREACHED.value == "breached"
        assert SLOComplianceStatus.UNKNOWN.value == "unknown"


class TestSLODefinition:
    """Tests for SLODefinition model."""

    def test_slo_definition_minimal(self):
        """Test creating SLODefinition with minimal fields."""
        slo = SLODefinition(
            name="API Availability",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,
            service_name="api-service",
        )

        assert slo.name == "API Availability"
        assert slo.slo_type == SLOType.AVAILABILITY
        assert slo.target == 99.9
        assert slo.service_name == "api-service"
        assert slo.window_days == 30  # default

    def test_slo_definition_complete(self):
        """Test creating SLODefinition with all fields."""
        slo = SLODefinition(
            name="P95 Latency",
            description="95th percentile latency must be under 500ms",
            slo_type=SLOType.LATENCY,
            target=99.0,
            window_days=7,
            service_name="api-service",
            labels={"env": "production", "team": "backend"},
            threshold_ms=500.0,
            percentile=95.0,
        )

        assert slo.description == "95th percentile latency must be under 500ms"
        assert slo.window_days == 7
        assert slo.labels["env"] == "production"
        assert slo.threshold_ms == 500.0
        assert slo.percentile == 95.0

    def test_slo_definition_target_validation_upper(self):
        """Test that target cannot exceed 100%."""
        with pytest.raises(ValidationError):
            SLODefinition(
                name="Test",
                slo_type=SLOType.AVAILABILITY,
                target=101.0,  # Invalid: > 100
                service_name="test",
            )

    def test_slo_definition_target_validation_lower(self):
        """Test that target cannot be negative."""
        with pytest.raises(ValidationError):
            SLODefinition(
                name="Test",
                slo_type=SLOType.AVAILABILITY,
                target=-1.0,  # Invalid: < 0
                service_name="test",
            )

    def test_slo_definition_error_budget_property(self):
        """Test error_budget_percent property calculation."""
        slo = SLODefinition(
            name="Test",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,
            service_name="test",
        )

        assert abs(slo.error_budget_percent - 0.1) < 0.01

        slo = SLODefinition(
            name="Test",
            slo_type=SLOType.AVAILABILITY,
            target=95.0,
            service_name="test",
        )

        assert slo.error_budget_percent == 5.0


class TestSLIMetric:
    """Tests for SLIMetric model."""

    def test_sli_metric_minimal(self):
        """Test creating SLIMetric with minimal fields."""
        now = datetime.now()
        metric = SLIMetric(
            timestamp=now,
            service_name="api-service",
            slo_type=SLOType.AVAILABILITY,
        )

        assert metric.timestamp == now
        assert metric.service_name == "api-service"
        assert metric.slo_type == SLOType.AVAILABILITY
        assert metric.good_events == 0
        assert metric.total_events == 0

    def test_sli_metric_with_events(self):
        """Test creating SLIMetric with event counts."""
        now = datetime.now()
        metric = SLIMetric(
            timestamp=now,
            service_name="api-service",
            slo_type=SLOType.AVAILABILITY,
            good_events=950,
            total_events=1000,
        )

        assert metric.good_events == 950
        assert metric.total_events == 1000

    def test_sli_metric_success_rate_property(self):
        """Test success_rate property calculation."""
        now = datetime.now()

        # Normal case
        metric = SLIMetric(
            timestamp=now,
            service_name="test",
            slo_type=SLOType.AVAILABILITY,
            good_events=95,
            total_events=100,
        )
        assert metric.success_rate == 0.95

        # Zero total events (edge case)
        metric = SLIMetric(
            timestamp=now,
            service_name="test",
            slo_type=SLOType.AVAILABILITY,
            good_events=0,
            total_events=0,
        )
        assert metric.success_rate == 1.0  # Defaults to 100%

    def test_sli_metric_failure_rate_property(self):
        """Test failure_rate property calculation."""
        now = datetime.now()
        metric = SLIMetric(
            timestamp=now,
            service_name="test",
            slo_type=SLOType.AVAILABILITY,
            good_events=90,
            total_events=100,
        )

        assert abs(metric.failure_rate - 0.1) < 0.01

    def test_sli_metric_with_direct_value(self):
        """Test SLIMetric with direct value instead of events."""
        now = datetime.now()
        metric = SLIMetric(
            timestamp=now,
            service_name="test",
            slo_type=SLOType.LATENCY,
            value=250.5,
        )

        assert metric.value == 250.5

    def test_sli_metric_with_labels(self):
        """Test SLIMetric with labels."""
        now = datetime.now()
        metric = SLIMetric(
            timestamp=now,
            service_name="test",
            slo_type=SLOType.AVAILABILITY,
            labels={"region": "us-west", "version": "v1.2.3"},
        )

        assert metric.labels["region"] == "us-west"
        assert metric.labels["version"] == "v1.2.3"


class TestErrorBudget:
    """Tests for ErrorBudget model."""

    def test_error_budget_minimal(self):
        """Test creating ErrorBudget with minimal fields."""
        budget = ErrorBudget(
            slo_name="Test SLO",
            slo_target=99.9,
            window_days=30,
        )

        assert budget.slo_name == "Test SLO"
        assert budget.slo_target == 99.9
        assert budget.window_days == 30
        assert budget.status == SLOComplianceStatus.UNKNOWN

    def test_error_budget_complete(self):
        """Test creating ErrorBudget with all fields."""
        now = datetime.now()
        budget = ErrorBudget(
            slo_name="API Availability",
            slo_target=99.9,
            window_days=30,
            calculated_at=now,
            total_events=10000,
            good_events=9990,
            bad_events=10,
            current_sli=99.9,
            allowed_failures=10.0,
            consumed_failures=10,
            remaining_budget=0.0,
            budget_consumed_percent=100.0,
            status=SLOComplianceStatus.BREACHED,
            time_remaining_days=15.0,
            projected_budget_at_window_end=-5.0,
        )

        assert budget.total_events == 10000
        assert budget.good_events == 9990
        assert budget.bad_events == 10
        assert budget.status == SLOComplianceStatus.BREACHED

    def test_error_budget_is_budget_exhausted_property(self):
        """Test is_budget_exhausted property."""
        # Budget remaining
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            remaining_budget=5.0,
        )
        assert not budget.is_budget_exhausted

        # Budget exhausted
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            remaining_budget=0.0,
        )
        assert budget.is_budget_exhausted

        # Budget overdrawn
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            remaining_budget=-10.0,
        )
        assert budget.is_budget_exhausted

    def test_error_budget_budget_remaining_percent_property(self):
        """Test budget_remaining_percent property."""
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            budget_consumed_percent=75.0,
        )

        assert budget.budget_remaining_percent == 25.0

        # Over-consumed
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            budget_consumed_percent=110.0,
        )

        assert budget.budget_remaining_percent == 0.0  # Clamped to 0

    def test_error_budget_current_sli_validation(self):
        """Test current_sli validation bounds."""
        # Valid SLI
        budget = ErrorBudget(
            slo_name="Test",
            slo_target=99.0,
            window_days=30,
            current_sli=99.5,
        )
        assert budget.current_sli == 99.5

        # Invalid: > 100
        with pytest.raises(ValidationError):
            ErrorBudget(
                slo_name="Test",
                slo_target=99.0,
                window_days=30,
                current_sli=100.5,
            )

        # Invalid: < 0
        with pytest.raises(ValidationError):
            ErrorBudget(
                slo_name="Test",
                slo_target=99.0,
                window_days=30,
                current_sli=-1.0,
            )


class TestBurnRate:
    """Tests for BurnRate model."""

    def test_burn_rate_minimal(self):
        """Test creating BurnRate with minimal fields."""
        burn_rate = BurnRate(
            slo_name="Test SLO",
            window_hours=1.0,
            burn_rate=1.0,
        )

        assert burn_rate.slo_name == "Test SLO"
        assert burn_rate.window_hours == 1.0
        assert burn_rate.burn_rate == 1.0
        assert burn_rate.alert_severity == "none"

    def test_burn_rate_complete(self):
        """Test creating BurnRate with all fields."""
        now = datetime.now()
        burn_rate = BurnRate(
            calculated_at=now,
            slo_name="API Availability",
            window_hours=6.0,
            burn_rate=14.4,
            burn_rate_short=20.0,
            burn_rate_long=10.0,
            budget_consumed_in_window=12.0,
            alert_severity="critical",
            time_to_exhaustion_hours=5.0,
            is_critical=True,
            is_warning=False,
            recommendations=[
                "Investigate immediately",
                "Page on-call engineer",
            ],
        )

        assert burn_rate.burn_rate == 14.4
        assert burn_rate.is_critical is True
        assert len(burn_rate.recommendations) == 2

    def test_burn_rate_warning_vs_critical(self):
        """Test burn rate warning and critical flags."""
        # Warning level
        burn_rate = BurnRate(
            slo_name="Test",
            window_hours=1.0,
            burn_rate=3.0,
            is_warning=True,
            is_critical=False,
        )

        assert burn_rate.is_warning is True
        assert burn_rate.is_critical is False

        # Critical level
        burn_rate = BurnRate(
            slo_name="Test",
            window_hours=1.0,
            burn_rate=14.4,
            is_warning=False,
            is_critical=True,
        )

        assert burn_rate.is_warning is False
        assert burn_rate.is_critical is True

    def test_burn_rate_multi_window(self):
        """Test burn rate with multiple window measurements."""
        burn_rate = BurnRate(
            slo_name="Test",
            window_hours=6.0,
            burn_rate=5.0,
            burn_rate_short=8.0,
            burn_rate_long=3.0,
        )

        assert burn_rate.burn_rate_short == 8.0
        assert burn_rate.burn_rate == 5.0
        assert burn_rate.burn_rate_long == 3.0


class TestSLOReport:
    """Tests for SLOReport model."""

    def test_slo_report_minimal(self):
        """Test creating SLOReport with minimal fields."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()

        report = SLOReport(
            report_period_start=start,
            report_period_end=end,
            service_name="api-service",
        )

        assert report.service_name == "api-service"
        assert report.overall_compliance == SLOComplianceStatus.UNKNOWN
        assert report.total_slos == 0

    def test_slo_report_complete(self):
        """Test creating SLOReport with all fields."""
        start = datetime.now() - timedelta(days=30)
        end = datetime.now()
        now = datetime.now()

        slo = SLODefinition(
            name="API Availability",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,
            service_name="api",
        )

        budget = ErrorBudget(
            slo_name="API Availability",
            slo_target=99.9,
            window_days=30,
        )

        burn_rate = BurnRate(
            slo_name="API Availability",
            window_hours=1.0,
            burn_rate=1.0,
        )

        report = SLOReport(
            generated_at=now,
            report_period_start=start,
            report_period_end=end,
            service_name="api-service",
            slo_definitions=[slo],
            error_budgets=[budget],
            burn_rates=[burn_rate],
            overall_compliance=SLOComplianceStatus.COMPLIANT,
            slos_compliant=3,
            slos_at_risk=1,
            slos_breached=0,
            total_slos=4,
            critical_alerts=["Error budget exhausted for latency SLO"],
            warnings=["Burn rate elevated"],
            recommendations=["Review recent deployments"],
        )

        assert report.total_slos == 4
        assert report.slos_compliant == 3
        assert len(report.slo_definitions) == 1
        assert len(report.critical_alerts) == 1

    def test_slo_report_compliance_percentage_property(self):
        """Test compliance_percentage property calculation."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()

        # 75% compliant
        report = SLOReport(
            report_period_start=start,
            report_period_end=end,
            service_name="test",
            total_slos=4,
            slos_compliant=3,
        )

        assert report.compliance_percentage == 75.0

        # 100% compliant
        report = SLOReport(
            report_period_start=start,
            report_period_end=end,
            service_name="test",
            total_slos=5,
            slos_compliant=5,
        )

        assert report.compliance_percentage == 100.0

        # No SLOs
        report = SLOReport(
            report_period_start=start,
            report_period_end=end,
            service_name="test",
            total_slos=0,
            slos_compliant=0,
        )

        assert report.compliance_percentage == 100.0  # Default when no SLOs

    def test_slo_report_compliance_breakdown(self):
        """Test SLO compliance breakdown in report."""
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()

        report = SLOReport(
            report_period_start=start,
            report_period_end=end,
            service_name="test",
            total_slos=10,
            slos_compliant=7,
            slos_at_risk=2,
            slos_breached=1,
        )

        assert report.total_slos == 10
        assert report.slos_compliant == 7
        assert report.slos_at_risk == 2
        assert report.slos_breached == 1
        assert report.slos_compliant + report.slos_at_risk + report.slos_breached == 10
