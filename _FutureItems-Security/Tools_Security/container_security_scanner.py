#!/usr/bin/env python3
"""
Container Security Scanner
Analyzes Dockerfiles and container configurations for security issues.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ContainerSecurityIssue:
    """Represents a container security issue."""
    file_path: str
    line_number: int
    severity: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class ContainerSecurityScanner:
    """Scans container configurations for security issues."""

    # Dockerfile patterns
    DOCKERFILE_PATTERNS = [
        {
            'pattern': r'^FROM\s+.*:latest',
            'severity': 'MEDIUM',
            'type': 'latest_tag',
            'description': 'Using :latest tag is unpredictable',
            'recommendation': 'Pin specific version: FROM image:1.2.3'
        },
        {
            'pattern': r'^USER\s+root',
            'severity': 'HIGH',
            'type': 'root_user',
            'description': 'Container runs as root',
            'recommendation': 'Create non-root user: USER appuser'
        },
        {
            'pattern': r'^(?!.*USER\s+\w)',
            'severity': 'MEDIUM',
            'type': 'no_user_directive',
            'description': 'No USER directive (defaults to root)',
            'recommendation': 'Add USER directive with non-root user'
        },
        {
            'pattern': r'(?:curl|wget).*\|\s*(?:bash|sh)',
            'severity': 'CRITICAL',
            'type': 'curl_bash',
            'description': 'Piping curl/wget to shell is dangerous',
            'recommendation': 'Download, verify, then execute scripts'
        },
        {
            'pattern': r'(?:password|passwd|secret|key|token)\s*[=:]\s*[\'"][^\'"]+[\'"]',
            'severity': 'CRITICAL',
            'type': 'hardcoded_secret',
            'description': 'Hardcoded secret in Dockerfile',
            'recommendation': 'Use build args or secrets management'
        },
        {
            'pattern': r'^ADD\s+(?:https?://|ftp://)',
            'severity': 'HIGH',
            'type': 'add_remote',
            'description': 'ADD with remote URL is risky',
            'recommendation': 'Use COPY with verified local files'
        },
        {
            'pattern': r'^EXPOSE\s+22',
            'severity': 'MEDIUM',
            'type': 'ssh_exposed',
            'description': 'SSH port exposed',
            'recommendation': 'Avoid SSH in containers, use docker exec'
        },
        {
            'pattern': r'apt-get\s+(?:install|upgrade)(?!.*--no-install-recommends)',
            'severity': 'LOW',
            'type': 'no_recommends',
            'description': 'Installing unnecessary packages',
            'recommendation': 'Use --no-install-recommends'
        },
        {
            'pattern': r'apt-get\s+(?!.*&&.*rm.*apt)',
            'severity': 'LOW',
            'type': 'apt_cache',
            'description': 'apt cache not cleaned',
            'recommendation': 'Clean apt cache: && rm -rf /var/lib/apt/lists/*'
        },
        {
            'pattern': r'^RUN\s+chmod\s+777',
            'severity': 'HIGH',
            'type': 'chmod_777',
            'description': 'World-writable permissions',
            'recommendation': 'Use minimal required permissions'
        },
        {
            'pattern': r'(?:npm|pip|gem)\s+install(?!.*--production|.*--only=prod)',
            'severity': 'LOW',
            'type': 'dev_dependencies',
            'description': 'May install dev dependencies',
            'recommendation': 'Install only production dependencies'
        },
        {
            'pattern': r'^COPY\s+\.\s+',
            'severity': 'MEDIUM',
            'type': 'copy_all',
            'description': 'Copying entire directory may include secrets',
            'recommendation': 'Copy specific files, use .dockerignore'
        },
        {
            'pattern': r'HEALTHCHECK\s+NONE',
            'severity': 'MEDIUM',
            'type': 'no_healthcheck',
            'description': 'Health check disabled',
            'recommendation': 'Implement proper health check'
        },
        {
            'pattern': r'--privileged',
            'severity': 'CRITICAL',
            'type': 'privileged_mode',
            'description': 'Privileged mode gives full host access',
            'recommendation': 'Avoid privileged mode, use specific capabilities'
        },
        {
            'pattern': r'(?:SYS_ADMIN|CAP_SYS_ADMIN)',
            'severity': 'HIGH',
            'type': 'sys_admin_cap',
            'description': 'SYS_ADMIN capability is dangerous',
            'recommendation': 'Use minimal required capabilities'
        },
    ]

    # Docker Compose patterns
    COMPOSE_PATTERNS = [
        {
            'pattern': r'privileged:\s*true',
            'severity': 'CRITICAL',
            'type': 'privileged_container',
            'description': 'Container running in privileged mode',
            'recommendation': 'Remove privileged: true'
        },
        {
            'pattern': r'network_mode:\s*[\'"]?host',
            'severity': 'HIGH',
            'type': 'host_network',
            'description': 'Container using host network',
            'recommendation': 'Use bridge network with port mapping'
        },
        {
            'pattern': r'pid:\s*[\'"]?host',
            'severity': 'HIGH',
            'type': 'host_pid',
            'description': 'Container sharing host PID namespace',
            'recommendation': 'Remove pid: host'
        },
        {
            'pattern': r'/var/run/docker\.sock',
            'severity': 'CRITICAL',
            'type': 'docker_socket',
            'description': 'Docker socket mounted (container escape risk)',
            'recommendation': 'Avoid mounting Docker socket'
        },
        {
            'pattern': r'(?:volumes|bind).*:\s*/(?:etc|root|home)',
            'severity': 'HIGH',
            'type': 'sensitive_mount',
            'description': 'Sensitive host directory mounted',
            'recommendation': 'Mount only necessary directories'
        },
        {
            'pattern': r'cap_add:.*(?:ALL|SYS_ADMIN|NET_ADMIN)',
            'severity': 'HIGH',
            'type': 'dangerous_capability',
            'description': 'Dangerous capability added',
            'recommendation': 'Use minimal required capabilities'
        },
        {
            'pattern': r'security_opt:.*(?:no-new-privileges:false|seccomp:unconfined|apparmor:unconfined)',
            'severity': 'HIGH',
            'type': 'security_disabled',
            'description': 'Security feature disabled',
            'recommendation': 'Keep security features enabled'
        },
        {
            'pattern': r'(?:MYSQL_ROOT_PASSWORD|POSTGRES_PASSWORD):\s*[\'"]?[^\'"$\{]{1,20}[\'"]?',
            'severity': 'HIGH',
            'type': 'weak_db_password',
            'description': 'Database password may be weak/hardcoded',
            'recommendation': 'Use strong passwords from secrets'
        },
    ]

    # Kubernetes patterns
    K8S_PATTERNS = [
        {
            'pattern': r'privileged:\s*true',
            'severity': 'CRITICAL',
            'type': 'privileged_pod',
            'description': 'Pod running in privileged mode',
            'recommendation': 'Set privileged: false'
        },
        {
            'pattern': r'runAsUser:\s*0',
            'severity': 'HIGH',
            'type': 'root_user',
            'description': 'Container running as root',
            'recommendation': 'Set runAsUser to non-zero UID'
        },
        {
            'pattern': r'allowPrivilegeEscalation:\s*true',
            'severity': 'HIGH',
            'type': 'privilege_escalation',
            'description': 'Privilege escalation allowed',
            'recommendation': 'Set allowPrivilegeEscalation: false'
        },
        {
            'pattern': r'hostNetwork:\s*true',
            'severity': 'HIGH',
            'type': 'host_network',
            'description': 'Pod using host network',
            'recommendation': 'Set hostNetwork: false'
        },
        {
            'pattern': r'hostPID:\s*true',
            'severity': 'HIGH',
            'type': 'host_pid',
            'description': 'Pod sharing host PID namespace',
            'recommendation': 'Set hostPID: false'
        },
        {
            'pattern': r'hostIPC:\s*true',
            'severity': 'MEDIUM',
            'type': 'host_ipc',
            'description': 'Pod sharing host IPC namespace',
            'recommendation': 'Set hostIPC: false'
        },
        {
            'pattern': r'readOnlyRootFilesystem:\s*false',
            'severity': 'MEDIUM',
            'type': 'writable_rootfs',
            'description': 'Root filesystem is writable',
            'recommendation': 'Set readOnlyRootFilesystem: true'
        },
        {
            'pattern': r'capabilities:.*add:.*(?:ALL|SYS_ADMIN|NET_ADMIN)',
            'severity': 'HIGH',
            'type': 'dangerous_capability',
            'description': 'Dangerous capability added',
            'recommendation': 'Use minimal required capabilities'
        },
    ]

    def __init__(self):
        self.issues: List[ContainerSecurityIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {
            'dockerfile': [(re.compile(p['pattern'], re.IGNORECASE | re.MULTILINE), p) for p in self.DOCKERFILE_PATTERNS],
            'compose': [(re.compile(p['pattern'], re.IGNORECASE), p) for p in self.COMPOSE_PATTERNS],
            'k8s': [(re.compile(p['pattern'], re.IGNORECASE), p) for p in self.K8S_PATTERNS],
        }

    def detect_file_type(self, file_path: Path) -> str:
        """Detect container config file type."""
        name = file_path.name.lower()

        if name == 'dockerfile' or name.endswith('.dockerfile'):
            return 'dockerfile'
        elif name in {'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'}:
            return 'compose'
        elif file_path.suffix in {'.yml', '.yaml'}:
            # Check content for k8s indicators
            try:
                with open(file_path, 'r') as f:
                    content = f.read(500)
                    if 'kind:' in content and 'apiVersion:' in content:
                        return 'k8s'
            except IOError:
                pass

        return ''

    def scan_file(self, file_path: Path) -> List[ContainerSecurityIssue]:
        """Scan a single file for container security issues."""
        issues = []
        file_type = self.detect_file_type(file_path)

        if not file_type:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        # Check patterns
        for regex, config in self.compiled_patterns[file_type]:
            for line_num, line in enumerate(lines, 1):
                if regex.search(line):
                    issue = ContainerSecurityIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=config['severity'],
                        issue_type=config['type'],
                        code_snippet=line.strip()[:150],
                        description=config['description'],
                        recommendation=config['recommendation']
                    )
                    issues.append(issue)

        # Check for missing USER directive in Dockerfile
        if file_type == 'dockerfile':
            if not any('USER' in line.upper() for line in lines if not line.strip().startswith('#')):
                issues.append(ContainerSecurityIssue(
                    file_path=str(file_path),
                    line_number=0,
                    severity='MEDIUM',
                    issue_type='no_user_directive',
                    code_snippet='',
                    description='No USER directive (defaults to root)',
                    recommendation='Add USER directive with non-root user'
                ))

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[ContainerSecurityIssue]:
        """Scan directory for container security issues."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

        if recursive:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    file_path = Path(root) / file
                    issues = self.scan_file(file_path)
                    all_issues.extend(issues)
        else:
            for item in directory.iterdir():
                if item.is_file():
                    issues = self.scan_file(item)
                    all_issues.extend(issues)

        self.issues = all_issues
        return all_issues

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_issues': len(self.issues),
            'files_scanned': self.files_scanned,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.issue_type not in summary['by_type']:
                summary['by_type'][issue.issue_type] = 0
            summary['by_type'][issue.issue_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("CONTAINER SECURITY SCAN")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\n" + "-" * 70)
            print("SECURITY ISSUES FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.issue_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                if issue.code_snippet:
                    print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No container security issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan container configs for security issues'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='File or directory to scan (default: current directory)'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='Scan directories recursively (default: True)'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not scan directories recursively'
    )

    args = parser.parse_args()
    scanner = ContainerSecurityScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning container configs: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
        scanner.issues = scanner.issues
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
