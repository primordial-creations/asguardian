"""Tests for security misconfiguration scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.Misconfig.services.misconfig_scanner import SecurityMisconfigScanner
from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import MisconfigScanConfig, MisconfigScanReport


class TestSecurityMisconfigScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert SecurityMisconfigScanner() is not None


class TestSecurityMisconfigScannerCleanCode:
    def test_debug_false_returns_no_findings(self, tmp_path):
        (tmp_path / "settings.py").write_text(
            "import os\n"
            "DEBUG = False\n"
            "SECRET_KEY = os.environ.get('SECRET_KEY')\n"
        )
        config = MisconfigScanConfig(scan_path=tmp_path)
        report: MisconfigScanReport = SecurityMisconfigScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestSecurityMisconfigScannerBadCode:
    def test_debug_true_and_hardcoded_secret_detected(self, tmp_path):
        (tmp_path / "settings.py").write_text(
            'DEBUG = True\nSECRET_KEY = "hardcoded_secret"\n'
        )
        config = MisconfigScanConfig(scan_path=tmp_path)
        report: MisconfigScanReport = SecurityMisconfigScanner().scan(config)
        assert report.total_findings > 0
