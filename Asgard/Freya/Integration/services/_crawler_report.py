"""
Freya Site Crawler report generation.

Report building and HTML generation extracted from site_crawler.py.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from Asgard.Freya.Integration.models.integration_models import (
    PageStatus,
    PageTestResult,
    SiteCrawlReport,
)


def generate_report(
    config,
    discovered_pages: dict,
    tested_pages: dict,
    crawl_started: str,
    crawl_completed: str,
    total_duration: int,
) -> SiteCrawlReport:
    """Generate the final crawl report."""
    page_results = list(tested_pages.values())

    pages_discovered = len(discovered_pages)
    pages_tested = len([p for p in discovered_pages.values() if p.status == PageStatus.TESTED])
    pages_skipped = len([p for p in discovered_pages.values() if p.status == PageStatus.SKIPPED])
    pages_errored = len([p for p in discovered_pages.values() if p.status == PageStatus.ERROR])

    if page_results:
        avg_accessibility = sum(r.accessibility_score for r in page_results) / len(page_results)
        avg_visual = sum(r.visual_score for r in page_results) / len(page_results)
        avg_responsive = sum(r.responsive_score for r in page_results) / len(page_results)
        avg_overall = sum(r.overall_score for r in page_results) / len(page_results)
    else:
        avg_accessibility = avg_visual = avg_responsive = avg_overall = 0.0

    total_critical = sum(r.critical_issues for r in page_results)
    total_serious = sum(r.serious_issues for r in page_results)
    total_moderate = sum(r.moderate_issues for r in page_results)
    total_minor = sum(r.minor_issues for r in page_results)

    worst_pages = sorted(page_results, key=lambda r: r.overall_score)[:5]
    worst_page_urls = [p.url for p in worst_pages]

    issue_counter: Counter = Counter()
    for result in page_results:
        for issue in result.issues:
            issue_key = f"{issue.get('type', 'unknown')}:{issue.get('message', '')}"
            issue_counter[issue_key] += 1

    common_issues = [
        {"issue": key.split(":")[0], "message": key.split(":", 1)[1], "count": count}
        for key, count in issue_counter.most_common(10)
    ]

    return SiteCrawlReport(
        start_url=config.start_url,
        crawl_started=crawl_started,
        crawl_completed=crawl_completed,
        total_duration_ms=total_duration,
        pages_discovered=pages_discovered,
        pages_tested=pages_tested,
        pages_skipped=pages_skipped,
        pages_errored=pages_errored,
        average_accessibility_score=avg_accessibility,
        average_visual_score=avg_visual,
        average_responsive_score=avg_responsive,
        average_overall_score=avg_overall,
        total_critical=total_critical,
        total_serious=total_serious,
        total_moderate=total_moderate,
        total_minor=total_minor,
        page_results=page_results,
        worst_pages=worst_page_urls,
        common_issues=common_issues,
        config=config,
    )


async def save_report(report: SiteCrawlReport, output_dir: Path) -> None:
    """Save the crawl report to files."""
    json_path = output_dir / "crawl_report.json"
    with open(json_path, "w") as f:
        f.write(report.model_dump_json(indent=2))

    html_path = output_dir / "crawl_report.html"
    html_content = generate_html_report(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def url_to_filename(url: str) -> str:
    """Convert URL to safe filename."""
    url = url.replace("https://", "").replace("http://", "")
    url = url.replace("/", "_").replace(":", "_").replace("?", "_")
    url = url.replace("&", "_").replace("=", "_").replace("#", "_")
    return url[:100]


def _score_color(score: float) -> str:
    if score >= 90:
        return "#22c55e"
    elif score >= 70:
        return "#eab308"
    elif score >= 50:
        return "#f97316"
    return "#ef4444"


def generate_html_report(report: SiteCrawlReport) -> str:
    """Generate HTML report from crawl results."""
    page_rows = ""
    for result in sorted(report.page_results, key=lambda r: r.overall_score):
        status = "PASS" if result.passed else "FAIL"
        status_color = "#22c55e" if result.passed else "#ef4444"
        page_rows += f"""
        <tr>
            <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <a href="{result.url}" target="_blank">{result.url}</a>
            </td>
            <td style="text-align: center; color: {_score_color(result.overall_score)}; font-weight: bold;">
                {result.overall_score:.0f}
            </td>
            <td style="text-align: center;">{result.accessibility_score:.0f}</td>
            <td style="text-align: center;">{result.visual_score:.0f}</td>
            <td style="text-align: center;">{result.responsive_score:.0f}</td>
            <td style="text-align: center; color: {status_color}; font-weight: bold;">{status}</td>
            <td style="text-align: center;">{result.critical_issues + result.serious_issues + result.moderate_issues + result.minor_issues}</td>
        </tr>
        """

    common_issues_html = ""
    for issue in report.common_issues[:10]:
        common_issues_html += f"""
        <tr>
            <td>{issue['issue']}</td>
            <td>{issue['message']}</td>
            <td style="text-align: center; font-weight: bold;">{issue['count']}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Freya Site Crawl Report - {report.start_url}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; padding: 40px 0; border-bottom: 1px solid #334155; margin-bottom: 40px; }}
        .header h1 {{ font-size: 2.5rem; color: #f8fafc; margin-bottom: 10px; }}
        .header p {{ color: #94a3b8; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .summary-card {{ background: #1e293b; border-radius: 12px; padding: 24px; text-align: center; }}
        .summary-card h3 {{ color: #94a3b8; font-size: 14px; text-transform: uppercase; margin-bottom: 8px; }}
        .summary-card .value {{ font-size: 2.5rem; font-weight: bold; }}
        .score-section {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .score-card {{ background: #1e293b; border-radius: 12px; padding: 24px; }}
        .score-card h3 {{ color: #94a3b8; font-size: 14px; margin-bottom: 16px; }}
        .score-bar {{ height: 8px; background: #334155; border-radius: 4px; overflow: hidden; }}
        .score-fill {{ height: 100%; border-radius: 4px; }}
        .score-value {{ font-size: 2rem; font-weight: bold; margin-top: 8px; }}
        .section {{ background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
        .section h2 {{ color: #f8fafc; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #334155; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        tr:hover {{ background: #334155; }}
        a {{ color: #60a5fa; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .footer {{ text-align: center; padding: 40px 0; color: #64748b; border-top: 1px solid #334155; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Freya Site Crawl Report</h1>
            <p>{report.start_url}</p>
            <p style="margin-top: 10px; font-size: 14px;">Generated: {report.crawl_completed} | Duration: {report.total_duration_ms / 1000:.1f}s</p>
        </div>
        <div class="summary-grid">
            <div class="summary-card"><h3>Pages Discovered</h3><div class="value" style="color: #60a5fa;">{report.pages_discovered}</div></div>
            <div class="summary-card"><h3>Pages Tested</h3><div class="value" style="color: #22c55e;">{report.pages_tested}</div></div>
            <div class="summary-card"><h3>Critical Issues</h3><div class="value" style="color: #ef4444;">{report.total_critical}</div></div>
            <div class="summary-card"><h3>Total Issues</h3><div class="value" style="color: #f97316;">{report.total_critical + report.total_serious + report.total_moderate + report.total_minor}</div></div>
        </div>
        <div class="score-section">
            <div class="score-card"><h3>Overall Score</h3><div class="score-bar"><div class="score-fill" style="width: {report.average_overall_score}%; background: {_score_color(report.average_overall_score)};"></div></div><div class="score-value" style="color: {_score_color(report.average_overall_score)};">{report.average_overall_score:.0f}/100</div></div>
            <div class="score-card"><h3>Accessibility</h3><div class="score-bar"><div class="score-fill" style="width: {report.average_accessibility_score}%; background: {_score_color(report.average_accessibility_score)};"></div></div><div class="score-value" style="color: {_score_color(report.average_accessibility_score)};">{report.average_accessibility_score:.0f}/100</div></div>
            <div class="score-card"><h3>Visual</h3><div class="score-bar"><div class="score-fill" style="width: {report.average_visual_score}%; background: {_score_color(report.average_visual_score)};"></div></div><div class="score-value" style="color: {_score_color(report.average_visual_score)};">{report.average_visual_score:.0f}/100</div></div>
            <div class="score-card"><h3>Responsive</h3><div class="score-bar"><div class="score-fill" style="width: {report.average_responsive_score}%; background: {_score_color(report.average_responsive_score)};"></div></div><div class="score-value" style="color: {_score_color(report.average_responsive_score)};">{report.average_responsive_score:.0f}/100</div></div>
        </div>
        <div class="section">
            <h2>Common Issues Across Site</h2>
            <table><thead><tr><th>Issue Type</th><th>Description</th><th>Occurrences</th></tr></thead>
            <tbody>{common_issues_html if common_issues_html else '<tr><td colspan="3" style="text-align: center;">No issues found</td></tr>'}</tbody></table>
        </div>
        <div class="section">
            <h2>All Pages ({report.pages_tested} tested)</h2>
            <table><thead><tr><th>URL</th><th>Overall</th><th>A11y</th><th>Visual</th><th>Responsive</th><th>Status</th><th>Issues</th></tr></thead>
            <tbody>{page_rows if page_rows else '<tr><td colspan="7" style="text-align: center;">No pages tested</td></tr>'}</tbody></table>
        </div>
        <div class="footer"><p>Generated by Freya - Visual and UI Testing</p><p>Named after the Norse goddess of beauty and love</p></div>
    </div>
</body>
</html>"""
