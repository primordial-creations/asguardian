"""Tests for backdoor detector."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.Backdoor.services.backdoor_detector import BackdoorDetector
from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import (
    BackdoorScanConfig,
    BackdoorScanReport,
)


class TestBackdoorDetectorInstantiation:
    def test_detector_can_be_instantiated(self):
        assert BackdoorDetector() is not None


class TestBackdoorDetectorCleanCode:
    def test_clean_php_returns_no_findings(self, tmp_path):
        (tmp_path / "clean.php").write_text(
            "<?php\nfunction greet($name) {\n  return 'Hello ' . htmlspecialchars($name);\n}\n"
        )
        config = BackdoorScanConfig(scan_path=tmp_path)
        report: BackdoorScanReport = BackdoorDetector().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestBackdoorDetectorBadCode:
    def test_eval_base64_detected(self, tmp_path):
        (tmp_path / "vuln.php").write_text(
            "<?php\neval(base64_decode($_GET['cmd']));\n"
        )
        config = BackdoorScanConfig(scan_path=tmp_path)
        report: BackdoorScanReport = BackdoorDetector().scan(config)
        assert report.total_findings > 0
