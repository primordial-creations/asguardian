"""Tests for information disclosure scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.InfoDisclosure.services.info_disclosure_scanner import InfoDisclosureScanner
from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import (
    InfoDisclosureScanConfig,
    InfoDisclosureScanReport,
)


class TestInfoDisclosureScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert InfoDisclosureScanner() is not None


class TestInfoDisclosureScannerCleanCode:
    def test_clean_logging_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text(
            "import logging\nlogger = logging.getLogger(__name__)\n"
            "def handle_error(e):\n    logger.error('An error occurred')\n"
        )
        config = InfoDisclosureScanConfig(scan_path=tmp_path)
        report: InfoDisclosureScanReport = InfoDisclosureScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestInfoDisclosureScannerBadCode:
    def test_stack_trace_in_response_detected(self, tmp_path):
        # Pattern: stack.*res. (stack before res) triggers stack_trace_response
        (tmp_path / "vuln.js").write_text(
            "app.use((err, req, res, next) => {\n"
            "    const stack = err.stack; res.json({ error: stack });\n"
            "});\n"
        )
        config = InfoDisclosureScanConfig(scan_path=tmp_path)
        report: InfoDisclosureScanReport = InfoDisclosureScanner().scan(config)
        assert report.total_findings > 0

    def test_api_key_in_code_detected(self, tmp_path):
        # api_key_in_response pattern
        (tmp_path / "vuln.py").write_text(
            "api_key = 'sk_live_abcdef1234567890ghij'\n"
            "response.json({'api_key': api_key})\n"
        )
        config = InfoDisclosureScanConfig(scan_path=tmp_path)
        report: InfoDisclosureScanReport = InfoDisclosureScanner().scan(config)
        assert report.total_findings > 0
