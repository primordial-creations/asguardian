"""Tests for SSRF/XXE scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.SSRF.services.ssrf_scanner import SSRFXXEScanner
from Asgard.Heimdall.Security.SSRF.models.ssrf_models import SSRFScanConfig, SSRFScanReport


class TestSSRFXXEScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert SSRFXXEScanner() is not None


class TestSSRFXXEScannerCleanCode:
    def test_hardcoded_allowed_url_returns_no_findings(self, tmp_path):
        # No dynamic URL, no user-controlled input — should not trigger
        (tmp_path / "safe.py").write_text(
            "import requests\n"
            "def fetch():\n"
            "    return requests.get('https://api.example.com/data')\n"
        )
        config = SSRFScanConfig(scan_path=tmp_path)
        report: SSRFScanReport = SSRFXXEScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestSSRFXXEScannerBadCode:
    def test_fstring_url_in_requests_detected(self, tmp_path):
        # Pattern: requests.get(f'...') — f-string URL triggers ssrf_requests
        (tmp_path / "vuln.py").write_text(
            "import requests\n"
            "def fetch(target):\n"
            "    return requests.get(f'http://{target}/api')\n"
        )
        config = SSRFScanConfig(scan_path=tmp_path)
        report: SSRFScanReport = SSRFXXEScanner().scan(config)
        assert report.total_findings > 0

    def test_php_file_get_contents_url_param_detected(self, tmp_path):
        (tmp_path / "vuln.php").write_text(
            "<?php\n$data = file_get_contents($_GET['url']);\necho $data;\n"
        )
        config = SSRFScanConfig(scan_path=tmp_path)
        report: SSRFScanReport = SSRFXXEScanner().scan(config)
        assert report.total_findings > 0
