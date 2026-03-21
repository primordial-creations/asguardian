"""
Heimdall Dockerfile Analyzer Service

Service for detecting security issues in Dockerfiles.
"""

import fnmatch
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerConfig,
    ContainerFinding,
    ContainerReport,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import (
    parse_dockerfile,
    parse_stages,
)
from Asgard.Heimdall.Security.Container.services._dockerfile_checks import (
    DOCKERFILE_PATTERNS,
    DockerfilePattern,
    check_add_instead_of_copy,
    check_exposed_ports,
    check_latest_tag,
    check_missing_healthcheck,
    check_root_user,
    check_run_patterns,
    check_secrets_in_env,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class DockerfileAnalyzer:
    """
    Analyzes Dockerfiles for security issues.

    Detects:
    - Running as root (missing USER directive)
    - Using :latest tag
    - Secrets in ENV variables
    - Exposed sensitive ports
    - chmod 777
    - apt-get install sudo
    - curl | bash patterns
    - Missing HEALTHCHECK
    - ADD instead of COPY
    """

    def __init__(self, config: Optional[ContainerConfig] = None):
        """
        Initialize the Dockerfile analyzer.

        Args:
            config: Container security configuration. Uses defaults if not provided.
        """
        self.config = config or ContainerConfig()
        self.patterns = DOCKERFILE_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> ContainerReport:
        """
        Scan the specified path for Dockerfile security issues.

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

        dockerfiles = self._find_dockerfiles(path)

        for dockerfile_path in dockerfiles:
            report.total_files_scanned += 1
            report.dockerfiles_analyzed += 1
            findings = self._analyze_dockerfile(dockerfile_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)
                    report.dockerfile_issues += 1

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _find_dockerfiles(self, root_path: Path) -> List[Path]:
        """
        Find all Dockerfiles in the given path.

        Args:
            root_path: Root directory to search

        Returns:
            List of paths to Dockerfiles
        """
        dockerfiles: List[Path] = []

        def _is_excluded(path: Path) -> bool:
            for pattern in self.config.exclude_patterns:
                if fnmatch.fnmatch(path.name, pattern):
                    return True
                if any(fnmatch.fnmatch(part, pattern) for part in path.parts):
                    return True
            return False

        def _matches_dockerfile_pattern(name: str) -> bool:
            for pattern in self.config.dockerfile_names:
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
                        if _matches_dockerfile_pattern(entry.name):
                            dockerfiles.append(entry)
            except PermissionError:
                pass

        _scan_recursive(root_path)
        return dockerfiles

    def _analyze_dockerfile(self, file_path: Path, root_path: Path) -> List[ContainerFinding]:
        """
        Analyze a single Dockerfile for security issues.

        Args:
            file_path: Path to the Dockerfile
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
        instructions = parse_dockerfile(content)
        stages = parse_stages(content)

        relative_path = str(file_path.relative_to(root_path))

        findings.extend(check_root_user(instructions, lines, relative_path))
        findings.extend(check_latest_tag(stages, lines, relative_path))
        findings.extend(check_secrets_in_env(
            instructions, lines, relative_path, self.config.secret_env_patterns,
        ))
        findings.extend(check_exposed_ports(
            instructions, lines, relative_path,
            self.config.check_ports, self.config.sensitive_ports,
        ))
        findings.extend(check_add_instead_of_copy(instructions, lines, relative_path))
        findings.extend(check_missing_healthcheck(instructions, lines, relative_path))
        findings.extend(check_run_patterns(instructions, lines, relative_path, self.patterns))

        return findings

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
