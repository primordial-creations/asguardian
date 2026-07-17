"""
Heimdall Technical Debt Analyzer Service

Quantifies and prioritizes technical debt across the codebase using multiple metrics:
- Code Debt: Quality issues, complexity, maintainability
- Design Debt: Architectural issues, coupling problems
- Test Debt: Coverage gaps, test quality issues
- Documentation Debt: Missing or poor documentation
- Dependency Debt: Outdated or vulnerable dependencies

Provides ROI analysis, time horizon projections, and business impact weighting.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Asgard.Bragi.Quality.models.debt_models import (
    DebtConfig,
    DebtItem,
    DebtReport,
    DebtType,
    EffortInterval,
    ROIAnalysis,
    TimeHorizon,
    TimeProjection,
)
from Asgard.Bragi.Quality.services._debt_aggregator import CentralityProvider, DebtAggregator
from Asgard.Bragi.Quality.services._debt_workers import (
    analyze_code_debt,
    analyze_dependency_debt,
    analyze_design_debt,
    analyze_documentation_debt,
    analyze_test_debt,
    count_file_lines,
    count_lines_of_code,
)
from Asgard.Bragi.Quality.services._remediation_model import RemediationModel
from Asgard.Bragi.Quality.services._technical_debt_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class TechnicalDebtAnalyzer:
    """
    Analyzes and quantifies technical debt using multiple dimensions.

    Debt Categories:
    - Code: Complexity, quality issues, maintainability problems
    - Design: Architectural issues, coupling, abstraction debt
    - Test: Coverage gaps, test quality, missing test types
    - Documentation: Missing/outdated/poor quality docs
    - Dependencies: Outdated, vulnerable, or unused dependencies

    Usage:
        analyzer = TechnicalDebtAnalyzer()
        report = analyzer.analyze(Path("./src"))

        print(f"Total debt: {report.total_debt_hours} hours")
        for item in report.prioritized_items[:10]:
            print(f"{item.description}: {item.effort_hours}h")
    """

    def __init__(self, config: Optional[DebtConfig] = None):
        """
        Initialize technical debt analyzer.

        Args:
            config: Configuration for debt analysis. If None, uses defaults.
        """
        self.config = config or DebtConfig()
        # Centrality feed arrives with Plan 03 Phase B (DependencyGraphService);
        # until wired, exposure multipliers stay at 1.0.
        self.centrality_provider: Optional[CentralityProvider] = None
        self.remediation_model = RemediationModel()
        self.aggregator = DebtAggregator(
            remediation_model=self.remediation_model,
            centrality_provider=self.centrality_provider,
        )

    def analyze(self, path: Path) -> DebtReport:
        """
        Analyze a directory for technical debt.

        Args:
            path: Path to directory to analyze

        Returns:
            DebtReport with complete debt analysis

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = DebtReport(scan_path=str(path))

        enabled_types = self.config.get_enabled_debt_types()

        if DebtType.CODE.value in enabled_types:
            analyze_code_debt(path, report, self.config)

        if DebtType.DESIGN.value in enabled_types:
            analyze_design_debt(path, report, self.config)

        if DebtType.TEST.value in enabled_types:
            analyze_test_debt(path, report, self.config)

        if DebtType.DOCUMENTATION.value in enabled_types:
            analyze_documentation_debt(path, report, self.config)

        if DebtType.DEPENDENCIES.value in enabled_types:
            analyze_dependency_debt(path, report, self.config)

        report.total_lines_of_code = count_lines_of_code(path, self.config)
        if report.total_lines_of_code > 0:
            report.debt_ratio = report.total_debt_hours / report.total_lines_of_code * 1000

        # Plan 02: batched, pessimism-corrected aggregation with effort
        # intervals, plus the standard TDR (30 min/LOC development-cost
        # anchor) - the single source of truth for the Maintainability grade.
        file_loc = {
            fp: count_file_lines(fp)
            for fp in {item.file_path for item in report.debt_items}
        }
        aggregated = self.aggregator.aggregate(report.debt_items, file_loc=file_loc)
        report.aggregated_debt_hours = aggregated.total_hours
        report.effort_interval = aggregated.effort_interval
        report.file_recommendations = aggregated.recommendations
        for item in report.debt_items:
            minutes = self.remediation_model.minutes_for(item)
            item.effort_interval = self._item_interval(minutes)
            item.non_remediation_factor = self.remediation_model.non_remediation_factor(item)
        if report.total_lines_of_code > 0:
            development_minutes = report.total_lines_of_code * 30.0
            report.tdr_percent = aggregated.total_minutes / development_minutes * 100.0

        report.prioritized_items = self._prioritize_debt_items(report.debt_items)
        report.roi_analysis = self._calculate_roi_analysis(report.debt_items)
        report.time_projection = self._calculate_time_projection(report.debt_items)
        report.most_indebted_files = self._calculate_most_indebted_files(report.debt_items)
        report.remediation_priorities = self._generate_remediation_priorities(report)
        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def analyze_single_file(self, file_path: Path) -> DebtReport:
        """
        Analyze a single file for technical debt.

        Args:
            file_path: Path to Python file

        Returns:
            DebtReport with detected debt
        """
        return self.analyze(file_path)

    @staticmethod
    def _item_interval(minutes: float) -> EffortInterval:
        """Per-item effort interval from the corrected minute estimate."""
        return EffortInterval(
            low_minutes=minutes * 0.75,
            high_minutes=minutes * 1.5,
            confidence="medium",
            width_reason="model-based estimate; no coverage/churn telemetry supplied",
        )

    def _prioritize_debt_items(self, debt_items: List[DebtItem]) -> List[DebtItem]:
        """Prioritize debt items by ROI."""
        return sorted(debt_items, key=lambda item: item.priority_score, reverse=True)

    def _calculate_roi_analysis(self, debt_items: List[DebtItem]) -> ROIAnalysis:
        """Calculate ROI analysis for debt remediation."""
        if not debt_items:
            return ROIAnalysis()

        total_effort = sum(item.effort_hours for item in debt_items)
        total_benefit = sum(item.business_impact * item.interest_rate for item in debt_items)

        roi_by_type: Dict[str, float] = {}
        for debt_type in DebtType:
            type_items = [item for item in debt_items if item.debt_type == debt_type.value]
            if type_items:
                type_effort = sum(item.effort_hours for item in type_items)
                type_benefit = sum(item.business_impact * item.interest_rate for item in type_items)
                roi_by_type[debt_type.value] = type_benefit / max(type_effort, 0.1)

        overall_roi = total_benefit / max(total_effort, 0.1)

        if overall_roi > 0:
            payback_months = 1 / overall_roi * 3
        else:
            payback_months = float("inf")

        return ROIAnalysis(
            overall_roi=overall_roi,
            roi_by_type=roi_by_type,
            payback_period_months=min(payback_months, 999),
            total_effort_hours=total_effort,
            total_benefit=total_benefit,
        )

    def _calculate_time_projection(self, debt_items: List[DebtItem]) -> TimeProjection:
        """Calculate debt growth projections."""
        if not debt_items:
            return TimeProjection()

        current_debt = sum(item.effort_hours for item in debt_items)

        horizon = self.config.time_horizon
        if isinstance(horizon, str):
            horizon = TimeHorizon(horizon)

        quarters = {
            TimeHorizon.SPRINT: 0.2,
            TimeHorizon.QUARTER: 1.0,
            TimeHorizon.YEAR: 4.0,
        }.get(horizon, 1.0)

        projected_debt = 0.0
        for item in debt_items:
            growth_factor = (1 + item.interest_rate) ** quarters
            projected_debt += item.effort_hours * growth_factor

        growth_pct = ((projected_debt - current_debt) / max(current_debt, 1)) * 100

        return TimeProjection(
            current_debt_hours=current_debt,
            projected_debt_hours=projected_debt,
            growth_percentage=growth_pct,
            time_horizon=horizon if isinstance(horizon, str) else horizon.value,
        )

    def _calculate_most_indebted_files(self, debt_items: List[DebtItem]) -> List[Tuple[str, float]]:
        """Calculate files with most debt."""
        file_debt: Dict[str, float] = {}
        for item in debt_items:
            file_debt[item.file_path] = file_debt.get(item.file_path, 0.0) + item.effort_hours

        return sorted(file_debt.items(), key=lambda x: x[1], reverse=True)[:10]

    def _generate_remediation_priorities(self, report: DebtReport) -> List[str]:
        """Generate prioritized remediation recommendations."""
        priorities = []

        critical_count = report.critical_count
        if critical_count > 0:
            priorities.append(f"CRITICAL: Address {critical_count} critical debt items immediately")

        high_count = report.high_count
        if high_count > 0:
            priorities.append(f"HIGH: Review {high_count} high-severity debt items")

        for debt_type, hours in sorted(report.debt_by_type.items(), key=lambda x: x[1], reverse=True):
            if hours > 20:
                priorities.append(f"Focus on {debt_type} debt ({hours:.1f} hours)")

        if report.roi_analysis.overall_roi > 0.1:
            priorities.append(f"High ROI opportunity: payback in ~{report.roi_analysis.payback_period_months:.1f} months")

        if report.time_projection.growth_percentage > 20:
            priorities.append(f"Warning: Debt growing {report.time_projection.growth_percentage:.1f}% per {report.time_projection.time_horizon}")

        return priorities

    def generate_report(self, report: DebtReport, output_format: str = "text") -> str:
        """
        Generate formatted technical debt report.

        Args:
            report: DebtReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower == "markdown" or format_lower == "md":
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
