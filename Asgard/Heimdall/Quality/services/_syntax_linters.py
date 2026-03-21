import json
import subprocess
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.models.syntax_models import (
    LinterType,
    SyntaxConfig,
    SyntaxIssue,
    SyntaxSeverity,
)


def run_ruff(scan_path: Path, config: SyntaxConfig) -> List[SyntaxIssue]:
    """Run ruff linter and parse output."""
    issues = []

    try:
        exclude_args = []
        for pattern in config.exclude_patterns:
            exclude_args.extend(["--exclude", pattern])

        cmd = [
            "ruff", "check",
            str(scan_path),
            "--output-format", "json",
        ] + exclude_args

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.stdout:
            try:
                findings = json.loads(result.stdout)
                for finding in findings:
                    severity = _ruff_severity(finding.get("fix"))
                    issue = SyntaxIssue(
                        file_path=finding.get("filename", ""),
                        line_number=finding.get("location", {}).get("row", 0),
                        column=finding.get("location", {}).get("column", 0),
                        code=finding.get("code", ""),
                        message=finding.get("message", ""),
                        severity=severity,
                        linter=LinterType.RUFF,
                        fixable=finding.get("fix") is not None,
                        suggested_fix=finding.get("fix", {}).get("message") if finding.get("fix") else None,
                    )
                    issues.append(issue)
            except json.JSONDecodeError:
                pass

    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass

    return issues


def run_ruff_fix(scan_path: Path, config: SyntaxConfig) -> int:
    """Run ruff with --fix and return number of fixes."""
    try:
        exclude_args = []
        for pattern in config.exclude_patterns:
            exclude_args.extend(["--exclude", pattern])

        cmd = [
            "ruff", "check",
            str(scan_path),
            "--fix",
            "--output-format", "json",
        ] + exclude_args

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.stdout:
            try:
                findings = json.loads(result.stdout)
                return sum(1 for f in findings if f.get("fix"))
            except json.JSONDecodeError:
                pass

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return 0


def run_flake8(scan_path: Path, config: SyntaxConfig) -> List[SyntaxIssue]:
    """Run flake8 linter and parse output."""
    issues = []

    try:
        exclude_str = ",".join(config.exclude_patterns)

        cmd = [
            "flake8",
            str(scan_path),
            "--format", "%(path)s:%(row)d:%(col)d:%(code)s:%(text)s",
            "--exclude", exclude_str,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split(":", 4)
            if len(parts) >= 5:
                severity = _flake8_severity(parts[3])
                issue = SyntaxIssue(
                    file_path=parts[0],
                    line_number=int(parts[1]) if parts[1].isdigit() else 0,
                    column=int(parts[2]) if parts[2].isdigit() else 0,
                    code=parts[3],
                    message=parts[4],
                    severity=severity,
                    linter=LinterType.FLAKE8,
                    fixable=False,
                )
                issues.append(issue)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return issues


def run_pylint(scan_path: Path, config: SyntaxConfig) -> List[SyntaxIssue]:
    """Run pylint and parse output."""
    issues = []

    try:
        ignore_str = ",".join(config.exclude_patterns)

        cmd = [
            "pylint",
            str(scan_path),
            "--output-format", "json",
            "--ignore", ignore_str,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        if result.stdout:
            try:
                findings = json.loads(result.stdout)
                for finding in findings:
                    severity = _pylint_severity(finding.get("type", ""))
                    issue = SyntaxIssue(
                        file_path=finding.get("path", ""),
                        line_number=finding.get("line", 0),
                        column=finding.get("column", 0),
                        code=finding.get("message-id", ""),
                        message=finding.get("message", ""),
                        severity=severity,
                        linter=LinterType.PYLINT,
                        fixable=False,
                    )
                    issues.append(issue)
            except json.JSONDecodeError:
                pass

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return issues


def run_mypy(scan_path: Path, config: SyntaxConfig) -> List[SyntaxIssue]:
    """Run mypy type checker and parse output."""
    issues = []

    try:
        exclude_pattern = "|".join(config.exclude_patterns)

        cmd = [
            "mypy",
            str(scan_path),
            "--output", "json",
            "--exclude", exclude_pattern,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                finding = json.loads(line)
                severity = _mypy_severity(finding.get("severity", "error"))
                issue = SyntaxIssue(
                    file_path=finding.get("file", ""),
                    line_number=finding.get("line", 0),
                    column=finding.get("column", 0),
                    code=finding.get("code", "mypy"),
                    message=finding.get("message", ""),
                    severity=severity,
                    linter=LinterType.MYPY,
                    fixable=False,
                )
                issues.append(issue)
            except json.JSONDecodeError:
                pass

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return issues


def _ruff_severity(fix_info: Optional[dict]) -> SyntaxSeverity:
    """Convert ruff fix info to severity."""
    return SyntaxSeverity.WARNING


def _flake8_severity(code: str) -> SyntaxSeverity:
    """Convert flake8 code to severity."""
    if code.startswith("E"):
        return SyntaxSeverity.ERROR
    elif code.startswith("W"):
        return SyntaxSeverity.WARNING
    elif code.startswith("F"):
        return SyntaxSeverity.ERROR
    elif code.startswith("C"):
        return SyntaxSeverity.STYLE
    return SyntaxSeverity.INFO


def _pylint_severity(msg_type: str) -> SyntaxSeverity:
    """Convert pylint message type to severity."""
    type_map = {
        "error": SyntaxSeverity.ERROR,
        "fatal": SyntaxSeverity.ERROR,
        "warning": SyntaxSeverity.WARNING,
        "convention": SyntaxSeverity.STYLE,
        "refactor": SyntaxSeverity.INFO,
        "information": SyntaxSeverity.INFO,
    }
    return type_map.get(msg_type.lower(), SyntaxSeverity.WARNING)


def _mypy_severity(severity: str) -> SyntaxSeverity:
    """Convert mypy severity to our severity."""
    severity_map = {
        "error": SyntaxSeverity.ERROR,
        "warning": SyntaxSeverity.WARNING,
        "note": SyntaxSeverity.INFO,
    }
    return severity_map.get(severity.lower(), SyntaxSeverity.ERROR)
