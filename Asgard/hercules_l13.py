"""Public Asgard adapter for the Hercules L13 scanner protocol.

The adapter owns the provider-specific translation from Heimdall's security
report models to the small, versioned wire contract consumed by Hercules.
Both a clean scan and a scan with findings are successful executions. Scanner
or domain failures are reported with a non-zero process exit code.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from Asgard import __version__
from Asgard.Heimdall.Security.models.security_models import (
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.services.static_security_service import (
    StaticSecurityService,
)
from Asgard.Heimdall.Security.services.injection_detection_service import (
    MAX_INJECTION_FILE_BYTES,
    MAX_INJECTION_LINE_CHARS,
)
from Asgard.Heimdall.Security.utilities.security_utils import (
    SECURITY_SCAN_EXTENSIONS,
    is_binary_file,
    is_excluded_path,
)


CONTRACT_VERSION = "hercules-l13/v1"
COMPLETION_PREFIX = "HERCULES_SCAN:"
FINDING_PREFIX = "HERCULES_FINDINGS:"
EXIT_EXECUTION_FAILURE = 3
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_FINDINGS = 500
MAX_STRING_CHARS = 4096
MAX_RECORD_CHARS = 64 * 1024
MAX_ROUTED_RECORD_BYTES = 60 * 1024
MAX_ROUTED_OUTPUT_BYTES = 7 * 1024 * 1024

_REPORT_FINDING_FIELDS = (
    ("secrets", "secrets_report", "findings"),
    ("dependencies", "dependency_report", "vulnerabilities"),
    ("vulnerabilities", "vulnerability_report", "findings"),
    ("crypto", "crypto_report", "findings"),
    ("access", "access_report", "findings"),
    ("auth", "auth_report", "findings"),
    ("headers", "headers_report", "findings"),
    ("tls", "tls_report", "findings"),
    ("container", "container_report", "findings"),
    ("infrastructure", "infrastructure_report", "findings"),
)
_SEVERITY_ALIASES = {"moderate": "medium", "safe": "info"}
_VALID_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
_SEVERITY_RANK = {severity: rank for rank, severity in enumerate(
    ("info", "low", "medium", "high", "critical")
)}
_ADDITIONAL_ANALYZER_EXTENSIONS = frozenset({".html", ".cfg", ".tf"})
_DOCKERFILE_PATTERNS = ("Dockerfile", "Dockerfile.*", "*.dockerfile", "dockerfile")
_COMPOSE_PATTERNS = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.*.yml",
    "docker-compose.*.yaml",
    "compose.yml",
    "compose.yaml",
)
_DEPENDENCY_EXCLUDE_DIRS = frozenset(
    {"node_modules", ".venv", "venv", ".git", "__pycache__"}
)
_COUNT_FIELDS = {
    "secrets_report": "secrets_found",
    "vulnerability_report": "vulnerabilities_found",
    "crypto_report": "issues_found",
    "access_report": "total_issues",
    "auth_report": "total_issues",
    "headers_report": "total_issues",
    "tls_report": "total_issues",
    "container_report": "total_issues",
    "infrastructure_report": "total_issues",
}


class ContractScanError(RuntimeError):
    """Raised when Asgard cannot complete a trustworthy contract scan."""


def add_scan_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the public scanner adapter on Asgard's root CLI."""
    parser = subparsers.add_parser(
        "scan",
        help="Run a machine-readable security scan for an external orchestrator",
        description=(
            "Run Heimdall security analysis and write the versioned Hercules "
            "L13 scanner protocol."
        ),
    )
    parser.add_argument("--target", required=True, help="Local directory to scan")
    parser.add_argument("--output", required=True, help="Protocol output file")
    parser.add_argument(
        "--contract-version",
        choices=[CONTRACT_VERSION],
        required=True,
        help=f"Wire contract version (supported: {CONTRACT_VERSION})",
    )
    parser.add_argument(
        "--severity",
        choices=[member.value for member in SecuritySeverity],
        default=SecuritySeverity.LOW.value,
        help="Minimum finding severity across every enabled scan domain",
    )


def _value(raw: Any) -> Any:
    if isinstance(raw, Enum):
        return raw.value
    return raw


