#!/usr/bin/env python3
"""
Sensitive Data Exposure Scanner
Detects exposed sensitive data, PII, and hardcoded secrets in code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SensitiveDataIssue:
    """Represents sensitive data exposure."""
    file_path: str
    line_number: int
    severity: str
    data_type: str
    pattern_type: str
    masked_value: str
    description: str
    recommendation: str


class SensitiveDataScanner:
    """Scans for exposed sensitive data and PII."""

    SENSITIVE_PATTERNS = {
        'credentials': [
            {
                'pattern': r'(?:password|passwd|pwd|pass)\s*(?:=|:)\s*[\'"`]([^\'"` ]{4,})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'hardcoded_password',
                'description': 'Hardcoded password',
                'recommendation': 'Use environment variables or secrets manager'
            },
            {
                'pattern': r'(?:api[_-]?key|apikey)\s*(?:=|:)\s*[\'"`]([A-Za-z0-9_-]{16,})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'api_key',
                'description': 'Hardcoded API key',
                'recommendation': 'Store in environment variables'
            },
            {
                'pattern': r'(?:secret[_-]?key|secretkey)\s*(?:=|:)\s*[\'"`]([^\'"` ]{8,})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'secret_key',
                'description': 'Hardcoded secret key',
                'recommendation': 'Use secrets management'
            },
            {
                'pattern': r'(?:auth[_-]?token|access[_-]?token)\s*(?:=|:)\s*[\'"`]([A-Za-z0-9_.-]{20,})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'auth_token',
                'description': 'Hardcoded authentication token',
                'recommendation': 'Never hardcode tokens'
            },
        ],
        'pii': [
            {
                'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
                'severity': 'CRITICAL',
                'type': 'ssn',
                'description': 'Social Security Number pattern',
                'recommendation': 'Remove or encrypt SSN data'
            },
            {
                'pattern': r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
                'severity': 'CRITICAL',
                'type': 'credit_card',
                'description': 'Credit card number pattern',
                'recommendation': 'Never store credit card numbers in code'
            },
            {
                'pattern': r'\b[A-Z]{2}\d{6,9}\b',
                'severity': 'HIGH',
                'type': 'passport',
                'description': 'Passport number pattern',
                'recommendation': 'Remove or encrypt passport data'
            },
        ],
        'private_keys': [
            {
                'pattern': r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
                'severity': 'CRITICAL',
                'type': 'private_key',
                'description': 'Private key in code',
                'recommendation': 'Store keys securely, never in code'
            },
            {
                'pattern': r'-----BEGIN PGP PRIVATE KEY BLOCK-----',
                'severity': 'CRITICAL',
                'type': 'pgp_private_key',
                'description': 'PGP private key in code',
                'recommendation': 'Use secure key storage'
            },
        ],
        'cloud_credentials': [
            {
                'pattern': r'AKIA[0-9A-Z]{16}',
                'severity': 'CRITICAL',
                'type': 'aws_access_key',
                'description': 'AWS Access Key ID',
                'recommendation': 'Use IAM roles or secrets manager'
            },
            {
                'pattern': r'(?:aws[_-]?secret|secret[_-]?access[_-]?key)\s*(?:=|:)\s*[\'"`]([A-Za-z0-9/+=]{40})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'aws_secret_key',
                'description': 'AWS Secret Access Key',
                'recommendation': 'Use IAM roles or AWS Secrets Manager'
            },
            {
                'pattern': r'(?:gcp|google)[_-]?(?:api[_-]?key|credentials|service[_-]?account)',
                'severity': 'HIGH',
                'type': 'gcp_credentials',
                'description': 'GCP credentials reference',
                'recommendation': 'Use workload identity or secret manager'
            },
            {
                'pattern': r'(?:azure|az)[_-]?(?:storage[_-]?key|subscription|client[_-]?secret)',
                'severity': 'HIGH',
                'type': 'azure_credentials',
                'description': 'Azure credentials reference',
                'recommendation': 'Use managed identity or Key Vault'
            },
        ],
        'database': [
            {
                'pattern': r'(?:mongodb|mysql|postgres|redis|mssql)://[^\s\'"`<>]+:[^\s\'"`<>]+@',
                'severity': 'CRITICAL',
                'type': 'database_url',
                'description': 'Database URL with credentials',
                'recommendation': 'Use environment variables'
            },
            {
                'pattern': r'(?:db[_-]?password|database[_-]?password)\s*(?:=|:)\s*[\'"`]([^\'"` ]+)[\'"`]',
                'severity': 'CRITICAL',
                'type': 'db_password',
                'description': 'Database password',
                'recommendation': 'Use secrets management'
            },
        ],
        'tokens': [
            {
                'pattern': r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}',
                'severity': 'CRITICAL',
                'type': 'github_token',
                'description': 'GitHub token',
                'recommendation': 'Use GitHub Actions secrets'
            },
            {
                'pattern': r'(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}',
                'severity': 'CRITICAL',
                'type': 'stripe_key',
                'description': 'Stripe API key',
                'recommendation': 'Use environment variables'
            },
            {
                'pattern': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*',
                'severity': 'CRITICAL',
                'type': 'slack_token',
                'description': 'Slack token',
                'recommendation': 'Use Slack app configuration'
            },
            {
                'pattern': r'(?:SG\.)[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}',
                'severity': 'CRITICAL',
                'type': 'sendgrid_key',
                'description': 'SendGrid API key',
                'recommendation': 'Use environment variables'
            },
            {
                'pattern': r'(?:twilio|TWILIO).*(?:SK|AC)[a-f0-9]{32}',
                'severity': 'HIGH',
                'type': 'twilio_key',
                'description': 'Twilio credentials',
                'recommendation': 'Use environment variables'
            },
        ],
        'jwt': [
            {
                'pattern': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
                'severity': 'HIGH',
                'type': 'jwt_token',
                'description': 'JWT token in code',
                'recommendation': 'Never hardcode JWT tokens'
            },
        ],
        'encryption': [
            {
                'pattern': r'(?:encryption[_-]?key|cipher[_-]?key|aes[_-]?key)\s*(?:=|:)\s*[\'"`]([^\'"` ]{8,})[\'"`]',
                'severity': 'CRITICAL',
                'type': 'encryption_key',
                'description': 'Hardcoded encryption key',
                'recommendation': 'Use key management service'
            },
            {
                'pattern': r'(?:iv|nonce)\s*(?:=|:)\s*[\'"`]([A-Za-z0-9+/=]{16,})[\'"`]',
                'severity': 'HIGH',
                'type': 'hardcoded_iv',
                'description': 'Hardcoded IV/nonce',
                'recommendation': 'Generate IV randomly for each encryption'
            },
        ],
        'urls': [
            {
                'pattern': r'https?://[^\s\'"`<>]*:[^\s\'"`<>@]+@',
                'severity': 'HIGH',
                'type': 'url_credentials',
                'description': 'URL with embedded credentials',
                'recommendation': 'Use authentication headers instead'
            },
        ],
        'internal': [
            {
                'pattern': r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b',
                'severity': 'LOW',
                'type': 'internal_ip',
                'description': 'Internal IP address',
                'recommendation': 'Use configuration files for IPs'
            },
            {
                'pattern': r'(?:localhost|127\.0\.0\.1):\d{4,5}',
                'severity': 'LOW',
                'type': 'localhost_port',
                'description': 'Localhost with port',
                'recommendation': 'Use environment-based configuration'
            },
        ],
    }

    def __init__(self):
        self.issues: List[SensitiveDataIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for data_type, patterns in self.SENSITIVE_PATTERNS.items():
            self.compiled_patterns[data_type] = []
            for p in patterns:
                try:
                    self.compiled_patterns[data_type].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def mask_value(self, value: str) -> str:
        """Mask sensitive value for safe display."""
        if len(value) <= 8:
            return '*' * len(value)
        return value[:4] + '*' * (len(value) - 8) + value[-4:]

    def scan_file(self, file_path: Path) -> List[SensitiveDataIssue]:
        """Scan a single file for sensitive data."""
        issues = []

        # Skip binary and media files
        skip_extensions = {'.pyc', '.exe', '.dll', '.so', '.jpg', '.png', '.gif', '.pdf', '.zip'}
        if file_path.suffix.lower() in skip_extensions:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for data_type, patterns in self.compiled_patterns.items():
                for pattern_config in patterns:
                    match = pattern_config['regex'].search(line)
                    if match:
                        # Get matched value
                        matched = match.group(1) if match.groups() else match.group(0)

                        issue = SensitiveDataIssue(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=pattern_config['severity'],
                            data_type=data_type,
                            pattern_type=pattern_config['type'],
                            masked_value=self.mask_value(matched),
                            description=pattern_config['description'],
                            recommendation=pattern_config['recommendation']
                        )
                        issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[SensitiveDataIssue]:
        """Scan directory for sensitive data."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor', 'dist', 'build'}

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
            'by_data_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.data_type not in summary['by_data_type']:
                summary['by_data_type'][issue.data_type] = 0
            summary['by_data_type'][issue.data_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("SENSITIVE DATA EXPOSURE SCAN")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\nBy Data Type:")
            for data_type, count in sorted(summary['by_data_type'].items(), key=lambda x: -x[1]):
                print(f"  {data_type}: {count}")

            print("\n" + "-" * 70)
            print("SENSITIVE DATA FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.pattern_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Value: {issue.masked_value}")
                print(f"  {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No sensitive data exposure detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan for exposed sensitive data and PII'
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
    scanner = SensitiveDataScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for sensitive data: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
