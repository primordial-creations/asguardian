"""
Asgard MCP Server

Implements a Model Context Protocol (MCP) JSON-RPC server that exposes
Asgard analysis capabilities to AI agents. Uses Python's stdlib http.server
module — no external network dependencies required.

Exposed tools:
    asgard_quality_analyze   - Run quality analysis
    asgard_security_scan     - Run security scan
    asgard_quality_gate      - Evaluate quality gate
    asgard_ratings           - Calculate A-E ratings
    asgard_sbom              - Generate SBOM
    asgard_list_issues       - List tracked issues
    asgard_compliance_report - Get OWASP/CWE compliance
"""

import json
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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
from Asgard.MCP.models.mcp_models import (
    MCPRequest,
    MCPResponse,
    MCPServerConfig,
    MCPTool,
    MCPToolParam,
)


_SERVER_INFO = {
    "name": "asguardian-mcp",
    "version": "1.0.0",
    "description": "Asgard code analysis MCP server",
}

_CAPABILITIES: Dict[str, Any] = {
    "tools": {},
}


def _build_tool_list() -> List[MCPTool]:
    """Return the list of tools exposed by this MCP server."""
    return [
        MCPTool(
            name="asgard_quality_analyze",
            description="Run Asgard quality analysis on a directory. Returns file counts, violation counts by type, and top violations.",
            parameters=[
                MCPToolParam(name="path", description="Path to the directory to analyze.", type="string", required=True),
                MCPToolParam(name="checks", description="List of checks to run (e.g. ['complexity', 'duplication', 'smells']). Omit for all checks.", type="array", required=False, default=None),
            ],
        ),
        MCPTool(
            name="asgard_security_scan",
            description="Run Asgard security scan on a directory. Returns vulnerability counts by severity and top findings.",
            parameters=[
                MCPToolParam(name="path", description="Path to the directory to scan.", type="string", required=True),
                MCPToolParam(name="scan_type", description="Type of scan: 'secrets', 'vulnerabilities', 'hotspots', or 'all'. Defaults to 'all'.", type="string", required=False, default="all"),
            ],
        ),
        MCPTool(
            name="asgard_quality_gate",
            description="Evaluate the Asgard quality gate against analysis results for a directory.",
            parameters=[
                MCPToolParam(name="path", description="Path to the directory to evaluate.", type="string", required=True),
                MCPToolParam(name="gate_name", description="Quality gate name to use. Defaults to 'Asgard Way'.", type="string", required=False, default="Asgard Way"),
            ],
        ),
        MCPTool(
            name="asgard_ratings",
            description="Calculate A-E quality ratings (security, reliability, maintainability) for a directory.",
            parameters=[
                MCPToolParam(name="path", description="Path to the directory to rate.", type="string", required=True),
            ],
        ),
        MCPTool(
            name="asgard_sbom",
            description="Generate a Software Bill of Materials (SBOM) for a project directory.",
            parameters=[
                MCPToolParam(name="path", description="Path to the project directory.", type="string", required=True),
                MCPToolParam(name="format", description="SBOM format: 'spdx' or 'cyclonedx'. Defaults to 'cyclonedx'.", type="string", required=False, default="cyclonedx"),
            ],
        ),
        MCPTool(
            name="asgard_list_issues",
            description="List tracked issues for a project.",
            parameters=[
                MCPToolParam(name="path", description="Path to the project directory.", type="string", required=True),
                MCPToolParam(name="status", description="Issue status filter (e.g. 'open', 'confirmed', 'resolved'). Defaults to 'open'.", type="string", required=False, default="open"),
                MCPToolParam(name="limit", description="Maximum number of issues to return. Defaults to 20.", type="integer", required=False, default=20),
            ],
        ),
        MCPTool(
            name="asgard_compliance_report",
            description="Get OWASP Top 10 or CWE Top 25 compliance report for a directory.",
            parameters=[
                MCPToolParam(name="path", description="Path to the directory to analyze.", type="string", required=True),
                MCPToolParam(name="standard", description="Compliance standard: 'owasp' or 'cwe'. Defaults to 'owasp'.", type="string", required=False, default="owasp"),
            ],
        ),
    ]


