"""
L5 Compliance Tests — Architecture Scanner Ground-Truth Fixture Library.

Tests verify that SOLID and Hexagonal architecture violations in known-bad
code fixtures are reliably detected.  Failures indicate broken scanner logic.
"""

from pathlib import Path

import pytest

from Asgard.Heimdall.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Heimdall.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureConfig
from Asgard.Heimdall.Architecture.models._solid_models import SOLIDPrinciple


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, name: str, code: str) -> Path:
    p = tmp_path / name
    p.write_text(code)
    return p


# ===========================================================================
# SOLID — Single Responsibility Principle
# ===========================================================================
class TestSOLIDSRPCompliance:
    """God class with 15+ public methods triggers SRP violation."""

    def _god_class_code(self) -> str:
        methods = "\n".join(
            f"    def do_task_{i}(self):\n        pass"
            for i in range(21)   # 21 methods > default threshold of 20
        )
        return f"class GodClass:\n{methods}\n"

    def test_srp_god_class_detected(self, tmp_path: Path) -> None:
        _write(tmp_path, "god_class.py", self._god_class_code())
        validator = SOLIDValidator()
        report = validator.validate(scan_path=tmp_path)
        srp_violations = [v for v in report.violations if v.principle == SOLIDPrinciple.SRP]
        assert len(srp_violations) > 0, (
            "SOLIDValidator did not detect SRP violation for a class with 21 methods"
        )


# ===========================================================================
# SOLID — Interface Segregation Principle
# ===========================================================================
class TestSOLIDISPCompliance:
    """Abstract class with 8+ abstract methods triggers ISP violation."""

    def _fat_interface_code(self) -> str:
        methods = "\n".join(
            f"    def method_{i}(self): ..."
            for i in range(8)
        )
        return (
            "from abc import ABC, abstractmethod\n\n"
            "class FatInterface(ABC):\n"
            + "\n".join(
                f"    @abstractmethod\n    def abstract_{i}(self): ..."
                for i in range(8)
            )
            + "\n"
        )

    def test_isp_fat_interface_detected(self, tmp_path: Path) -> None:
        _write(tmp_path, "fat_interface.py", self._fat_interface_code())
        validator = SOLIDValidator()
        report = validator.validate(scan_path=tmp_path)
        isp_violations = [v for v in report.violations if v.principle == SOLIDPrinciple.ISP]
        assert len(isp_violations) > 0, (
            "SOLIDValidator did not detect ISP violation for an interface with 8 abstract methods"
        )


# ===========================================================================
# SOLID — Dependency Inversion Principle
# ===========================================================================
class TestSOLIDDIPCompliance:
    """Constructor that directly instantiates 4+ concrete classes triggers DIP violation."""

    BAD_CODE = """\
class ConcreteA:
    pass

class ConcreteB:
    pass

class ConcreteC:
    pass

class ConcreteD:
    pass

class ConcreteE:
    pass

class Violator:
    def __init__(self):
        self.a = ConcreteA()
        self.b = ConcreteB()
        self.c = ConcreteC()
        self.d = ConcreteD()
        self.e = ConcreteE()
"""

    def test_dip_concrete_instantiation_detected(self, tmp_path: Path) -> None:
        _write(tmp_path, "dip_violator.py", self.BAD_CODE)
        validator = SOLIDValidator()
        report = validator.validate(scan_path=tmp_path)
        dip_violations = [v for v in report.violations if v.principle == SOLIDPrinciple.DIP]
        assert len(dip_violations) > 0, (
            "SOLIDValidator did not detect DIP violation for constructor with 5 concrete instantiations"
        )


# ===========================================================================
# Hexagonal — Domain Isolation
# ===========================================================================
class TestHexagonalDomainIsolationCompliance:
    """A Python file inside a 'domain/' directory that imports sqlalchemy
    triggers an isolation violation."""

    BAD_CODE = """\
import sqlalchemy
from sqlalchemy import Column, Integer, String

class UserEntity:
    id: int
    name: str
"""

    def test_domain_isolation_violation_detected(self, tmp_path: Path) -> None:
        domain_dir = tmp_path / "domain"
        domain_dir.mkdir()
        (domain_dir / "__init__.py").write_text("")
        (domain_dir / "user_entity.py").write_text(self.BAD_CODE)

        analyzer = HexagonalAnalyzer()
        report = analyzer.analyze(scan_path=tmp_path)
        # HexagonalViolation uses 'message' not 'description'
        isolation_violations = [
            v for v in report.violations
            if any(
                kw in v.message.lower()
                for kw in ("domain", "isolation", "framework", "sqlalchemy")
            )
        ]
        assert len(isolation_violations) > 0 or report.total_violations > 0, (
            "HexagonalAnalyzer did not detect any violation for sqlalchemy import inside domain/"
        )
