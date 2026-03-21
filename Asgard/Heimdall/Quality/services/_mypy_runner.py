"""
Heimdall Type Checker - mypy runner helpers.

Standalone functions for running mypy and parsing its output.
Accepts TypeCheckConfig as an explicit parameter rather than relying on
instance state, so the TypeChecker class can delegate without exposing
implementation details.
"""

import fnmatch
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from Asgard.Heimdall.Quality.models.type_check_models import (
    FileTypeCheckStats,
    TypeCheckCategory,
    TypeCheckConfig,
    TypeCheckDiagnostic,
    TypeCheckReport,
    TypeCheckSeverity,
)


def run_mypy(path: Path, report: TypeCheckReport, config: TypeCheckConfig) -> None:
    """
    Run mypy per top-level module via subprocess.

    Scoping each mypy invocation to one top-level module avoids two issues:
    1. Duplicate module name conflicts (e.g. multiple setup.py files).
    2. A fatal syntax error in one module aborting analysis of all others.

    subprocess is used instead of mypy.api.run() because the API does not
    reset mypy's global state between calls in the same process, causing
    hangs on subsequent invocations.  Each module group has far fewer files
    than the per-process OS argument-list limit.
    """
    mypy_bin = shutil.which("mypy")
    if not mypy_bin:
        raise RuntimeError(
            "mypy is not available. Install with: pip install mypy"
        )

    report.pyright_version = get_mypy_version(mypy_bin)

    py_files = collect_python_files(path, config)
    report.files_scanned = len(py_files)

    if not py_files:
        return

    groups: Dict[str, List[Path]] = {}
    for f in py_files:
        try:
            rel = f.relative_to(path)
        except ValueError:
            rel = f
        top = str(rel.parts[0]) if len(rel.parts) > 1 else "__root__"
        groups.setdefault(top, []).append(f)

    base_cmd: List[str] = [
        mypy_bin,
        "--show-error-codes",
        "--no-error-summary",
        "--ignore-missing-imports",
        "--no-incremental",
        "--explicit-package-bases",
    ]

    if config.type_checking_mode == "strict":
        base_cmd.append("--strict")

    if config.python_version:
        base_cmd.extend(["--python-version", config.python_version])

    if config.venv_path:
        base_cmd.extend(
            ["--python-executable", str(Path(config.venv_path) / "bin" / "python")]
        )

    combined_output = ""
    worst_exit = 0
    cwd = str(path) if path.is_dir() else str(path.parent)

    for group_files in groups.values():
        cmd = base_cmd + [str(f) for f in group_files]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.subprocess_timeout,
                cwd=cwd,
            )
            combined_output += result.stdout + result.stderr
            ec = result.returncode
            if ec == 2:
                ec = 1
            worst_exit = max(worst_exit, ec)
        except subprocess.TimeoutExpired:
            worst_exit = max(worst_exit, 1)
        except Exception:
            pass

    report.exit_code = worst_exit
    parse_mypy_output(combined_output, path, report, config)


