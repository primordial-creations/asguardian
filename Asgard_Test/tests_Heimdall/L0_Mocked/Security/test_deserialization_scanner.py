"""Tests for deserialization vulnerability scanner."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import DeserializationScanner
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationScanConfig,
    DeserializationScanReport,
)


class TestDeserializationScannerInstantiation:
    def test_scanner_can_be_instantiated(self):
        assert DeserializationScanner() is not None


class TestDeserializationScannerCleanCode:
    def test_json_loads_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text(
            "import json\ndef parse(data):\n    return json.loads(data)\n"
        )
        config = DeserializationScanConfig(scan_path=tmp_path)
        report: DeserializationScanReport = DeserializationScanner().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestDeserializationScannerBadCode:
    def test_pickle_loads_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text(
            "import pickle\ndef load_user(user_data):\n    return pickle.loads(user_data)\n"
        )
        config = DeserializationScanConfig(scan_path=tmp_path)
        report: DeserializationScanReport = DeserializationScanner().scan(config)
        assert report.total_findings > 0
