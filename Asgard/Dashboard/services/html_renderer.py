"""
Asgard Dashboard HTML Renderer

Generates all HTML pages for the web dashboard using Python f-strings only.
No external templating library is used.
"""

from pathlib import Path
from typing import List

from Asgard.Dashboard.models.dashboard_models import DashboardState, IssueSummaryData, RatingData
from Asgard.Dashboard.services._html_helpers import (
    gate_badge,
    rating_badge,
    rating_to_score,
    severity_badge,
    status_badge,
    truncate_path,
)
from Asgard.Dashboard.services._html_templates import EMBEDDED_CSS


class HtmlRenderer:
    """
    Generates HTML pages for the Asgard web dashboard.

    All rendering is done with Python f-strings. No external templating library is used.
    """

    def render_page(
        self,
        title: str,
        content: str,
        active_page: str,
        project_path: str,
    ) -> str:
        """
        Wrap content in a full HTML document with sidebar navigation and embedded CSS.

        Args:
            title: Page title shown in the browser tab.
            content: HTML fragment for the main content area.
            active_page: One of 'overview', 'issues', 'history'.
            project_path: Project path displayed in the sidebar.

        Returns:
            Complete HTML document as a string.
        """
        project_label = Path(project_path).name or project_path

        def nav_link(href: str, label: str, page_key: str) -> str:
            css_class = "active" if active_page == page_key else ""
            return f'<a href="{href}" class="{css_class}">{label}</a>'

        nav_html = (
            nav_link("/", "Overview", "overview")
            + nav_link("/issues", "Issues", "issues")
            + nav_link("/history", "History", "history")
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - Asgard Dashboard</title>
<style>
{EMBEDDED_CSS}
</style>
</head>
<body>
<nav class="sidebar">
  <div class="sidebar-header">
    <h1>Asgard</h1>
    <div class="sidebar-project" title="{project_path}">{project_label}</div>
  </div>
  <div class="sidebar-nav">
    {nav_html}
  </div>
  <div class="sidebar-footer">
    <a href="/refresh">Refresh</a>
  </div>
</nav>
<main class="main-content">
  {content}
</main>
<script>
(function() {{
  var selects = document.querySelectorAll('.filter-form select');
  selects.forEach(function(sel) {{
    sel.addEventListener('change', function() {{
      sel.closest('form').submit();
    }});
  }});
}})();
</script>
</body>
</html>"""

    def render_overview(self, state: DashboardState) -> str:
        """
        Render the overview page with quality gate, ratings, and issue summary cards.

        Args:
            state: DashboardState populated by DataCollector.

        Returns:
            Complete HTML document string.
        """
        gate_status = state.quality_gate_status or "unknown"
        gate_html = gate_badge(gate_status)

        ts_html = ""
        if state.last_analyzed:
            ts_html = f'<p class="ts" style="margin-top:8px;">Last analyzed: {state.last_analyzed.strftime("%Y-%m-%d %H:%M:%S")}</p>'

        ratings_html = ""
        if state.ratings:
            r = state.ratings
            ratings_html = f"""
<div class="section-title">Quality Ratings</div>
<div class="cards-grid">
  <div class="card">
    <div class="card-label">Maintainability</div>
    <div>{rating_badge(r.maintainability)}</div>
  </div>
  <div class="card">
    <div class="card-label">Reliability</div>
    <div>{rating_badge(r.reliability)}</div>
  </div>
  <div class="card">
    <div class="card-label">Security</div>
    <div>{rating_badge(r.security)}</div>
  </div>
  <div class="card">
    <div class="card-label">Overall</div>
    <div>{rating_badge(r.overall)}</div>
  </div>
</div>"""

        s = state.issue_summary
        issue_cards = f"""
<div class="section-title">Issue Summary</div>
<div class="cards-grid">
  <div class="card">
    <div class="card-label">Total Issues</div>
    <div class="card-value">{s.total}</div>
  </div>
  <div class="card">
    <div class="card-label">Open</div>
    <div class="card-value" style="color:#e67e22;">{s.open}</div>
  </div>
  <div class="card">
    <div class="card-label">Confirmed</div>
    <div class="card-value" style="color:#e74c3c;">{s.confirmed}</div>
  </div>
  <div class="card">
    <div class="card-label">Critical</div>
    <div class="card-value" style="color:#e74c3c;">{s.critical}</div>
  </div>
  <div class="card">
    <div class="card-label">High</div>
    <div class="card-value" style="color:#e67e22;">{s.high}</div>
  </div>
  <div class="card">
    <div class="card-label">Medium</div>
    <div class="card-value" style="color:#f39c12;">{s.medium}</div>
  </div>
  <div class="card">
    <div class="card-label">Low</div>
    <div class="card-value" style="color:#3498db;">{s.low}</div>
  </div>
</div>"""

        content = f"""
<h2 class="page-title">Overview</h2>
<div class="section-title">Quality Gate</div>
<div class="card" style="display:inline-block;margin-bottom:28px;">
  {gate_html}
  {ts_html}
</div>
{ratings_html}
{issue_cards}
"""
        return self.render_page("Overview", content, "overview", state.project_path)

    def render_issues(
        self,
        state: DashboardState,
        status_filter: str,
        severity_filter: str,
    ) -> str:
        """
        Render the issues page with filter bar and paginated issues table.

        Args:
            state: DashboardState populated by DataCollector.
            status_filter: Active status filter value ('all' or a specific status string).
            severity_filter: Active severity filter value ('all' or a specific severity string).

        Returns:
            Complete HTML document string.
        """
        issues = state.recent_issues

        if status_filter and status_filter != "all":
            issues = [i for i in issues if str(i.get("status", "")).lower() == status_filter.lower()]

        if severity_filter and severity_filter != "all":
            issues = [i for i in issues if str(i.get("severity", "")).lower() == severity_filter.lower()]

        total_count = len(issues)
        page_issues = issues[:50]

        status_options = [
            ("all", "All Statuses"),
            ("open", "Open"),
            ("confirmed", "Confirmed"),
            ("resolved", "Resolved"),
            ("false_positive", "False Positive"),
            ("wont_fix", "Wont Fix"),
        ]
        severity_options = [
            ("all", "All Severities"),
            ("critical", "Critical"),
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("info", "Info"),
        ]

        def build_options(options: list, current: str) -> str:
            parts = []
            for val, label in options:
                selected = ' selected' if val == current else ''
                parts.append(f'<option value="{val}"{selected}>{label}</option>')
            return "".join(parts)

        status_opts_html = build_options(status_options, status_filter or "all")
        severity_opts_html = build_options(severity_options, severity_filter or "all")

        filter_bar = f"""
<form method="get" action="/issues" class="filter-bar filter-form">
  <label for="status-filter">Status:</label>
  <select name="status" id="status-filter">
    {status_opts_html}
  </select>
  <label for="severity-filter">Severity:</label>
  <select name="severity" id="severity-filter">
    {severity_opts_html}
  </select>
  <button type="submit">Filter</button>
</form>"""

        pagination_html = ""
        if total_count > 50:
            pagination_html = f'<div class="pagination-info">Showing 1-50 of {total_count}</div>'
        elif total_count == 0:
            pagination_html = '<div class="pagination-info">No issues match the current filters.</div>'
        else:
            pagination_html = f'<div class="pagination-info">Showing {total_count} issue{"s" if total_count != 1 else ""}</div>'

        rows_html = ""
        for issue in page_issues:
            severity_str = str(issue.get("severity", ""))
            status_str = str(issue.get("status", ""))
            file_path = str(issue.get("file_path", ""))
            line_number = issue.get("line_number", "")
            first_detected = issue.get("first_detected", "")
            if first_detected and "T" in str(first_detected):
                first_detected = str(first_detected).split("T")[0]

            rows_html += f"""<tr>
  <td>{severity_badge(severity_str)}</td>
  <td>{issue.get("issue_type", "")}</td>
  <td title="{file_path}">{truncate_path(file_path)}</td>
  <td>{line_number}</td>
  <td>{issue.get("rule_id", "")}</td>
  <td>{status_badge(status_str)}</td>
  <td class="ts">{first_detected}</td>
  <td>{issue.get("assigned_to", "") or ""}</td>
</tr>"""

        table_html = f"""
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Severity</th>
        <th>Type</th>
        <th>File</th>
        <th>Line</th>
        <th>Rule</th>
        <th>Status</th>
        <th>First Detected</th>
        <th>Assigned To</th>
      </tr>
    </thead>
    <tbody>
      {rows_html if rows_html else '<tr><td colspan="8" style="text-align:center;color:#718096;padding:20px;">No issues found.</td></tr>'}
    </tbody>
  </table>
</div>"""

        content = f"""
<h2 class="page-title">Issues</h2>
{filter_bar}
{pagination_html}
{table_html}
"""
        return self.render_page("Issues", content, "issues", state.project_path)

    def render_history(self, state: DashboardState) -> str:
        """
        Render the history page with snapshot table and a CSS quality score bar chart.

        Args:
            state: DashboardState populated by DataCollector.

        Returns:
            Complete HTML document string.
        """
        snapshots = state.snapshots

        rows_html = ""
        for snap in snapshots:
            ts = snap.get("scan_timestamp", "")
            if ts and "T" in str(ts):
                ts_display = str(ts).replace("T", " ").split(".")[0]
            else:
                ts_display = str(ts) if ts else ""

            commit = snap.get("git_commit", "") or ""
            commit_short = commit[:8] if commit else ""
            gate_status = snap.get("quality_gate_status", "") or ""
            ratings = snap.get("ratings") or {}

            maint = ratings.get("maintainability", "?")
            reli = ratings.get("reliability", "?")
            sec = ratings.get("security", "?")
            overall = ratings.get("overall", "?")
            score = rating_to_score(overall)

            rows_html += f"""<tr>
  <td class="ts">{ts_display}</td>
  <td><code>{commit_short}</code></td>
  <td>{gate_badge(gate_status) if gate_status else ""}</td>
  <td>{rating_badge(maint)}</td>
  <td>{rating_badge(reli)}</td>
  <td>{rating_badge(sec)}</td>
  <td><strong>{score}</strong></td>
</tr>"""

        table_html = f"""
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Commit</th>
        <th>Gate</th>
        <th>Maintainability</th>
        <th>Reliability</th>
        <th>Security</th>
        <th>Quality Score</th>
      </tr>
    </thead>
    <tbody>
      {rows_html if rows_html else '<tr><td colspan="7" style="text-align:center;color:#718096;padding:20px;">No snapshots recorded yet.</td></tr>'}
    </tbody>
  </table>
</div>"""

        chart_snapshots = snapshots[:10]
        chart_items: List[str] = []
        max_score = 100

        for snap in reversed(chart_snapshots):
            ts = snap.get("scan_timestamp", "")
            ts_label = str(ts).split("T")[0] if ts and "T" in str(ts) else str(ts)[:10]
            ratings = snap.get("ratings") or {}
            overall = ratings.get("overall", "?")
            score = rating_to_score(overall)
            bar_pct = int((score / max_score) * 100)

            chart_items.append(f"""<div class="bar-row">
  <div class="bar-label">{ts_label}</div>
  <div class="bar-outer">
    <div class="bar-inner" style="width:{bar_pct}%;"></div>
  </div>
  <div class="bar-value">{score}</div>
</div>""")

        chart_html = ""
        if chart_items:
            chart_html = f"""
<div class="bar-chart">
  <div class="bar-chart-title">Quality Score Trend (last {len(chart_items)} runs, A=100 to E=20)</div>
  {"".join(chart_items)}
</div>"""

        content = f"""
<h2 class="page-title">History</h2>
{chart_html}
<div class="section-title">Analysis Snapshots</div>
{table_html}
"""
        return self.render_page("History", content, "history", state.project_path)

    def render_error(self, message: str) -> str:
        """
        Render a simple error page.

        Args:
            message: Error message to display.

        Returns:
            Complete HTML document string.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Error - Asgard Dashboard</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #f5f6fa; }}
{EMBEDDED_CSS}
</style>
</head>
<body style="display:block;">
<div class="error-container">
  <div class="error-title">Dashboard Error</div>
  <div class="error-message">{message}</div>
  <p style="margin-top:20px;"><a href="/" style="color:#3182ce;">Return to Overview</a></p>
</div>
</body>
</html>"""
