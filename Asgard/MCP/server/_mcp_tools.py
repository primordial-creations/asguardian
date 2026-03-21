"""
Asgard MCP Server - Tool Implementations

Implements the individual tool handler functions called by AsgardMCPServer.
Each function takes a params dict and an MCPServerConfig and returns a result dict.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, cast

from Asgard.Heimdall.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat
from Asgard.Heimdall.Dependencies.services.sbom_generator import SBOMGenerator
from Asgard.Heimdall.Issues.models.issue_models import IssueFilter, IssueStatus
from Asgard.Heimdall.Issues.services.issue_tracker import IssueTracker
from Asgard.Heimdall.Quality.models.analysis_models import AnalysisConfig
from Asgard.Heimdall.Quality.models.debt_models import DebtConfig
from Asgard.Heimdall.Quality.services.file_length_analyzer import FileAnalyzer
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.Ratings.models.ratings_models import RatingsConfig
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService
from Asgard.MCP.models.mcp_models import MCPServerConfig


def tool_quality_analyze(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Run quality analysis and return a summary."""
    path = params.get("path", config.project_path)
    scan_path = Path(path).resolve()

    analysis_config = AnalysisConfig(scan_path=scan_path)
    analyzer = FileAnalyzer(analysis_config)
    result = analyzer.analyze()

    top_violations = []
    if hasattr(result, "violations"):
        for v in list(result.violations)[:10]:
            top_violations.append({
                "file": str(getattr(v, "file_path", "")),
                "line": getattr(v, "line_number", 0),
                "message": getattr(v, "message", ""),
                "severity": str(getattr(v, "severity", "")),
            })

    return {
        "scan_path": str(scan_path),
        "analyzed_at": datetime.now().isoformat(),
        "total_files": getattr(result, "total_files", 0),
        "total_violations": getattr(result, "total_violations", 0),
        "violations_by_severity": getattr(result, "violations_by_severity", {}),
        "top_violations": top_violations,
    }


