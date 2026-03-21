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

from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Quality.models.type_check_models import (
    TypeCheckConfig,
    TypeCheckReport,
)
from Asgard.Heimdall.Quality.services._mypy_runner import run_mypy
from Asgard.Heimdall.Quality.services._pyright_runner import run_pyright
from Asgard.Heimdall.Quality.services._type_checker_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
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
            run_pyright(path, report, self.config)
        else:
            run_mypy(path, report, self.config)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()
        return report

    def generate_report(self, report: TypeCheckReport, output_format: str = "text") -> str:
        """Generate formatted type checking report."""
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report, self.config.engine)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report, self.config.engine)
        return generate_text_report(report, self.config.engine)
