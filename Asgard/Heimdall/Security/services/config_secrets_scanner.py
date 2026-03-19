"""
Heimdall Config Secrets Scanner Service

Detects hardcoded secrets and credentials in configuration files
(YAML, JSON, TOML, INI). Reads config files directly (not via AST)
and identifies suspicious key/value pairs.

Detects:
- Keys named token, api_key, password, secret, credential, auth, private_key
  (case-insensitive) with non-placeholder values
- High-entropy strings (Shannon entropy > 3.5) for strings longer than 20 chars
"""

import configparser
import fnmatch
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import tomllib

import yaml  # type: ignore[import-untyped]

from Asgard.Heimdall.Security.models.config_secrets_models import (
    ConfigSecretFinding,
    ConfigSecretSeverity,
    ConfigSecretType,
    ConfigSecretsConfig,
    ConfigSecretsReport,
)


# Values that look like placeholders and should be ignored
PLACEHOLDER_FRAGMENTS = [
    "${", "{{", "<", "changeme", "todo", "replace", "your-", "your_",
    "example", "placeholder", "xxxxx", "00000", "insert",
]


def _is_placeholder(value: str) -> bool:
    """Return True if a string looks like a placeholder, not a real secret."""
    if not value:
        return True
    value_lower = value.lower()
    for fragment in PLACEHOLDER_FRAGMENTS:
        if fragment in value_lower:
            return True
    return False


def _shannon_entropy(text: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not text:
        return 0.0
    freq: Dict[str, int] = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    return entropy


def _mask_value(value: str) -> str:
    """Return a masked version of the value for safe display."""
    if len(value) <= 4:
        return "****"
    visible = max(2, len(value) // 6)
    return value[:visible] + "****" + value[-visible:]


def _is_credential_key(key: str, credential_key_names: List[str]) -> bool:
    """Return True if the key name suggests it holds a credential."""
    key_lower = key.lower()
    for fragment in credential_key_names:
        if fragment in key_lower:
            return True
    return False


def _flatten_dict(
    data: Any, prefix: str = ""
) -> Iterator[Tuple[str, str, Any]]:
    """
    Recursively yield (context_path, key, value) tuples from a nested dict/list structure.

    Args:
        data: The data structure to flatten
        prefix: Dot-notation path prefix for context
    """
    if isinstance(data, dict):
        for key, value in data.items():
            full_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                yield from _flatten_dict(value, full_path)
            else:
                yield full_path, key, value
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            full_path = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)):
                yield from _flatten_dict(item, full_path)
            else:
                yield full_path, str(idx), item


