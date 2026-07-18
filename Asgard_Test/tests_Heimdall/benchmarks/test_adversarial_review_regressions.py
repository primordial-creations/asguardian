"""
Regression tests for the adversarial-review findings on the 7 Heimdall
plan-07 domains implemented in this worktree (BLOCKER-1/2/3,
MAJOR-4/5/6/7).

Each test uses the reviewer's exact repro and calls the scanner
END-TO-END (constructing the real service/analyzer and running .scan()
or the real module-level entry point) rather than unit-testing an
internal helper in isolation -- the reviewer's note was that some
existing tests passed while the code was broken because they didn't
exercise the actual call path.
"""
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# BLOCKER-1: TLS crash on uppercase severity literal ("LOW") passed into a
# lowercase-only SecuritySeverity enum, which crashed the ENTIRE
# TLSAnalyzer.scan() (a raised ValidationError inside CertificateValidator
# propagates up and loses ALL TLS findings, not just the certificate ones).
# ---------------------------------------------------------------------------
def test_blocker1_certificate_validator_does_not_crash_on_verify_false():
    from Asgard.Heimdall.Security.TLS.services.certificate_validator import CertificateValidator
    from Asgard.Heimdall.Security.TLS.models.tls_models import TLSConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "client.py"
        file_path.write_text('requests.get(url, verify=False)\n')

        validator = CertificateValidator(TLSConfig(scan_path=Path(tmpdir)))
        # Must not raise pydantic_core.ValidationError.
        report = validator.scan()

    assert report.findings, "requests.get(url, verify=False) must be flagged"
    finding = report.findings[0]
    # SecuritySeverity has use_enum_values=True -- the resolved value must
    # be the lowercase enum value, not a raw uppercase literal.
    assert finding.severity in ("high", "critical")


def test_blocker1_outbound_verify_false_not_downgraded_to_low_hotspot():
    """
    Reviewer's explicit correction: a TLS-terminating proxy protects
    INBOUND connections, not an OUTBOUND client call disabling its own
    certificate verification. verify=False must stay HIGH/CRITICAL, not
    be demoted to a LOW hotspot.
    """
    from Asgard.Heimdall.Security.TLS.services.certificate_validator import CertificateValidator
    from Asgard.Heimdall.Security.TLS.models.tls_models import TLSConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "client.py"
        file_path.write_text('requests.get(url, verify=False)\n')

        validator = CertificateValidator(TLSConfig(scan_path=Path(tmpdir)))
        report = validator.scan()

    finding = report.findings[0]
    assert finding.severity != "low"
    assert finding.is_hotspot is False


def test_blocker1_full_tls_analyzer_end_to_end_includes_cert_findings():
    """End-to-end through the real TLSAnalyzer.scan() entry point (not
    just CertificateValidator directly) -- confirms the crash doesn't
    silently swallow all TLS findings for the whole domain."""
    from Asgard.Heimdall.Security.TLS.services.tls_analyzer import TLSAnalyzer
    from Asgard.Heimdall.Security.TLS.models.tls_models import TLSConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "client.py"
        file_path.write_text('requests.get(url, verify=False)\n')

        analyzer = TLSAnalyzer(TLSConfig(scan_path=Path(tmpdir)))
        report = analyzer.scan()

    assert report.findings, "TLSAnalyzer.scan() must not lose certificate findings"


def test_blocker1_no_uppercase_severity_literals_remain_in_tls_headers():
    """Static guard: no uppercase severity string literal should be passed
    directly into a *Finding(...) constructor anywhere in TLS/Headers."""
    import re
    import Asgard.Heimdall.Security.TLS as tls_pkg
    import Asgard.Heimdall.Security.Headers as headers_pkg

    bad_pattern = re.compile(r'severity\s*=\s*["\'](?:HIGH|MEDIUM|LOW|CRITICAL|INFO)["\']')
    for pkg in (tls_pkg, headers_pkg):
        pkg_dir = Path(pkg.__file__).parent
        for py_file in pkg_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            assert not bad_pattern.search(content), f"uppercase severity literal found in {py_file}"


