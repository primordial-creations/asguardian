"""
Freya HTML Reporter

Generates HTML reports from test results.
"""

import json
from pathlib import Path
from typing import Optional

from Asgard.Freya.Integration.models.integration_models import (
    ReportConfig,
    ReportFormat,
    TestSeverity,
    UnifiedTestReport,
)
from Asgard.Freya.Integration.services._reporter_styles import get_css, get_javascript


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
        {accessibility_html}
        {visual_html}
        {responsive_html}
        {screenshots_html}
    </main>
    <footer><p>Generated by Freya - Visual Testing Framework</p></footer>
    <script>{js}</script>
</body>
</html>"""

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
