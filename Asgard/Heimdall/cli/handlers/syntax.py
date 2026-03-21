import argparse
from pathlib import Path

from Asgard.Heimdall.Quality.models.syntax_models import (
    LinterType,
    SyntaxConfig,
    SyntaxSeverity,
)
from Asgard.Heimdall.Quality.services.syntax_checker import SyntaxChecker
from Asgard.Heimdall.Dependencies.models.requirements_models import RequirementsConfig
from Asgard.Heimdall.Dependencies.services.requirements_checker import RequirementsChecker
from Asgard.Heimdall.Dependencies.models.license_models import LicenseConfig
from Asgard.Heimdall.Dependencies.services.license_checker import LicenseChecker


def run_syntax_analysis(args: argparse.Namespace, verbose: bool = False, fix_mode: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".mypy_cache", ".pytest_cache", "*.egg-info", "build", "dist",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    linter_map = {
        "ruff": LinterType.RUFF,
        "flake8": LinterType.FLAKE8,
        "pylint": LinterType.PYLINT,
        "mypy": LinterType.MYPY,
    }
    linters = [linter_map[l] for l in args.linters if l in linter_map]

    severity_map = {
        "error": SyntaxSeverity.ERROR,
        "warning": SyntaxSeverity.WARNING,
        "info": SyntaxSeverity.INFO,
        "style": SyntaxSeverity.STYLE,
    }
    min_severity = severity_map.get(args.severity, SyntaxSeverity.WARNING)

    config = SyntaxConfig(
        scan_path=scan_path,
        include_extensions=args.extensions,
        exclude_patterns=exclude_patterns,
        linters=linters,
        min_severity=min_severity,
        include_style=getattr(args, 'include_style', False),
        fix_mode=fix_mode,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = SyntaxChecker(config)

        if fix_mode:
            result, fixes_applied = checker.fix()
            report = checker.generate_report(result, args.format)
            print(report)
            if fixes_applied > 0:
                print(f"\nApplied {fixes_applied} auto-fixes.")
            return 1 if result.has_errors else 0
        else:
            result = checker.analyze()
            report = checker.generate_report(result, args.format)
            print(report)
            return 1 if result.has_errors else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_requirements_analysis(args: argparse.Namespace, verbose: bool = False, sync_mode: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
        "*.egg-info",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    check_unused = getattr(args, "check_unused", True)
    if getattr(args, "no_check_unused", False):
        check_unused = False

    config = RequirementsConfig(
        scan_path=scan_path,
        requirements_files=getattr(args, "requirements_files", ["requirements.txt"]),
        exclude_patterns=exclude_patterns,
        check_unused=check_unused,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = RequirementsChecker(config)

        if sync_mode:
            result, changes = checker.sync(
                target_file=getattr(args, 'target_file', 'requirements.txt')
            )
            report = checker.generate_report(result, args.format)
            print(report)
            if changes:
                print(f"\nSync complete: {len(changes)} changes made")
            return 1 if result.has_issues else 0
        else:
            result = checker.analyze()
            report = checker.generate_report(result, args.format)
            print(report)
            return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_licenses_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    config = LicenseConfig(
        scan_path=scan_path,
        requirements_files=getattr(args, "requirements_files", ["requirements.txt"]),
        allowed_licenses=getattr(args, "allowed", None),
        prohibited_licenses=getattr(args, "prohibited", None),
        warning_licenses=getattr(args, "warn", None),
        use_cache=not getattr(args, "no_cache", False),
        output_format=args.format,
        verbose=verbose,
    )

    try:
        checker = LicenseChecker(config)
        result = checker.analyze()
        report = checker.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
