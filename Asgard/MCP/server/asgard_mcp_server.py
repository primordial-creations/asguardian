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
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List

from Asgard.MCP.models.mcp_models import (
    MCPRequest,
    MCPResponse,
    MCPServerConfig,
    MCPTool,
    MCPToolParam,
)
from Asgard.MCP.server._mcp_tools import (
    tool_compliance_report,
    tool_list_issues,
    tool_quality_analyze,
    tool_quality_gate,
    tool_ratings,
    tool_sbom,
    tool_security_scan,
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
                pass

        httpd = HTTPServer((self._config.host, self._config.port), _Handler)
        print(f"Asgard MCP server listening on {self._config.host}:{self._config.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Asgard MCP server stopped.")
        finally:
            httpd.server_close()

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

        dispatch = {
            "asgard_quality_analyze": tool_quality_analyze,
            "asgard_security_scan": tool_security_scan,
            "asgard_quality_gate": tool_quality_gate,
            "asgard_ratings": tool_ratings,
            "asgard_sbom": tool_sbom,
            "asgard_list_issues": tool_list_issues,
            "asgard_compliance_report": tool_compliance_report,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            }

        try:
            result = handler(tool_params, self._config)
            return {
                "content": [{"type": "text", "text": json.dumps(result, default=str, indent=2)}],
            }
        except Exception as exc:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {exc}\n{traceback.format_exc()}"}],
            }
