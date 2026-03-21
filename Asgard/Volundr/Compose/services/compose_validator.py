"""
Docker Compose Validator Service

Validates docker-compose files for best practices,
security issues, and configuration problems.
"""

import os
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.common.output_formatter import (
    FormattedIssue,
    FormattedReport,
    Severity,
)
from Asgard.Volundr.Compose.services.compose_validator_helpers import (
    build_report,
    initialize_rules,
    validate_network,
    validate_service,
    validate_volume,
)


class ComposeValidator:
    """Validates Docker Compose configurations."""

    def __init__(self):
        self.rules = initialize_rules()

    def validate_file(self, file_path: str) -> FormattedReport:
        issues: List[FormattedIssue] = []

        if not os.path.exists(file_path):
            issues.append(FormattedIssue(
                message=f"File not found: {file_path}",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return build_report(file_path, issues)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                compose_dict = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(FormattedIssue(
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return build_report(file_path, issues)

        if compose_dict is None:
            issues.append(FormattedIssue(
                message="Empty compose file",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return build_report(file_path, issues)

        issues.extend(self._validate_compose_dict(compose_dict, file_path))
        return build_report(file_path, issues)

    def validate_content(self, content: str, source: str = "compose") -> FormattedReport:
        issues: List[FormattedIssue] = []

        try:
            compose_dict = yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(FormattedIssue(
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR,
                file_path=source,
            ))
            return build_report(source, issues)

        if compose_dict is None:
            issues.append(FormattedIssue(
                message="Empty compose content",
                severity=Severity.ERROR,
                file_path=source,
            ))
            return build_report(source, issues)

        issues.extend(self._validate_compose_dict(compose_dict, source))
        return build_report(source, issues)

    def _validate_compose_dict(
        self, compose: Dict[str, Any], file_path: str
    ) -> List[FormattedIssue]:
        issues: List[FormattedIssue] = []

        version = compose.get("version")
        if version:
            try:
                version_float = float(version)
                if version_float < 3.0:
                    issues.append(FormattedIssue(
                        message=f"Compose version {version} is outdated, use 3.8 or higher",
                        severity=Severity.WARNING,
                        file_path=file_path,
                        rule_id="compose-version",
                    ))
            except ValueError:
                pass

        services = compose.get("services", {})
        if not services:
            issues.append(FormattedIssue(
                message="No services defined in compose file",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="no-services",
            ))
        else:
            for service_name, service_config in services.items():
                issues.extend(validate_service(service_name, service_config, file_path))

        networks = compose.get("networks", {})
        for network_name, network_config in networks.items():
            issues.extend(validate_network(network_name, network_config, file_path))

        volumes = compose.get("volumes", {})
        for volume_name, volume_config in volumes.items():
            issues.extend(validate_volume(volume_name, volume_config, file_path))

        return issues
