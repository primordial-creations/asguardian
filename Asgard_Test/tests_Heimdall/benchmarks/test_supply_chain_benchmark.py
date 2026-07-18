"""Benchmark for supply-chain typosquat/dependency-confusion/dev-dependency
discount analysis (plan 07.10, RESEARCH_16). Static/offline only -- no
network calls (OSV/NVD live queries are out of scope for default paths).
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.services._supply_chain_analysis import (
    check_dependency_confusion,
    check_typosquat,
    detect_private_index,
    is_dev_dependency_file,
)
from Asgard.Heimdall.Security.services.dependency_vulnerability_service import (
    DependencyVulnerabilityService,
)


def test_typosquat_flags_one_char_off_popular_package():
    finding = check_typosquat("reqeusts", "1.0.0")
    assert finding is not None
    assert finding.finding_kind == "typosquat"
    assert finding.mechanism_id
    assert finding.risk_level in ("low", "moderate")


def test_typosquat_does_not_flag_exact_popular_package():
    assert check_typosquat("requests", "2.31.0") is None


def test_typosquat_does_not_flag_unrelated_package():
    assert check_typosquat("my-totally-unrelated-internal-lib", "1.0.0") is None


def test_dependency_confusion_flags_internal_name_without_private_index():
    finding = check_dependency_confusion("internal-billing-lib", "0.1.0", has_private_index=False)
    assert finding is not None
    assert finding.finding_kind == "dependency_confusion"
    assert finding.mechanism_id


def test_dependency_confusion_suppressed_when_private_index_present():
    finding = check_dependency_confusion("internal-billing-lib", "0.1.0", has_private_index=True)
    assert finding is None


def test_detect_private_index_from_requirements_txt():
    with tempfile.TemporaryDirectory() as tmpdir:
        req = Path(tmpdir) / "requirements.txt"
        req.write_text("--extra-index-url https://pkgs.internal.example.com/simple\nrequests==2.31.0\n")
        assert detect_private_index([req]) is True


def test_is_dev_dependency_file_heuristic():
    assert is_dev_dependency_file(Path("requirements-dev.txt")) is True
    assert is_dev_dependency_file(Path("requirements.txt")) is False


def test_dev_dependency_gets_risk_discount_not_suppression():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
        (tmp_path / "requirements-dev.txt").write_text("pyyaml==5.3\n")

        report = DependencyVulnerabilityService().scan(tmp_path)

        dev_vulns = [v for v in report.vulnerabilities if v.package_name == "pyyaml"]
        assert dev_vulns, "pyyaml<5.4 should be flagged as a known vulnerability"
        assert dev_vulns[0].is_dev_dependency is True
        # discounted from critical -> high, never suppressed to zero findings
        assert dev_vulns[0].risk_level != "safe"
        assert dev_vulns[0].risk_level == "high"


def test_prod_dependency_not_discounted():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "requirements.txt").write_text("pyyaml==5.3\n")

        report = DependencyVulnerabilityService().scan(tmp_path)

        prod_vulns = [v for v in report.vulnerabilities if v.package_name == "pyyaml"]
        assert prod_vulns
        assert prod_vulns[0].is_dev_dependency is False
        assert prod_vulns[0].risk_level == "critical"


def test_every_finding_gets_mechanism_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "requirements.txt").write_text("pyyaml==5.3\nreqeusts==1.0\n")

        report = DependencyVulnerabilityService().scan(tmp_path)
        assert report.vulnerabilities
        assert all(v.mechanism_id for v in report.vulnerabilities)