# ---------------------------------------------------------------------------
# BLOCKER-2: secrets semantic-context identifier resolution was dead code
# because the wrong offset (start of match == start of identifier) was
# passed to _identifier_before_match, which always returned "".
# ---------------------------------------------------------------------------
def test_blocker2_keyworded_secret_gets_high_signal_boost_end_to_end():
    from Asgard.Heimdall.Security.services.secrets_detection_service import SecretsDetectionService
    from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "settings.py"
        # 40-char base64-ish value matching the AWS secret key pattern,
        # with a high-signal identifier name.
        file_path.write_text(
            'aws_secret_access_key = "odJFCrnl2edlBD=dz1C5Jau2RJtBRnlWmTSHf6pW"\n'
        )

        service = SecretsDetectionService(SecurityScanConfig(scan_path=Path(tmpdir)))
        report = service.scan()

    matches = [f for f in report.findings if "aws" in f.pattern_name.lower()]
    assert matches, "aws_secret_access_key assignment should be detected"
    finding = matches[0]
    # High-signal identifier resolution must have fired: semantic_score
    # folds to >= 0.9 for a high-signal identifier match (base >= 0.9 or
    # boosted). Before the fix, the identifier was never recovered so
    # semantic_score fell through to the neutral 0.4 default and the
    # confidence stayed at the unfolded base value.
    assert finding.semantic_score >= 0.9, (
        f"expected high-signal identifier boost (semantic_score>=0.9), got {finding.semantic_score}"
    )


# ---------------------------------------------------------------------------
# BLOCKER-3: is_false_positive fully dropped any match with an unrelated
# os.environ/getenv/example/sample word within 100 chars -- even when the
# matched VALUE itself was a real high-entropy secret.
# ---------------------------------------------------------------------------
def test_blocker3_real_secret_not_dropped_by_unrelated_env_proximity():
    from Asgard.Heimdall.Security.services.secrets_detection_service import SecretsDetectionService
    from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "config.py"
        # Reviewer's exact repro: an unrelated os.environ call sits above
        # a real aws_secret_access_key assignment, within the 100-char
        # proximity window.
        file_path.write_text(
            'db_host = os.environ.get("DB_HOST")\n'
            'aws_secret_access_key = "odJFCrnl2edlBD=dz1C5Jau2RJtBRnlWmTSHf6pW"\n'
        )

        service = SecretsDetectionService(SecurityScanConfig(scan_path=Path(tmpdir)))
        report = service.scan()

    matches = [f for f in report.findings if "aws" in f.pattern_name.lower()]
    assert matches, (
        "real aws_secret_access_key must NOT be fully dropped just because an "
        "unrelated os.environ call is nearby -- floor confidence, never drop"
    )
    # Still visible (floored), not necessarily "certain".
    assert matches[0].confidence > 0.0


def test_blocker3_placeholder_value_still_dropped():
    """Sanity check that the narrowing didn't remove real placeholder
    filtering: a value that is ITSELF a placeholder must still be
    dropped."""
    from Asgard.Heimdall.Security.services.secrets_detection_service import SecretsDetectionService
    from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "config.py"
        file_path.write_text('api_key = "your_key_here_XXXXXXXXXXXXXXXXXXXX"\n')

        service = SecretsDetectionService(SecurityScanConfig(scan_path=Path(tmpdir)))
        report = service.scan()

    matches = [f for f in report.findings if "api" in f.pattern_name.lower()]
    assert not matches, "an obvious placeholder value should still be dropped"


# ---------------------------------------------------------------------------
# MAJOR-4: dev-dependency filename heuristic used a naive substring check
# ("test" in name), mislabeling requirements-latest.txt as dev/test-only.
# ---------------------------------------------------------------------------
def test_major4_requirements_latest_not_misdetected_as_dev_dependency():
    from Asgard.Heimdall.Security.services._supply_chain_analysis import is_dev_dependency_file

    assert is_dev_dependency_file(Path("requirements-latest.txt")) is False
    assert is_dev_dependency_file(Path("requirements-dev.txt")) is True
    assert is_dev_dependency_file(Path("dev-requirements.txt")) is True
    assert is_dev_dependency_file(Path("requirements-test.txt")) is True
    assert is_dev_dependency_file(Path("requirements.txt")) is False


def test_major4_typosquat_on_prod_manifest_not_discounted_end_to_end():
    from Asgard.Heimdall.Security.services.dependency_vulnerability_service import (
        DependencyVulnerabilityService,
    )
    from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        # "reqeusts" is a 1-edit-distance typosquat of "requests", placed
        # in a manifest whose name contains "latest" (substring "test").
        req_file = Path(tmpdir) / "requirements-latest.txt"
        req_file.write_text("reqeusts==2.28.0\n")

        service = DependencyVulnerabilityService(SecurityScanConfig(scan_path=Path(tmpdir)))
        report = service.scan()

    typosquats = [
        v for v in report.vulnerabilities
        if getattr(v, "finding_kind", "") == "typosquat"
    ]
    assert typosquats, "typosquat should be flagged in requirements-latest.txt"
    assert typosquats[0].is_dev_dependency is False, (
        "requirements-latest.txt is a PRODUCTION manifest and must not be "
        "misdetected as dev-only just because 'test' is a substring of 'latest'"
    )


