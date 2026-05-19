"""Expanded tests for SOLID principle validator."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureConfig, SOLIDReport


class TestSOLIDValidatorInstantiation:
    def test_validator_can_be_instantiated(self):
        assert SOLIDValidator() is not None

    def test_validator_accepts_config(self, tmp_path):
        config = ArchitectureConfig(scan_path=tmp_path)
        validator = SOLIDValidator(config=config)
        assert validator is not None


class TestSOLIDValidatorCleanCode:
    def test_single_responsibility_class_passes(self, tmp_path):
        (tmp_path / "clean.py").write_text(
            "class EmailSender:\n"
            "    def send(self, to, subject, body):\n"
            "        pass\n"
            "    def validate_address(self, address):\n"
            "        pass\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        assert report is not None
        violations = [v for v in report.violations if v.file_path.endswith("clean.py")]
        assert len(violations) == 0


class TestSOLIDValidatorSRPViolation:
    def test_god_class_with_many_methods_flagged(self, tmp_path):
        methods = "\n".join(
            [f"    def method_{i}(self):\n        pass" for i in range(15)]
        )
        (tmp_path / "god_class.py").write_text(f"class GodClass:\n{methods}\n")
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        srp_violations = [v for v in report.violations if "SRP" in str(v.principle)]
        assert len(srp_violations) > 0


class TestSOLIDValidatorOCPViolation:
    def test_long_isinstance_chain_flagged(self, tmp_path):
        (tmp_path / "ocp_violation.py").write_text(
            "class ShapeRenderer:\n"
            "    def render(self, shape):\n"
            "        if isinstance(shape, Circle):\n"
            "            self._draw_circle(shape)\n"
            "        elif isinstance(shape, Square):\n"
            "            self._draw_square(shape)\n"
            "        elif isinstance(shape, Triangle):\n"
            "            self._draw_triangle(shape)\n"
            "        elif isinstance(shape, Rectangle):\n"
            "            self._draw_rectangle(shape)\n"
            "        elif isinstance(shape, Hexagon):\n"
            "            self._draw_hexagon(shape)\n"
            "    def _draw_circle(self, s): pass\n"
            "    def _draw_square(self, s): pass\n"
            "    def _draw_triangle(self, s): pass\n"
            "    def _draw_rectangle(self, s): pass\n"
            "    def _draw_hexagon(self, s): pass\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        ocp_violations = [v for v in report.violations if "OCP" in str(v.principle)]
        assert len(ocp_violations) > 0


class TestSOLIDValidatorISPViolation:
    def test_fat_interface_flagged(self, tmp_path):
        methods = "\n".join(
            [f"    def method_{i}(self): ..." for i in range(12)]
        )
        (tmp_path / "isp_violation.py").write_text(
            "from abc import ABC, abstractmethod\n"
            "class FatInterface(ABC):\n"
            + "\n".join(
                [f"    @abstractmethod\n    def method_{i}(self): ..." for i in range(12)]
            )
            + "\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        isp_violations = [v for v in report.violations if "ISP" in str(v.principle)]
        assert len(isp_violations) > 0


class TestSOLIDValidatorOCPClean:
    def test_polymorphic_dispatch_not_flagged(self, tmp_path):
        (tmp_path / "ocp_clean.py").write_text(
            "class ShapeRenderer:\n"
            "    def render(self, shape):\n"
            "        shape.draw()\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        ocp_violations = [v for v in report.violations if "OCP" in str(v.principle)
                          and v.file_path.endswith("ocp_clean.py")]
        assert len(ocp_violations) == 0


class TestSOLIDValidatorISPClean:
    def test_small_interface_not_flagged(self, tmp_path):
        (tmp_path / "isp_clean.py").write_text(
            "from abc import ABC, abstractmethod\n"
            "class Readable(ABC):\n"
            "    @abstractmethod\n"
            "    def read(self): ...\n"
            "    @abstractmethod\n"
            "    def close(self): ...\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        isp_violations = [v for v in report.violations if "ISP" in str(v.principle)
                          and v.file_path.endswith("isp_clean.py")]
        assert len(isp_violations) == 0


class TestSOLIDValidatorDIPClean:
    def test_injected_dependencies_not_flagged(self, tmp_path):
        (tmp_path / "dip_clean.py").write_text(
            "class UserService:\n"
            "    def __init__(self, repo, mailer, cache):\n"
            "        self.repo = repo\n"
            "        self.mailer = mailer\n"
            "        self.cache = cache\n"
            "    def get_user(self, user_id):\n"
            "        return self.repo.find(user_id)\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        dip_violations = [v for v in report.violations if "DIP" in str(v.principle)
                          and v.file_path.endswith("dip_clean.py")]
        assert len(dip_violations) == 0


class TestSOLIDValidatorDIPViolation:
    def test_concrete_dependency_instantiation_flagged(self, tmp_path):
        # DIP triggers when __init__ instantiates > 3 concrete (non-benign) classes
        (tmp_path / "dip_violation.py").write_text(
            "class UserService:\n"
            "    def __init__(self):\n"
            "        self.db = MySQLDatabase()\n"
            "        self.cache = RedisCache()\n"
            "        self.mailer = SMTPMailer()\n"
            "        self.logger = FileLogger()\n"
            "        self.metrics = StatsDMetrics()\n"
            "    def get_user(self, user_id):\n"
            "        return self.db.query(user_id)\n"
        )
        validator = SOLIDValidator()
        report: SOLIDReport = validator.validate(scan_path=tmp_path)
        dip_violations = [v for v in report.violations if "DIP" in str(v.principle)]
        assert len(dip_violations) > 0
