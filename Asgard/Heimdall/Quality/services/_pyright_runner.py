"""
Heimdall Type Checker - Pyright runner helpers.

Standalone functions for running Pyright and parsing its JSON output.
Accepts TypeCheckConfig as an explicit parameter rather than relying on
instance state.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from Asgard.Heimdall.Quality.models.type_check_models import (
    RULE_CATEGORY_MAP,
    FileTypeCheckStats,
    TypeCheckCategory,
    TypeCheckConfig,
    TypeCheckDiagnostic,
    TypeCheckReport,
    TypeCheckSeverity,
)


def run_pyright(path: Path, report: TypeCheckReport, config: TypeCheckConfig) -> None:
    """Run Pyright and populate the report."""
    verify_pyright_available(config)
    pyright_output = invoke_pyright(path, config)
    parse_pyright_output(pyright_output, path, report, config)


def verify_pyright_available(config: TypeCheckConfig) -> None:
    """Verify that pyright is available via npx."""
    try:
        result = subprocess.run(
            [config.npx_path, "pyright", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Pyright is not available. Install with: npm install -g pyright"
            )
    except FileNotFoundError:
        raise RuntimeError(
            f"npx not found at '{config.npx_path}'. "
            "Install Node.js or switch to engine='mypy'."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Pyright version check timed out.")


def build_pyright_config(path: Path, config: TypeCheckConfig) -> dict:
    """Build pyrightconfig dict."""
    config_data: dict = {"typeCheckingMode": config.type_checking_mode}

    if config.python_version:
        config_data["pythonVersion"] = config.python_version
    if config.python_platform:
        config_data["pythonPlatform"] = config.python_platform
    if config.venv_path:
        config_data["venvPath"] = str(Path(config.venv_path).parent)
        config_data["venv"] = Path(config.venv_path).name

    excludes = list(config.exclude_patterns)
    if not config.include_tests:
        excludes.extend(["**/test_*.py", "**/*_test.py", "**/tests/", "**/Hercules/"])
    config_data["exclude"] = excludes
    return config_data


def invoke_pyright(path: Path, config: TypeCheckConfig) -> dict:
    """Run pyright subprocess and return parsed JSON."""
    cmd: List[str] = [config.npx_path, "pyright", "--outputjson"]
    config_data = build_pyright_config(path, config)

    config_dir = path if path.is_dir() else path.parent
    existing_config = config_dir / "pyrightconfig.json"
    temp_config_path: Optional[Path] = None
    use_project_flag = existing_config.exists()

    try:
        if use_project_flag:
            temp_config_path = config_dir / ".pyrightconfig.heimdall.json"
            cmd.extend(["--project", str(temp_config_path)])
        else:
            temp_config_path = existing_config

        with open(temp_config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        cmd.append(str(path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.subprocess_timeout,
            cwd=str(path) if path.is_dir() else str(path.parent),
        )

        if result.stdout:
            try:
                return cast(Dict[Any, Any], json.loads(result.stdout))
            except json.JSONDecodeError:
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("{"):
                        try:
                            return cast(Dict[Any, Any], json.loads(line))
                        except json.JSONDecodeError:
                            continue

    finally:
        if temp_config_path and temp_config_path.exists():
            try:
                temp_config_path.unlink()
            except OSError:
                pass

    return {
        "version": "unknown",
        "generalDiagnostics": [],
        "summary": {"filesAnalyzed": 0, "errorCount": 0, "warningCount": 0, "informationCount": 0},
    }


def parse_pyright_output(
    output: dict,
    scan_path: Path,
    report: TypeCheckReport,
    config: TypeCheckConfig,
) -> None:
    """Parse pyright JSON output into the report."""
    report.pyright_version = output.get("version", "unknown")
    summary = output.get("summary", {})
    report.files_scanned = summary.get("filesAnalyzed", 0)
    report.exit_code = 1 if summary.get("errorCount", 0) > 0 else 0

    file_diagnostics: Dict[str, List[TypeCheckDiagnostic]] = {}

    for diag in output.get("generalDiagnostics", []):
        severity_str = diag.get("severity", "error").lower()

        if config.severity_filter and severity_str != config.severity_filter:
            continue
        if not config.include_warnings and severity_str != "error":
            continue

        severity = TypeCheckSeverity.ERROR
        if severity_str == "warning":
            severity = TypeCheckSeverity.WARNING
        elif severity_str == "information":
            severity = TypeCheckSeverity.INFORMATION

        file_path = diag.get("file", "")
        range_data = diag.get("range", {})
        start = range_data.get("start", {})
        end = range_data.get("end", {})

        try:
            relative_path = str(Path(file_path).relative_to(scan_path))
        except (ValueError, TypeError):
            relative_path = os.path.basename(file_path) if file_path else ""

        rule = diag.get("rule", "")
        category = RULE_CATEGORY_MAP.get(rule, TypeCheckCategory.GENERAL)

        if config.category_filter:
            if category.value != config.category_filter and category != config.category_filter:
                continue

        diagnostic = TypeCheckDiagnostic(
            file_path=file_path,
            relative_path=relative_path,
            line=start.get("line", 0) + 1,
            column=start.get("character", 0),
            end_line=end.get("line", 0) + 1,
            end_column=end.get("character", 0),
            severity=severity,
            message=diag.get("message", ""),
            rule=rule,
            category=category,
        )

        report.add_diagnostic(diagnostic)

        if file_path not in file_diagnostics:
            file_diagnostics[file_path] = []
        file_diagnostics[file_path].append(diagnostic)

    for file_path, diags in file_diagnostics.items():
        try:
            rel_path = str(Path(file_path).relative_to(scan_path))
        except (ValueError, TypeError):
            rel_path = os.path.basename(file_path) if file_path else ""

        file_stats = FileTypeCheckStats(
            file_path=file_path,
            relative_path=rel_path,
            error_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.ERROR.value),
            warning_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.WARNING.value),
            info_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.INFORMATION.value),
            diagnostics=diags,
        )
        report.add_file_stats(file_stats)
