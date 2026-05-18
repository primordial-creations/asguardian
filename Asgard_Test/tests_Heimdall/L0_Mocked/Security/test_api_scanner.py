"""Tests for API security scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.API.services.api_scanner import APISecurityScanner
from Asgard.Heimdall.Security.API.models.api_models import APIScanConfig, APIScanReport


class TestAPISecurityScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert APISecurityScanner() is not None


class TestAPISecurityScannerCleanCode:
    def test_clean_code_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.js").write_text(
            "function getUser(id) {\n"
            "  const user = db.findById(sanitize(id));\n"
            "  res.json({ id: user.id, name: user.name });\n"
            "}\n"
        )
        config = APIScanConfig(scan_path=tmp_path)
        report: APIScanReport = APISecurityScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestAPISecurityScannerBadCode:
    def test_data_exposure_detected(self, tmp_path):
        (tmp_path / "vuln.js").write_text(
            "app.get('/user/:id', (req, res) => {\n"
            "  const user = db.findById(req.params.id);\n"
            "  res.json(user);\n"
            "});\n"
        )
        config = APIScanConfig(scan_path=tmp_path)
        report: APIScanReport = APISecurityScanner().scan(config)
        assert report.total_findings > 0