def _relative_location(raw: Any, target: Path) -> str:
    if raw is None or str(raw).strip() == "":
        return "."
    path = Path(str(raw))
    if not path.is_absolute():
        path = target / path
    try:
        return path.resolve().relative_to(target).as_posix()
    except ValueError as exc:
        raise ContractScanError("finding location is outside the scan target") from exc


def _contract_string(raw: Any, field: str) -> str:
    value = str(raw).strip()
    if not value:
        raise ContractScanError(f"finding {field} cannot be empty")
    if len(value) > MAX_STRING_CHARS:
        raise ContractScanError(
            f"finding {field} exceeds the {MAX_STRING_CHARS}-character routing limit"
        )
    return value


def _rule_name(domain: str, finding: Any) -> str:
    for field in (
        "mechanism_id",
        "finding_type",
        "vulnerability_type",
        "issue_type",
        "pattern_name",
        "cve_id",
        "ghsa_id",
        "title",
    ):
        candidate = _value(getattr(finding, field, None))
        if candidate is not None and str(candidate).strip():
            value = str(candidate).strip().lower().replace(" ", "_")
            return _contract_string(
                value if "." in value else f"{domain}.{value}", "rule"
            )
    return _contract_string(f"{domain}.{type(finding).__name__.lower()}", "rule")


def _message(finding: Any, rule: str) -> str:
    for field in ("message", "description", "title"):
        candidate = getattr(finding, field, None)
        if candidate is not None and str(candidate).strip():
            return _contract_string(candidate, "message")
    return _contract_string(rule, "message")


def _severity(finding: Any) -> str:
    raw = _value(
        getattr(finding, "severity", None)
        or getattr(finding, "risk_level", None)
        or "info"
    )
    severity = _SEVERITY_ALIASES.get(str(raw).lower(), str(raw).lower())
    if severity not in _VALID_SEVERITIES:
        raise ContractScanError(f"finding has unsupported severity: {raw}")
    return severity


def _coordinate(finding: Any, field: str) -> int | None:
    value = getattr(finding, field, None)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractScanError(
            f"finding {field} must be a non-negative integer or null"
        )
    return value


def normalize_finding(domain: str, finding: Any, target: Path) -> dict[str, Any]:
    """Normalize one native Heimdall finding into the L13 v1 schema."""
    rule = _rule_name(domain, finding)
    location = {
        "path": _contract_string(
            _relative_location(getattr(finding, "file_path", None), target),
            "location path",
        ),
        "line": _coordinate(finding, "line_number"),
        "column": _coordinate(finding, "column_start"),
    }
    normalized = {
        "rule": rule,
        "severity": _severity(finding),
        "message": _message(finding, rule),
        "location": location,
    }
    identity = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    normalized["id"] = f"asgard:{hashlib.sha256(identity.encode()).hexdigest()}"
    return normalized


def normalize_report(
    report: Any, target: Path, min_severity: str = SecuritySeverity.LOW.value
) -> list[dict[str, Any]]:
    """Return a stable, sorted set of normalized findings from a report."""
    findings: list[dict[str, Any]] = []
    finding_ids: set[str] = set()
    for domain, report_field, findings_field in _REPORT_FINDING_FIELDS:
        sub_report = getattr(report, report_field, None)
        for finding in getattr(sub_report, findings_field, []) if sub_report else []:
            if getattr(finding, "suppressed_by_context", False):
                continue
            normalized = normalize_finding(domain, finding, target)
            if _SEVERITY_RANK[normalized["severity"]] < _SEVERITY_RANK[min_severity]:
                continue
            if normalized["id"] in finding_ids:
                raise ContractScanError(
                    f"security scan returned duplicate finding: {normalized['id']}"
                )
            if len(findings) >= MAX_FINDINGS:
                raise ContractScanError(
                    f"scan returned more than the {MAX_FINDINGS}-finding routing limit"
                )
            finding_ids.add(normalized["id"])
            findings.append(normalized)
    findings.sort(
        key=lambda finding: (
            finding["location"]["path"],
            finding["location"]["line"] or 0,
            finding["rule"],
            finding["id"],
        )
    )
    return findings


