"""Main C++ analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.languages.cpp.models.cpp_models import (
    CppFinding,
    CppReport,
    CppScanConfig,
)
from Asgard.Heimdall.Quality.languages.cpp.services._cpp_rules import (
    check_buffer_overflow,
    check_format_string,
    check_integer_overflow,
    check_memory_leak,
    check_null_deref,
    check_hardcoded_credentials,
    check_command_injection,
    check_use_after_free,
)

_RULES = [
    check_buffer_overflow,
    check_format_string,
    check_integer_overflow,
    check_memory_leak,
    check_null_deref,
    check_hardcoded_credentials,
    check_command_injection,
    check_use_after_free,
]

_CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"}


class CppAnalyzer:
    """Analyses C++ source files for security and quality issues."""

    def __init__(self, config: Optional[CppScanConfig] = None) -> None:
        self._config = config or CppScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> CppReport:
        """Analyze all C++ files under scan_path and return a CppReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = CppReport(scan_path=str(path))
        for ext in self._config.include_extensions:
            for src_file in path.rglob(f"*{ext}"):
                try:
                    source = src_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                lines = source.splitlines()
                for rule_fn in _RULES:
                    rule_id = rule_fn.__doc__.split(":")[0].strip() if rule_fn.__doc__ else ""
                    enabled = self._config.rules.get(rule_id, True)
                    report.findings.extend(rule_fn(str(src_file), lines, enabled=enabled))
        return report

    def analyze_file(self, file_path: Path) -> List[CppFinding]:
        if file_path.suffix.lower() not in _CPP_EXTENSIONS:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[CppFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[CppScanConfig] = None) -> List[CppFinding]:
        cfg = config or CppScanConfig(scan_path=scan_path)
        findings: List[CppFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