class AsgardMCPServer:
    """
    MCP server exposing Asgard analysis tools via JSON-RPC over HTTP.

    The server handles POST requests to / with JSON-RPC 2.0 bodies.
    All MCP protocol methods (initialize, tools/list, tools/call) are
    dispatched through handle_request().
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._tools = _build_tool_list()

    def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        Route a JSON-RPC request to the appropriate handler method.

        Args:
            request: Parsed MCPRequest instance.

        Returns:
            MCPResponse with either a result or an error payload.
        """
        method = request.method
        req_id = request.id
        params = request.params or {}

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params)
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            else:
                return MCPResponse(
                    id=req_id,
                    error={"code": -32601, "message": f"Method not found: {method}"},
                )
        except Exception as exc:
            return MCPResponse(
                id=req_id,
                error={"code": -32603, "message": "Internal error", "data": str(exc)},
            )

        return MCPResponse(id=req_id, result=result)

    def run(self) -> None:
        """Start the HTTP/JSON-RPC server and block until interrupted."""
        server_instance = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b""

                try:
                    body = json.loads(raw_body.decode("utf-8"))
                    request = MCPRequest(**body)
                    response = server_instance.handle_request(request)
                    response_body = response.json().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                except json.JSONDecodeError:
                    error_response = MCPResponse(
                        id=None,
                        error={"code": -32700, "message": "Parse error"},
                    )
                    body_bytes = error_response.json().encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body_bytes)))
                    self.end_headers()
                    self.wfile.write(body_bytes)
                except Exception:
                    error_response = MCPResponse(
                        id=None,
                        error={"code": -32603, "message": "Internal server error"},
                    )
                    body_bytes = error_response.json().encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body_bytes)))
                    self.end_headers()
                    self.wfile.write(body_bytes)

            def log_message(self, fmt: str, *args: Any) -> None:
                # Suppress default access log output
                pass

        httpd = HTTPServer((self._config.host, self._config.port), _Handler)
        print(f"Asgard MCP server listening on {self._config.host}:{self._config.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Asgard MCP server stopped.")
        finally:
            httpd.server_close()

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the MCP initialize handshake."""
        return {
            "serverInfo": _SERVER_INFO,
            "capabilities": _CAPABILITIES,
            "protocolVersion": "2024-11-05",
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the list of available tools."""
        tools_payload = []
        for tool in self._tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        param.name: {
                            "type": param.type,
                            "description": param.description,
                        }
                        for param in tool.parameters
                    },
                    "required": [p.name for p in tool.parameters if p.required],
                },
            }
            tools_payload.append(tool_dict)
        return {"tools": tools_payload}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a tools/call request to the appropriate tool implementation."""
        tool_name = params.get("name", "")
        tool_params = params.get("arguments", {})

        dispatch: Dict[str, Any] = {
            "asgard_quality_analyze": self._tool_quality_analyze,
            "asgard_security_scan": self._tool_security_scan,
            "asgard_quality_gate": self._tool_quality_gate,
            "asgard_ratings": self._tool_ratings,
            "asgard_sbom": self._tool_sbom,
            "asgard_list_issues": self._tool_list_issues,
            "asgard_compliance_report": self._tool_compliance_report,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            }

        try:
            result = handler(tool_params)
            return {
                "content": [{"type": "text", "text": json.dumps(result, default=str, indent=2)}],
            }
        except Exception as exc:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {exc}\n{traceback.format_exc()}"}],
            }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_quality_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run quality analysis and return a summary."""
        path = params.get("path", self._config.project_path)
        scan_path = Path(path).resolve()

        config = AnalysisConfig(scan_path=scan_path)
        analyzer = FileAnalyzer(config)
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

    def _tool_security_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run security scan and return a summary."""
        path = params.get("path", self._config.project_path)
        scan_path = Path(path).resolve()

        config = SecurityScanConfig(scan_path=scan_path)
        service = StaticSecurityService(config)
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

    def _tool_quality_gate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the quality gate and return gate status."""
        path = params.get("path", self._config.project_path)
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

    def _tool_ratings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate A-E ratings and return the result."""
        path = params.get("path", self._config.project_path)
        scan_path = Path(path).resolve()

        debt_config = DebtConfig(scan_path=scan_path)
        debt_analyzer = TechnicalDebtAnalyzer(debt_config)
        debt_report = debt_analyzer.analyze(scan_path)

        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = StaticSecurityService(sec_config)
        security_report = sec_service.scan(str(scan_path))

        config = RatingsConfig(scan_path=scan_path)
        calculator = RatingsCalculator(config)
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

    def _tool_sbom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an SBOM and return the document."""
        path = params.get("path", self._config.project_path)
        fmt_str = params.get("format", "cyclonedx")
        scan_path = Path(path).resolve()

        fmt = SBOMFormat.CYCLONEDX if fmt_str == "cyclonedx" else SBOMFormat.SPDX
        config = SBOMConfig(scan_path=scan_path, output_format=fmt)
        generator = SBOMGenerator(config)
        document = generator.generate(str(scan_path))

        if fmt == SBOMFormat.CYCLONEDX:
            return cast(Dict[str, Any], generator.to_cyclonedx_json(document))
        return cast(Dict[str, Any], generator.to_spdx_json(document))

    def _tool_list_issues(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List tracked issues for a project."""
        path = params.get("path", self._config.project_path)
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

    def _tool_compliance_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an OWASP or CWE compliance report."""
        path = params.get("path", self._config.project_path)
        standard = params.get("standard", "owasp")
        scan_path = Path(path).resolve()

        config = SecurityScanConfig(scan_path=scan_path)
        service = StaticSecurityService(config)
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
