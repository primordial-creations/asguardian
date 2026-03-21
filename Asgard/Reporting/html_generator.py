"""
HTML Report Generator

Generates rich HTML reports with dashboards, charts, and drill-down capabilities.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from Asgard.Reporting._html_templates import REPORT_CSS, REPORT_JS


@dataclass
class ScoreCard:
    """Represents a dashboard score card."""
    title: str
    value: str
    label: str
    status: str = "good"  # good, warning, bad


class HTMLReportGenerator:
    """
    Generates rich HTML reports for Asgard analysis results.

    Features:
    - Dashboard with score cards
    - File-level drill-down
    - Code snippets with line highlighting
    - Severity badges
    - Collapsible sections
    - Self-contained (inline CSS/JS)

    Usage:
        generator = HTMLReportGenerator()

        # Generate from various reports
        html = generator.generate_quality_report(
            quality_result,
            complexity_result,
            smell_report,
        )

        # Save to file
        with open("report.html", "w") as f:
            f.write(html)
    """

    def __init__(self, title: str = "Asgard Analysis Report"):
        """
        Initialize the HTML report generator.

        Args:
            title: Report title
        """
        self.title = title

    def _wrap_html(self, content: str, title: str) -> str:
        """Wrap content in complete HTML document."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{REPORT_CSS}</style>
</head>
<body>
    <div class="container">
        {content}
    </div>
    <script>{REPORT_JS}</script>
