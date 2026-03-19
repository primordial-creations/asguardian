"""MCP server package."""

import argparse

from Asgard.MCP.models.mcp_models import MCPServerConfig
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer


def main() -> None:
    """CLI entry point for the Asgard MCP server."""
    parser = argparse.ArgumentParser(
        prog="asguardian-mcp",
        description="Asgard MCP server - exposes Asgard analysis tools to AI agents via JSON-RPC.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Default project path for analysis tools (default: current directory)",
    )
    args = parser.parse_args()

    config = MCPServerConfig(
        host=args.host,
        port=args.port,
        project_path=args.path,
    )
    server = AsgardMCPServer(config)
    server.run()


__all__ = [
    "AsgardMCPServer",
    "main",
]
