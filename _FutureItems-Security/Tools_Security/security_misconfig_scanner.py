#!/usr/bin/env python3
"""
Security Misconfiguration Scanner
Detects security misconfigurations in code and configuration files.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class MisconfigIssue:
    """Represents a security misconfiguration."""
    file_path: str
    line_number: int
    severity: str
    category: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class SecurityMisconfigScanner:
    """Scans for security misconfigurations."""

    MISCONFIG_PATTERNS = {
        'debug_mode': [
            {
                'pattern': r'(?:DEBUG|debug)\s*(?:=|:)\s*(?:True|true|1|yes|on)',
                'severity': 'HIGH',
                'type': 'debug_enabled',
                'description': 'Debug mode enabled',
                'recommendation': 'Disable debug mode in production'
            },
            {
                'pattern': r'(?:NODE_ENV|FLASK_ENV|RAILS_ENV|APP_ENV)\s*(?:=|:)\s*[\'"`]?(?:development|dev)[\'"`]?',
                'severity': 'MEDIUM',
                'type': 'dev_environment',
                'description': 'Development environment configuration',
                'recommendation': 'Use production environment in deployment'
            },
            {
                'pattern': r'(?:FLASK_DEBUG|DJANGO_DEBUG)\s*(?:=|:)\s*(?:True|true|1)',
                'severity': 'HIGH',
                'type': 'framework_debug',
                'description': 'Framework debug mode enabled',
                'recommendation': 'Disable framework debug in production'
            },
        ],
        'default_credentials': [
            {
                'pattern': r'(?:password|passwd|pwd)\s*(?:=|:)\s*[\'"`](?:admin|password|123456|root|default|test)[\'"`]',
                'severity': 'CRITICAL',
                'type': 'default_password',
                'description': 'Default/weak password',
                'recommendation': 'Use strong, unique passwords'
            },
            {
                'pattern': r'(?:user|username|login)\s*(?:=|:)\s*[\'"`](?:admin|root|test|user)[\'"`]',
                'severity': 'MEDIUM',
                'type': 'default_username',
                'description': 'Default username',
                'recommendation': 'Avoid common usernames'
            },
        ],
        'insecure_protocols': [
            {
                'pattern': r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
                'severity': 'MEDIUM',
                'type': 'http_protocol',
                'description': 'HTTP instead of HTTPS',
                'recommendation': 'Use HTTPS for all external connections'
            },
            {
                'pattern': r'ftp://[^\s\'"`]+',
                'severity': 'MEDIUM',
                'type': 'ftp_protocol',
                'description': 'FTP protocol (unencrypted)',
                'recommendation': 'Use SFTP or FTPS instead'
            },
            {
                'pattern': r'telnet://[^\s\'"`]+',
                'severity': 'HIGH',
                'type': 'telnet_protocol',
                'description': 'Telnet protocol (unencrypted)',
                'recommendation': 'Use SSH instead of Telnet'
            },
        ],
        'ssl_tls': [
            {
                'pattern': r'(?:ssl|tls).*(?:verify|check)\s*(?:=|:)\s*(?:False|false|0|no)',
                'severity': 'CRITICAL',
                'type': 'ssl_verify_disabled',
                'description': 'SSL/TLS verification disabled',
                'recommendation': 'Always verify SSL certificates'
            },
            {
                'pattern': r'(?:SSLv2|SSLv3|TLSv1\.0|TLSv1\.1)',
                'severity': 'HIGH',
                'type': 'weak_tls',
                'description': 'Weak SSL/TLS version',
                'recommendation': 'Use TLS 1.2 or higher'
            },
            {
                'pattern': r'(?:CERT_NONE|VERIFY_NONE|InsecureRequestWarning)',
                'severity': 'CRITICAL',
                'type': 'cert_validation_disabled',
                'description': 'Certificate validation disabled',
                'recommendation': 'Enable certificate validation'
            },
        ],
        'cors': [
            {
                'pattern': r'(?:Access-Control-Allow-Origin|cors.*origin)\s*(?:=|:)\s*[\'"`]\*[\'"`]',
                'severity': 'MEDIUM',
                'type': 'cors_wildcard',
                'description': 'CORS allows all origins',
                'recommendation': 'Whitelist specific origins'
            },
            {
                'pattern': r'(?:Access-Control-Allow-Credentials)\s*(?:=|:)\s*(?:True|true|[\'"`]true[\'"`])',
                'severity': 'MEDIUM',
                'type': 'cors_credentials',
                'description': 'CORS with credentials enabled',
                'recommendation': 'Ensure origin is properly validated'
            },
        ],
        'session': [
            {
                'pattern': r'(?:session|cookie).*(?:secure)\s*(?:=|:)\s*(?:False|false|0)',
                'severity': 'HIGH',
                'type': 'insecure_cookie',
                'description': 'Cookie secure flag disabled',
                'recommendation': 'Enable secure flag for cookies'
            },
            {
                'pattern': r'(?:httponly|http_only)\s*(?:=|:)\s*(?:False|false|0)',
                'severity': 'MEDIUM',
                'type': 'no_httponly',
                'description': 'HTTPOnly flag disabled',
                'recommendation': 'Enable HTTPOnly for session cookies'
            },
            {
                'pattern': r'(?:samesite)\s*(?:=|:)\s*[\'"`]?(?:None|none)[\'"`]?',
                'severity': 'MEDIUM',
                'type': 'samesite_none',
                'description': 'SameSite=None on cookies',
                'recommendation': 'Use SameSite=Strict or Lax'
            },
        ],
        'database': [
            {
                'pattern': r'(?:ALLOW_EMPTY_PASSWORD|allow_empty_password)\s*(?:=|:)\s*(?:True|true|yes|1)',
                'severity': 'CRITICAL',
                'type': 'empty_db_password',
                'description': 'Empty database password allowed',
                'recommendation': 'Require strong database passwords'
            },
            {
                'pattern': r'(?:bind[-_]?address|host)\s*(?:=|:)\s*[\'"`]?0\.0\.0\.0[\'"`]?',
                'severity': 'MEDIUM',
                'type': 'bind_all_interfaces',
                'description': 'Service bound to all interfaces',
                'recommendation': 'Bind to specific interface or localhost'
            },
        ],
        'logging': [
            {
                'pattern': r'(?:log|logging).*(?:level)\s*(?:=|:)\s*[\'"`]?(?:DEBUG|TRACE)[\'"`]?',
                'severity': 'LOW',
                'type': 'verbose_logging',
                'description': 'Verbose logging in production',
                'recommendation': 'Use INFO or WARN level in production'
            },
            {
                'pattern': r'(?:password|secret|token|key).*(?:log|print|console)',
                'severity': 'HIGH',
                'type': 'logging_sensitive',
                'description': 'Potentially logging sensitive data',
                'recommendation': 'Never log secrets or passwords'
            },
        ],
        'docker': [
            {
                'pattern': r'(?:privileged)\s*(?:=|:)\s*(?:True|true)',
                'severity': 'CRITICAL',
                'type': 'privileged_container',
                'description': 'Privileged container',
                'recommendation': 'Avoid privileged containers'
            },
            {
                'pattern': r'USER\s+root',
                'severity': 'MEDIUM',
                'type': 'root_user',
                'description': 'Container running as root',
                'recommendation': 'Use non-root user in containers'
            },
            {
                'pattern': r'(?:--cap-add|cap_add).*(?:ALL|SYS_ADMIN)',
                'severity': 'HIGH',
                'type': 'excessive_capabilities',
                'description': 'Excessive container capabilities',
                'recommendation': 'Use minimal required capabilities'
            },
        ],
        'cloud': [
            {
                'pattern': r'(?:public[-_]?access|public[-_]?read)\s*(?:=|:)\s*(?:True|true|enabled)',
                'severity': 'HIGH',
                'type': 'public_access',
                'description': 'Public access enabled',
                'recommendation': 'Restrict public access'
            },
            {
                'pattern': r'(?:encryption)\s*(?:=|:)\s*(?:False|false|disabled|none)',
                'severity': 'HIGH',
                'type': 'encryption_disabled',
                'description': 'Encryption disabled',
                'recommendation': 'Enable encryption at rest'
            },
        ],
        'secrets': [
            {
                'pattern': r'(?:SECRET_KEY|JWT_SECRET)\s*(?:=|:)\s*[\'"`](?:changeme|secret|default|your-secret)[\'"`]',
                'severity': 'CRITICAL',
                'type': 'default_secret',
                'description': 'Default/placeholder secret key',
                'recommendation': 'Generate strong random secret'
            },
        ],
        'admin': [
            {
                'pattern': r'(?:admin|manage|control).*(?:url|path|route)\s*(?:=|:)\s*[\'"`]/admin[\'"`]',
                'severity': 'LOW',
                'type': 'predictable_admin',
                'description': 'Predictable admin URL',
                'recommendation': 'Use non-obvious admin paths'
            },
        ],
        'error_handling': [
            {
                'pattern': r'(?:display_errors|show_errors)\s*(?:=|:)\s*(?:On|on|True|true|1)',
                'severity': 'MEDIUM',
                'type': 'display_errors',
                'description': 'Error display enabled',
                'recommendation': 'Disable error display in production'
            },
        ],
        'xml': [
            {
                'pattern': r'(?:external[-_]?entities|load[-_]?external)\s*(?:=|:)\s*(?:True|true|1)',
                'severity': 'HIGH',
                'type': 'xxe_enabled',
                'description': 'External XML entities enabled',
                'recommendation': 'Disable external entities'
            },
        ],
    }

    def __init__(self):
        self.issues: List[MisconfigIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for category, patterns in self.MISCONFIG_PATTERNS.items():
            self.compiled_patterns[category] = []
            for p in patterns:
                try:
                    self.compiled_patterns[category].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def is_config_file(self, file_path: Path) -> bool:
        """Check if file is a configuration file."""
        config_extensions = {
            '.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.cfg',
            '.env', '.properties', '.xml', '.tf', '.tfvars'
        }
        config_names = {
            'dockerfile', 'docker-compose', 'nginx.conf', 'apache.conf',
            'settings', 'config', 'application', 'web.config'
        }

        if file_path.suffix.lower() in config_extensions:
            return True

        if any(name in file_path.stem.lower() for name in config_names):
            return True

        # Also scan code files
        code_extensions = {'.py', '.js', '.ts', '.rb', '.php', '.java', '.go'}
        return file_path.suffix.lower() in code_extensions

    def scan_file(self, file_path: Path) -> List[MisconfigIssue]:
        """Scan a single file for misconfigurations."""
        issues = []

        if not self.is_config_file(file_path):
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for category, patterns in self.compiled_patterns.items():
                for pattern_config in patterns:
                    if pattern_config['regex'].search(line):
                        issue = MisconfigIssue(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=pattern_config['severity'],
                            category=category,
                            issue_type=pattern_config['type'],
                            code_snippet=line.strip()[:150],
                            description=pattern_config['description'],
                            recommendation=pattern_config['recommendation']
                        )
                        issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[MisconfigIssue]:
        """Scan directory for misconfigurations."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor'}

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
            'by_category': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.category not in summary['by_category']:
                summary['by_category'][issue.category] = 0
            summary['by_category'][issue.category] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("SECURITY MISCONFIGURATION SCAN")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\nBy Category:")
            for category, count in sorted(summary['by_category'].items(), key=lambda x: -x[1]):
                print(f"  {category}: {count}")

            print("\n" + "-" * 70)
            print("MISCONFIGURATIONS FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.category} - {issue.issue_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Config: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No security misconfigurations detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan for security misconfigurations'
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
    scanner = SecurityMisconfigScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for misconfigurations: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