</body>
</html>"""

    def _generate_header(self, subtitle: str = "") -> str:
        """Generate report header."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subtitle_html = f"<div class='meta'>{subtitle}</div>" if subtitle else ""
        return f"""
<header>
    <h1>{self.title}</h1>
    {subtitle_html}
    <div class='meta'>Generated: {timestamp}</div>
</header>"""

    def _generate_score_card(self, card: ScoreCard) -> str:
        """Generate a single score card."""
        return f"""
<div class="card">
    <h2>{card.title}</h2>
    <div class="score {card.status}">{card.value}</div>
    <div class="label">{card.label}</div>
</div>"""

    def _generate_dashboard(self, cards: List[ScoreCard]) -> str:
        """Generate dashboard with score cards."""
        cards_html = "\n".join(self._generate_score_card(card) for card in cards)
        return f"""
<div class="dashboard">
    {cards_html}
</div>"""

    def _generate_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: str = "",
    ) -> str:
        """Generate an HTML table."""
        header_html = "".join(f"<th>{h}</th>" for h in headers)
        rows_html = "\n".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in rows
        )

        title_html = f"<h2>{title}</h2>" if title else ""

        return f"""
<div class="section">
    {title_html}
    <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>"""

    def _generate_severity_badge(self, severity: str) -> str:
        """Generate a severity badge."""
        severity_lower = severity.lower()
        return f'<span class="severity-badge severity-{severity_lower}">{severity}</span>'

    def _generate_code_block(
        self,
        code: str,
        highlight_line: Optional[int] = None,
        start_line: int = 1,
    ) -> str:
        """Generate a code block with optional line highlighting."""
        lines_html = []
        for i, line in enumerate(code.split("\n"), start=start_line):
            line_class = "highlight" if i == highlight_line else ""
            escaped_line = line.replace("<", "&lt;").replace(">", "&gt;")
            lines_html.append(
                f'<span class="{line_class}"><span class="line-number">{i:4d}</span>{escaped_line}</span>'
            )

        return f"""
<div class="code-block">
    <pre>{"".join(lines_html)}</pre>
</div>"""

    def _generate_file_list(
        self,
        files: List[tuple],
        title: str = "Files",
    ) -> str:
        """Generate a file list with counts."""
        items_html = "\n".join(
            f'<li><span class="file-path">{path}</span><span class="badge-count">{count}</span></li>'
            for path, count in files
        )

        return f"""
<div class="section">
    <h2>{title}</h2>
    <ul class="file-list">
        {items_html}
    </ul>
</div>"""

    def _generate_progress_bar(
        self,
        value: float,
        max_value: float = 100,
        label: str = "",
    ) -> str:
        """Generate a progress bar."""
        percentage = min(100, (value / max_value) * 100) if max_value > 0 else 0
        status = "good" if percentage >= 80 else "warning" if percentage >= 50 else "bad"

        return f"""
<div>
    <span>{label}: {value:.1f}%</span>
    <div class="progress-bar">
        <div class="fill {status}" style="width: {percentage}%"></div>
    </div>
</div>"""

    def generate_typing_report(self, report) -> str:
        """
        Generate HTML report for typing coverage analysis.

        Args:
            report: TypingReport object

        Returns:
            Complete HTML document string
        """
        coverage_status = "good" if report.coverage_percentage >= 80 else \
                         "warning" if report.coverage_percentage >= 50 else "bad"

        cards = [
            ScoreCard(
                title="Type Coverage",
                value=f"{report.coverage_percentage:.1f}%",
                label=f"Threshold: {report.threshold:.1f}%",
                status=coverage_status,
            ),
            ScoreCard(
                title="Functions",
                value=str(report.total_functions),
                label="Total analyzed",
                status="good",
            ),
            ScoreCard(
                title="Fully Typed",
                value=str(report.fully_annotated),
                label=f"{report.fully_annotated / max(1, report.total_functions) * 100:.0f}% of total",
                status="good" if report.fully_annotated == report.total_functions else "warning",
            ),
            ScoreCard(
                title="Status",
                value="PASS" if report.is_passing else "FAIL",
                label=f"Files: {report.files_scanned}",
                status="good" if report.is_passing else "bad",
            ),
        ]

        file_rows = []
        for f in sorted(report.files_analyzed, key=lambda x: x.coverage_percentage)[:20]:
            coverage_badge = self._generate_severity_badge(
                "good" if f.coverage_percentage >= 80 else
                "warning" if f.coverage_percentage >= 50 else "low"
            )
            file_rows.append([
                f.relative_path,
                str(f.total_functions),
                str(f.fully_annotated),
                f"{f.coverage_percentage:.1f}%",
                coverage_badge,
            ])

        file_table = self._generate_table(
            ["File", "Functions", "Typed", "Coverage", "Status"],
            file_rows,
            "File Coverage (Bottom 20)",
        )

        func_rows = []
        for func in report.unannotated_functions[:30]:
            missing = ", ".join(func.missing_parameter_names[:3])
            if len(func.missing_parameter_names) > 3:
                missing += "..."
            severity_badge = self._generate_severity_badge(
                func.severity if isinstance(func.severity, str) else func.severity.value
            )
            func_rows.append([
                func.relative_path,
                func.qualified_name,
                str(func.line_number),
                missing or "-",
                "Yes" if func.has_return_annotation else "No",
                severity_badge,
            ])

        func_table = self._generate_table(
            ["File", "Function", "Line", "Missing Params", "Has Return", "Severity"],
            func_rows,
            "Functions Needing Annotations",
        )

        content = f"""
{self._generate_header(f"Scan: {report.scan_path}")}
{self._generate_dashboard(cards)}
{file_table}
{func_table}
<footer>Generated by Asgard Heimdall</footer>
"""
        return self._wrap_html(content, f"Type Coverage - {self.title}")

    def generate_quality_dashboard(
        self,
        quality_result=None,
        complexity_result=None,
        smell_report=None,
        typing_report=None,
        datetime_report=None,
        forbidden_report=None,
    ) -> str:
        """
        Generate a unified quality dashboard HTML report.

        Args:
            quality_result: File length analysis result
            complexity_result: Complexity analysis result
            smell_report: Code smell report
            typing_report: Typing coverage report
            datetime_report: Datetime usage report
            forbidden_report: Forbidden imports report

        Returns:
            Complete HTML document string
        """
        cards = []
        sections = []

        if quality_result:
            violation_count = len(quality_result.files_over_threshold)
            cards.append(ScoreCard(
                title="File Length",
                value=str(violation_count),
                label="files over threshold",
                status="good" if violation_count == 0 else "warning" if violation_count < 5 else "bad",
            ))

        if complexity_result:
            cards.append(ScoreCard(
                title="Complexity",
                value=str(complexity_result.total_violations),
                label="complex functions",
                status="good" if complexity_result.total_violations == 0 else
                       "warning" if complexity_result.total_violations < 10 else "bad",
            ))

        if smell_report:
            cards.append(ScoreCard(
                title="Code Smells",
                value=str(smell_report.total_smells),
                label="detected issues",
                status="good" if smell_report.total_smells == 0 else
                       "warning" if smell_report.total_smells < 20 else "bad",
            ))

        if typing_report:
            cards.append(ScoreCard(
                title="Type Coverage",
                value=f"{typing_report.coverage_percentage:.0f}%",
                label=f"threshold: {typing_report.threshold:.0f}%",
                status="good" if typing_report.is_passing else "bad",
            ))

        if datetime_report:
            cards.append(ScoreCard(
                title="Datetime Issues",
                value=str(datetime_report.total_violations),
                label="deprecated/unsafe",
                status="good" if datetime_report.total_violations == 0 else "bad",
            ))

        if forbidden_report:
            cards.append(ScoreCard(
                title="Forbidden Imports",
                value=str(forbidden_report.total_violations),
                label="wrapper violations",
                status="good" if forbidden_report.total_violations == 0 else "bad",
            ))

        if complexity_result and complexity_result.has_violations:
            rows = []
            for fa in complexity_result.file_analyses:
                for func in fa.functions:
                    if func.cyclomatic_complexity > 10 or func.cognitive_complexity > 15:
                        severity = self._generate_severity_badge(
                            func.cyclomatic_severity if isinstance(func.cyclomatic_severity, str)
                            else func.cyclomatic_severity.value
                        )
                        rows.append([
                            Path(fa.file_path).name,
                            func.name,
                            str(func.line_number),
                            str(func.cyclomatic_complexity),
                            str(func.cognitive_complexity),
                            severity,
                        ])
            if rows:
                sections.append(self._generate_table(
                    ["File", "Function", "Line", "Cyclomatic", "Cognitive", "Severity"],
                    rows[:30],
                    "Complex Functions",
                ))

        if smell_report and smell_report.has_smells:
            rows = []
            for smell in smell_report.smells[:30]:
                severity = self._generate_severity_badge(
                    smell.severity if isinstance(smell.severity, str) else smell.severity.value
                )
                rows.append([
                    Path(smell.file_path).name,
                    smell.smell_type,
                    str(smell.line_number),
                    smell.description[:60] + "..." if len(smell.description) > 60 else smell.description,
                    severity,
                ])
            sections.append(self._generate_table(
                ["File", "Smell", "Line", "Description", "Severity"],
                rows,
                "Code Smells",
            ))

        content = f"""
{self._generate_header("Quality Dashboard")}
{self._generate_dashboard(cards)}
{"".join(sections)}
<footer>Generated by Asgard Heimdall</footer>
"""
        return self._wrap_html(content, f"Quality Dashboard - {self.title}")