def get_mypy_version(mypy_bin: str) -> str:
    """Get mypy version string (e.g. '1.19.1')."""
    try:
        result = subprocess.run(
            [mypy_bin, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        parts = result.stdout.strip().split()
        return parts[1] if len(parts) >= 2 else "unknown"
    except Exception:
        return "unknown"


def collect_python_files(path: Path, config: TypeCheckConfig) -> List[Path]:
    """
    Collect Python files to check, respecting exclude patterns.

    Files in directories whose names are not valid Python identifiers are
    excluded because mypy cannot construct a module name for them and will
    abort with a fatal error when it encounters them.
    """
    if path.is_file():
        return [path] if path.suffix == ".py" else []

    files: List[Path] = []
    for root, dirs, filenames in os.walk(str(path)):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if not is_excluded(root_path / d, path, config)
            and is_valid_package_name(d)
        ]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            file_path = root_path / filename
            if is_excluded(file_path, path, config):
                continue
            if not config.include_tests:
                rel = str(file_path.relative_to(path) if file_path.is_relative_to(path) else file_path)
                if "test_" in filename or filename.endswith("_test.py") or "/tests/" in rel:
                    continue
            files.append(file_path)

    return files


def is_valid_package_name(name: str) -> bool:
    """
    Return True if 'name' is a valid Python identifier (and thus a valid
    package/module name that mypy can handle).
    """
    return name.isidentifier()


def is_excluded(file_path: Path, root: Path, config: TypeCheckConfig) -> bool:
    """Check if a path matches any exclude pattern."""
    parts = file_path.parts
    name = file_path.name
    for pattern in config.exclude_patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def mypy_code_to_category(code: str) -> TypeCheckCategory:
    """Map a mypy error code to a TypeCheckCategory."""
    if not code:
        return TypeCheckCategory.GENERAL

    code_lower = code.lower()
    if code_lower in ("import", "import-untyped", "import-not-found", "no-redef"):
        return TypeCheckCategory.MISSING_IMPORT
    if code_lower in ("name-defined", "used-before-def"):
        return TypeCheckCategory.UNDEFINED_VARIABLE
    if code_lower in ("arg-type", "call-arg", "call-overload", "misc"):
        return TypeCheckCategory.ARGUMENT_ERROR
    if code_lower in ("return-value", "return", "no-return"):
        return TypeCheckCategory.RETURN_TYPE
    if code_lower in ("attr-defined", "union-attr"):
        return TypeCheckCategory.ATTRIBUTE_ERROR
    if code_lower in ("assignment", "incompatible-types"):
        return TypeCheckCategory.ASSIGNMENT_ERROR
    if code_lower in ("operator",):
        return TypeCheckCategory.OPERATOR_ERROR
    if code_lower in ("override",):
        return TypeCheckCategory.OVERRIDE_ERROR
    if code_lower in ("type-arg", "valid-type"):
        return TypeCheckCategory.GENERIC_ERROR
    if code_lower in ("typeddict-item", "typeddict-unknown-key"):
        return TypeCheckCategory.TYPED_DICT_ERROR
    if code_lower in ("unreachable",):
        return TypeCheckCategory.UNREACHABLE_CODE
    return TypeCheckCategory.GENERAL


def parse_mypy_output(
    output: str,
    scan_path: Path,
    report: TypeCheckReport,
    config: TypeCheckConfig,
) -> None:
    """
    Parse mypy text output into the report.

    mypy output format:
        path/to/file.py:42: error: message  [error-code]
        path/to/file.py:42: note: message
    """
    file_diagnostics: Dict[str, List[TypeCheckDiagnostic]] = {}

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Found ") or line.startswith("Success:"):
            continue

        match = re.match(
            r'^(.+?):(\d+)(?::(\d+))?\s*:\s*(error|warning|note)\s*:\s*(.+?)(?:\s+\[([^\]]+)\])?$',
            line,
        )
        if not match:
            continue

        file_path_str, line_num, col_num, sev_str, message, error_code = match.groups()

        if sev_str == "note":
            sev_str = "information"
        severity = TypeCheckSeverity.ERROR if sev_str == "error" else (
            TypeCheckSeverity.WARNING if sev_str == "warning" else TypeCheckSeverity.INFORMATION
        )

        if config.severity_filter and sev_str != config.severity_filter:
            continue
        if not config.include_warnings and severity != TypeCheckSeverity.ERROR:
            continue

        try:
            rel_path = str(Path(file_path_str).relative_to(scan_path))
        except (ValueError, TypeError):
            rel_path = os.path.basename(file_path_str)

        rule = error_code or ""
        category = mypy_code_to_category(rule)

        if config.category_filter:
            if category.value != config.category_filter:
                continue

        diagnostic = TypeCheckDiagnostic(
            file_path=file_path_str,
            relative_path=rel_path,
            line=int(line_num),
            column=int(col_num) if col_num else 0,
            severity=severity,
            message=message.strip(),
            rule=rule,
            category=category,
        )

        report.add_diagnostic(diagnostic)

        if file_path_str not in file_diagnostics:
            file_diagnostics[file_path_str] = []
        file_diagnostics[file_path_str].append(diagnostic)

    for file_path_str, diags in file_diagnostics.items():
        try:
            rel_path = str(Path(file_path_str).relative_to(scan_path))
        except (ValueError, TypeError):
            rel_path = os.path.basename(file_path_str)

        file_stats = FileTypeCheckStats(
            file_path=file_path_str,
            relative_path=rel_path,
            error_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.ERROR.value),
            warning_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.WARNING.value),
            info_count=sum(1 for d in diags if d.severity == TypeCheckSeverity.INFORMATION.value),
            diagnostics=diags,
        )
        report.add_file_stats(file_stats)
