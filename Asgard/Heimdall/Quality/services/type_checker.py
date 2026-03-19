"""
Heimdall Type Checker Service

Static type checking analysis using either mypy (default) or Pyright.

Engines:
- mypy (default): Pure Python, installed as a package dependency. Covers the
  vast majority of type checking use cases without requiring Node.js.
- pyright: Microsoft's Pyright engine (same as Pylance). Requires Node.js and
  npx. Use when you need exact Pylance feature parity.

Features (both engines):
- Type inference and validation
- Type compatibility/assignability checking
- Missing/undefined attribute detection
- Incorrect argument types/counts
- Return type mismatches
- Union type narrowing
- Generic type validation
- Protocol conformance
- TypedDict validation
- Import resolution errors
- Unreachable code detection

Pyright-only features:
- Overload resolution diagnostics
- Deprecated API usage detection
- Platform-specific type narrowing
"""

import fnmatch
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.type_check_models import (
    RULE_CATEGORY_MAP,
    FileTypeCheckStats,
    TypeCheckCategory,
    TypeCheckConfig,
    TypeCheckDiagnostic,
    TypeCheckReport,
    TypeCheckSeverity,
)


class TypeChecker:
    """
    Static type checker supporting mypy (default) and Pyright backends.

    mypy is the default engine - it is a pure Python package already present
    in the project's venv and covers all common type checking scenarios.
    Pyright requires Node.js/npx and provides exact Pylance feature parity.

    Usage:
        # Default: mypy engine
        checker = TypeChecker()
        report = checker.analyze(Path("./src"))

        # Pyright engine (Pylance parity, requires Node.js)
        checker = TypeChecker(TypeCheckConfig(engine="pyright"))
        report = checker.analyze(Path("./src"))

        print(f"Errors: {report.total_errors}")
        for diag in report.all_diagnostics:
            print(f"  {diag.qualified_location}: {diag.message}")
    """

    def __init__(self, config: Optional[TypeCheckConfig] = None):
        """
        Initialize type checker.

        Args:
            config: Configuration for type checking. If None, uses mypy defaults.
        """
        self.config = config or TypeCheckConfig()

    def analyze(self, path: Path) -> TypeCheckReport:
        """
        Run type checking on a file or directory.

        Args:
            path: Path to file or directory to analyze

        Returns:
            TypeCheckReport with all diagnostics

        Raises:
            FileNotFoundError: If path does not exist
            RuntimeError: If the selected engine is not available
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = TypeCheckReport(
            scan_path=str(path),
            type_checking_mode=self.config.type_checking_mode,
        )

        if self.config.engine == "pyright":
            self._run_pyright(path, report)
        else:
            self._run_mypy(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()
        return report

    # ------------------------------------------------------------------
    # mypy backend
    # ------------------------------------------------------------------

    def _run_mypy(self, path: Path, report: TypeCheckReport) -> None:
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

        report.pyright_version = self._get_mypy_version(mypy_bin)

        py_files = self._collect_python_files(path)
        report.files_scanned = len(py_files)

        if not py_files:
            return

        # Group files by top-level subdirectory under the scan root.
        # Files directly in the root go into "__root__".
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

        if self.config.type_checking_mode == "strict":
            base_cmd.append("--strict")

        if self.config.python_version:
            base_cmd.extend(["--python-version", self.config.python_version])

        if self.config.venv_path:
            base_cmd.extend(
                ["--python-executable", str(Path(self.config.venv_path) / "bin" / "python")]
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
                    timeout=self.config.subprocess_timeout,
                    cwd=cwd,
                )
                combined_output += result.stdout + result.stderr
                ec = result.returncode
                # Exit code 2 = fatal (e.g. syntax error). Treat as 1 so we
                # capture the diagnostic and continue to the next module.
                if ec == 2:
                    ec = 1
                worst_exit = max(worst_exit, ec)
            except subprocess.TimeoutExpired:
                worst_exit = max(worst_exit, 1)
            except Exception:
                pass

        report.exit_code = worst_exit
        self._parse_mypy_output(combined_output, path, report)

    def _get_mypy_version(self, mypy_bin: str) -> str:
        """Get mypy version string (e.g. '1.19.1')."""
        try:
            result = subprocess.run(
                [mypy_bin, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            # output: "mypy 1.19.1 (compiled: yes)" — grab the second token
            parts = result.stdout.strip().split()
            return parts[1] if len(parts) >= 2 else "unknown"
        except Exception:
            return "unknown"

    def _collect_python_files(self, path: Path) -> List[Path]:
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

            # Prune excluded directories and directories with invalid Python
            # identifiers (mypy cannot handle them and aborts on encounter).
            dirs[:] = [
                d for d in dirs
                if not self._is_excluded(root_path / d, path)
                and self._is_valid_package_name(d)
            ]

            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                file_path = root_path / filename
                if self._is_excluded(file_path, path):
                    continue
                if not self.config.include_tests:
                    rel = str(file_path.relative_to(path) if file_path.is_relative_to(path) else file_path)
                    if "test_" in filename or filename.endswith("_test.py") or "/tests/" in rel:
                        continue
                files.append(file_path)

        return files

    @staticmethod
    def _is_valid_package_name(name: str) -> bool:
        """
        Return True if 'name' is a valid Python identifier (and thus a valid
        package/module name that mypy can handle).
        """
        return name.isidentifier()

    def _is_excluded(self, file_path: Path, root: Path) -> bool:
        """Check if a path matches any exclude pattern."""
        parts = file_path.parts
        name = file_path.name
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _parse_mypy_output(self, output: str, scan_path: Path, report: TypeCheckReport) -> None:
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

            # Match: filepath:line: severity: message  [code]
            match = re.match(
                r'^(.+?):(\d+)(?::(\d+))?\s*:\s*(error|warning|note)\s*:\s*(.+?)(?:\s+\[([^\]]+)\])?$',
                line,
            )
            if not match:
                continue

            file_path_str, line_num, col_num, sev_str, message, error_code = match.groups()

            # Normalise severity
            if sev_str == "note":
                sev_str = "information"
            severity = TypeCheckSeverity.ERROR if sev_str == "error" else (
                TypeCheckSeverity.WARNING if sev_str == "warning" else TypeCheckSeverity.INFORMATION
            )

            # Apply severity filter
            if self.config.severity_filter and sev_str != self.config.severity_filter:
                continue
            if not self.config.include_warnings and severity != TypeCheckSeverity.ERROR:
                continue

            # Resolve relative path
            try:
                rel_path = str(Path(file_path_str).relative_to(scan_path))
            except (ValueError, TypeError):
                rel_path = os.path.basename(file_path_str)

            # Map error code to category
            rule = error_code or ""
            category = self._mypy_code_to_category(rule)

            # Apply category filter
            if self.config.category_filter:
                if category.value != self.config.category_filter:
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

        # Build per-file stats
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

    def _mypy_code_to_category(self, code: str) -> TypeCheckCategory:
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

    # ------------------------------------------------------------------
    # Pyright backend
    # ------------------------------------------------------------------

    def _run_pyright(self, path: Path, report: TypeCheckReport) -> None:
        """Run Pyright and populate the report."""
        self._verify_pyright_available()

        pyright_output = self._invoke_pyright(path)
        self._parse_pyright_output(pyright_output, path, report)

    def _verify_pyright_available(self) -> None:
        """Verify that pyright is available via npx."""
        try:
            result = subprocess.run(
                [self.config.npx_path, "pyright", "--version"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Pyright is not available. Install with: npm install -g pyright"
                )
            version = result.stdout.strip()
            self._pyright_version = version.split()[-1] if version.split() else version
        except FileNotFoundError:
            raise RuntimeError(
                f"npx not found at '{self.config.npx_path}'. "
                "Install Node.js or switch to engine='mypy'."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Pyright version check timed out.")

    def _build_pyright_config(self, path: Path) -> dict:
        """Build pyrightconfig dict."""
        config_data: dict = {"typeCheckingMode": self.config.type_checking_mode}

        if self.config.python_version:
            config_data["pythonVersion"] = self.config.python_version
        if self.config.python_platform:
            config_data["pythonPlatform"] = self.config.python_platform
        if self.config.venv_path:
            config_data["venvPath"] = str(Path(self.config.venv_path).parent)
            config_data["venv"] = Path(self.config.venv_path).name

        excludes = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            excludes.extend(["**/test_*.py", "**/*_test.py", "**/tests/", "**/Hercules/"])
        config_data["exclude"] = excludes
        return config_data

    def _invoke_pyright(self, path: Path) -> dict:
        """Run pyright subprocess and return parsed JSON."""
        cmd = [self.config.npx_path, "pyright", "--outputjson"]
        config_data = self._build_pyright_config(path)

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
                timeout=self.config.subprocess_timeout,
                cwd=str(path) if path.is_dir() else str(path.parent),
            )

            if result.stdout:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    for line in result.stdout.split("\n"):
                        line = line.strip()
                        if line.startswith("{"):
                            try:
                                return json.loads(line)
                            except json.JSONDecodeError:
                                continue

        finally:
            if temp_config_path and temp_config_path.exists():
                try:
                    temp_config_path.unlink()
                except OSError:
                    pass

        return {
            "version": getattr(self, "_pyright_version", "unknown"),
            "generalDiagnostics": [],
            "summary": {"filesAnalyzed": 0, "errorCount": 0, "warningCount": 0, "informationCount": 0},
        }

    def _parse_pyright_output(self, output: dict, scan_path: Path, report: TypeCheckReport) -> None:
        """Parse pyright JSON output into the report."""
        report.pyright_version = output.get("version", getattr(self, "_pyright_version", "unknown"))
        summary = output.get("summary", {})
        report.files_scanned = summary.get("filesAnalyzed", 0)
        report.exit_code = 1 if summary.get("errorCount", 0) > 0 else 0

        file_diagnostics: Dict[str, List[TypeCheckDiagnostic]] = {}

        for diag in output.get("generalDiagnostics", []):
            severity_str = diag.get("severity", "error").lower()

            if self.config.severity_filter and severity_str != self.config.severity_filter:
                continue
            if not self.config.include_warnings and severity_str != "error":
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

            if self.config.category_filter:
                if category.value != self.config.category_filter and category != self.config.category_filter:
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

    # ------------------------------------------------------------------
    # Report generation (shared)
    # ------------------------------------------------------------------

    def generate_report(self, report: TypeCheckReport, output_format: str = "text") -> str:
        """Generate formatted type checking report."""
        format_lower = output_format.lower()
        if format_lower == "json":
            return self._generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return self._generate_markdown_report(report)
        return self._generate_text_report(report)

    # Maps rule codes (mypy / pyright) to short plain-English descriptions.
    _RULE_DESCRIPTIONS: Dict[str, str] = {
        # mypy codes
        "import": "module or name cannot be found at import time",
        "import-untyped": "imported module has no type stubs",
        "import-not-found": "module or name cannot be found at import time",
        "no-redef": "name re-defined in an incompatible way",
        "name-defined": "name used that was never assigned or imported",
        "used-before-def": "name used before it is assigned",
        "arg-type": "wrong type passed as an argument",
        "call-arg": "wrong number of arguments passed to a function",
        "call-overload": "no matching overload for the given arguments",
        "misc": "miscellaneous type error",
        "return-value": "returned value is incompatible with the declared return type",
        "return": "function return type mismatch",
        "no-return": "function with NoReturn actually returns",
        "attr-defined": "accessing a member that does not exist on the type",
        "union-attr": "member access on a union type that may not have the attribute",
        "assignment": "assigning a value of an incompatible type",
        "incompatible-types": "value is incompatible with the expected type",
        "operator": "operator used with incompatible operand types",
        "override": "subclass method signature does not match the base class",
        "type-arg": "generic type used with incorrect type arguments",
        "valid-type": "type expression is not valid",
        "typeddict-item": "TypedDict key has an incompatible value type",
        "typeddict-unknown-key": "unknown key used with a TypedDict",
        "unreachable": "code path that can never execute",
        # pyright codes
        "reportMissingImports": "module or name cannot be found at import time",
        "reportMissingModuleSource": "source for an imported module cannot be located",
        "reportUndefinedVariable": "name used that was never assigned or imported",
        "reportArgumentType": "wrong type passed as an argument",
        "reportCallIssue": "incorrect function or method call",
        "reportReturnType": "returned value is incompatible with the declared return type",
        "reportAttributeAccessIssue": "accessing a member that does not exist on the type",
        "reportAssignmentType": "assigning a value of an incompatible type",
        "reportOperatorIssue": "operator used with incompatible operand types",
        "reportIncompatibleMethodOverride": "subclass method signature does not match the base class",
        "reportIncompatibleVariableOverride": "subclass variable type does not match the base class",
        "reportIndexIssue": "subscript used on a non-subscriptable type",
        "reportGeneralTypeIssues": "general type incompatibility",
        "reportUnusedImport": "imported name is never used",
        "reportUnusedVariable": "variable is assigned but never used",
        "reportDeprecated": "use of a deprecated API",
    }

    def _generate_text_report(self, report: TypeCheckReport) -> str:
        """Generate plain text report."""
        engine_label = f"{'Pyright' if self.config.engine == 'pyright' else 'mypy'} {report.pyright_version}"
        lines = [
            "=" * 70,
            f"STATIC TYPE CHECKING REPORT ({engine_label})",
            "=" * 70,
            "",
            f"Scan Path: {report.scan_path}",
            f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {report.scan_duration_seconds:.2f} seconds",
            f"Engine: {engine_label}",
            f"Mode: {report.type_checking_mode}",
            f"Files Analyzed: {report.files_scanned}",
            "",
            "SUMMARY",
            "-" * 50,
            f"Total Errors: {report.total_errors}",
            f"Total Warnings: {report.total_warnings}",
            f"Total Info: {report.total_info}",
            f"Files With Errors: {report.files_with_errors}",
            f"Status: {'PASSING' if report.is_compliant else 'FAILING'}",
            "",
        ]

        if report.errors_by_category:
            lines.extend(["ERRORS BY CATEGORY", "-" * 50])
            for cat, count in sorted(report.errors_by_category.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  {cat.replace('_', ' ').title():<30} {count:>5}")
            lines.extend([
                "",
                "  CATEGORY DESCRIPTIONS",
                "  " + "-" * 47,
                "  missing_import     — Module or name cannot be found at import time",
                "  undefined_variable — Name used that was never assigned or imported",
                "  argument_error     — Wrong number or type of arguments passed to a function",
                "  return_type        — Function returns a value incompatible with its declared type",
                "  attribute_error    — Accessing a member that doesn't exist on the type",
                "  assignment_error   — Assigning a value of an incompatible type to a variable",
                "  operator_error     — Using an operator (+ - * / etc.) with incompatible types",
                "  override_error     — Subclass method signature doesn't match the base class",
                "  type_mismatch      — Value used where a different type is expected",
                "  general            — Other type errors not fitting a specific category",
                "  unreachable_code   — Code path that can never execute",
                "  deprecated         — Use of a deprecated API",
                "",
            ])

        if report.errors_by_rule:
            lines.extend(["TOP RULES / ERROR CODES", "-" * 50])
            for rule, count in sorted(report.errors_by_rule.items(), key=lambda x: x[1], reverse=True):
                desc = self._RULE_DESCRIPTIONS.get(rule, "")
                desc_suffix = f"  ({desc})" if desc else ""
                lines.append(f"  {rule:<45} {count:>5}{desc_suffix}")
            lines.append("")

        problem_files = report.get_most_problematic_files(len(report.files_analyzed))
        if problem_files:
            lines.extend(["MOST PROBLEMATIC FILES", "-" * 50])
            for f in problem_files:
                lines.append(f"  {f.relative_path:<55} E:{f.error_count:>3} W:{f.warning_count:>3}")
            lines.append("")

        if report.all_diagnostics:
            lines.extend(["DIAGNOSTICS", "-" * 50])
            by_file: Dict[str, List[TypeCheckDiagnostic]] = {}
            for diag in report.all_diagnostics:
                key = diag.relative_path or diag.file_path
                if key not in by_file:
                    by_file[key] = []
                by_file[key].append(diag)

            for file_path in sorted(by_file.keys()):
                lines.append(f"\n  {file_path}")
                for diag in sorted(by_file[file_path], key=lambda d: d.line):
                    sev_marker = {"error": "[ERROR]", "warning": "[WARN] ", "information": "[INFO] "}.get(diag.severity, "[????] ")
                    rule_suffix = f" ({diag.rule})" if diag.rule else ""
                    lines.append(f"    L{diag.line}:{diag.column} {sev_marker} {diag.message}{rule_suffix}")

        lines.extend(["", "=" * 70])
        return "\n".join(lines)

    def _generate_json_report(self, report: TypeCheckReport) -> str:
        """Generate JSON report."""
        return json.dumps({
            "scan_info": {
                "scan_path": report.scan_path,
                "scanned_at": report.scanned_at.isoformat(),
                "duration_seconds": report.scan_duration_seconds,
                "engine": self.config.engine,
                "engine_version": report.pyright_version,
                "type_checking_mode": report.type_checking_mode,
                "files_analyzed": report.files_scanned,
            },
            "summary": {
                "total_errors": report.total_errors,
                "total_warnings": report.total_warnings,
                "total_info": report.total_info,
                "files_with_errors": report.files_with_errors,
                "is_passing": report.is_compliant,
                "errors_by_category": report.errors_by_category,
                "errors_by_rule": report.errors_by_rule,
            },
            "files": [
                {"file_path": f.file_path, "relative_path": f.relative_path,
                 "error_count": f.error_count, "warning_count": f.warning_count, "info_count": f.info_count}
                for f in report.files_analyzed
            ],
            "diagnostics": [
                {"file_path": d.file_path, "relative_path": d.relative_path,
                 "line": d.line, "column": d.column, "severity": d.severity,
                 "message": d.message, "rule": d.rule, "category": d.category}
                for d in report.all_diagnostics
            ],
        }, indent=2)

    def _generate_markdown_report(self, report: TypeCheckReport) -> str:
        """Generate Markdown report."""
        engine_label = f"{'Pyright' if self.config.engine == 'pyright' else 'mypy'} {report.pyright_version}"
        status = "PASS" if report.is_compliant else "FAIL"
        lines = [
            "# Static Type Checking Report",
            "",
            f"**Engine:** {engine_label}",
            f"**Mode:** `{report.type_checking_mode}`",
            f"**Scan Path:** `{report.scan_path}`",
            f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Files Analyzed:** {report.files_scanned}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Errors | {report.total_errors} |",
            f"| Total Warnings | {report.total_warnings} |",
            f"| Total Info | {report.total_info} |",
            f"| Files With Errors | {report.files_with_errors} |",
            f"| **Status** | **{status}** |",
            "",
        ]

        if report.errors_by_category:
            lines += ["## Issues by Category", "", "| Category | Count |", "|----------|-------|"]
            for cat, count in sorted(report.errors_by_category.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| {cat.replace('_', ' ').title()} | {count} |")
            lines.append("")

        if report.errors_by_rule:
            lines += ["## Top Error Codes", "", "| Code | Count |", "|------|-------|"]
            for rule, count in sorted(report.errors_by_rule.items(), key=lambda x: x[1], reverse=True)[:20]:
                lines.append(f"| `{rule}` | {count} |")
            lines.append("")

        problem_files = report.get_most_problematic_files(20)
        if problem_files:
            lines += ["## Most Problematic Files", "", "| File | Errors | Warnings |", "|------|--------|----------|"]
            for f in problem_files:
                lines.append(f"| `{f.relative_path}` | {f.error_count} | {f.warning_count} |")
            lines.append("")

        return "\n".join(lines)
