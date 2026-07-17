import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from Asgard.Bragi.Quality.models.debt_models import DebtConfig
from Asgard.Bragi.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer as _TechDebtAnalyzer
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService as _StaticSecuritySvc
from Asgard.Bragi.Ratings.models.ratings_models import RatingsConfig
from Asgard.Bragi.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Bragi.Quality.models.documentation_models import DocumentationConfig
from Asgard.Bragi.Quality.services.documentation_scanner import DocumentationScanner
from Asgard.Reporting.History.services.history_store import HistoryStore
from Asgard.Reporting.History.models.history_models import AnalysisSnapshot, MetricSnapshot


def _save_ratings_to_history(project_path: str, ratings) -> None:
    store = HistoryStore()
    metrics = [
        MetricSnapshot(metric_name="maintainability_score", value=float(ratings.maintainability.score), unit="score"),
        MetricSnapshot(metric_name="reliability_score", value=float(ratings.reliability.score), unit="score"),
        MetricSnapshot(metric_name="security_score", value=float(ratings.security.score), unit="score"),
    ]
    rating_values = {
        "maintainability": str(ratings.maintainability.rating),
        "reliability": str(ratings.reliability.rating),
        "security": str(ratings.security.rating),
    }
    snapshot = AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        project_path=project_path,
        scan_timestamp=datetime.now(),
        metrics=metrics,
        ratings=rating_values,
    )
    store.save_snapshot(snapshot)


def _save_gate_to_history(project_path: str, gate_result, ratings) -> None:
    store = HistoryStore()
    metrics: List[MetricSnapshot] = []
    if ratings is not None:
        metrics.extend([
            MetricSnapshot(metric_name="maintainability_score", value=float(ratings.maintainability.score), unit="score"),
            MetricSnapshot(metric_name="reliability_score", value=float(ratings.reliability.score), unit="score"),
            MetricSnapshot(metric_name="security_score", value=float(ratings.security.score), unit="score"),
        ])
    gate_status = str(getattr(gate_result, "status", "unknown")).lower()
    rating_values = {}
    if ratings is not None:
        rating_values = {
            "maintainability": str(ratings.maintainability.rating),
            "reliability": str(ratings.reliability.rating),
            "security": str(ratings.security.rating),
        }
    snapshot = AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        project_path=project_path,
        scan_timestamp=datetime.now(),
        metrics=metrics,
        quality_gate_status=gate_status,
        ratings=rating_values,
    )
    store.save_snapshot(snapshot)


def run_ratings_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        debt_config = DebtConfig(scan_path=scan_path)
        debt_analyzer = _TechDebtAnalyzer(debt_config)
        debt_report = debt_analyzer.analyze(scan_path)

        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        config = RatingsConfig(scan_path=scan_path)
        calculator = RatingsCalculator(config)
        ratings = calculator.calculate_from_reports(
            scan_path=str(scan_path),
            debt_report=debt_report,
            security_report=security_report,
        )

        if getattr(args, "history", False):
            try:
                _save_ratings_to_history(str(scan_path), ratings)
            except Exception as hist_err:
                print(f"Warning: could not save to history: {hist_err}")

        if args.format == "json":
            output = {
                "scan_path": ratings.scan_path,
                "scanned_at": ratings.scanned_at.isoformat(),
                "overall_rating": ratings.overall_rating,
                "maintainability": {
                    "rating": ratings.maintainability.rating,
                    "score": ratings.maintainability.score,
                    "rationale": ratings.maintainability.rationale,
                    "issues_count": ratings.maintainability.issues_count,
                },
                "reliability": {
                    "rating": ratings.reliability.rating,
                    "score": ratings.reliability.score,
                    "rationale": ratings.reliability.rationale,
                    "issues_count": ratings.reliability.issues_count,
                },
                "security": {
                    "rating": ratings.security.rating,
                    "score": ratings.security.score,
                    "rationale": ratings.security.rationale,
                    "issues_count": ratings.security.issues_count,
                },
            }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL QUALITY RATINGS REPORT",
                "=" * 70,
                "",
                f"  Scan Path:           {ratings.scan_path}",
                f"  Calculated At:       {ratings.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"  Overall Rating:      [{ratings.overall_rating}]",
                "",
                "-" * 70,
                f"  Maintainability:     [{ratings.maintainability.rating}]",
                f"    {ratings.maintainability.rationale}",
                f"  Reliability:         [{ratings.reliability.rating}]",
                f"    {ratings.reliability.rationale}",
                f"  Security:            [{ratings.security.rating}]",
                f"    {ratings.security.rationale}",
                "",
                "=" * 70,
            ]
            print("\n".join(lines))

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def _security_findings_to_gate(security_report) -> List:
    """Coerce StaticSecurityService sub-report findings into GateFindings."""
    from Asgard.Bragi.QualityGate.models.quality_gate_models import GateFinding

    gate_findings = []
    for attr in (
        "secrets_report", "vulnerability_report", "crypto_report",
        "access_report", "auth_report", "headers_report", "tls_report",
        "container_report", "infrastructure_report",
    ):
        sub = getattr(security_report, attr, None)
        if sub is None or not hasattr(sub, "findings"):
            continue
        for f in sub.findings:
            severity = str(getattr(f, "severity", "medium")).lower()
            if severity not in ("critical", "high", "medium", "low", "info"):
                severity = "medium"
            gate_findings.append(GateFinding(
                rule_id=str(
                    getattr(f, "rule_id", None)
                    or getattr(f, "finding_type", None)
                    or attr
                ),
                file_path=str(getattr(f, "file_path", "") or ""),
                line=getattr(f, "line_number", None),
                severity=severity,
                confidence=float(getattr(f, "confidence", 1.0) or 1.0),
                message=str(
                    getattr(f, "title", None)
                    or getattr(f, "description", "")
                    or ""
                ),
                snippet=str(getattr(f, "code_snippet", "") or ""),
            ))
    return gate_findings


