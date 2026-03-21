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
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tomllib

import yaml  # type: ignore[import-untyped]

from Asgard.Heimdall.Security.models.config_secrets_models import (
    ConfigSecretFinding,
    ConfigSecretSeverity,
    ConfigSecretType,
    ConfigSecretsConfig,
    ConfigSecretsReport,
)
from Asgard.Heimdall.Security.services._config_secrets_helpers import (
    flatten_dict,
    is_credential_key,
    is_placeholder,
    mask_value,
    shannon_entropy,
)
from Asgard.Heimdall.Security.services._config_secrets_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


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
        """Analyze a single config file for hardcoded secrets."""
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
        """Check a key/value pair for potential secrets."""
        findings: List[ConfigSecretFinding] = []

        if not isinstance(value, str):
            return findings

        str_value = value.strip()
        if not str_value:
            return findings

        if is_placeholder(str_value):
            return findings

        file_path_str = str(file_path.absolute())

        if is_credential_key(key, self.config.credential_key_names):
            masked = mask_value(str_value)
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
            return findings

        if len(str_value) >= self.config.entropy_min_length:
            entropy = shannon_entropy(str_value)
            if entropy > self.config.entropy_threshold:
                masked = mask_value(str_value)
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
        """Scan a parsed data structure for secrets."""
        findings = []
        for context_path, key, value in flatten_dict(data):
            findings.extend(self._check_value(file_path, key, value, context_path))
        return findings

    def _analyze_directory(self, directory: Path, report: ConfigSecretsReport) -> None:
        """Analyze all config files in a directory."""
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
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
