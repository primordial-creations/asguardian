"""
Asgard Dashboard Web Adapter

Provides a lightweight HTTP server built on the Python standard library
http.server module. This module is a web adapter (infrastructure layer):
it parses HTTP requests, wires up concrete repository implementations,
and delegates business logic to the DataCollector domain service.

Concrete dependency wiring is performed here rather than in domain services,
satisfying the Dependency Inversion Principle.
"""

import http.server
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from Asgard.Dashboard.models.dashboard_models import DashboardConfig
from Asgard.Dashboard.services.data_collector import DataCollector
from Asgard.Dashboard.services.html_renderer import HtmlRenderer
from Asgard.Shared.Issues.services._issue_repository import SQLiteIssueRepository
from Asgard.Reporting.History.services._history_repository import SQLiteHistoryRepository


def _build_repositories(config: DashboardConfig):
    """
    Construct concrete repository instances from the dashboard configuration.

    Args:
        config: DashboardConfig instance holding optional db_path override.

    Returns:
        Tuple of (SQLiteIssueRepository, SQLiteHistoryRepository).
    """
    if config.db_path is not None:
        base = Path(config.db_path)
        issue_repo = SQLiteIssueRepository(db_path=base / "issues.db")
        history_repo = SQLiteHistoryRepository(db_path=base / "history.db")
    else:
        issue_repo = SQLiteIssueRepository()
        history_repo = SQLiteHistoryRepository()
    return issue_repo, history_repo


def _make_handler_class(config: DashboardConfig) -> type:
    """
    Factory that returns a BaseHTTPRequestHandler subclass bound to the given config.

    A factory is used so the handler can close over the config without relying on
    global state or dynamic attribute injection. Concrete repository instances are
    created once per handler class construction and reused across requests.

    Args:
        config: DashboardConfig instance shared across all requests.

    Returns:
        A BaseHTTPRequestHandler subclass.
    """
    issue_repo, history_repo = _build_repositories(config)

    class _AsgardHandler(http.server.BaseHTTPRequestHandler):
        """HTTP request handler for the Asgard dashboard."""

        _config = config
        _issue_repository = issue_repo
        _history_repository = history_repo
        _renderer = HtmlRenderer()

        def log_message(self, format: str, *args) -> None:  # type: ignore[override]
            """Override to write access log to stdout in a clean format."""
            print(f"[asguardian-dashboard] {self.address_string()} {format % args}")

        def _send_html(self, html: str, status: int = 200) -> None:
            """Send an HTML response."""
            encoded = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_redirect(self, location: str) -> None:
            """Send a 302 redirect."""
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def do_GET(self) -> None:
            """Handle GET requests and dispatch to the appropriate page renderer."""
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            if path == "/refresh":
                self._send_redirect("/")
                return

            try:
                collector = DataCollector(
                    issue_repository=self._issue_repository,
                    history_repository=self._history_repository,
                )
                state = collector.collect(self._config.project_path)
            except Exception as exc:
                error_html = self._renderer.render_error(
                    f"Failed to collect dashboard data: {exc}"
                )
                self._send_html(error_html, status=500)
                return

            if path == "/" or path == "":
                html = self._renderer.render_overview(state)
                self._send_html(html)

            elif path == "/issues":
                status_filter = query.get("status", ["all"])[0]
                severity_filter = query.get("severity", ["all"])[0]
                html = self._renderer.render_issues(state, status_filter, severity_filter)
                self._send_html(html)

            elif path == "/history":
                html = self._renderer.render_history(state)
                self._send_html(html)

            else:
                error_html = self._renderer.render_error(
                    f"Page not found: {path}"
                )
                self._send_html(error_html, status=404)

    return _AsgardHandler


class DashboardServer:
    """
    Serves the Asgard web dashboard using Python's built-in http.server module.

    Usage:
        config = DashboardConfig(project_path="/path/to/project")
        DashboardServer(config).run()
    """

    def __init__(self, config: DashboardConfig) -> None:
        self._config = config

    def run(self) -> None:
        """
        Start the HTTP server and optionally open a browser tab.

        Blocks until the process is interrupted (Ctrl-C).
        """
        handler_class = _make_handler_class(self._config)
        server_address = (self._config.host, self._config.port)
        httpd = http.server.HTTPServer(server_address, handler_class)

        url = f"http://{self._config.host}:{self._config.port}/"
        print(f"Asgard dashboard running at {url}")
        print(f"Project: {self._config.project_path}")
        print("Press Ctrl-C to stop.")

        if self._config.open_browser:
            webbrowser.open(url)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard server stopped.")
        finally:
            httpd.server_close()
