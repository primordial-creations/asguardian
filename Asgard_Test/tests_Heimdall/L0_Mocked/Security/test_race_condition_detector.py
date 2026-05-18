"""Tests for race condition detector."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.RaceCondition.services.race_condition_detector import RaceConditionDetector
from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import (
    RaceConditionScanConfig,
    RaceConditionScanReport,
)


class TestRaceConditionDetectorInstantiation:
    def test_detector_can_be_instantiated(self):
        assert RaceConditionDetector() is not None


class TestRaceConditionDetectorCleanCode:
    def test_exception_based_open_returns_no_findings(self, tmp_path):
        (tmp_path / "safe.py").write_text(
            "def read_file(filepath):\n"
            "    try:\n"
            "        with open(filepath) as f:\n"
            "            return f.read()\n"
            "    except FileNotFoundError:\n"
            "        return None\n"
        )
        config = RaceConditionScanConfig(scan_path=tmp_path)
        report: RaceConditionScanReport = RaceConditionDetector().scan(config)
        assert report.total_findings == 0
        assert len(report.findings) == 0


class TestRaceConditionDetectorBadCode:
    def test_toctou_exists_then_open_detected(self, tmp_path):
        (tmp_path / "vuln.py").write_text(
            "import os\n"
            "def read_file(filepath):\n"
            "    if os.path.exists(filepath):\n"
            "        with open(filepath) as f:\n"
            "            return f.read()\n"
        )
        config = RaceConditionScanConfig(scan_path=tmp_path)
        report: RaceConditionScanReport = RaceConditionDetector().scan(config)
        assert report.total_findings > 0
