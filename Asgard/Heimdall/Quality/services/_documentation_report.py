import json
from typing import Dict

from Asgard.Heimdall.Quality.models.documentation_models import (
    ClassDocumentation,
    DocumentationReport,
    FileDocumentation,
    FunctionDocumentation,
)


def generate_text_report(report: DocumentationReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "DOCUMENTATION COVERAGE REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Files: {report.total_files}",
        f"Comment Density: {report.overall_comment_density:.1f}%",
        f"API Documentation Coverage: {report.overall_api_coverage:.1f}%",
        f"Total Public APIs: {report.total_public_apis}",
        f"Undocumented APIs: {report.undocumented_apis}",
        "",
    ]

    problem_files = [
        f for f in report.file_results
        if f.comment_density < 10.0 or f.public_api_coverage < 70.0
    ]

    if problem_files:
        lines.extend(["FILES WITH ISSUES", "-" * 40, ""])
        for f in sorted(problem_files, key=lambda x: x.public_api_coverage):
            lines.append(f"  {f.path}")
            lines.append(f"    Comment density: {f.comment_density:.1f}% | API coverage: {f.public_api_coverage:.1f}% | Undocumented: {f.undocumented_count}")
            lines.append("")
    else:
        lines.extend(["All files meet documentation thresholds.", ""])

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: DocumentationReport) -> str:
    """Generate JSON report."""
    def serialize_function(func: FunctionDocumentation) -> Dict:
        return {
            "name": func.name,
            "line_number": func.line_number,
            "has_docstring": func.has_docstring,
            "is_public": func.is_public,
            "docstring_lines": func.docstring_lines,
        }

    def serialize_class(cls: ClassDocumentation) -> Dict:
        return {
            "name": cls.name,
            "line_number": cls.line_number,
            "has_docstring": cls.has_docstring,
            "is_public": cls.is_public,
            "docstring_lines": cls.docstring_lines,
            "methods": [serialize_function(m) for m in cls.methods],
        }

    def serialize_file(f: FileDocumentation) -> Dict:
        return {
            "path": f.path,
            "total_lines": f.total_lines,
            "code_lines": f.code_lines,
            "comment_lines": f.comment_lines,
            "blank_lines": f.blank_lines,
            "comment_density": f.comment_density,
            "public_api_coverage": f.public_api_coverage,
            "undocumented_count": f.undocumented_count,
            "functions": [serialize_function(fn) for fn in f.functions],
            "classes": [serialize_class(c) for c in f.classes],
        }

    output = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
        },
        "summary": {
            "total_files": report.total_files,
            "overall_comment_density": report.overall_comment_density,
            "overall_api_coverage": report.overall_api_coverage,
            "total_public_apis": report.total_public_apis,
            "undocumented_apis": report.undocumented_apis,
        },
        "file_results": [serialize_file(f) for f in report.file_results],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(report: DocumentationReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Documentation Coverage Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Files | {report.total_files} |",
        f"| Comment Density | {report.overall_comment_density:.1f}% |",
        f"| API Documentation Coverage | {report.overall_api_coverage:.1f}% |",
        f"| Total Public APIs | {report.total_public_apis} |",
        f"| Undocumented APIs | {report.undocumented_apis} |",
        "",
    ]

    problem_files = [
        f for f in report.file_results
        if f.comment_density < 10.0 or f.public_api_coverage < 70.0
    ]

    if problem_files:
        lines.extend(["## Files With Issues", ""])
        for f in sorted(problem_files, key=lambda x: x.public_api_coverage):
            lines.extend([
                f"### `{f.path}`",
                f"- **Comment Density:** {f.comment_density:.1f}%",
                f"- **API Coverage:** {f.public_api_coverage:.1f}%",
                f"- **Undocumented APIs:** {f.undocumented_count}",
                "",
            ])
    else:
        lines.extend(["All files meet documentation thresholds.", ""])

    return "\n".join(lines)
