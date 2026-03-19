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


class ComposeValidator:
    """Validates Docker Compose configurations."""

    def __init__(self):
        """Initialize the compose validator."""
        self.rules = self._initialize_rules()

    def validate_file(self, file_path: str) -> FormattedReport:
        """
        Validate a docker-compose.yaml file.

        Args:
            file_path: Path to the compose file

        Returns:
            FormattedReport with validation results
        """
        issues: List[FormattedIssue] = []

        if not os.path.exists(file_path):
            issues.append(FormattedIssue(
                message=f"File not found: {file_path}",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return self._build_report(file_path, issues)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                compose_dict = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(FormattedIssue(
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return self._build_report(file_path, issues)

        if compose_dict is None:
            issues.append(FormattedIssue(
                message="Empty compose file",
                severity=Severity.ERROR,
                file_path=file_path,
            ))
            return self._build_report(file_path, issues)

        issues.extend(self._validate_compose_dict(compose_dict, file_path))
        return self._build_report(file_path, issues)

    def validate_content(self, content: str, source: str = "compose") -> FormattedReport:
        """
        Validate docker-compose content from string.

        Args:
            content: YAML content to validate
            source: Source identifier for reporting

        Returns:
            FormattedReport with validation results
        """
        issues: List[FormattedIssue] = []

        try:
            compose_dict = yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(FormattedIssue(
                message=f"Invalid YAML: {e}",
                severity=Severity.ERROR,
                file_path=source,
            ))
            return self._build_report(source, issues)

        if compose_dict is None:
            issues.append(FormattedIssue(
                message="Empty compose content",
                severity=Severity.ERROR,
                file_path=source,
            ))
            return self._build_report(source, issues)

        issues.extend(self._validate_compose_dict(compose_dict, source))
        return self._build_report(source, issues)

    def _validate_compose_dict(
        self, compose: Dict[str, Any], file_path: str
    ) -> List[FormattedIssue]:
        """Validate compose dictionary."""
        issues: List[FormattedIssue] = []

        # Check version
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

        # Check services
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
                issues.extend(self._validate_service(
                    service_name, service_config, file_path
                ))

        # Check networks
        networks = compose.get("networks", {})
        for network_name, network_config in networks.items():
            issues.extend(self._validate_network(
                network_name, network_config, file_path
            ))

        # Check volumes
        volumes = compose.get("volumes", {})
        for volume_name, volume_config in volumes.items():
            issues.extend(self._validate_volume(
                volume_name, volume_config, file_path
            ))

        return issues

    def _validate_service(
        self, name: str, config: Dict[str, Any], file_path: str
    ) -> List[FormattedIssue]:
        """Validate a service configuration."""
        issues: List[FormattedIssue] = []

        if config is None:
            config = {}

        # Check image or build
        if not config.get("image") and not config.get("build"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no image or build configuration",
                severity=Severity.ERROR,
                file_path=file_path,
                rule_id="no-image-or-build",
            ))

        # Check for latest tag
        image = config.get("image", "")
        if image.endswith(":latest") or (image and ":" not in image):
            issues.append(FormattedIssue(
                message=f"Service '{name}' uses :latest or untagged image - pin to specific version",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="unpinned-image",
                suggestion="Use a specific version tag instead of :latest",
            ))

        # Check health check
        if not config.get("healthcheck"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no health check defined",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="no-healthcheck",
                suggestion="Add a healthcheck to detect container failures",
            ))

        # Check restart policy
        restart = config.get("restart")
        if not restart or restart == "no":
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no restart policy",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="no-restart-policy",
                suggestion="Add 'restart: unless-stopped' or 'restart: always'",
            ))

        # Check privileged mode
        if config.get("privileged"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' uses privileged mode - security concern",
                severity=Severity.ERROR,
                file_path=file_path,
                rule_id="privileged-container",
                suggestion="Avoid privileged mode; use specific capabilities if needed",
            ))

        # Check resource limits
        deploy = config.get("deploy", {})
        resources = deploy.get("resources", {})
        if not resources.get("limits"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no resource limits defined",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="no-resource-limits",
                suggestion="Add deploy.resources.limits for cpu and memory",
            ))

        # Check for secrets in environment
        environment = config.get("environment", {})
        if isinstance(environment, dict):
            for key, value in environment.items():
                if self._looks_like_secret(key, value):
                    issues.append(FormattedIssue(
                        message=f"Service '{name}' has potential secret in environment: {key}",
                        severity=Severity.WARNING,
                        file_path=file_path,
                        rule_id="secret-in-env",
                        suggestion="Use Docker secrets or external secret management",
                    ))

        # Check logging
        if not config.get("logging"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no logging configuration",
                severity=Severity.INFO,
                file_path=file_path,
                rule_id="no-logging-config",
                suggestion="Add logging configuration with max-size and max-file",
            ))

        # Check security options
        if not config.get("security_opt") and not config.get("cap_drop"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' has no security hardening (no cap_drop or security_opt)",
                severity=Severity.INFO,
                file_path=file_path,
                rule_id="no-security-hardening",
                suggestion="Add 'cap_drop: [ALL]' and only add required capabilities",
            ))

        # Check user
        if not config.get("user"):
            issues.append(FormattedIssue(
                message=f"Service '{name}' runs as root (no user specified)",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="running-as-root",
                suggestion="Add 'user: 1000:1000' or similar non-root user",
            ))

        # Check for host network mode
        network_mode = config.get("network_mode")
        if network_mode == "host":
            issues.append(FormattedIssue(
                message=f"Service '{name}' uses host network mode",
                severity=Severity.WARNING,
                file_path=file_path,
                rule_id="host-network-mode",
                suggestion="Avoid host network mode unless absolutely necessary",
            ))

        return issues

    def _validate_network(
        self, name: str, config: Optional[Dict[str, Any]], file_path: str
    ) -> List[FormattedIssue]:
        """Validate a network configuration."""
        issues: List[FormattedIssue] = []

        if config is None:
            return issues

        # External networks without name
        if config.get("external") and not config.get("name"):
            issues.append(FormattedIssue(
                message=f"External network '{name}' should specify explicit name",
                severity=Severity.INFO,
                file_path=file_path,
                rule_id="external-network-no-name",
            ))

        return issues

    def _validate_volume(
        self, name: str, config: Optional[Dict[str, Any]], file_path: str
    ) -> List[FormattedIssue]:
        """Validate a volume configuration."""
        issues: List[FormattedIssue] = []

        if config is None:
            return issues

        # Check for appropriate driver
        driver = config.get("driver", "local")
        if driver == "local" and config.get("driver_opts"):
            opts = config.get("driver_opts", {})
            if opts.get("type") == "nfs" or opts.get("type") == "cifs":
                # NFS/CIFS should have proper options
                if "o" not in opts:
                    issues.append(FormattedIssue(
                        message=f"Volume '{name}' uses NFS/CIFS but missing mount options",
                        severity=Severity.WARNING,
                        file_path=file_path,
                        rule_id="volume-missing-options",
                    ))

        return issues

    def _looks_like_secret(self, key: str, value: Any) -> bool:
        """Check if an environment variable looks like a secret."""
        secret_patterns = [
            "password", "secret", "key", "token", "api_key",
            "apikey", "auth", "credential", "private",
        ]

        key_lower = key.lower()
        for pattern in secret_patterns:
            if pattern in key_lower:
                # Check if it looks like a real value (not a variable reference)
                if value and isinstance(value, str):
                    if not value.startswith("${") and not value.startswith("$"):
                        return True

        return False

    def _initialize_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize validation rules."""
        return {
            "compose-version": {
                "description": "Compose file version check",
                "severity": Severity.WARNING,
            },
            "no-services": {
                "description": "No services defined",
                "severity": Severity.WARNING,
            },
            "no-image-or-build": {
                "description": "Service missing image or build",
                "severity": Severity.ERROR,
            },
            "unpinned-image": {
                "description": "Image uses :latest or no tag",
                "severity": Severity.WARNING,
            },
            "no-healthcheck": {
                "description": "Service missing health check",
                "severity": Severity.WARNING,
            },
            "no-restart-policy": {
                "description": "Service missing restart policy",
                "severity": Severity.WARNING,
            },
            "privileged-container": {
                "description": "Container runs in privileged mode",
                "severity": Severity.ERROR,
            },
            "no-resource-limits": {
                "description": "Service missing resource limits",
                "severity": Severity.WARNING,
            },
            "secret-in-env": {
                "description": "Potential secret in environment variable",
                "severity": Severity.WARNING,
            },
            "no-logging-config": {
                "description": "Service missing logging configuration",
                "severity": Severity.INFO,
            },
            "no-security-hardening": {
                "description": "Service missing security hardening",
                "severity": Severity.INFO,
            },
            "running-as-root": {
                "description": "Container running as root",
                "severity": Severity.WARNING,
            },
            "host-network-mode": {
                "description": "Container uses host network mode",
                "severity": Severity.WARNING,
            },
        }

    def _build_report(
        self, source: str, issues: List[FormattedIssue]
    ) -> FormattedReport:
        """Build a validation report."""
        error_count = sum(1 for i in issues if i.severity in (Severity.ERROR, Severity.CRITICAL))
        warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)
        info_count = sum(1 for i in issues if i.severity == Severity.INFO)

        return FormattedReport(
            title=f"Docker Compose Validation: {source}",
            summary=f"Found {error_count} errors, {warning_count} warnings, {info_count} info",
            issues=issues,
            stats={
                "total_issues": len(issues),
                "errors": error_count,
                "warnings": warning_count,
                "info": info_count,
            },
            metadata={"source": source},
        )
