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
    ContainerFindingType,
    ContainerReport,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import extract_code_snippet
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

            findings.extend(self._check_privileged(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_network_mode(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_pid_mode(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_capabilities(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_environment_secrets(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_volumes(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_security_opt(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_image_tag(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_read_only(
                service_name, service_config, lines, relative_path, service_line
            ))
            findings.extend(self._check_exposed_ports(
                service_name, service_config, lines, relative_path, service_line
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

    def _check_privileged(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for privileged containers."""
        findings: List[ContainerFinding] = []

        if service_config.get("privileged", False):
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=service_line,
                finding_type=ContainerFindingType.PRIVILEGED_MODE,
                severity=SecuritySeverity.CRITICAL,
                title="Privileged Container",
                description=f"Service '{service_name}' runs in privileged mode, giving it full access to the host.",
                code_snippet=extract_code_snippet(lines, service_line),
                service_name=service_name,
                cwe_id="CWE-250",
                confidence=0.95,
                remediation="Remove privileged: true. Use specific capabilities instead if needed.",
                references=[
                    "https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities",
                    "https://cwe.mitre.org/data/definitions/250.html",
                ],
            ))

        return findings

    def _check_network_mode(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for host network mode."""
        findings: List[ContainerFinding] = []

        network_mode = service_config.get("network_mode", "")
        if network_mode == "host":
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=service_line,
                finding_type=ContainerFindingType.HOST_NETWORK,
                severity=SecuritySeverity.HIGH,
                title="Host Network Mode",
                description=f"Service '{service_name}' uses host network mode, bypassing Docker network isolation.",
                code_snippet=extract_code_snippet(lines, service_line),
                service_name=service_name,
                cwe_id="CWE-653",
                confidence=0.95,
                remediation="Use Docker networks instead of host network mode for better isolation.",
                references=[
                    "https://docs.docker.com/network/",
                ],
            ))

        return findings

    def _check_pid_mode(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for host PID namespace."""
        findings: List[ContainerFinding] = []

        pid_mode = service_config.get("pid", "")
        if pid_mode == "host":
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=service_line,
                finding_type=ContainerFindingType.HOST_PID,
                severity=SecuritySeverity.HIGH,
                title="Host PID Namespace",
                description=f"Service '{service_name}' shares the host PID namespace, allowing it to see and interact with all host processes.",
                code_snippet=extract_code_snippet(lines, service_line),
                service_name=service_name,
                cwe_id="CWE-653",
                confidence=0.95,
                remediation="Remove pid: host unless absolutely necessary for debugging.",
                references=[
                    "https://docs.docker.com/engine/reference/run/#pid-settings---pid",
                ],
            ))

        return findings

    def _check_capabilities(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for dangerous capabilities."""
        findings: List[ContainerFinding] = []

        dangerous_caps = {
            "SYS_ADMIN": "Allows mounting filesystems, loading kernel modules, and more",
            "NET_ADMIN": "Allows full network administration",
            "SYS_PTRACE": "Allows process tracing and debugging",
            "DAC_READ_SEARCH": "Allows bypassing file read permission checks",
            "ALL": "Grants all capabilities",
        }

        cap_add = service_config.get("cap_add", [])
        if isinstance(cap_add, list):
            for cap in cap_add:
                cap_upper = str(cap).upper()
                if cap_upper in dangerous_caps:
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.CAP_SYS_ADMIN,
                        severity=SecuritySeverity.HIGH,
                        title=f"Dangerous Capability: {cap_upper}",
                        description=f"Service '{service_name}' has {cap_upper} capability. {dangerous_caps[cap_upper]}.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-250",
                        confidence=0.9,
                        remediation="Remove this capability and use more specific, less privileged alternatives.",
                        references=[
                            "https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities",
                        ],
                    ))

        return findings

    def _check_environment_secrets(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for secrets in environment variables."""
        findings: List[ContainerFinding] = []

        environment = service_config.get("environment", {})

        env_list: List[str] = []
        if isinstance(environment, dict):
            env_list = [f"{k}={v}" for k, v in environment.items() if v is not None]
        elif isinstance(environment, list):
            env_list = [str(e) for e in environment]

        for env_entry in env_list:
            if "=" not in env_entry:
                continue

            key, value = env_entry.split("=", 1)

            for pattern in self.config.secret_env_patterns:
                if re.search(pattern, key, re.IGNORECASE):
                    if value and not value.startswith("${") and not value.startswith("$"):
                        findings.append(ContainerFinding(
                            file_path=file_path,
                            line_number=service_line,
                            finding_type=ContainerFindingType.HARDCODED_SECRET,
                            severity=SecuritySeverity.CRITICAL,
                            title="Hardcoded Secret in Environment",
                            description=f"Service '{service_name}' has a hardcoded secret in environment variable '{key}'.",
                            code_snippet=extract_code_snippet(lines, service_line),
                            service_name=service_name,
                            cwe_id="CWE-798",
                            confidence=0.85,
                            remediation="Use Docker secrets, environment files, or external secret management.",
                            references=[
                                "https://docs.docker.com/compose/use-secrets/",
                                "https://cwe.mitre.org/data/definitions/798.html",
                            ],
                        ))
                    break

        return findings

    def _check_volumes(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for dangerous volume mounts."""
        findings: List[ContainerFinding] = []

        dangerous_mounts = {
            "/": "Root filesystem",
            "/etc": "System configuration",
            "/var/run/docker.sock": "Docker socket",
            "/proc": "Process information",
            "/sys": "System information",
        }

        volumes = service_config.get("volumes", [])
        if isinstance(volumes, list):
            for volume in volumes:
                volume_str = str(volume)

                if ":" in volume_str:
                    parts = volume_str.split(":")
                    host_path = parts[0]
                else:
                    host_path = volume_str

                for dangerous_path, description in dangerous_mounts.items():
                    if host_path == dangerous_path or host_path.startswith(dangerous_path + "/"):
                        findings.append(ContainerFinding(
                            file_path=file_path,
                            line_number=service_line,
                            finding_type=ContainerFindingType.UNRESTRICTED_VOLUME,
                            severity=SecuritySeverity.HIGH,
                            title=f"Dangerous Volume Mount: {dangerous_path}",
                            description=f"Service '{service_name}' mounts {dangerous_path} ({description}) from the host.",
                            code_snippet=extract_code_snippet(lines, service_line),
                            service_name=service_name,
                            cwe_id="CWE-250",
                            confidence=0.9,
                            remediation="Avoid mounting sensitive host paths. Use named volumes or specific subdirectories.",
                            references=[
                                "https://docs.docker.com/storage/volumes/",
                            ],
                        ))
                        break

        return findings

    def _check_security_opt(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for disabled security options."""
        findings: List[ContainerFinding] = []

        security_opt = service_config.get("security_opt", [])
        if isinstance(security_opt, list):
            for opt in security_opt:
                opt_str = str(opt).lower()

                if "apparmor:unconfined" in opt_str:
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.NO_SECURITY_OPT,
                        severity=SecuritySeverity.HIGH,
                        title="AppArmor Disabled",
                        description=f"Service '{service_name}' runs with AppArmor disabled.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-693",
                        confidence=0.9,
                        remediation="Use the default AppArmor profile or create a custom profile.",
                        references=[
                            "https://docs.docker.com/engine/security/apparmor/",
                        ],
                    ))

                if "seccomp:unconfined" in opt_str:
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.NO_SECURITY_OPT,
                        severity=SecuritySeverity.HIGH,
                        title="Seccomp Disabled",
                        description=f"Service '{service_name}' runs with seccomp disabled.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-693",
                        confidence=0.9,
                        remediation="Use the default seccomp profile or create a custom profile.",
                        references=[
                            "https://docs.docker.com/engine/security/seccomp/",
                        ],
                    ))

        return findings

    def _check_image_tag(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for latest tag in images."""
        findings: List[ContainerFinding] = []

        image = service_config.get("image", "")
        if isinstance(image, str):
            if ":" not in image or image.endswith(":latest"):
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=service_line,
                    finding_type=ContainerFindingType.LATEST_TAG,
                    severity=SecuritySeverity.MEDIUM,
                    title="Using :latest Tag",
                    description=f"Service '{service_name}' uses :latest tag or no tag for image '{image}'.",
                    code_snippet=extract_code_snippet(lines, service_line),
                    service_name=service_name,
                    cwe_id="CWE-829",
                    confidence=0.85,
                    remediation="Pin images to specific version tags or digest hashes.",
                    references=[
                        "https://docs.docker.com/engine/reference/commandline/tag/",
                    ],
                ))

        return findings

    def _check_read_only(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for writable root filesystem."""
        findings: List[ContainerFinding] = []

        if not service_config.get("read_only", False):
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=service_line,
                finding_type=ContainerFindingType.WRITABLE_ROOT_FS,
                severity=SecuritySeverity.LOW,
                title="Writable Root Filesystem",
                description=f"Service '{service_name}' has a writable root filesystem.",
                code_snippet=extract_code_snippet(lines, service_line),
                service_name=service_name,
                cwe_id="CWE-732",
                confidence=0.6,
                remediation="Consider adding read_only: true and using volumes for writable paths.",
                references=[
                    "https://docs.docker.com/compose/compose-file/05-services/#read_only",
                ],
            ))

        return findings

    def _check_exposed_ports(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        lines: List[str],
        file_path: str,
        service_line: int
    ) -> List[ContainerFinding]:
        """Check for exposed sensitive ports."""
        findings: List[ContainerFinding] = []

        if not self.config.check_ports:
            return findings

        ports = service_config.get("ports", [])
        if isinstance(ports, list):
            for port_mapping in ports:
                port_str = str(port_mapping)

                port_match = re.search(r":(\d+)(?:/|$)", port_str)
                if port_match:
                    container_port = int(port_match.group(1))
                    if container_port in self.config.sensitive_ports:
                        findings.append(ContainerFinding(
                            file_path=file_path,
                            line_number=service_line,
                            finding_type=ContainerFindingType.EXPOSED_PORTS,
                            severity=SecuritySeverity.MEDIUM,
                            title=f"Sensitive Port {container_port} Exposed",
                            description=f"Service '{service_name}' exposes port {container_port}.",
                            code_snippet=extract_code_snippet(lines, service_line),
                            service_name=service_name,
                            cwe_id="CWE-200",
                            confidence=0.7,
                            remediation="Consider if this port needs to be exposed publicly.",
                            references=[
                                "https://docs.docker.com/compose/compose-file/05-services/#ports",
                            ],
                        ))

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
