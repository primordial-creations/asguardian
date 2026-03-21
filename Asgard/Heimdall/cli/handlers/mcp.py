import argparse
import traceback as _traceback
from pathlib import Path

from Asgard.Dashboard.models.dashboard_models import DashboardConfig
from Asgard.Dashboard.services.dashboard_server import DashboardServer
from Asgard.MCP.models.mcp_models import MCPServerConfig
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer


def run_mcp_server(args: argparse.Namespace, verbose: bool = False) -> int:
    host = getattr(args, "host", "localhost")
    port = int(getattr(args, "port", 8765))
    project_path = getattr(args, "project_path", ".")

    config = MCPServerConfig(
        host=host,
        port=port,
        project_path=str(Path(project_path).resolve()),
    )

    try:
        server = AsgardMCPServer(config)
        server.run()
        return 0
    except Exception as exc:
        print(f"Error starting MCP server: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def run_dashboard(args: argparse.Namespace, verbose: bool = False) -> int:
    config = DashboardConfig(
        host=args.host,
        port=args.port,
        project_path=args.path,
        open_browser=not args.no_open_browser,
    )
    server = DashboardServer(config)
    server.run()
    return 0
