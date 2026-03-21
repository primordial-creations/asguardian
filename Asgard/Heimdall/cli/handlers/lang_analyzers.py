import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import JSAnalysisConfig
from Asgard.Heimdall.Quality.languages.javascript.services.js_analyzer import JSAnalyzer
from Asgard.Heimdall.Quality.languages.typescript.services.ts_analyzer import TSAnalyzer
from Asgard.Heimdall.Quality.languages.shell.models.shell_models import ShellAnalysisConfig
from Asgard.Heimdall.Quality.languages.shell.services.shell_analyzer import ShellAnalyzer


def run_js_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        max_file_lines = getattr(args, "max_file_lines", 500)
        max_complexity = getattr(args, "max_complexity", 10)

        config = JSAnalysisConfig(
            scan_path=scan_path,
            language="javascript",
            include_extensions=[".js", ".jsx"],
            exclude_patterns=[
                "node_modules", ".git", "dist", "build", "__pycache__", "*.min.js"
            ] + exclude,
            disabled_rules=disabled,
            max_file_lines=max_file_lines,
            max_complexity=max_complexity,
        )
        analyzer = JSAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  JAVASCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def run_ts_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        max_file_lines = getattr(args, "max_file_lines", 500)
        max_complexity = getattr(args, "max_complexity", 10)

        config = JSAnalysisConfig(
            scan_path=scan_path,
            language="typescript",
            include_extensions=[".ts", ".tsx"],
            exclude_patterns=[
                "node_modules", ".git", "dist", "build", "__pycache__"
            ] + exclude,
            disabled_rules=disabled,
            max_file_lines=max_file_lines,
            max_complexity=max_complexity,
        )
        analyzer = TSAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  TYPESCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def run_shell_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    try:
        scan_path = Path(args.path).resolve()
        if not scan_path.exists():
            print(f"Error: Path does not exist: {scan_path}")
            return 1

        exclude = list(args.exclude) if getattr(args, "exclude", None) else []
        disabled = list(args.disabled_rules) if getattr(args, "disabled_rules", None) else []
        also_check_shebangs = not getattr(args, "no_shebang_check", False)

        config = ShellAnalysisConfig(
            scan_path=scan_path,
            exclude_patterns=["node_modules", ".git", "__pycache__"] + exclude,
            also_check_shebangs=also_check_shebangs,
            disabled_rules=disabled,
        )
        analyzer = ShellAnalyzer(config)
        report = analyzer.analyze()

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.dict(), default=str, indent=2))
            return 1 if report.error_count > 0 else 0

        out_lines = [
            "",
            "=" * 70,
            "  SHELL SCRIPT ANALYSIS REPORT",
            "=" * 70,
            f"  Scan Path:       {report.scan_path}",
            f"  Files Analyzed:  {report.files_analyzed}",
            f"  Total Findings:  {report.total_findings}",
            f"  Errors:          {report.error_count}",
            f"  Warnings:        {report.warning_count}",
            f"  Info:            {report.info_count}",
            f"  Duration:        {report.scan_duration_seconds:.2f}s",
            "",
        ]
        if report.findings:
            out_lines.extend(["-" * 70, "  FINDINGS", "-" * 70, ""])
            for finding in report.findings:
                severity_label = str(finding.severity).upper()
                out_lines.append(f"  [{severity_label}] {finding.rule_id}: {finding.title}")
                out_lines.append(f"  File: {finding.file_path}:{finding.line_number}")
                if finding.code_snippet:
                    out_lines.append(f"  Code: {finding.code_snippet.strip()}")
                if verbose:
                    out_lines.append(f"  Description: {finding.description}")
                    if finding.fix_suggestion:
                        out_lines.append(f"  Fix: {finding.fix_suggestion}")
                out_lines.append("")
        else:
            out_lines.extend(["  No findings detected.", ""])
        out_lines.append("=" * 70)
        print("\n".join(out_lines))
        return 1 if report.error_count > 0 else 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1
