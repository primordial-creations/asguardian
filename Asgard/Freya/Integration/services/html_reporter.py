"""
Freya HTML Reporter

Generates HTML reports from test results.
"""

import json
import math
from pathlib import Path
from typing import Optional

from Asgard.Freya.Integration.models.integration_models import (
    ReportConfig,
    ReportFormat,
    TestSeverity,
    UnifiedTestReport,
)
from Asgard.Freya.Integration.services._reporter_styles import get_css, get_javascript
from Asgard.Freya.Scoring.models.scoring_models import GradedScore
from Asgard.Freya.Scoring.services.epistemics import LAB_DATA_DISCLAIMER


class HTMLReporter:
    """
    HTML report generation service.

    Generates styled HTML reports from test results.
    """

    def __init__(self, config: Optional[ReportConfig] = None):
        """
        Initialize the HTML Reporter.

        Args:
            config: Report configuration
        """
        self.config = config

    def generate(
        self,
        report: UnifiedTestReport,
        output_path: str,
        title: Optional[str] = None
    ) -> str:
        """
        Generate an HTML report.

        Args:
            report: Unified test report
            output_path: Output file path
            title: Optional report title

        Returns:
            Path to generated report
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._build_html(report, title or "Freya Test Report")

        with open(output, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(output)

    def generate_json(self, report: UnifiedTestReport, output_path: str) -> str:
        """Generate JSON report."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)

        return str(output)

    def generate_junit(self, report: UnifiedTestReport, output_path: str) -> str:
        """Generate JUnit XML report for CI/CD."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        xml_content = self._build_junit_xml(report)

        with open(output, "w", encoding="utf-8") as f:
            f.write(xml_content)

        return str(output)

    def _build_html(self, report: UnifiedTestReport, title: str) -> str:
        """Build complete HTML report."""
        css = get_css()
        js = get_javascript()

        accessibility_html = self._build_results_section(
            "Accessibility",
            report.accessibility_results,
            report.accessibility_score
        )
        visual_html = self._build_results_section(
            "Visual",
            report.visual_results,
            report.visual_score
        )
        responsive_html = self._build_results_section(
            "Responsive",
            report.responsive_results,
            report.responsive_score
        )

        screenshots_html = self._build_screenshots_section(report.screenshots)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <h1>{title}</h1>
        <div class="meta">
            <span>URL: <a href="{report.url}" target="_blank">{report.url}</a></span>
            <span>Tested: {report.tested_at}</span>
            <span>Duration: {report.duration_ms}ms</span>
        </div>
    </header>
    <main>
        <section class="summary">
            <h2>Summary</h2>
            <div class="score-grid">
                <div class="score-card overall"><div class="score-value">{report.overall_score:.0f}</div><div class="score-label">Overall Score</div></div>
                <div class="score-card"><div class="score-value">{report.accessibility_score:.0f}</div><div class="score-label">Accessibility</div></div>
                <div class="score-card"><div class="score-value">{report.visual_score:.0f}</div><div class="score-label">Visual</div></div>
                <div class="score-card"><div class="score-value">{report.responsive_score:.0f}</div><div class="score-label">Responsive</div></div>
            </div>
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value">{report.total_tests}</div><div class="stat-label">Total Tests</div></div>
                <div class="stat-card passed"><div class="stat-value">{report.passed}</div><div class="stat-label">Passed</div></div>
                <div class="stat-card failed"><div class="stat-value">{report.failed}</div><div class="stat-label">Failed</div></div>
            </div>
            <div class="severity-grid">
                <div class="severity-card critical"><span class="count">{report.critical_count}</span><span class="label">Critical</span></div>
                <div class="severity-card serious"><span class="count">{report.serious_count}</span><span class="label">Serious</span></div>
                <div class="severity-card moderate"><span class="count">{report.moderate_count}</span><span class="label">Moderate</span></div>
                <div class="severity-card minor"><span class="count">{report.minor_count}</span><span class="label">Minor</span></div>
            </div>
        </section>
        {self._build_grade_section(report)}
        {self._build_findings_inbox(report)}
        {accessibility_html}
        {visual_html}
        {responsive_html}
        {screenshots_html}
    </main>
    <footer>
        <p>Generated by Freya - Visual Testing Framework</p>
        <p style="font-size: 12px; opacity: 0.8;">{LAB_DATA_DISCLAIMER}</p>
    </footer>
    <script>{js}</script>
</body>
</html>"""

    def _build_grade_section(self, report: UnifiedTestReport) -> str:
        """Executive surface: capped letter grade plus category radar (inline SVG)."""
        graded = getattr(report, "graded", None)
        if not isinstance(graded, GradedScore):
            return ""

        grade_colors = {"A": "#22c55e", "B": "#84cc16", "C": "#eab308", "D": "#f97316", "F": "#ef4444"}
        color = grade_colors.get(graded.grade.value, "#94a3b8")
        cap_html = (
            f"<p>Grade capped by: {graded.cap_reason}</p>" if graded.cap_reason
            else "<p>No capping findings.</p>"
        )
        radar = self._build_radar_svg(graded.category_scores)
        radar_json = json.dumps(graded.category_scores)

        return f"""
        <section class="results-section" id="grade">
            <h2>Grade<span class="section-score" style="color: {color};">{graded.grade.value}</span></h2>
            {cap_html}
            <p>Base score (trend indicator only): {graded.base_score:.0f}/100 &mdash;
               capped score: {graded.capped_score:.0f}/100. The grade is non-compensatory:
               the highest-severity unresolved issue dictates the ceiling.</p>
            {radar}
            <script type="application/json" id="radar-data">{radar_json}</script>
        </section>"""

    @staticmethod
    def _build_radar_svg(category_scores: dict) -> str:
        """Simple SVG polygon radar - no external libraries."""
        categories = sorted(category_scores)
        if len(categories) < 3:
            return ""
        cx, cy, radius = 150.0, 150.0, 120.0
        n = len(categories)
        axis_lines = []
        labels = []
        points = []
        for i, category in enumerate(categories):
            angle = (2 * math.pi * i / n) - math.pi / 2
            x_edge = cx + radius * math.cos(angle)
            y_edge = cy + radius * math.sin(angle)
            axis_lines.append(
                f'<line x1="{cx}" y1="{cy}" x2="{x_edge:.1f}" y2="{y_edge:.1f}" stroke="#64748b" stroke-width="1"/>'
            )
            labels.append(
                f'<text x="{cx + (radius + 18) * math.cos(angle):.1f}" '
                f'y="{cy + (radius + 18) * math.sin(angle):.1f}" '
                f'font-size="11" text-anchor="middle" fill="#94a3b8">{category}</text>'
            )
            score = max(0.0, min(100.0, float(category_scores[category])))
            r = radius * score / 100.0
            points.append(f"{cx + r * math.cos(angle):.1f},{cy + r * math.sin(angle):.1f}")
        polygon = f'<polygon points="{" ".join(points)}" fill="#60a5fa55" stroke="#60a5fa" stroke-width="2"/>'
        return (
            '<svg viewBox="0 0 300 300" width="300" height="300" role="img" '
            'aria-label="Category score radar chart">'
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#334155"/>'
            f"{''.join(axis_lines)}{polygon}{''.join(labels)}</svg>"
        )

    def _build_findings_inbox(self, report: UnifiedTestReport) -> str:
        """Developer surface: all findings sorted by severity, URL, selector."""
        findings = getattr(report, "findings", None) or []
        if not findings:
            return ""

        order = {"blocker": 0, "critical": 1, "major": 2, "minor": 3}
        try:
            ordered = sorted(
                findings,
                key=lambda f: (order.get(f.severity.value, 4), f.url or "", f.selector or ""),
            )
        except (AttributeError, TypeError):
            return ""

        rows = []
        for finding in ordered:
            review = " (needs review)" if finding.needs_review else ""
            rows.append(f"""
            <tr class="result-row {finding.severity.value}">
                <td><span class="severity-badge {finding.severity.value}">{finding.severity.value}{review}</span></td>
                <td>{finding.category}</td>
                <td><code>{finding.check_id}</code></td>
                <td>{finding.message}</td>
                <td><code>{finding.selector or '-'}</code></td>
            </tr>""")

        return f"""
        <section class="results-section" id="findings-inbox">
            <h2>Findings Inbox</h2>
            <table class="results-table">
                <thead><tr><th>Severity</th><th>Category</th><th>Check</th><th>Message</th><th>Element</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </section>"""

    def _build_results_section(self, category: str, results: list, score: float) -> str:
        """Build HTML section for a category."""
        if not results:
            return ""

        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]

        rows = []
        for result in failed:
            severity_class = result.severity.value if result.severity else "moderate"
            wcag_html = f'<span class="wcag">{result.wcag_reference}</span>' if result.wcag_reference else ""
            rows.append(f"""
            <tr class="result-row {severity_class}">
                <td><span class="severity-badge {severity_class}">{severity_class}</span></td>
                <td>{result.test_name}</td>
                <td>{result.message} {wcag_html}</td>
                <td><code>{result.element_selector or '-'}</code></td>
                <td>{result.suggested_fix or '-'}</td>
            </tr>""")

        for result in passed:
            rows.append(f"""
            <tr class="result-row passed">
                <td><span class="severity-badge passed">pass</span></td>
                <td>{result.test_name}</td>
                <td>{result.message}</td>
                <td>-</td>
                <td>-</td>
            </tr>""")

        return f"""
        <section class="results-section" id="{category.lower()}">
            <h2>{category}<span class="section-score">{score:.0f}/100</span></h2>
            <table class="results-table">
                <thead><tr><th>Severity</th><th>Test</th><th>Message</th><th>Element</th><th>Suggested Fix</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </section>"""

    def _build_screenshots_section(self, screenshots: dict) -> str:
        """Build screenshots gallery section."""
        if not screenshots:
            return ""

        items = []
        for name, path in screenshots.items():
            items.append(f"""
            <div class="screenshot-item">
                <img src="{path}" alt="{name}" loading="lazy">
                <div class="screenshot-label">{name}</div>
            </div>""")

        return f"""
        <section class="screenshots-section" id="screenshots">
            <h2>Screenshots</h2>
            <div class="screenshot-gallery">{''.join(items)}</div>
        </section>"""

    def _build_junit_xml(self, report: UnifiedTestReport) -> str:
        """Build JUnit XML format for CI/CD integration."""
        test_cases = []

        all_results = (
            report.accessibility_results +
            report.visual_results +
            report.responsive_results
        )

        for result in all_results:
            if result.passed:
                test_cases.append(
                    f'    <testcase name="{result.test_name}" classname="{result.category.value}"/>'
                )
            else:
                severity = result.severity.value if result.severity else "moderate"
                message = result.message.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
                test_cases.append(f'''    <testcase name="{result.test_name}" classname="{result.category.value}">
      <failure type="{severity}" message="{message}">
{result.suggested_fix or ''}
      </failure>
    </testcase>''')

        return f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Freya Tests" tests="{report.total_tests}" failures="{report.failed}" timestamp="{report.tested_at}">
{chr(10).join(test_cases)}
</testsuite>'''
