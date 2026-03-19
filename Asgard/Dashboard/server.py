"""
Asgard Dashboard CLI Entry Point

Entry point for the asguardian-dashboard command-line script.
"""

import argparse
import sys

from Asgard.Dashboard.models.dashboard_models import DashboardConfig
from Asgard.Dashboard.services.dashboard_server import DashboardServer


def main() -> None:
    """Parse CLI arguments and start the dashboard server."""
    parser = argparse.ArgumentParser(
        prog="asguardian-dashboard",
        description="Launch the Asgard web dashboard to browse code analysis results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  asguardian-dashboard --path ./my-project\n"
            "  asguardian-dashboard --path ./my-project --port 9090\n"
            "  asguardian-dashboard --path ./my-project --no-open-browser\n"
        ),
    )

    parser.add_argument(
        "--path",
        default=".",
        help="Project path to display in the dashboard (default: current directory)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to serve the dashboard on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not automatically open a browser tab on launch",
    )

    args = parser.parse_args()

    config = DashboardConfig(
        host=args.host,
        port=args.port,
        project_path=args.path,
        open_browser=not args.no_open_browser,
    )

    server = DashboardServer(config)
    server.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
