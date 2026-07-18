"""
Error Budget Calculator Service

Calculates error budget consumption and status for SLOs.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from Asgard.Verdandi.SLO.models.slo_models import (
    ErrorBudget,
    SLIMetric,
    SLOComplianceStatus,
    SLODefinition,
)


class ErrorBudgetCalculator:
    """
    Calculator for error budget consumption.

    Error budget is the acceptable amount of unreliability within an SLO
    window. This calculator tracks how much of the budget has been consumed.

    Example:
        calculator = ErrorBudgetCalculator()
        slo = SLODefinition(name="API Availability", target=99.9, ...)
        metrics = [sli1, sli2, ...]
        budget = calculator.calculate(slo, metrics)
        print(f"Budget remaining: {budget.remaining_budget}")
    """

    def __init__(
        self,
        at_risk_threshold: float = 80.0,
        breached_threshold: float = 100.0,
    ):
        """
        Initialize the error budget calculator.

        Args:
            at_risk_threshold: Percentage consumed before marking as at_risk
            breached_threshold: Percentage consumed to mark as breached
        """
        self.at_risk_threshold = at_risk_threshold
        self.breached_threshold = breached_threshold

    def calculate(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        current_time: Optional[datetime] = None,
    ) -> ErrorBudget:
        """
        Calculate error budget consumption for an SLO.

        Args:
            slo: The SLO definition
            metrics: SLI metrics within the SLO window
            current_time: Current time for calculations (default: now)

        Returns:
            ErrorBudget with consumption statistics
        """
        current_time = current_time or datetime.now()

        # Filter metrics within the SLO window
        window_start = current_time - timedelta(days=slo.window_days)
        window_metrics = [
            m for m in metrics if m.timestamp >= window_start and m.timestamp <= current_time
        ]

        # Calculate totals from metrics
        total_events = sum(m.total_events for m in window_metrics)
        good_events = sum(m.good_events for m in window_metrics)
        rejected_events = sum(m.rejected_events for m in window_metrics)
        # Valid rejections (e.g. typed INSUFFICIENT_DATA outcomes) never
        # consume error budget (DEEPTHINK_01).
        bad_events = max(0, total_events - good_events - rejected_events)

        # Calculate current SLI
        current_sli = (good_events / total_events * 100.0) if total_events > 0 else 100.0

        # Calculate error budget
        error_budget_percent = 100.0 - slo.target
        allowed_failures = (error_budget_percent / 100.0) * total_events if total_events > 0 else 0.0

        # Calculate remaining budget
        remaining_budget = allowed_failures - bad_events

        # Calculate consumption percentage
        budget_consumed_percent = (
            (bad_events / allowed_failures * 100.0) if allowed_failures > 0 else 0.0
        )
        if allowed_failures == 0 and bad_events > 0:
            budget_consumed_percent = 100.0

        # Determine status
        status = self._determine_status(budget_consumed_percent)

        # Calculate time remaining in window
        time_remaining = max(
            0.0,
            (window_start + timedelta(days=slo.window_days) - current_time).total_seconds()
            / (24 * 3600),
        )

        # Project budget at window end
        projected_budget = self._project_budget_at_end(
            remaining_budget, bad_events, time_remaining, slo.window_days
        )

        return ErrorBudget(
            slo_name=slo.name,
            slo_target=slo.target,
            window_days=slo.window_days,
            calculated_at=current_time,
            total_events=total_events,
            good_events=good_events,
            bad_events=bad_events,
            current_sli=current_sli,
            allowed_failures=allowed_failures,
            consumed_failures=bad_events,
            remaining_budget=remaining_budget,
            budget_consumed_percent=budget_consumed_percent,
            status=status,
            time_remaining_days=time_remaining,
            projected_budget_at_window_end=projected_budget,
        )

    def calculate_for_period(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        start_time: datetime,
        end_time: datetime,
    ) -> ErrorBudget:
        """
        Calculate error budget for a specific time period.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            start_time: Start of the period
            end_time: End of the period

        Returns:
            ErrorBudget for the specified period
        """
        # Filter metrics within the period
        period_metrics = [
            m for m in metrics if m.timestamp >= start_time and m.timestamp <= end_time
        ]

        # Calculate using the period duration
        period_days = (end_time - start_time).total_seconds() / (24 * 3600)

        # Create temporary SLO with adjusted window
        temp_slo = SLODefinition(
            name=slo.name,
            slo_type=slo.slo_type,
            target=slo.target,
            window_days=max(1, int(period_days)),
            service_name=slo.service_name,
        )

        return self.calculate(temp_slo, period_metrics, end_time)

    def calculate_multi_window(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        windows: List[int],
        current_time: Optional[datetime] = None,
    ) -> List[ErrorBudget]:
        """
        Calculate error budget for multiple time windows.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            windows: List of window sizes in days
            current_time: Current time for calculations

        Returns:
            List of ErrorBudget for each window
        """
        results = []
        for window_days in windows:
            temp_slo = SLODefinition(
                name=f"{slo.name} ({window_days}d)",
                slo_type=slo.slo_type,
                target=slo.target,
                window_days=window_days,
                service_name=slo.service_name,
            )
            results.append(self.calculate(temp_slo, metrics, current_time))
        return results

    def get_daily_budgets(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        days: int = 30,
        current_time: Optional[datetime] = None,
    ) -> List[ErrorBudget]:
        """
        Get daily error budget calculations.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            days: Number of days to calculate
            current_time: Current time for calculations

        Returns:
            List of ErrorBudget for each day
        """
        current_time = current_time or datetime.now()
        results = []

        for day_offset in range(days):
            day_end = current_time - timedelta(days=day_offset)
            day_start = day_end - timedelta(days=1)

            day_metrics = [
                m for m in metrics
                if m.timestamp >= day_start and m.timestamp <= day_end
            ]

            if day_metrics:
                temp_slo = SLODefinition(
                    name=slo.name,
                    slo_type=slo.slo_type,
                    target=slo.target,
                    window_days=1,
                    service_name=slo.service_name,
                )
                results.append(self.calculate(temp_slo, day_metrics, day_end))

        return results

    def _determine_status(self, consumed_percent: float) -> SLOComplianceStatus:
        """Determine compliance status based on consumption."""
        if consumed_percent >= self.breached_threshold:
            return SLOComplianceStatus.BREACHED
        elif consumed_percent >= self.at_risk_threshold:
            return SLOComplianceStatus.AT_RISK
        else:
            return SLOComplianceStatus.COMPLIANT

    def _project_budget_at_end(
        self,
        remaining_budget: float,
        consumed_so_far: int,
        time_remaining_days: float,
        window_days: int,
    ) -> Optional[float]:
        """Project remaining budget at window end based on current consumption rate."""
        if time_remaining_days <= 0:
            return remaining_budget

        # Calculate elapsed time
        elapsed_days = window_days - time_remaining_days
        if elapsed_days <= 0:
            return None

        # Calculate consumption rate (failures per day)
        consumption_rate = consumed_so_far / elapsed_days

        # Project additional consumption
        projected_additional = consumption_rate * time_remaining_days

        return remaining_budget - projected_additional