def tool_security_scan(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Run security scan and return a summary."""
    path = params.get("path", config.project_path)
    scan_path = Path(path).resolve()

    scan_config = SecurityScanConfig(scan_path=scan_path)
    service = StaticSecurityService(scan_config)
    report = service.scan(str(scan_path))

    top_findings = []
    if hasattr(report, "findings"):
        for f in list(report.findings)[:10]:
            top_findings.append({
                "file": str(getattr(f, "file_path", "")),
                "line": getattr(f, "line_number", 0),
                "title": getattr(f, "title", ""),
                "severity": str(getattr(f, "severity", "")),
                "type": str(getattr(f, "vulnerability_type", "")),
            })

    return {
        "scan_path": str(scan_path),
        "scanned_at": datetime.now().isoformat(),
        "security_score": getattr(report, "security_score", 0),
        "total_findings": getattr(report, "total_findings", 0),
        "findings_by_severity": getattr(report, "findings_by_severity", {}),
        "top_findings": top_findings,
    }


def tool_quality_gate(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Evaluate the quality gate and return gate status."""
    path = params.get("path", config.project_path)
    scan_path = Path(path).resolve()

    debt_config = DebtConfig(scan_path=scan_path)
    debt_analyzer = TechnicalDebtAnalyzer(debt_config)
    debt_report = debt_analyzer.analyze(scan_path)

    sec_config = SecurityScanConfig(scan_path=scan_path)
    sec_service = StaticSecurityService(sec_config)
    security_report = sec_service.scan(str(scan_path))

    ratings_config = RatingsConfig(scan_path=scan_path)
    calculator = RatingsCalculator(ratings_config)
    ratings = calculator.calculate_from_reports(
        scan_path=str(scan_path),
        debt_report=debt_report,
        security_report=security_report,
    )

    evaluator = QualityGateEvaluator()
    gate = evaluator.get_default_gate()
    gate_result = evaluator.evaluate_from_reports(
        gate,
        ratings=ratings,
        security_report=security_report,
    )

    conditions = []
    if hasattr(gate_result, "condition_results"):
        for cr in gate_result.condition_results:
            conditions.append({
                "metric": str(getattr(cr, "metric", "")),
                "status": str(getattr(cr, "status", "")),
                "actual_value": getattr(cr, "actual_value", None),
                "threshold": getattr(cr, "threshold", None),
            })

    return {
        "scan_path": str(scan_path),
        "gate_name": getattr(gate, "name", "Asgard Way"),
        "status": str(getattr(gate_result, "status", "")),
        "passed": getattr(gate_result, "passed", False),
        "conditions": conditions,
        "evaluated_at": datetime.now().isoformat(),
    }


def tool_ratings(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Calculate A-E ratings and return the result."""
    path = params.get("path", config.project_path)
    scan_path = Path(path).resolve()

    debt_config = DebtConfig(scan_path=scan_path)
    debt_analyzer = TechnicalDebtAnalyzer(debt_config)
    debt_report = debt_analyzer.analyze(scan_path)

    sec_config = SecurityScanConfig(scan_path=scan_path)
    sec_service = StaticSecurityService(sec_config)
    security_report = sec_service.scan(str(scan_path))

    ratings_config = RatingsConfig(scan_path=scan_path)
    calculator = RatingsCalculator(ratings_config)
    ratings = calculator.calculate_from_reports(
        scan_path=str(scan_path),
        debt_report=debt_report,
        security_report=security_report,
    )

    return {
        "scan_path": str(scan_path),
        "overall_rating": getattr(ratings, "overall_rating", ""),
        "maintainability": {
            "rating": getattr(ratings.maintainability, "rating", ""),
            "score": getattr(ratings.maintainability, "score", 0),
            "rationale": getattr(ratings.maintainability, "rationale", ""),
        },
        "reliability": {
            "rating": getattr(ratings.reliability, "rating", ""),
            "score": getattr(ratings.reliability, "score", 0),
            "rationale": getattr(ratings.reliability, "rationale", ""),
        },
        "security": {
            "rating": getattr(ratings.security, "rating", ""),
            "score": getattr(ratings.security, "score", 0),
            "rationale": getattr(ratings.security, "rationale", ""),
        },
        "calculated_at": datetime.now().isoformat(),
    }


def tool_sbom(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Generate an SBOM and return the document."""
    path = params.get("path", config.project_path)
    fmt_str = params.get("format", "cyclonedx")
    scan_path = Path(path).resolve()

    fmt = SBOMFormat.CYCLONEDX if fmt_str == "cyclonedx" else SBOMFormat.SPDX
    sbom_config = SBOMConfig(scan_path=scan_path, output_format=fmt)
    generator = SBOMGenerator(sbom_config)
    document = generator.generate(str(scan_path))

    if fmt == SBOMFormat.CYCLONEDX:
        return cast(Dict[str, Any], generator.to_cyclonedx_json(document))
    return cast(Dict[str, Any], generator.to_spdx_json(document))


def tool_list_issues(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """List tracked issues for a project."""
    path = params.get("path", config.project_path)
    status_str = params.get("status", "open")
    limit = int(params.get("limit", 20))
    scan_path = str(Path(path).resolve())

    try:
        status = IssueStatus(status_str)
    except ValueError:
        status = IssueStatus.OPEN

    tracker = IssueTracker()
    issue_filter = IssueFilter(project_path=scan_path, statuses=[status], limit=limit)
    issues = tracker.list_issues(issue_filter)

    issue_list = []
    for issue in issues:
        issue_list.append({
            "issue_id": str(getattr(issue, "issue_id", "")),
            "rule_id": getattr(issue, "rule_id", ""),
            "file_path": getattr(issue, "file_path", ""),
            "line_number": getattr(issue, "line_number", 0),
            "severity": str(getattr(issue, "severity", "")),
            "status": str(getattr(issue, "status", "")),
            "title": getattr(issue, "title", ""),
            "created_at": str(getattr(issue, "created_at", "")),
        })

    return {
        "project_path": scan_path,
        "status_filter": status_str,
        "total_returned": len(issue_list),
        "issues": issue_list,
    }


def tool_compliance_report(params: Dict[str, Any], config: MCPServerConfig) -> Dict[str, Any]:
    """Generate an OWASP or CWE compliance report."""
    path = params.get("path", config.project_path)
    standard = params.get("standard", "owasp")
    scan_path = Path(path).resolve()

    scan_config = SecurityScanConfig(scan_path=scan_path)
    service = StaticSecurityService(scan_config)
    security_report = service.scan(str(scan_path))

    compliance_data: Dict[str, Any] = {
        "scan_path": str(scan_path),
        "standard": standard,
        "generated_at": datetime.now().isoformat(),
    }

    if standard == "owasp" and hasattr(security_report, "owasp_compliance"):
        owasp = security_report.owasp_compliance
        categories = {}
        if hasattr(owasp, "categories"):
            for cat in owasp.categories:
                categories[str(getattr(cat, "category_id", ""))] = {
                    "name": getattr(cat, "name", ""),
                    "grade": str(getattr(cat, "grade", "")),
                    "finding_count": getattr(cat, "finding_count", 0),
                }
        compliance_data["owasp_top10"] = categories
        compliance_data["overall_grade"] = str(getattr(owasp, "overall_grade", ""))
    elif standard == "cwe" and hasattr(security_report, "cwe_compliance"):
        cwe = security_report.cwe_compliance
        categories = {}
        if hasattr(cwe, "categories"):
            for cat in cwe.categories:
                categories[str(getattr(cat, "cwe_id", ""))] = {
                    "name": getattr(cat, "name", ""),
                    "grade": str(getattr(cat, "grade", "")),
                    "finding_count": getattr(cat, "finding_count", 0),
                }
        compliance_data["cwe_top25"] = categories
        compliance_data["overall_grade"] = str(getattr(cwe, "overall_grade", ""))
    else:
        compliance_data["note"] = (
            f"Compliance data for standard '{standard}' is not available in this scan result. "
            "Run 'heimdall security compliance' for a full report."
        )
        compliance_data["total_findings"] = getattr(security_report, "total_findings", 0)

    return compliance_data
