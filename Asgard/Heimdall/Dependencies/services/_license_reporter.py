"""
Heimdall License Checker - report generation helpers.

Standalone functions for generating text, JSON, and Markdown reports
from a LicenseResult.
"""

import json

from Asgard.Heimdall.Dependencies.models.license_models import (
    LicenseCategory,
    LicenseResult,
    LicenseSeverity,
)


def generate_text_report(result: LicenseResult) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL LICENSE CHECK REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:           {result.scan_path}")
    lines.append(f"  Scanned At:          {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration:            {result.scan_duration_seconds:.2f}s")
    lines.append(f"  Requirements Files:  {', '.join(result.requirements_files_found) or 'None found'}")
    lines.append("")

    if result.has_issues:
        lines.append("-" * 70)
        lines.append("  LICENSE ISSUES")
        lines.append("-" * 70)
        lines.append("")

        by_severity = result.get_issues_by_severity()

        for severity in [LicenseSeverity.CRITICAL, LicenseSeverity.HIGH, LicenseSeverity.MODERATE, LicenseSeverity.LOW]:
            issues = by_severity.get(severity.value, [])
            if issues:
                lines.append(f"  [{severity.value.upper()}] ({len(issues)} packages):")
                lines.append("")
                for issue in issues:
                    lines.append(f"    - {issue.package_name}: {issue.license_name}")
                    lines.append(f"        {issue.message}")
                lines.append("")
    else:
        lines.append("  All packages have compliant licenses!")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  LICENSE SUMMARY BY CATEGORY")
    lines.append("-" * 70)
    lines.append("")

    by_category = result.get_packages_by_category()
    for category in [LicenseCategory.PERMISSIVE, LicenseCategory.PUBLIC_DOMAIN,
                     LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT,
                     LicenseCategory.UNKNOWN]:
        pkgs = by_category.get(category.value, [])
        if pkgs:
            lines.append(f"  {category.value.upper()} ({len(pkgs)} packages):")
            for pkg in pkgs[:5]:
                lines.append(f"    - {pkg.package_name}: {pkg.display_license}")
            if len(pkgs) > 5:
                lines.append(f"    ... and {len(pkgs) - 5} more")
            lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Total Packages:      {result.total_packages}")
    lines.append(f"  Compliant:           {result.compliant_packages}")
    lines.append(f"  Warnings:            {result.warning_packages}")
    lines.append(f"  Prohibited:          {result.prohibited_packages}")
    lines.append(f"  Unknown:             {result.unknown_packages}")
    lines.append(f"  Compliance Rate:     {result.compliance_rate:.1f}%")
    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    return "\n".join(lines)


def generate_json_report(result: LicenseResult) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "requirements_files": result.requirements_files_found,
        "summary": {
            "total_packages": result.total_packages,
            "compliant": result.compliant_packages,
            "warnings": result.warning_packages,
            "prohibited": result.prohibited_packages,
            "unknown": result.unknown_packages,
            "compliance_rate": round(result.compliance_rate, 2),
            "has_issues": result.has_issues,
        },
        "packages": [
            {
                "name": p.package_name,
                "version": p.version,
                "license": p.display_license,
                "category": p.category.value,
                "severity": p.severity.value,
                "is_allowed": p.is_allowed,
                "is_prohibited": p.is_prohibited,
            }
            for p in result.packages
        ],
        "issues": [
            {
                "type": i.issue_type.value,
                "severity": i.severity.value,
                "package": i.package_name,
                "license": i.license_name,
                "message": i.message,
            }
            for i in result.issues
        ],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: LicenseResult) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall License Check Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append(f"- **Requirements Files:** {', '.join(result.requirements_files_found) or 'None found'}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Packages:** {result.total_packages}")
    lines.append(f"- **Compliant:** {result.compliant_packages}")
    lines.append(f"- **Warnings:** {result.warning_packages}")
    lines.append(f"- **Prohibited:** {result.prohibited_packages}")
    lines.append(f"- **Unknown:** {result.unknown_packages}")
    lines.append(f"- **Compliance Rate:** {result.compliance_rate:.1f}%")
    lines.append("")

    if result.has_issues:
        lines.append("## Issues")
        lines.append("")
        lines.append("| Package | License | Category | Severity |")
        lines.append("|---------|---------|----------|----------|")
        for issue in result.issues:
            lines.append(
                f"| `{issue.package_name}` | {issue.license_name} | "
                f"{issue.issue_type.value} | {issue.severity.value.upper()} |"
            )
        lines.append("")

    lines.append("## All Packages")
    lines.append("")
    lines.append("| Package | Version | License | Category |")
    lines.append("|---------|---------|---------|----------|")
    for pkg in result.packages:
        lines.append(
            f"| `{pkg.package_name}` | {pkg.version or 'N/A'} | "
            f"{pkg.display_license} | {pkg.category.value} |"
        )
    lines.append("")

    return "\n".join(lines)
