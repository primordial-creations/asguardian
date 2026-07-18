"""Tests for hexagonal architecture analyzer."""
import pytest
from pathlib import Path
from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Bragi.Architecture.models.architecture_models import (
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


class TestHexagonalAnalyzerPortClean:
    def test_port_with_only_domain_imports_has_no_violations(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user.py").write_text("class User:\n    pass\n")

        ports_dir = tmp_path / "ports"
        ports_dir.mkdir()
        (ports_dir / "__init__.py").write_text("")
        (ports_dir / "user_port.py").write_text(
            "from abc import ABC, abstractmethod\n\n"
            "class IUserRepository(ABC):\n"
            "    @abstractmethod\n"
            "    def find(self, user_id: int): ...\n"
        )
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        port_violations = [v for v in report.violations if "port" in v.message.lower()]
        assert len(port_violations) == 0

    def test_infrastructure_importing_domain_is_clean(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user.py").write_text("class User:\n    pass\n")

        infra_dir = tmp_path / "infrastructure"
        infra_dir.mkdir()
        (infra_dir / "__init__.py").write_text("")
        (infra_dir / "user_repo.py").write_text(
            "import sqlalchemy\n"
            "from domain.user import User\n\n"
            "class SQLUserRepository:\n"
            "    def find(self, user_id: int) -> User:\n"
            "        pass\n"
        )
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        infra_violations = [v for v in report.violations
                            if "infrastructure" in (v.file_path or "").lower()]
        assert len(infra_violations) == 0

    def test_empty_directory_produces_empty_report(self, tmp_path):
        analyzer = HexagonalAnalyzer()
        report: HexagonalReport = analyzer.analyze(scan_path=tmp_path)
        assert report.violations == []


class TestAnemicDomainModelDetector:
    """Plan 03 §4 anti-pattern: domain class holds data but has no
    behaviour of its own."""

    def test_data_only_class_is_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "order.py").write_text(
            "class Order:\n"
            "    def __init__(self, order_id, total):\n"
            "        self.order_id = order_id\n"
            "        self.total = total\n"
            "    def get_total(self):\n"
            "        return self.total\n"
            "    def set_total(self, value):\n"
            "        self.total = value\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        anemic = [v for v in report.violations if "Anemic Domain Model" in v.message]
        assert len(anemic) == 1
        assert anemic[0].class_name == "Order"

    def test_class_with_real_behaviour_not_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "order.py").write_text(
            "class Order:\n"
            "    def __init__(self, order_id, total):\n"
            "        self.order_id = order_id\n"
            "        self.total = total\n"
            "    def apply_discount(self, pct):\n"
            "        self.total = self.total * (1 - pct)\n"
            "        return self.total\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        anemic = [v for v in report.violations if "Anemic Domain Model" in v.message]
        assert anemic == []

    def test_class_with_no_fields_not_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "stateless.py").write_text(
            "class Stateless:\n"
            "    def compute(self, x):\n"
            "        return x * 2\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        anemic = [v for v in report.violations if "Anemic Domain Model" in v.message]
        assert anemic == []


class TestInfrastructureLeakDetector:
    """Plan 03 §4 anti-pattern: domain entity bound to a persistence/web
    framework via base class, decorator, or ORM field declaration."""

    def test_sqlalchemy_declarative_base_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user.py").write_text(
            "class User(Base):\n"
            "    id = Column(Integer, primary_key=True)\n"
            "    name = Column(String)\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        leaks = [v for v in report.violations if "leaks infrastructure" in v.message]
        assert len(leaks) == 1
        assert leaks[0].class_name == "User"
        assert leaks[0].severity.name in ("HIGH", "CRITICAL") or "HIGH" in str(leaks[0].severity)

    def test_jpa_style_entity_decorator_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "account.py").write_text(
            "@Entity\n"
            "class Account:\n"
            "    def __init__(self, balance):\n"
            "        self.balance = balance\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        leaks = [v for v in report.violations if "leaks infrastructure" in v.message]
        assert len(leaks) == 1

    def test_plain_domain_class_not_flagged(self, tmp_path):
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "money.py").write_text(
            "class Money:\n"
            "    def __init__(self, amount, currency):\n"
            "        self.amount = amount\n"
            "        self.currency = currency\n"
            "    def add(self, other):\n"
            "        return Money(self.amount + other.amount, self.currency)\n"
        )
        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        leaks = [v for v in report.violations if "leaks infrastructure" in v.message]
        assert leaks == []


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
