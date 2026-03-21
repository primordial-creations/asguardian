"""
Freya Visual Regression HTML report generation.

Report builder extracted from visual_regression.py.
"""

from datetime import datetime
from pathlib import Path

from Asgard.Freya.Visual.models.visual_models import RegressionReport


def generate_html_report(report: RegressionReport, output_directory: Path) -> Path:
    """Generate HTML report for regression suite."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visual Regression Report - {report.suite_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .pass {{ color: #4CAF50; }}
        .fail {{ color: #f44336; }}
        .test-case {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .test-pass {{ border-left: 4px solid #4CAF50; }}
        .test-fail {{ border-left: 4px solid #f44336; }}
        .images {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .images img {{ max-width: 300px; height: auto; }}
    </style>
</head>
<body>
    <h1>Visual Regression Report: {report.suite_name}</h1>
    <div class="summary">
        <p><strong>Total:</strong> {report.total_comparisons}</p>
        <p class="pass"><strong>Passed:</strong> {report.passed_comparisons}</p>
        <p class="fail"><strong>Failed:</strong> {report.failed_comparisons}</p>
        <p><strong>Overall Similarity:</strong> {report.overall_similarity:.2%}</p>
        <p><strong>Generated:</strong> {report.report_timestamp}</p>
    </div>
"""

    for result in report.results:
        status_class = "test-pass" if result.is_similar else "test-fail"
        status = "PASS" if result.is_similar else "FAIL"

        html += f"""
    <div class="test-case {status_class}">
        <h3>{Path(result.baseline_path).name} - {status}</h3>
        <p><strong>Similarity:</strong> {result.similarity_score:.2%}</p>
        <p><strong>Method:</strong> {result.comparison_method.value}</p>
        <p><strong>Differences:</strong> {len(result.difference_regions)}</p>
    </div>
"""

    html += """
</body>
</html>
"""

    report_path = output_directory / "reports" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    report_path.write_text(html)

    return report_path
