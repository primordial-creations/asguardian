"""Tests for data exfiltration detector."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.DataExfil.services.data_exfil_detector import DataExfiltrationDetector
from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import ExfilScanConfig, ExfilScanReport


class TestDataExfiltrationDetectorInstantiation:
    def test_detector_can_be_instantiated(self):
        assert DataExfiltrationDetector() is not None


class TestDataExfiltrationDetectorCleanCode:
    def test_clean_code_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text(
            "import requests\n"
            "def submit(url):\n"
            "    return requests.post(url, data={'action': 'submit'})\n"
        )
        config = ExfilScanConfig(scan_path=tmp_path)
        report: ExfilScanReport = DataExfiltrationDetector().scan(config)
        assert report.total_findings == 0


class TestDataExfiltrationDetectorBadCode:
    def test_password_in_post_data_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text(
            "import requests\n"
            "def leak(url, password):\n"
            "    return requests.post(url, data={'password': password})\n"
        )
        config = ExfilScanConfig(scan_path=tmp_path)
        report: ExfilScanReport = DataExfiltrationDetector().scan(config)
        assert report.total_findings > 0