def _run_differential_gate(args, scan_path: Path, security_report) -> int:
    """Evaluate and print the differential gate. Returns exit contribution."""
    evaluator = QualityGateEvaluator()
    tier = getattr(args, "tier", None)
    mode = "diff" if (getattr(args, "diff", False) or tier == "pr") else "baseline"
    findings = _security_findings_to_gate(security_report)
    result = evaluator.evaluate_differential(
        findings,
        project_path=scan_path,
        base_branch=getattr(args, "base", "main"),
        mode=mode,
    )
    raw_status = getattr(result, "status", "not_evaluated")
    status = str(getattr(raw_status, "value", raw_status)).lower()
    if args.format == "json":
        payload = {
            "differential_gate": {
                "status": status,
                "mode": mode,
                "tier": tier,
                "base": getattr(args, "base", "main"),
                "baseline_available": result.baseline_available,
                "new_findings": len(result.new_findings),
                "blocking_findings": len(result.blocking_findings),
                "advisory_findings": len(result.advisory_findings),
                "suppressed_findings": len(result.suppressed_findings),
                "preexisting_count": result.preexisting_count,
            }
        }
        print(json.dumps(payload, indent=2))
    else:
        lines = [
            "",
            "-" * 70,
            "  DIFFERENTIAL GATE (clean as you code)",
            "-" * 70,
            "",
            f"  Mode:      {mode}" + (f" (tier: {tier})" if tier else ""),
            f"  Base:      {getattr(args, 'base', 'main')}",
            f"  Status:    [{status.upper()}]",
            f"  Baseline:  {'available' if result.baseline_available else 'NOT AVAILABLE (gate not evaluated)'}",
            f"  New: {len(result.new_findings)}  Blocking: {len(result.blocking_findings)}"
            f"  Advisory: {len(result.advisory_findings)}"
            f"  Pre-existing: {result.preexisting_count}",
        ]
        for f in result.blocking_findings[:20]:
            lines.append(
                f"    [BLOCK] {f.rule_id} {f.file_path}:{f.line or '?'} {f.message}"
            )
        lines.append("")
        print("\n".join(lines))
    return 1 if status == "failed" else 0


def run_gate_evaluation(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    try:
        debt_config = DebtConfig(scan_path=scan_path)
        debt_analyzer = _TechDebtAnalyzer(debt_config)
        debt_report = debt_analyzer.analyze(scan_path)

        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        ratings_calculator = RatingsCalculator()
        ratings = ratings_calculator.calculate_from_reports(
            scan_path=str(scan_path),
            debt_report=debt_report,
            security_report=security_report,
        )

        doc_scanner = DocumentationScanner()
        doc_report = doc_scanner.scan(scan_path)

        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        result = evaluator.evaluate_from_reports(
            gate,
            ratings=ratings,
            documentation_report=doc_report,
            security_report=security_report,
            debt_report=debt_report,
            scan_path=str(scan_path),
        )

        if args.format == "json":
            output = {
                "gate_name": result.gate_name,
                "status": result.status,
                "summary": result.summary,
                "scan_path": result.scan_path,
                "evaluated_at": result.evaluated_at.isoformat(),
                "condition_results": [
                    {
                        "metric": r.condition.metric,
                        "operator": r.condition.operator,
                        "threshold": r.condition.threshold,
                        "actual_value": r.actual_value,
                        "passed": r.passed,
                        "error_on_fail": r.condition.error_on_fail,
                        "message": r.message,
                    }
                    for r in result.condition_results
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            status_str = str(result.status).upper()
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL QUALITY GATE EVALUATION",
                "=" * 70,
                "",
                f"  Gate:         {result.gate_name}",
                f"  Scan Path:    {result.scan_path}",
                f"  Evaluated At: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"  Status:       [{status_str}]",
                f"  Summary:      {result.summary}",
                "",
                "-" * 70,
                "  CONDITION RESULTS",
                "-" * 70,
                "",
            ]
            for r in result.condition_results:
                pass_marker = "[PASS]" if r.passed else ("[FAIL]" if r.condition.error_on_fail else "[WARN]")
                lines.append(f"  {pass_marker} {r.message}")
                if verbose and r.condition.description:
                    lines.append(f"         {r.condition.description}")
            lines.extend(["", "=" * 70])
            print("\n".join(lines))

        if getattr(args, "history", False):
            try:
                _save_gate_to_history(str(scan_path), result, ratings)
            except Exception as hist_err:
                print(f"Warning: could not save to history: {hist_err}")

        exit_code = 1 if str(result.status).lower() == "failed" else 0

        # Differential ("clean as you code") gate: opt-in via --diff/--tier.
        if getattr(args, "diff", False) or getattr(args, "tier", None):
            try:
                exit_code = max(
                    exit_code,
                    _run_differential_gate(args, scan_path, security_report),
                )
            except Exception as diff_err:
                print(f"Warning: differential gate failed to evaluate: {diff_err}")

        return exit_code

    except Exception as e:
        print(f"Error: {e}")
        return 1