# ---------------------------------------------------------------------------
# MAJOR-5: Container confidence_bucket field never actually computed from
# confidence -- always stuck at the Field default "probable".
# ---------------------------------------------------------------------------
def test_major5_container_confidence_bucket_computed_end_to_end():
    from Asgard.Heimdall.Security.Container.services.dockerfile_analyzer import DockerfileAnalyzer
    from Asgard.Heimdall.Security.Container.models.container_models import ContainerConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile = Path(tmpdir) / "Dockerfile"
        # ROOT_USER check: high confidence -> should land in "certain".
        dockerfile.write_text("FROM ubuntu:latest\nUSER root\n")

        analyzer = DockerfileAnalyzer(ContainerConfig(scan_path=Path(tmpdir)))
        report = analyzer.scan()

    assert report.findings
    for finding in report.findings:
        expected_bucket = (
            "certain" if finding.confidence > 0.85 else
            "probable" if finding.confidence >= 0.50 else
            "possible" if finding.confidence >= 0.25 else
            "unlikely"
        )
        assert finding.confidence_bucket == expected_bucket, (
            f"confidence_bucket={finding.confidence_bucket!r} does not match "
            f"confidence={finding.confidence} for finding_type={finding.finding_type}"
        )


# ---------------------------------------------------------------------------
# MAJOR-6: `ADD http://...` was never flagged by any check (the ADD-vs-COPY
# rule deliberately excludes URL ADDs, and nothing else caught the case).
# ---------------------------------------------------------------------------
def test_major6_add_remote_url_flagged_end_to_end():
    from Asgard.Heimdall.Security.Container.services.dockerfile_analyzer import DockerfileAnalyzer
    from Asgard.Heimdall.Security.Container.models.container_models import ContainerConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile = Path(tmpdir) / "Dockerfile"
        dockerfile.write_text(
            "FROM ubuntu:22.04\n"
            "ADD http://example.com/install.sh /tmp/install.sh\n"
        )

        analyzer = DockerfileAnalyzer(ContainerConfig(scan_path=Path(tmpdir)))
        report = analyzer.scan()

    remote_add_findings = [
        f for f in report.findings if f.finding_type == "add_remote_url"
    ]
    assert remote_add_findings, "ADD http://... must be flagged as a supply-chain/integrity risk"
    assert remote_add_findings[0].severity in ("medium", "high", "critical")


def test_major6_add_local_file_still_uses_add_instead_of_copy_rule():
    """Sanity check the pre-existing rule is untouched: a local-file ADD
    (not a URL) is still flagged by check_add_instead_of_copy, and does
    NOT trip the new remote-url check."""
    from Asgard.Heimdall.Security.Container.services.dockerfile_analyzer import DockerfileAnalyzer
    from Asgard.Heimdall.Security.Container.models.container_models import ContainerConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile = Path(tmpdir) / "Dockerfile"
        dockerfile.write_text("FROM ubuntu:22.04\nADD app.py /app/app.py\n")

        analyzer = DockerfileAnalyzer(ContainerConfig(scan_path=Path(tmpdir)))
        report = analyzer.scan()

    types = {f.finding_type for f in report.findings}
    assert "add_instead_of_copy" in types
    assert "add_remote_url" not in types


# ---------------------------------------------------------------------------
# MAJOR-7: PII-log-sink alias resolution was single-hop; a 2-hop rename
# chain defeated detection entirely (not even a hotspot).
# ---------------------------------------------------------------------------
def test_major7_two_hop_alias_rename_still_flagged_end_to_end():
    from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import (
        SensitiveDataScanner,
    )
    from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
        SensitiveDataScanConfig,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "app.py"
        # Reviewer's exact repro: x = user.ssn; y = x; logger.info(y)
        file_path.write_text(
            "def handler(user):\n"
            "    x = user.ssn\n"
            "    y = x\n"
            "    logger.info(y)\n"
        )

        scanner = SensitiveDataScanner()
        report = scanner.scan(SensitiveDataScanConfig(scan_path=Path(tmpdir)))

    pii_log_findings = [
        f for f in report.findings
        if f.mechanism_id.startswith("sensitive_data.pii_log_sink")
    ]
    assert pii_log_findings, (
        "a 2-hop rename (x = user.ssn; y = x; logger.info(y)) must still "
        "surface as at least a hotspot -- unresolved-origin != safe"
    )
    assert pii_log_findings[0].is_hotspot is True


def test_major7_direct_lexicon_match_still_not_a_hotspot():
    """Sanity check the direct-match path (no alias) is untouched and
    stays a confirmed (non-hotspot) finding."""
    from Asgard.Heimdall.Security.SensitiveData.services._pii_log_sink_analysis import scan_pii_log_sinks
    import ast

    source = "def handler(ssn):\n    logger.info(ssn)\n"
    tree = ast.parse(source)
    findings = scan_pii_log_sinks(tree, source.splitlines())

    assert findings
    assert findings[0].is_hotspot is False
