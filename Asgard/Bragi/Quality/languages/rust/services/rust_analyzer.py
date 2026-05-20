"""Main Rust analyzer — entry point for Heimdall quality scanning."""

from pathlib import Path
from typing import List, Optional

from Asgard.Bragi.Quality.languages.rust.models.rust_models import (
    RustFinding,
    RustReport,
    RustScanConfig,
)
from Asgard.Bragi.Quality.languages.rust.services._rust_rules import (
    check_unsafe_block,
    check_unwrap_in_production,
    check_transmute,
    check_raw_pointer_deref,
    check_command_injection,
    check_hardcoded_credentials,
    check_integer_overflow,
    check_path_traversal,
)

_RULES = [
    check_unsafe_block,
    check_unwrap_in_production,
    check_transmute,
    check_raw_pointer_deref,
    check_command_injection,
    check_hardcoded_credentials,
    check_integer_overflow,
    check_path_traversal,
]


class RustAnalyzer:
    """Analyses Rust source files for security and quality issues."""

    def __init__(self, config: Optional[RustScanConfig] = None) -> None:
        self._config = config or RustScanConfig()

    def analyze(self, scan_path: Optional[str] = None) -> RustReport:
        """Analyze all Rust files under scan_path and return a RustReport."""
        path = Path(scan_path) if scan_path else self._config.scan_path
        report = RustReport(scan_path=str(path))
        for src_file in path.rglob("*.rs"):
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

    def analyze_file(self, file_path: Path) -> List[RustFinding]:
        if file_path.suffix.lower() not in {".rs"}:
            return []
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        lines = source.splitlines()
        findings: List[RustFinding] = []
        for rule in _RULES:
            findings.extend(rule(str(file_path), lines, enabled=True))
        return findings

    def analyze_directory(self, scan_path: Path, config: Optional[RustScanConfig] = None) -> List[RustFinding]:
        cfg = config or RustScanConfig(scan_path=scan_path)
        findings: List[RustFinding] = []
        for ext in cfg.include_extensions:
            for src_file in scan_path.rglob(f"*{ext}"):
                findings.extend(self.analyze_file(src_file))
        return findings
