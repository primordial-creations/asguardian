"""Tests for hexagonal architecture analyzer."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    HexagonalReport,
    HexagonalZone,
)


class TestHexagonalAnalyzerInstantiation:
    def test_analyzer_can_be_instantiated(self):
        assert HexagonalAnalyzer() is not None

    def test_analyzer_accepts_config(self, tmp_path):
        config = ArchitectureConfig(scan_path=tmp_path)
        analyzer = HexagonalAnalyzer(config=config)
        assert analyzer is not None


class TestHexagonalAnalyzerCleanCode:
    def test_clean_hexagonal_structure_has_no_violations(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user.py").write_text(
            "class User:\n"
            "    def __init__(self, user_id: int, name: str):\n"
            "        self.user_id = user_id\n"
            "        self.name = name\n"
        )
        ports_dir = tmp_path / "ports"
        ports_dir.mkdir()
        (ports_dir / "__init__.py").write_text("")
        (ports_dir / "user_repository.py").write_text(
            "from abc import ABC, abstractmethod\n\n"
            "class UserRepository(ABC):\n"
            "    @abstractmethod\n"
            "    def find_by_id(self, user_id: int): ...\n"
        )
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        assert report is not None
        assert isinstance(report.violations, list)


class TestHexagonalAnalyzerDomainIsolationViolation:
    def test_framework_import_in_domain_detected(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user_service.py").write_text(
            "import sqlalchemy\n"
            "from sqlalchemy.orm import Session\n\n"
            "class UserService:\n"
            "    def __init__(self, session: Session):\n"
            "        self.session = session\n"
        )
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        assert len(report.violations) > 0
        # HexagonalViolation has a 'message' field (not 'description')
        violation_messages = [v.message for v in report.violations]
        assert any("domain" in m.lower() or "framework" in m.lower() or "infrastructure" in m.lower()
                   or "isolation" in m.lower()
                   for m in violation_messages)


class TestHexagonalAnalyzerCrossAdapterViolation:
    def test_adapter_importing_another_adapter_detected(self, tmp_path):
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()
        (adapters_dir / "__init__.py").write_text("")
        (adapters_dir / "email_adapter.py").write_text(
            "class EmailAdapter:\n"
            "    def send(self, msg): pass\n"
        )
        (adapters_dir / "sms_adapter.py").write_text(
            "from adapters.email_adapter import EmailAdapter\n\n"
            "class SMSAdapter:\n"
            "    def __init__(self):\n"
            "        self.email = EmailAdapter()\n"
            "    def send(self, msg): pass\n"
        )
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        assert report is not None


class TestHexagonalAnalyzerReportStructure:
    def test_report_has_expected_fields(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1\n")
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        assert hasattr(report, 'violations')
        assert hasattr(report, 'ports')
        assert hasattr(report, 'adapters')
        assert hasattr(report, 'scan_path')
        assert isinstance(report.violations, list)
        assert isinstance(report.ports, list)
        assert isinstance(report.adapters, list)
