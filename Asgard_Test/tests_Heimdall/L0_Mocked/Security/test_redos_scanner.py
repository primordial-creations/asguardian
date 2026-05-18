"""Tests for ReDoS vulnerability scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner
from Asgard.Heimdall.Security.ReDoS.models.redos_models import (
    ReDoSScanConfig,
    ReDoSScanReport,
    ReDoSSeverity,
)


class TestReDoSScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert ReDoSScanner() is not None


class TestReDoSScannerCleanCode:
    def test_clean_code_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text("import re\npattern = re.compile(r'a+')\n")
        report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestReDoSScannerBadCode:
    def test_nested_quantifiers_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text("import re\npattern = re.compile(r'(a+)+')\n")
        report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
        assert report.total_findings > 0

    def test_finding_severity_is_high_or_critical(self, tmp_path):
        (tmp_path / "vuln.py").write_text("import re\npattern = re.compile(r'(a+)+')\n")
        report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
        severities = {f.severity for f in report.findings}
        assert severities & {ReDoSSeverity.CRITICAL, ReDoSSeverity.HIGH}
