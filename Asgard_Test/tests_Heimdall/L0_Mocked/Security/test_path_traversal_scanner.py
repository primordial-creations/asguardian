"""Tests for path traversal scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.PathTraversal.services.path_traversal_scanner import PathTraversalScanner
from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import (
    PathTraversalScanConfig,
    PathTraversalScanReport,
)


class TestPathTraversalScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert PathTraversalScanner() is not None


class TestPathTraversalScannerCleanCode:
    def test_safe_path_join_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text(
            "import os\n"
            "SAFE_DIR = '/var/www/files'\n"
            "def get_file(filename):\n"
            "    return open(os.path.join(SAFE_DIR, filename))\n"
        )
        config = PathTraversalScanConfig(scan_path=tmp_path)
        report: PathTraversalScanReport = PathTraversalScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestPathTraversalScannerBadCode:
    def test_open_with_request_param_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text(
            "def get_file(request):\n"
            "    return open(request.args.get('file'))\n"
        )
        config = PathTraversalScanConfig(scan_path=tmp_path)
        report: PathTraversalScanReport = PathTraversalScanner().scan(config)
        assert report.total_findings > 0
