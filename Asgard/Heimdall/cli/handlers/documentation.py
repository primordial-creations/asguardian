import argparse
from pathlib import Path

from Asgard.Heimdall.Quality.models.documentation_models import DocumentationConfig
from Asgard.Heimdall.Quality.services.documentation_scanner import DocumentationScanner
from Asgard.Heimdall.Quality.models.naming_models import NamingConfig
from Asgard.Heimdall.Quality.services.naming_convention_scanner import NamingConventionScanner


def run_documentation_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    config = DocumentationConfig(
        scan_path=scan_path,
        min_comment_density=getattr(args, "min_comment_density", 10.0),
        min_api_coverage=getattr(args, "min_api_coverage", 70.0),
        include_tests=getattr(args, "include_tests", False),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
            "migrations", "test_*", "*_test.py",
        ],
        output_format=args.format,
    )

    try:
        scanner = DocumentationScanner(config)
        report = scanner.scan(scan_path)

        if args.format == "json":
            print(scanner.generate_report(report, "json"))
        elif args.format in ("markdown", "md"):
            print(scanner.generate_report(report, "markdown"))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL DOCUMENTATION COVERAGE REPORT",
                "=" * 70,
                "",
                f"  Scan Path:          {report.scan_path}",
                f"  Scanned At:         {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:           {report.scan_duration_seconds:.2f}s",
                "",
                f"  Files Analyzed:     {report.total_files}",
                f"  Comment Density:    {report.overall_comment_density:.1f}%",
                f"  API Coverage:       {report.overall_api_coverage:.1f}%",
                f"  Total Public APIs:  {report.total_public_apis}",
                f"  Undocumented APIs:  {report.undocumented_apis}",
                "",
            ]
            problem_files = [
                f for f in report.file_results
                if f.comment_density < config.min_comment_density or f.public_api_coverage < config.min_api_coverage
            ]
            if problem_files:
                lines.extend(["-" * 70, "  FILES BELOW THRESHOLDS", "-" * 70, ""])
                for f in sorted(problem_files, key=lambda x: x.public_api_coverage):
                    lines.append(f"  {f.path}")
                    lines.append(
                        f"    Density: {f.comment_density:.1f}%  "
                        f"Coverage: {f.public_api_coverage:.1f}%  "
                        f"Undocumented: {f.undocumented_count}"
                    )
                    lines.append("")
            else:
                lines.extend(["  All files meet documentation thresholds.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.undocumented_apis > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_naming_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    config = NamingConfig(
        scan_path=scan_path,
        check_functions=not getattr(args, "no_functions", False),
        check_classes=not getattr(args, "no_classes", False),
        check_variables=not getattr(args, "no_variables", False),
        check_constants=not getattr(args, "no_constants", False),
        allow_list=list(getattr(args, "allow_list", [])),
        include_tests=getattr(args, "include_tests", True),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist", "migrations",
        ],
        output_format=args.format,
    )

    try:
        scanner = NamingConventionScanner(config)
        report = scanner.scan(scan_path)

        if args.format == "json":
            print(scanner.generate_report(report, "json"))
        elif args.format in ("markdown", "md"):
            print(scanner.generate_report(report, "markdown"))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL NAMING CONVENTION REPORT",
                "=" * 70,
                "",
                f"  Scan Path:               {report.scan_path}",
                f"  Scanned At:              {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:                {report.scan_duration_seconds:.2f}s",
                "",
                f"  Total Violations:        {report.total_violations}",
                f"  Files With Violations:   {report.files_with_violations}",
                "",
            ]
            if report.violations_by_type:
                lines.append("  Violations by Type:")
                for etype, count in sorted(report.violations_by_type.items()):
                    lines.append(f"    {etype}: {count}")
                lines.append("")
            if report.has_violations:
                lines.extend(["-" * 70, "  VIOLATIONS", "-" * 70, ""])
                for file_path, violations in sorted(report.file_results.items()):
                    if not violations:
                        continue
                    lines.append(f"  {file_path}")
                    for v in sorted(violations, key=lambda x: x.line_number):
                        lines.append(f"    Line {v.line_number:4d}: [{v.element_type}] {v.element_name}")
                        if verbose:
                            lines.append(f"             {v.description}")
                    lines.append("")
            else:
                lines.extend(["  No naming violations found.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.has_violations else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1
