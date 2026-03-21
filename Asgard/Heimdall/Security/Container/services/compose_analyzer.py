"""
Heimdall Docker Compose Analyzer Service

Service for detecting security issues in docker-compose.yml files.
"""

import fnmatch
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerConfig,
    ContainerFinding,
    ContainerReport,
)
from Asgard.Heimdall.Security.Container.services._compose_checks import (
    check_capabilities,
    check_environment_secrets,
    check_exposed_ports,
    check_image_tag,
    check_network_mode,
    check_pid_mode,
    check_privileged,
    check_read_only,
    check_security_opt,
    check_volumes,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class ComposeAnalyzer:
    """
    Analyzes docker-compose.yml files for security issues.

    Detects:
    - Privileged containers
    - Host network mode
    - Host PID namespace
    - Dangerous capabilities (CAP_SYS_ADMIN, etc.)
    - Secrets in environment variables
    - Insecure volume mounts
    - No security options
    - Latest tags in images
    - Exposed sensitive ports
    """

    def __init__(self, config: Optional[ContainerConfig] = None):
        """
        Initialize the Compose analyzer.

        Args:
            config: Container security configuration. Uses defaults if not provided.
        """
        self.config = config or ContainerConfig()

    def scan(self, scan_path: Optional[Path] = None) -> ContainerReport:
        """
        Scan the specified path for docker-compose security issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            ContainerReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = ContainerReport(scan_path=str(path))

        compose_files = self._find_compose_files(path)

        for compose_path in compose_files:
            report.total_files_scanned += 1
            report.compose_files_analyzed += 1
            findings = self._analyze_compose_file(compose_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)
                    report.compose_issues += 1

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _find_compose_files(self, root_path: Path) -> List[Path]:
        """
        Find all docker-compose files in the given path.

        Args:
            root_path: Root directory to search

        Returns:
            List of paths to docker-compose files
        """
        compose_files: List[Path] = []

        def _is_excluded(path: Path) -> bool:
            for pattern in self.config.exclude_patterns:
                if fnmatch.fnmatch(path.name, pattern):
                    return True
                if any(fnmatch.fnmatch(part, pattern) for part in path.parts):
                    return True
            return False

        def _matches_compose_pattern(name: str) -> bool:
            for pattern in self.config.compose_names:
                if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name.lower(), pattern.lower()):
                    return True
            return False

        def _scan_recursive(current_path: Path) -> None:
            try:
                for entry in current_path.iterdir():
                    if _is_excluded(entry):
                        continue

                    if entry.is_dir():
                        _scan_recursive(entry)
                    elif entry.is_file():
                        if _matches_compose_pattern(entry.name):
                            compose_files.append(entry)
            except PermissionError:
                pass

        _scan_recursive(root_path)
        return compose_files

    def _analyze_compose_file(self, file_path: Path, root_path: Path) -> List[ContainerFinding]:
        """
        Analyze a single docker-compose file for security issues.

        Args:
            file_path: Path to the docker-compose file
            root_path: Root path for relative path calculation

        Returns:
            List of container security findings
        """
        findings: List[ContainerFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        relative_path = str(file_path.relative_to(root_path))

        try:
            compose_data = yaml.safe_load(content)
        except yaml.YAMLError:
            return findings

        if not compose_data or not isinstance(compose_data, dict):
            return findings

        services = compose_data.get("services", {})
        if not isinstance(services, dict):
            return findings

        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                continue

            service_line = self._find_service_line(lines, service_name)

            findings.extend(check_privileged(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_network_mode(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_pid_mode(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_capabilities(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_environment_secrets(
                service_name, service_config, lines, relative_path, service_line,
                self.config.secret_env_patterns,
            ))
            findings.extend(check_volumes(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_security_opt(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_image_tag(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_read_only(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(check_exposed_ports(
                service_name, service_config, lines, relative_path, service_line,
                self.config.check_ports,
                self.config.sensitive_ports,
            ))

        return findings

    def _find_service_line(self, lines: List[str], service_name: str) -> int:
        """
        Find the line number where a service is defined.

        Args:
            lines: File lines
            service_name: Name of the service

        Returns:
            Line number (1-indexed) or 1 if not found
        """
        pattern = rf"^\s*{re.escape(service_name)}\s*:"
        for i, line in enumerate(lines, start=1):
            if re.match(pattern, line):
                return i
        return 1

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity level meets the configured threshold."""
        severity_order = {
            SecuritySeverity.INFO.value: 0,
            SecuritySeverity.LOW.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.HIGH.value: 3,
            SecuritySeverity.CRITICAL.value: 4,
        }

        min_level = severity_order.get(self.config.min_severity, 1)
        finding_level = severity_order.get(severity, 1)

        return finding_level >= min_level

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            SecuritySeverity.CRITICAL.value: 0,
            SecuritySeverity.HIGH.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.LOW.value: 3,
            SecuritySeverity.INFO.value: 4,
        }
        return order.get(severity, 5)
