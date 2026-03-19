"""
Asgard MCP - Model Context Protocol Server

Exposes Asgard analysis capabilities to AI agents via a JSON-RPC MCP server.
Uses Python stdlib http.server - no external network dependencies required.

Exposed tools:
    asgard_quality_analyze   - Run quality analysis
    asgard_security_scan     - Run security scan
    asgard_quality_gate      - Evaluate quality gate
    asgard_ratings           - Calculate A-E ratings
    asgard_sbom              - Generate SBOM
    asgard_list_issues       - List tracked issues
    asgard_compliance_report - Get OWASP/CWE compliance

Usage:
    asguardian-mcp --port 8765 --path ./src

Programmatic Usage:
    from Asgard.MCP import AsgardMCPServer, MCPServerConfig

    config = MCPServerConfig(host="localhost", port=8765, project_path="./src")
    server = AsgardMCPServer(config)
    server.run()
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.MCP.models.mcp_models import (
    MCPRequest,
    MCPResponse,
    MCPServerConfig,
    MCPTool,
    MCPToolParam,
)
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer

__all__ = [
    "AsgardMCPServer",
    "MCPRequest",
    "MCPResponse",
    "MCPServerConfig",
    "MCPTool",
    "MCPToolParam",
]
