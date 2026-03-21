"""
Heimdall Code Smell Report - HTML report generation.
"""

import os
from typing import Callable

from Asgard.Heimdall.Quality.models.smell_models import (
    SmellCategory,
    SmellReport,
    SmellSeverity,
)


def generate_html_report(report: SmellReport, severity_level_fn: Callable) -> str:
    """Generate HTML report."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Code Smells Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .summary {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .critical {{ color: #c0392b; font-weight: bold; }}
        .high {{ color: #e67e22; font-weight: bold; }}
        .medium {{ color: #3498db; }}
        .low {{ color: #27ae60; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px 8px;
            text-align: left;
        }}
        th {{
            background-color: #3498db;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .smell-item {{
            margin-bottom: 20px;
            padding: 15px;
            border-left: 4px solid #ccc;
            background: #fafafa;
            border-radius: 0 5px 5px 0;
        }}
        .smell-critical {{ border-left-color: #c0392b; }}
        .smell-high {{ border-left-color: #e67e22; }}
        .smell-medium {{ border-left-color: #3498db; }}
        .smell-low {{ border-left-color: #27ae60; }}
        .smell-item h3 {{
            margin: 0 0 10px 0;
        }}
        .smell-item p {{
            margin: 5px 0;
        }}
        .smell-item strong {{
            color: #555;
        }}
        .priorities {{
            background: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
        }}
        .priorities li {{
            margin: 8px 0;
        }}
        .scan-info {{
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Code Smells Report</h1>

        <p class="scan-info">
            <strong>Scan Path:</strong> {report.scan_path}<br>
            <strong>Generated:</strong> {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>Duration:</strong> {report.scan_duration_seconds:.2f} seconds
        </p>

        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Total Code Smells:</strong> {report.total_smells}</p>

            <h3>By Severity</h3>
            <table>
                <tr>
                    <th>Severity</th>
                    <th>Count</th>
                </tr>
"""

    for severity in [SmellSeverity.CRITICAL, SmellSeverity.HIGH, SmellSeverity.MEDIUM, SmellSeverity.LOW]:
        count = report.smells_by_severity.get(severity.value, 0)
        html += f"""                <tr>
                    <td class="{severity.value}">{severity.value.title()}</td>
                    <td>{count}</td>
                </tr>
"""

    html += """            </table>

            <h3>By Category</h3>
            <table>
                <tr>
                    <th>Category</th>
                    <th>Count</th>
                </tr>
"""

    for category in SmellCategory:
        count = report.smells_by_category.get(category.value, 0)
        html += f"""                <tr>
                    <td>{category.value.replace('_', ' ').title()}</td>
                    <td>{count}</td>
                </tr>
"""

    html += """            </table>
        </div>
"""

    if report.most_problematic_files:
        html += """        <h2>Most Problematic Files</h2>
        <table>
            <tr>
                <th>File</th>
                <th>Smell Count</th>
            </tr>
"""
        for file_path, count in report.most_problematic_files[:10]:
            filename = os.path.basename(file_path)
            html += f"""            <tr>
                <td>{filename}</td>
                <td>{count}</td>
            </tr>
"""
        html += """        </table>
"""

    if report.remediation_priorities:
        html += """        <h2>Remediation Priorities</h2>
        <div class="priorities">
            <ul>
"""
        for priority in report.remediation_priorities:
            html += f"                <li>{priority}</li>\n"
        html += """            </ul>
        </div>
"""

    html += """        <h2>Detected Smells</h2>
"""

    sorted_smells = sorted(
        report.detected_smells,
        key=lambda x: severity_level_fn(x.severity),
        reverse=True,
    )

    for smell in sorted_smells[:50]:
        filename = os.path.basename(smell.file_path)
        sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
        cat = smell.category if isinstance(smell.category, str) else smell.category.value
        html += f"""        <div class="smell-item smell-{sev}">
            <h3 class="{sev}">{smell.name} - {filename}:{smell.line_number}</h3>
            <p><strong>Category:</strong> {cat.replace('_', ' ').title()}</p>
            <p><strong>Description:</strong> {smell.description}</p>
            <p><strong>Evidence:</strong> {smell.evidence}</p>
            <p><strong>Remediation:</strong> {smell.remediation}</p>
            <p><strong>Confidence:</strong> {smell.confidence:.0%}</p>
        </div>
"""

    html += """    </div>
</body>
</html>"""

    return html
