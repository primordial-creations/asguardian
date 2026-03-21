import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from Asgard.Heimdall.Quality.models.debt_models import DebtConfig
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer as _TechDebtAnalyzer
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService as _StaticSecuritySvc
from Asgard.Heimdall.Ratings.models.ratings_models import RatingsConfig
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.Quality.models.documentation_models import DocumentationConfig
from Asgard.Heimdall.Quality.services.documentation_scanner import DocumentationScanner
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

        return 1 if str(result.status).lower() == "failed" else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1
