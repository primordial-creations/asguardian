"""Contract-unit coverage for Asgard's public Hercules L13 adapter."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from Asgard.hercules_l13 import (
    COMPLETION_PREFIX,
    CONTRACT_VERSION,
    ContractScanError,
    EXIT_EXECUTION_FAILURE,
    FINDING_PREFIX,
    MAX_FINDINGS,
    MAX_ROUTED_RECORD_BYTES,
    MAX_STRING_CHARS,
    _validate_complete_report,
    _validate_scan_coverage,
    _write_atomic,
    execute_scan,
    normalize_finding,
    normalize_report,
    render_contract,
)
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig


def _payload(line: str, prefix: str) -> dict:
    assert line.startswith(prefix)
    return json.loads(line[len(prefix):])


def _empty_complete_report(**overrides):
    values = {"domain_errors": []}
    for report_field in (
        "secrets_report",
        "vulnerability_report",
        "crypto_report",
        "access_report",
        "auth_report",
        "headers_report",
        "tls_report",
        "container_report",
        "infrastructure_report",
    ):
        count = (
            "secrets_found"
            if report_field == "secrets_report"
            else "vulnerabilities_found"
            if report_field == "vulnerability_report"
            else "issues_found"
            if report_field == "crypto_report"
            else "total_issues"
        )
        values[report_field] = SimpleNamespace(findings=[], **{count: 0})
    values["dependency_report"] = SimpleNamespace(vulnerabilities=[])
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalized_finding_has_stable_identity_and_relative_location(tmp_path):
    target = tmp_path / "project with spaces"
    target.mkdir()
    finding = SimpleNamespace(
        mechanism_id="python.command-injection",
        severity="high",
        description="Untrusted input reaches a shell",
        file_path=str(target / "odd name.py"),
        line_number=7,
        column_start=3,
    )

    first = normalize_finding("vulnerabilities", finding, target)
    second = normalize_finding("vulnerabilities", finding, target)

    assert first == second
    assert first["id"].startswith("asgard:")
    assert len(first["id"]) == len("asgard:") + 64
    assert first["rule"] == "python.command-injection"
    assert first["severity"] == "high"
    assert first["location"] == {
        "path": "odd name.py",
        "line": 7,
        "column": 3,
    }


def test_v1_contract_has_explicit_clean_completion_record():
    lines = render_contract([], CONTRACT_VERSION).splitlines()

    assert len(lines) == 1
    completion = _payload(lines[0], COMPLETION_PREFIX)
    assert completion["contract_version"] == CONTRACT_VERSION
    assert completion["status"] == "clean"
    assert completion["finding_count"] == 0
    assert completion["scanner"]["name"] == "asgard"


def test_v1_contract_records_findings_without_failure_exit_semantics():
    finding = {
        "id": "asgard:" + "a" * 64,
        "rule": "python.command-injection",
        "severity": "high",
        "message": "Unsafe shell invocation",
        "location": {"path": "app.py", "line": 4, "column": 2},
    }

    lines = render_contract([finding], CONTRACT_VERSION).splitlines()

    assert _payload(lines[0], FINDING_PREFIX) == finding
    completion = _payload(lines[1], COMPLETION_PREFIX)
    assert completion["status"] == "findings"
    assert completion["finding_count"] == 1


def test_renderer_rejects_values_the_consumer_would_reject():
    finding = {
        "id": "asgard:" + "a" * 64,
        "rule": "test.rule",
        "severity": "high",
        "message": "unsafe",
        "location": {"path": "app.py", "line": 1, "column": 1},
    }
    with pytest.raises(ContractScanError, match="message must be a string"):
        render_contract([{**finding, "message": 7}], CONTRACT_VERSION)
    with pytest.raises(ContractScanError, match="path must be a string"):
        render_contract(
            [{**finding, "location": {**finding["location"], "path": 7}}],
            CONTRACT_VERSION,
        )


def test_domain_failure_returns_execution_failure_without_replacing_output(
    tmp_path, capsys
):
    output = tmp_path / "result.jsonl"
    output.write_text("previous\n")
    report = SimpleNamespace(domain_errors=[{"domain": "auth"}])
    with patch("Asgard.hercules_l13._validate_scan_coverage"), patch(
        "Asgard.hercules_l13.StaticSecurityService.scan", return_value=report
    ):
        try:
            execute_scan(
                str(tmp_path),
                str(output),
                CONTRACT_VERSION,
            )
        except Exception as exc:
            assert "domain failure" in str(exc)
        else:
            raise AssertionError("domain failure must not produce a successful scan")

    assert output.read_text() == "previous\n"
    assert capsys.readouterr().out == ""


def test_cli_execution_failure_code_is_distinct_from_findings(tmp_path):
    from Asgard.cli import main

    output = tmp_path / "result.jsonl"
    missing = tmp_path / "missing"

    code = main(
        [
            "scan",
            "--contract-version",
            CONTRACT_VERSION,
            "--target",
            str(missing),
            "--output",
            str(output),
        ]
    )

    assert code == EXIT_EXECUTION_FAILURE
    assert not output.exists()


def test_public_contract_requires_explicit_v1_and_rejects_unsupported_exclusions(
    tmp_path, capsys
):
    from Asgard.cli import main

    output = tmp_path / "result.jsonl"
    for args in (
        ["scan", "--target", str(tmp_path), "--output", str(output)],
        [
            "scan",
            "--contract-version",
            CONTRACT_VERSION,
            "--target",
            str(tmp_path),
            "--output",
            str(output),
            "--exclude",
            "vendor",
        ],
    ):
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 2
    assert not output.exists()
    assert "required" in capsys.readouterr().err


def test_url_target_fails_closed_without_creating_output(tmp_path, capsys):
    from Asgard.cli import main

    output = tmp_path / "result.jsonl"
    code = main(
        [
            "scan",
            "--contract-version",
            CONTRACT_VERSION,
            "--target=https://target.example/repository",
            f"--output={output}",
        ]
    )

    assert code == EXIT_EXECUTION_FAILURE
    assert not output.exists()
    assert "scan target is not a directory" in capsys.readouterr().err


def test_missing_report_and_inconsistent_count_fail_closed():
    with pytest.raises(ContractScanError, match="omitted requested domain"):
        _validate_complete_report(_empty_complete_report(auth_report=None))

    bad_secrets = SimpleNamespace(findings=[], secrets_found=1)
    with pytest.raises(ContractScanError, match="inconsistent count"):
        _validate_complete_report(_empty_complete_report(secrets_report=bad_secrets))


def test_malformed_native_finding_is_not_weakened_to_valid_contract(tmp_path):
    base = {
        "mechanism_id": "python.command-injection",
        "description": "unsafe",
        "file_path": "app.py",
        "line_number": 1,
        "column_start": 1,
    }
    with pytest.raises(ContractScanError, match="unsupported severity"):
        normalize_finding("vulnerabilities", SimpleNamespace(**base, severity="urgent"), tmp_path)
    with pytest.raises(ContractScanError, match="non-negative integer"):
        normalize_finding(
            "vulnerabilities",
            SimpleNamespace(**{**base, "severity": "high", "line_number": True}),
            tmp_path,
        )
    with pytest.raises(ContractScanError, match="outside the scan target"):
        normalize_finding(
            "vulnerabilities",
            SimpleNamespace(**{**base, "severity": "high", "file_path": "../escape.py"}),
            tmp_path,
        )


def test_routing_string_and_finding_bounds_fail_instead_of_truncating(tmp_path):
    finding = SimpleNamespace(
        mechanism_id="python.command-injection",
        severity="high",
        description="x" * (MAX_STRING_CHARS + 1),
        file_path="app.py",
        line_number=1,
        column_start=1,
    )
    with pytest.raises(ContractScanError, match="message exceeds"):
        normalize_finding("vulnerabilities", finding, tmp_path)

    finding.description = "雪" * MAX_STRING_CHARS
    boundary = normalize_finding("vulnerabilities", finding, tmp_path)
    assert len(boundary["message"]) == MAX_STRING_CHARS
    assert len(render_contract([boundary], CONTRACT_VERSION).encode("utf-8")) < 8 * 1024 * 1024
    routed = FINDING_PREFIX + json.dumps(boundary)
    assert len(routed.encode("utf-8")) <= MAX_ROUTED_RECORD_BYTES

    unroutable = {
        **boundary,
        "rule": "雪" * MAX_STRING_CHARS,
        "message": "雪" * 2016,
        "location": {**boundary["location"], "path": "雪" * MAX_STRING_CHARS},
    }
    with pytest.raises(ContractScanError, match="after Hercules serialization"):
        render_contract([unroutable], CONTRACT_VERSION)

    record = {
        "id": "asgard:" + "a" * 64,
        "rule": "test.rule",
        "severity": "high",
        "message": "unsafe",
        "location": {"path": "app.py", "line": 1, "column": 1},
    }
    assert _payload(
        render_contract([record] * MAX_FINDINGS, CONTRACT_VERSION).splitlines()[-1],
        COMPLETION_PREFIX,
    )["finding_count"] == MAX_FINDINGS
    with pytest.raises(ContractScanError, match="routing limit"):
        render_contract([record] * (MAX_FINDINGS + 1), CONTRACT_VERSION)


def test_duplicate_provider_records_fail_instead_of_double_reporting(tmp_path):
    finding = SimpleNamespace(
        mechanism_id="python.command-injection",
        severity="high",
        description="unsafe",
        file_path="app.py",
        line_number=1,
        column_start=1,
    )
    report = _empty_complete_report(
        vulnerability_report=SimpleNamespace(
            findings=[finding, finding], vulnerabilities_found=2
        )
    )
    with pytest.raises(ContractScanError, match="duplicate finding"):
        normalize_report(report, tmp_path)


def test_final_severity_filter_applies_across_provider_domains(tmp_path):
    low_dependency = SimpleNamespace(
        cve_id="CVE-LOW",
        risk_level="low",
        description="low dependency risk",
    )
    high_auth = SimpleNamespace(
        finding_type="weak_auth",
        severity="high",
        description="high auth risk",
        file_path="auth.py",
        line_number=2,
        column_start=1,
    )
    report = _empty_complete_report(
        dependency_report=SimpleNamespace(vulnerabilities=[low_dependency]),
        auth_report=SimpleNamespace(findings=[high_auth], total_issues=1),
    )

    findings = normalize_report(report, tmp_path, min_severity="high")

    assert [finding["severity"] for finding in findings] == ["high"]
    assert findings[0]["rule"] == "auth.weak_auth"


def test_coverage_preflight_rejects_injection_caps(tmp_path):
    config = SecurityScanConfig(scan_path=tmp_path, exclude_patterns=[])
    oversized = tmp_path / "oversized.py"
    oversized.write_bytes(b"x" * 1_048_577)
    with pytest.raises(ContractScanError, match="byte analysis limit"):
        _validate_scan_coverage(tmp_path, config)

    oversized.unlink()
    (tmp_path / "long-line.py").write_text("x" * 4097)
    with pytest.raises(ContractScanError, match="character limit"):
        _validate_scan_coverage(tmp_path, config)


def test_coverage_preflight_rejects_shadowed_target_and_read_error(tmp_path):
    shadowed = tmp_path / "Hercules"
    shadowed.mkdir()
    with pytest.raises(ContractScanError, match="shadowed"):
        _validate_scan_coverage(shadowed, SecurityScanConfig(scan_path=shadowed))

    source = tmp_path / "app.py"
    source.write_text("safe = True\n")
    original_open = Path.open

    def fail_source_open(path, *args, **kwargs):
        if path == source:
            raise PermissionError("denied")
        return original_open(path, *args, **kwargs)

    with patch.object(Path, "open", fail_source_open):
        with pytest.raises(ContractScanError, match="cannot read scan input"):
            _validate_scan_coverage(
                tmp_path, SecurityScanConfig(scan_path=tmp_path, exclude_patterns=[])
            )


@pytest.mark.parametrize(
    "name",
    [
        "index.html",
        "proxy.cfg",
        "main.tf",
        "Dockerfile.prod",
        "service.dockerfile",
        "docker-compose.prod.yml",
    ],
)
def test_coverage_preflight_includes_secondary_analyzer_inputs(tmp_path, name):
    source = tmp_path / name
    source.write_text("safe = true\n")
    original_open = Path.open

    def fail_source_open(path, *args, **kwargs):
        if path == source:
            raise PermissionError("denied")
        return original_open(path, *args, **kwargs)

    with patch.object(Path, "open", fail_source_open):
        with pytest.raises(ContractScanError, match="cannot read scan input"):
            _validate_scan_coverage(
                tmp_path, SecurityScanConfig(scan_path=tmp_path, exclude_patterns=[])
            )


def test_coverage_preflight_rejects_symlinked_scan_inputs(tmp_path):
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "app.py").write_text("safe = True\n")
    (tmp_path / "linked-source").symlink_to(destination, target_is_directory=True)

    with pytest.raises(ContractScanError, match="symbolic links are unsupported"):
        _validate_scan_coverage(
            tmp_path, SecurityScanConfig(scan_path=tmp_path, exclude_patterns=[])
        )


def test_atomic_write_cleans_temporary_file_when_sync_fails(tmp_path):
    output = tmp_path / "result.jsonl"
    output.write_text("previous\n")
    with patch("Asgard.hercules_l13.os.fsync", side_effect=OSError("disk error")):
        with pytest.raises(OSError, match="disk error"):
            _write_atomic(output, "replacement\n")
    assert output.read_text() == "previous\n"
    assert list(tmp_path.glob(".result.jsonl.*.tmp")) == []