def _validate_complete_report(report: Any) -> None:
    """Reject aggregate reports whose requested domains or counts are incomplete."""
    if getattr(report, "domain_errors", None):
        failed = ", ".join(
            str(error.get("domain", "unknown")) for error in report.domain_errors
        )
        raise ContractScanError(f"security scan domain failure(s): {failed}")

    for _domain, report_field, findings_field in _REPORT_FINDING_FIELDS:
        sub_report = getattr(report, report_field, None)
        if sub_report is None:
            raise ContractScanError(f"security scan omitted requested domain: {report_field}")
        findings = getattr(sub_report, findings_field, None)
        if not isinstance(findings, list):
            raise ContractScanError(f"security scan returned invalid findings for: {report_field}")
        count_field = _COUNT_FIELDS.get(report_field)
        if count_field is not None and getattr(sub_report, count_field, None) != len(findings):
            raise ContractScanError(f"security scan returned inconsistent count for: {report_field}")


def _validate_scan_coverage(target: Path, config: SecurityScanConfig) -> None:
    """Preflight readable inputs and Heimdall's documented injection caps."""
    exclusions = list(config.exclude_patterns)
    if is_excluded_path(target / "__asgard_l13_input_probe__.py", exclusions):
        raise ContractScanError(
            "scan target path is shadowed by Heimdall's default exclusions"
        )

    def walk(directory: Path) -> Iterable[Path]:
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    try:
                        if entry.is_symlink():
                            if (
                                path.name in _DEPENDENCY_EXCLUDE_DIRS
                                and is_excluded_path(path, exclusions)
                            ):
                                continue
                            raise ContractScanError(
                                f"symbolic links are unsupported scan inputs: {path}"
                            )
                        if entry.is_dir(follow_symlinks=False):
                            if path.name in _DEPENDENCY_EXCLUDE_DIRS:
                                continue
                            yield from walk(path)
                        elif entry.is_file(follow_symlinks=False):
                            yield path
                    except OSError as exc:
                        raise ContractScanError(f"cannot inspect scan input: {path}") from exc
        except OSError as exc:
            raise ContractScanError(f"cannot enumerate scan directory: {directory}") from exc

    for path in walk(target):
        injection_eligible = (
            path.suffix.lower() in SECURITY_SCAN_EXTENSIONS
            or path.name in {".env", ".htaccess", "Dockerfile"}
        ) and not is_binary_file(path) and not is_excluded_path(path, exclusions)
        container_eligible = any(
            fnmatch.fnmatch(path.name, pattern)
            or fnmatch.fnmatch(path.name.lower(), pattern.lower())
            for pattern in (*_DOCKERFILE_PATTERNS, *_COMPOSE_PATTERNS)
        ) and not is_excluded_path(path, exclusions)
        analyzer_eligible = injection_eligible or container_eligible or (
            path.suffix.lower() in _ADDITIONAL_ANALYZER_EXTENSIONS
            and not is_excluded_path(path, exclusions)
        )
        dependency_manifest = path.name in {
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
        } or (path.name.startswith("requirements") and path.name.endswith(".txt"))
        if not analyzer_eligible and not dependency_manifest:
            continue
        try:
            with path.open("rb") as source:
                raw = source.read()
        except OSError as exc:
            raise ContractScanError(f"cannot read scan input: {path}") from exc

        if not injection_eligible:
            continue
        if len(raw) > MAX_INJECTION_FILE_BYTES:
            raise ContractScanError(
                f"scan input exceeds Heimdall's {MAX_INJECTION_FILE_BYTES}-byte analysis limit: {path}"
            )
        text = raw.decode("utf-8", errors="ignore")
        if any(len(line) > MAX_INJECTION_LINE_CHARS for line in text.split("\n")):
            raise ContractScanError(
                f"scan input contains a line over Heimdall's {MAX_INJECTION_LINE_CHARS}-character limit: {path}"
            )


