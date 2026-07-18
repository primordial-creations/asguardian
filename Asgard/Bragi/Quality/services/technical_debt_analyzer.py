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

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Asgard.Bragi.Quality.models.debt_models import (
    DebtConfig,
    DebtItem,
    DebtReport,
    DebtSeverity,
    DebtType,
    EffortInterval,
    FileFriction,
    ROIAnalysis,
    TimeHorizon,
    TimeProjection,
)
from Asgard.Bragi.Quality.services._debt_aggregator import (
    CentralityProvider,
    DebtAggregator,
    compute_tdr_percent,
)
from Asgard.Bragi.Quality.services._debt_state_store import (
    DeltaResult,
    apply_delta,
    load_state,
    save_state,
)
from Asgard.Bragi.Quality.services._debt_workers import (
    analyze_code_debt,
    analyze_dependency_debt,
    analyze_design_debt,
    analyze_documentation_debt,
    analyze_file_complexity,
    analyze_test_debt,
    count_file_lines,
    count_lines_of_code,
    find_undocumented_functions,
    get_business_impact,
    should_analyze_file,
)
from Asgard.Bragi.Quality.services._git_friction import (
    collect_friction,
    compute_interest_scores,
    is_minefield,
    is_sleeping_bear,
    SEVERITY_DOWNGRADE,
)
from Asgard.Bragi.Quality.services._remediation_model import RemediationModel
from Asgard.Bragi.common.context_classifier import CodeContext, classify
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
        # Centrality feed from Plan 03 Phase B's DependencyGraphService —
        # wire it via set_centrality_provider() (or use_dependency_graph()).
        # Unwired, exposure multipliers stay at 1.0.
        self.centrality_provider: Optional[CentralityProvider] = None
        self.remediation_model = RemediationModel()
        self.aggregator = DebtAggregator(
            remediation_model=self.remediation_model,
            centrality_provider=self.centrality_provider,
        )
        # Git friction telemetry (Plan 02 Phase D). Opt-in via
        # use_git_friction(); off by default so analysis stays offline and
        # deterministic outside a git checkout.
        self._friction_by_file: Dict[str, FileFriction] = {}
        self._use_friction: bool = False
        # Plan 04 Phase A: absolute paths classified GENERATED/
        # SUSPECTED_GENERATED during the last analyze() call.
        self._generated_paths: set = set()

    def use_git_friction(self, repo_root: Optional[Path] = None) -> None:
        """
        Enable churn/author/bugfix-density friction collection from
        `repo_root` (default: the path passed to `analyze()`). Degrades
        gracefully to no telemetry outside a git repo.
        """
        self._use_friction = True
        if repo_root is not None:
            self._friction_by_file = collect_friction(Path(repo_root))

    def set_centrality_provider(
        self, provider: Optional[CentralityProvider]
    ) -> None:
        """
        Wire an afferent-percentile centrality provider (Plan 03 Phase B ->
        Plan 02 Exposure Factor). Pass None to unwire (multiplier 1.0).
        """
        self.centrality_provider = provider
        self.aggregator.centrality_provider = provider

    def use_dependency_graph(self, scan_path) -> None:
        """
        Convenience: build the shared dependency graph for `scan_path` and
        wire its centrality provider into debt exposure multipliers.
        """
        from Asgard.Bragi.Dependencies.services.graph_service import (
            DependencyGraphService,
        )
        service = DependencyGraphService()
        self.set_centrality_provider(service.centrality_provider(scan_path))

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

        # Plan 04 Phase A: stamp context on every item and exclude
        # GENERATED/SUSPECTED_GENERATED files from the debt report entirely
        # (a category error in maintainability metrics); test cases are
        # exempt from documentation debt (Plan 04 Sec.3.2).
        self._stamp_and_filter_context(report)

        report.total_lines_of_code = count_lines_of_code(
            path, self.config, exclude_paths=self._generated_paths
        )
        if report.total_lines_of_code > 0:
            report.debt_ratio = report.total_debt_hours / report.total_lines_of_code * 1000

        # Plan 02 Phase D: collect friction telemetry for this scan root if
        # not already wired via use_git_friction(repo_root=...).
        if self._use_friction and not self._friction_by_file:
            self._friction_by_file = collect_friction(path)
        interest_by_file = compute_interest_scores(self._friction_by_file)

        # Churn/age modulation (DEEPTHINK_07): dormant files ("Sleeping
        # Bear") are downgraded one severity tier and tagged
        # fix_when_touching; high-metric + high-churn files ("Minefield")
        # retain maximum severity.
        if self._friction_by_file:
            for item in report.debt_items:
                friction = self._friction_by_file.get(item.file_path)
                severity = item.severity if isinstance(item.severity, str) else item.severity.value
                high_metric = severity in ("high", "critical")
                if is_minefield(friction, high_metric):
                    continue
                if is_sleeping_bear(friction):
                    item.severity = DebtSeverity(SEVERITY_DOWNGRADE.get(severity, severity))
                    item.remediation_strategy = (
                        (item.remediation_strategy + " " if item.remediation_strategy else "")
                        + "[fix_when_touching: file dormant, low interest]"
                    ).strip()

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
            interest = interest_by_file.get(item.file_path)
            if interest is not None:
                item.interest_rate = interest
                # priority = interest x non_remediation_factor / remediation_minutes
                item.priority_score_override = (
                    interest * item.non_remediation_factor / max(minutes, 1.0)
                )
        report.tdr_percent = compute_tdr_percent(
            aggregated.total_minutes, report.total_lines_of_code)

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

    def analyze_delta(
        self, path: Path, changed_files: Optional[List[Path]] = None
    ) -> DeltaResult:
        """
        Incremental debt analysis (Plan 02 Phase E / RESEARCH_15).

        Only files whose SHA-256 content hash changed since the last run
        (or those explicitly passed via `changed_files`, e.g. from a PR
        diff for Plan 06's gating) are re-analyzed; the persisted project
        total in `.asgard_cache/bragi_debt_state.json` is updated
        arithmetically rather than by rescanning the whole tree.

        Covers code-complexity and documentation debt (the two categories
        that are naturally per-file); design/test/dependency debt require
        whole-project context and stay on the full `analyze()` path.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        all_files = [
            f for f in path.rglob("*")
            if f.is_file() and should_analyze_file(f.name, self.config)
        ]
        all_current_keys = set()
        for f in all_files:
            try:
                all_current_keys.add(str(f.resolve().relative_to(path.resolve())))
            except ValueError:
                continue

        state = load_state(path)
        to_analyze = changed_files if changed_files is not None else self._changed_since(path, all_files, state)

        file_items: Dict[str, List[DebtItem]] = {}
        for file_path in to_analyze:
            file_path = Path(file_path)
            try:
                rel = str(file_path.resolve().relative_to(path.resolve()))
            except ValueError:
                rel = str(file_path)
            items: List[DebtItem] = []
            items.extend(analyze_file_complexity(file_path, self.config))
            undocumented = find_undocumented_functions(file_path)
            if undocumented:
                items.append(DebtItem(
                    debt_type=DebtType.DOCUMENTATION,
                    file_path=str(file_path.absolute()),
                    line_number=undocumented[0][1],
                    description=f"{len(undocumented)} undocumented public functions",
                    severity=DebtSeverity.MEDIUM if len(undocumented) > 5 else DebtSeverity.LOW,
                    effort_hours=self.config.effort_models.documentation_factor * len(undocumented),
                    business_impact=get_business_impact(str(file_path), self.config),
                    interest_rate=self.config.interest_rates.poor_docs,
                    remediation_strategy="Add docstrings to public functions following project standards",
                ))
            for item in items:
                minutes = self.remediation_model.minutes_for(item)
                item.effort_interval = self._item_interval(minutes)
                item.non_remediation_factor = self.remediation_model.non_remediation_factor(item)
            file_items[rel] = items

        delta = apply_delta(path, state, file_items, all_current_keys)
        save_state(path, state)
        return delta

    @staticmethod
    def _changed_since(path: Path, all_files: List[Path], state) -> List[Path]:
        from Asgard.Bragi.Quality.services._debt_state_store import changed_files as _changed
        return _changed(path, all_files, state)

    def _stamp_and_filter_context(self, report: DebtReport) -> None:
        """
        Classify every debt item's file (Plan 04 Phase A) and:
          - drop items in GENERATED/SUSPECTED_GENERATED files entirely
            (category error in maintainability metrics);
          - drop DOCUMENTATION-type items in TEST files (test cases are
            docstring-exempt; only test infrastructure is doc-mandatory,
            which the analyzer cannot yet distinguish from a plain test
            case, so the conservative choice is full exemption).
        Recomputes total_debt_hours / debt_by_type / debt_by_severity from
        the filtered item list so aggregates stay consistent.
        """
        self._generated_paths = set()
        kept: List[DebtItem] = []
        classify_cache: Dict[str, str] = {}
        for item in report.debt_items:
            file_path = item.file_path
            if file_path not in classify_cache:
                try:
                    context = classify(file_path).value
                except Exception:
                    context = CodeContext.PRODUCTION.value
                classify_cache[file_path] = context
            item.context = classify_cache[file_path]

            if item.context in (CodeContext.GENERATED.value, CodeContext.SUSPECTED_GENERATED.value):
                self._generated_paths.add(os.path.abspath(file_path))
                continue
            debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
            if item.context == CodeContext.TEST.value and debt_type == DebtType.DOCUMENTATION.value:
                continue
            kept.append(item)

        report.debt_items = kept
        report.total_debt_hours = 0.0
        report.debt_by_type = {}
        report.debt_by_severity = {}
        for item in kept:
            report.total_debt_hours += item.effort_hours
            debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
            report.debt_by_type[debt_type] = report.debt_by_type.get(debt_type, 0.0) + item.effort_hours
            severity = item.severity if isinstance(item.severity, str) else item.severity.value
            report.debt_by_severity[severity] = report.debt_by_severity.get(severity, 0) + 1

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

        # High-Yield Refactors (DEEPTHINK_05 Sec.3 dashboard): top-N items by
        # friction-derived priority score, only when telemetry was available.
        friction_ranked = [
            item for item in report.prioritized_items
            if item.priority_score_override is not None
        ]
        for item in friction_ranked[:5]:
            priorities.append(
                f"High-Yield Refactor: {item.location} - {item.description} "
                f"(priority {item.priority_score:.2f})"
            )

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
