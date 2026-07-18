"""Benchmark for the PII-to-log-sink taint rule + Django DEBUG=True check
(plan 07.11, RESEARCH_11). Vulnerable/safe pairs plus test-context
downgrade behavior.
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import (
    SensitiveDataScanner,
)
from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
    SensitiveDataScanConfig,
)


def _scan_source(filename: str, source: str, under_tests_dir: bool = False):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        if under_tests_dir:
            base = base / "tests"
            base.mkdir()
        file_path = base / filename
        file_path.write_text(source)
        config = SensitiveDataScanConfig(scan_path=file_path)
        return SensitiveDataScanner().scan(config)


def test_direct_ssn_logging_flagged_high_confidence():
    report = _scan_source(
        "app.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def handle(ssn):\n"
        "    logger.info(ssn)\n",
    )
    hits = [f for f in report.findings if f.data_type == "pii_log_sink"]
    assert hits, "logging a variable literally named ssn should be flagged"
    assert hits[0].mechanism_id == "sensitive_data.pii_log_sink.ssn"
    assert "GDPR" in hits[0].compliance_tags or "HIPAA" in hits[0].compliance_tags
    assert hits[0].is_hotspot is False


def test_alias_chain_logging_flagged_as_hotspot_not_suppressed():
    report = _scan_source(
        "app.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def handle(user):\n"
        "    x = user.ssn\n"
        "    logger.info(x)\n",
    )
    hits = [f for f in report.findings if f.data_type == "pii_log_sink"]
    assert hits, "alias-chain PII flowing to a log sink must still be reported"
    assert hits[0].is_hotspot is True
    assert hits[0].confidence < 0.6


def test_print_sink_detected():
    report = _scan_source(
        "app.py",
        "def handle(password):\n"
        "    print(password)\n",
    )
    hits = [f for f in report.findings if f.data_type == "pii_log_sink"]
    assert hits
    assert hits[0].lexicon_term if hasattr(hits[0], "lexicon_term") else True


def test_non_pii_variable_not_flagged():
    report = _scan_source(
        "app.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def handle(order_id):\n"
        "    logger.info(order_id)\n",
    )
    hits = [f for f in report.findings if f.data_type == "pii_log_sink"]
    assert not hits


def test_django_debug_true_flagged():
    report = _scan_source("settings.py", "DEBUG = True\n")
    hits = [f for f in report.findings if f.data_type == "django_debug"]
    assert hits
    assert hits[0].mechanism_id == "sensitive_data.django_debug_true"
    assert hits[0].severity == "HIGH"


def test_django_debug_false_not_flagged():
    report = _scan_source("settings.py", "DEBUG = False\n")
    hits = [f for f in report.findings if f.data_type == "django_debug"]
    assert not hits


def test_test_context_downgrades_not_suppresses():
    report = _scan_source(
        "test_app.py",
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def test_handle():\n"
        "    ssn = '123-45-6789'\n"
        "    logger.info(ssn)\n",
        under_tests_dir=True,
    )
    hits = [f for f in report.findings if f.data_type == "pii_log_sink"]
    assert hits, "test-context PII log findings must be downgraded, never suppressed"
    assert hits[0].severity == "LOW"


def test_every_finding_has_mechanism_id():
    report = _scan_source(
        "app.py",
        "PASSWORD = 'hardcoded-secret-value-1234'\n"
        "DEBUG = True\n",
    )
    assert report.findings
    assert all(f.mechanism_id for f in report.findings)