def _json_line(prefix: str, payload: dict[str, Any]) -> str:
    return prefix + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _validate_contract_finding(finding: dict[str, Any]) -> None:
    if set(finding) != {"id", "rule", "severity", "message", "location"}:
        raise ContractScanError("finding record has an invalid schema")
    for field in ("id", "rule", "message"):
        if not isinstance(finding[field], str):
            raise ContractScanError(f"finding {field} must be a string")
        _contract_string(finding[field], field)
    if finding["severity"] not in _VALID_SEVERITIES:
        raise ContractScanError("finding record has an unsupported severity")
    location = finding["location"]
    if not isinstance(location, dict) or set(location) != {"path", "line", "column"}:
        raise ContractScanError("finding location has an invalid schema")
    if not isinstance(location["path"], str):
        raise ContractScanError("finding location path must be a string")
    _contract_string(location["path"], "location path")
    for field in ("line", "column"):
        value = location[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ContractScanError(
                f"finding location {field} must be a non-negative integer or null"
            )


def render_contract(findings: Iterable[dict[str, Any]], version: str) -> str:
    """Render a complete v1 output document within every Hercules bound."""
    records = list(findings)
    if len(records) > MAX_FINDINGS:
        raise ContractScanError(
            f"scan returned {len(records)} findings; routing limit is {MAX_FINDINGS}"
        )
    for finding in records:
        _validate_contract_finding(finding)
    finding_lines = [_json_line(FINDING_PREFIX, finding) for finding in records]
    if version != CONTRACT_VERSION:
        raise ContractScanError(f"unsupported contract version: {version}")
    completion = {
        "contract_version": CONTRACT_VERSION,
        "finding_count": len(records),
        "scanner": {"name": "asgard", "version": __version__},
        "status": "findings" if records else "clean",
    }
    lines = [*finding_lines, _json_line(COMPLETION_PREFIX, completion)]
    if any(len(line) > MAX_RECORD_CHARS for line in lines):
        raise ContractScanError(
            f"contract record exceeds the {MAX_RECORD_CHARS}-character routing limit"
        )
    content = "\n".join(lines) + "\n"
    if len(content.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ContractScanError(
            f"contract output exceeds the {MAX_OUTPUT_BYTES}-byte consumer limit"
        )
    routed_lines = [
        FINDING_PREFIX + json.dumps(finding) for finding in records
    ]
    if any(len(line.encode("utf-8")) > MAX_ROUTED_RECORD_BYTES for line in routed_lines):
        raise ContractScanError(
            "finding exceeds the routed-record limit after Hercules serialization"
        )
    routed_size = sum(len(line.encode("utf-8")) + 1 for line in routed_lines)
    if routed_size > MAX_ROUTED_OUTPUT_BYTES:
        raise ContractScanError(
            "findings exceed the routed-output limit after Hercules serialization"
        )
    return content


def _write_atomic(output: Path, content: str) -> None:
    if output.exists() and output.is_dir():
        raise ContractScanError(f"output path is a directory: {output}")
    parent = output.parent.resolve()
    if not parent.is_dir():
        raise ContractScanError(f"output parent does not exist: {parent}")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_name, output)
    finally:
        if temp_name is not None and Path(temp_name).exists():
            Path(temp_name).unlink()


def execute_scan(
    target_raw: str,
    output_raw: str,
    contract_version: str,
    severity: str = SecuritySeverity.LOW.value,
) -> int:
    """Run Heimdall and write one atomic contract document."""
    if "\x00" in target_raw or "\x00" in output_raw:
        raise ContractScanError("target and output paths cannot contain NUL bytes")
    target = Path(target_raw).resolve()
    if not target.is_dir():
        raise ContractScanError(f"scan target is not a directory: {target}")
    output = Path(output_raw)
    config = SecurityScanConfig(
        scan_path=target,
        min_severity=SecuritySeverity(severity),
        enable_network=False,
    )
    _validate_scan_coverage(target, config)
    report = StaticSecurityService(config).scan(target)
    _validate_complete_report(report)
    findings = normalize_report(report, target, min_severity=severity)
    _write_atomic(output, render_contract(findings, contract_version))
    return 0


def run_scan(args: argparse.Namespace) -> int:
    """CLI handler with stable exit semantics for orchestrators."""
    try:
        return execute_scan(
            target_raw=args.target,
            output_raw=args.output,
            contract_version=args.contract_version,
            severity=args.severity,
        )
    except Exception as exc:
        print(f"Asgard scanner execution failed: {exc}", file=sys.stderr)
        return EXIT_EXECUTION_FAILURE