class ConfigSecretsScanner:
    """
    Scans configuration files for hardcoded secrets and credentials.

    Reads YAML, JSON, TOML, and INI files directly and checks for:
    - Keys with credential-like names holding non-placeholder values
    - High-entropy strings that may be real secrets

    Usage:
        scanner = ConfigSecretsScanner()
        report = scanner.analyze(Path("./config"))

        for finding in report.detected_findings:
            print(f"{finding.location}: {finding.key_name} = {finding.masked_value}")
    """

    def __init__(self, config: Optional[ConfigSecretsConfig] = None):
        """
        Initialize config secrets scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or ConfigSecretsConfig()

    def analyze(self, path: Path) -> ConfigSecretsReport:
        """
        Analyze a file or directory for hardcoded secrets.

        Args:
            path: Path to file or directory to analyze

        Returns:
            ConfigSecretsReport with all detected findings

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = ConfigSecretsReport(scan_path=str(path))

        if path.is_file():
            findings = self._analyze_file(path, path.parent)
            for finding in findings:
                report.add_finding(finding)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        file_finding_counts: Dict[str, int] = defaultdict(int)
        for finding in report.detected_findings:
            file_finding_counts[finding.file_path] += 1

        report.most_problematic_files = sorted(
            file_finding_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return report

    def _analyze_file(
        self, file_path: Path, root_path: Path
    ) -> List[ConfigSecretFinding]:
        """
        Analyze a single config file for hardcoded secrets.

        Args:
            file_path: Path to config file
            root_path: Root path for calculating relative paths

        Returns:
            List of detected findings
        """
        suffix = file_path.suffix.lower()

        try:
            if suffix in (".yaml", ".yml"):
                findings = self._analyze_yaml(file_path)
            elif suffix == ".json":
                findings = self._analyze_json(file_path)
            elif suffix == ".toml":
                findings = self._analyze_toml(file_path)
            elif suffix in (".ini", ".cfg", ".conf"):
                findings = self._analyze_ini(file_path)
            else:
                return []

            for finding in findings:
                try:
                    finding.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    finding.relative_path = file_path.name

            filtered = [
                f for f in findings
                if self._severity_level(f.severity) >= self._severity_level(self.config.severity_filter)
            ]

            return filtered

        except Exception:
            return []

    def _check_value(
        self,
        file_path: Path,
        key: str,
        value: Any,
        context_path: str,
    ) -> List[ConfigSecretFinding]:
        """
        Check a key/value pair for potential secrets.

        Args:
            file_path: Path to the config file
            key: The key name
            value: The value to check
            context_path: Dot-notation path to this key

        Returns:
            List of findings (0, 1, or more)
        """
        findings = []

        # Only check string values
        if not isinstance(value, str):
            return findings

        str_value = value.strip()
        if not str_value:
            return findings

        # Skip placeholders
        if _is_placeholder(str_value):
            return findings

        file_path_str = str(file_path.absolute())

        # Check 1: credential key name with non-placeholder value
        if _is_credential_key(key, self.config.credential_key_names):
            masked = _mask_value(str_value)
            findings.append(ConfigSecretFinding(
                file_path=file_path_str,
                key_name=key,
                masked_value=masked,
                secret_type=ConfigSecretType.CREDENTIAL_KEY,
                severity=ConfigSecretSeverity.CRITICAL,
                context_path=context_path,
                context_description=(
                    f"Key '{key}' at path '{context_path}' has a credential-like name "
                    f"with a non-placeholder value: {masked}"
                ),
            ))
            # Return after credential key match to avoid duplicate
            return findings

        # Check 2: high-entropy string regardless of key name
        if len(str_value) >= self.config.entropy_min_length:
            entropy = _shannon_entropy(str_value)
            if entropy > self.config.entropy_threshold:
                masked = _mask_value(str_value)
                findings.append(ConfigSecretFinding(
                    file_path=file_path_str,
                    key_name=key,
                    masked_value=masked,
                    secret_type=ConfigSecretType.HIGH_ENTROPY_STRING,
                    severity=ConfigSecretSeverity.MEDIUM,
                    entropy=round(entropy, 2),
                    context_path=context_path,
                    context_description=(
                        f"Key '{key}' at path '{context_path}' contains a high-entropy string "
                        f"(entropy={entropy:.2f}) that may be a secret: {masked}"
                    ),
                ))

        return findings

    def _analyze_yaml(self, file_path: Path) -> List[ConfigSecretFinding]:
        """Parse and scan a YAML file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if data is None:
                return []
            return self._scan_data(file_path, data)
        except Exception:
            return []

    def _analyze_json(self, file_path: Path) -> List[ConfigSecretFinding]:
        """Parse and scan a JSON file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return self._scan_data(file_path, data)
        except Exception:
            return []

    def _analyze_toml(self, file_path: Path) -> List[ConfigSecretFinding]:
        """Parse and scan a TOML file."""
        try:
            content = file_path.read_bytes()
            data = tomllib.loads(content.decode("utf-8"))
            return self._scan_data(file_path, data)
        except Exception:
            return []

    def _analyze_ini(self, file_path: Path) -> List[ConfigSecretFinding]:
        """Parse and scan an INI/CFG file."""
        findings = []
        try:
            parser = configparser.ConfigParser()
            parser.read(str(file_path), encoding="utf-8")

            for section in parser.sections():
                for key, value in parser.items(section):
                    context_path = f"{section}.{key}"
                    findings.extend(
                        self._check_value(file_path, key, value, context_path)
                    )

            # Also check DEFAULT section
            for key, value in parser.defaults().items():
                context_path = f"DEFAULT.{key}"
                findings.extend(
                    self._check_value(file_path, key, value, context_path)
                )

        except Exception:
            pass

        return findings

    def _scan_data(
        self, file_path: Path, data: Any
    ) -> List[ConfigSecretFinding]:
        """
        Scan a parsed data structure for secrets.

        Args:
            file_path: Path to the config file
            data: Parsed data (dict, list, etc.)

        Returns:
            List of detected findings
        """
        findings = []
        for context_path, key, value in _flatten_dict(data):
            findings.extend(self._check_value(file_path, key, value, context_path))
        return findings

    def _analyze_directory(self, directory: Path, report: ConfigSecretsReport) -> None:
        """
        Analyze all config files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add findings to
        """
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, p) for p in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                if any(self._matches_pattern(file, p) for p in self.config.exclude_patterns):
                    continue

                file_path = root_path / file
                file_findings = self._analyze_file(file_path, directory)
                files_scanned += 1

                for finding in file_findings:
                    report.add_finding(finding)

        report.files_scanned = files_scanned

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension."""
        return any(filename.endswith(ext) for ext in self.config.include_extensions)

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def _severity_level(self, severity) -> int:
        """Convert severity to numeric level for comparison."""
        if isinstance(severity, str):
            severity = ConfigSecretSeverity(severity)
        levels = {
            ConfigSecretSeverity.LOW: 1,
            ConfigSecretSeverity.MEDIUM: 2,
            ConfigSecretSeverity.HIGH: 3,
            ConfigSecretSeverity.CRITICAL: 4,
        }
        return levels.get(severity, 1)

    def generate_report(self, report: ConfigSecretsReport, output_format: str = "text") -> str:
        """
        Generate formatted config secrets report.

        Args:
            report: ConfigSecretsReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return self._generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return self._generate_markdown_report(report)
        elif format_lower == "text":
            return self._generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")

    def _generate_text_report(self, report: ConfigSecretsReport) -> str:
        """Generate plain text report."""
        lines = [
            "=" * 70,
            "CONFIG SECRETS FINDINGS REPORT",
            "=" * 70,
            "",
            f"Scan Path: {report.scan_path}",
            f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {report.scan_duration_seconds:.2f} seconds",
            f"Files Scanned: {report.files_scanned}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Findings: {report.total_findings}",
            f"Clean: {'Yes' if report.is_clean else 'No'}",
            "",
        ]

        if report.has_findings:
            lines.append("By Severity:")
            for severity in [
                ConfigSecretSeverity.CRITICAL,
                ConfigSecretSeverity.HIGH,
                ConfigSecretSeverity.MEDIUM,
                ConfigSecretSeverity.LOW,
            ]:
                count = report.findings_by_severity.get(severity.value, 0)
                if count > 0:
                    lines.append(f"  {severity.value.upper()}: {count}")

            lines.extend(["", "By Type:"])
            for secret_type in ConfigSecretType:
                count = report.findings_by_type.get(secret_type.value, 0)
                if count > 0:
                    lines.append(f"  {secret_type.value.replace('_', ' ').title()}: {count}")

            if report.most_problematic_files:
                lines.extend(["", "Most Problematic Files:", "-" * 40])
                for file_path, count in report.most_problematic_files[:5]:
                    filename = os.path.basename(file_path)
                    lines.append(f"  {filename}: {count} findings")

            lines.extend(["", "FINDINGS", "-" * 40])

            for severity in [
                ConfigSecretSeverity.CRITICAL,
                ConfigSecretSeverity.HIGH,
                ConfigSecretSeverity.MEDIUM,
                ConfigSecretSeverity.LOW,
            ]:
                severity_findings = report.get_findings_by_severity(severity)
                if severity_findings:
                    lines.extend(["", f"[{severity.value.upper()}]"])
                    for f in severity_findings:
                        lines.append(f"  {f.location}")
                        lines.append(f"    Key: {f.key_name}")
                        lines.append(f"    Path: {f.context_path}")
                        lines.append(f"    Value: {f.masked_value}")
                        if f.entropy is not None:
                            lines.append(f"    Entropy: {f.entropy:.2f}")
                        lines.append(f"    Context: {f.context_description}")
                        lines.append(f"    Fix: {f.remediation}")
                        lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, report: ConfigSecretsReport) -> str:
        """Generate JSON report."""
        findings_data = []
        for f in report.detected_findings:
            findings_data.append({
                "file_path": f.file_path,
                "relative_path": f.relative_path,
                "line_number": f.line_number,
                "key_name": f.key_name,
                "masked_value": f.masked_value,
                "secret_type": f.secret_type if isinstance(f.secret_type, str) else f.secret_type.value,
                "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                "entropy": f.entropy,
                "context_path": f.context_path,
                "context_description": f.context_description,
                "remediation": f.remediation,
            })

        report_data = {
            "scan_info": {
                "scan_path": report.scan_path,
                "scanned_at": report.scanned_at.isoformat(),
                "duration_seconds": report.scan_duration_seconds,
                "files_scanned": report.files_scanned,
            },
            "summary": {
                "total_findings": report.total_findings,
                "is_clean": report.is_clean,
                "findings_by_severity": report.findings_by_severity,
                "findings_by_type": report.findings_by_type,
            },
            "findings": findings_data,
            "most_problematic_files": [
                {"file": fp, "finding_count": count}
                for fp, count in report.most_problematic_files
            ],
        }

        return json.dumps(report_data, indent=2)

    def _generate_markdown_report(self, report: ConfigSecretsReport) -> str:
        """Generate Markdown report."""
        lines = [
            "# Config Secrets Findings Report",
            "",
            f"**Scan Path:** `{report.scan_path}`",
            f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
            f"**Files Scanned:** {report.files_scanned}",
            "",
            "## Summary",
            "",
            f"**Total Findings:** {report.total_findings}",
            f"**Clean:** {'Yes' if report.is_clean else 'No'}",
            "",
        ]

        if report.has_findings:
            lines.extend([
                "### By Severity",
                "",
                "| Severity | Count |",
                "|----------|-------|",
            ])
            for severity in [
                ConfigSecretSeverity.CRITICAL,
                ConfigSecretSeverity.HIGH,
                ConfigSecretSeverity.MEDIUM,
                ConfigSecretSeverity.LOW,
            ]:
                count = report.findings_by_severity.get(severity.value, 0)
                lines.append(f"| {severity.value.title()} | {count} |")

            lines.extend([
                "",
                "### By Type",
                "",
                "| Type | Count |",
                "|------|-------|",
            ])
            for secret_type in ConfigSecretType:
                count = report.findings_by_type.get(secret_type.value, 0)
                if count > 0:
                    lines.append(f"| {secret_type.value.replace('_', ' ').title()} | {count} |")

            if report.most_problematic_files:
                lines.extend(["", "## Most Problematic Files", ""])
                for file_path, count in report.most_problematic_files[:10]:
                    filename = os.path.basename(file_path)
                    lines.append(f"- `{filename}`: {count} findings")

            lines.extend(["", "## Findings", ""])

            for severity in [
                ConfigSecretSeverity.CRITICAL,
                ConfigSecretSeverity.HIGH,
                ConfigSecretSeverity.MEDIUM,
                ConfigSecretSeverity.LOW,
            ]:
                severity_findings = report.get_findings_by_severity(severity)
                if severity_findings:
                    lines.extend([f"### {severity.value.title()} Severity", ""])
                    for f in severity_findings[:20]:
                        filename = os.path.basename(f.file_path)
                        lines.extend([
                            f"#### `{filename}` - `{f.key_name}`",
                            "",
                            f"**Key:** `{f.key_name}`",
                            f"**Path:** `{f.context_path}`",
                            f"**Masked Value:** `{f.masked_value}`",
                        ])
                        if f.entropy is not None:
                            lines.append(f"**Entropy:** {f.entropy:.2f}")
                        lines.extend([
                            "",
                            f"**Context:** {f.context_description}",
                            "",
                            f"**Remediation:** {f.remediation}",
                            "",
                        ])

        return "\n".join(lines)
