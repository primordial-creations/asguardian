"""Tests for frontend security scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.Frontend.services.frontend_scanner import FrontendSecurityScanner
from Asgard.Heimdall.Security.Frontend.models.frontend_models import FrontendScanConfig, FrontendScanReport


class TestFrontendSecurityScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert FrontendSecurityScanner() is not None


class TestFrontendSecurityScannerCleanCode:
    def test_textcontent_assignment_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.js").write_text(
            "function render(userInput) {\n"
            "  element.textContent = userInput;\n"
            "}\n"
        )
        config = FrontendScanConfig(scan_path=tmp_path)
        report: FrontendScanReport = FrontendSecurityScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestFrontendSecurityScannerBadCode:
    def test_innerhtml_with_user_input_detected(self, tmp_path):
        (tmp_path / "vuln.js").write_text(
            "function render(userInput) {\n"
            "  element.innerHTML = userInput;\n"
            "  eval(data);\n"
            "}\n"
        )
        config = FrontendScanConfig(scan_path=tmp_path)
        report: FrontendScanReport = FrontendSecurityScanner().scan(config)
        assert report.total_findings > 0
