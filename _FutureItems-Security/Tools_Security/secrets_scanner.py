#!/usr/bin/env python3
"""
Secrets Scanner
Scans files and directories for accidentally committed secrets, API keys, and credentials.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class SecretMatch:
    """Represents a found secret."""
    file_path: str
    line_number: int
    secret_type: str
    matched_text: str
    severity: str
    context: str


class SecretsScanner:
    """Scans for secrets and sensitive data in files."""

    # Pattern definitions with severity levels
    SECRET_PATTERNS = {
        # API Keys
        'AWS Access Key': {
            'pattern': r'AKIA[0-9A-Z]{16}',
            'severity': 'CRITICAL'
        },
        'AWS Secret Key': {
            'pattern': r'(?i)aws[_\-\.]?secret[_\-\.]?(?:access)?[_\-\.]?key[\s]*[=:]+[\s]*[\'"]?([A-Za-z0-9/+=]{40})[\'"]?',
            'severity': 'CRITICAL'
        },
        'Google API Key': {
            'pattern': r'AIza[0-9A-Za-z\-_]{35}',
            'severity': 'HIGH'
        },
        'Google OAuth': {
            'pattern': r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
            'severity': 'HIGH'
        },
        'GitHub Token': {
            'pattern': r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}',
            'severity': 'CRITICAL'
        },
        'GitHub OAuth': {
            'pattern': r'github[_\-\.]?oauth[_\-\.]?token[\s]*[=:]+[\s]*[\'"]?([a-f0-9]{40})[\'"]?',
            'severity': 'CRITICAL'
        },
        'Slack Token': {
            'pattern': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*',
            'severity': 'HIGH'
        },
        'Slack Webhook': {
            'pattern': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24}',
            'severity': 'HIGH'
        },
        'Stripe API Key': {
            'pattern': r'(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}',
            'severity': 'CRITICAL'
        },
        'Square Access Token': {
            'pattern': r'sq0atp-[0-9A-Za-z\-_]{22}',
            'severity': 'HIGH'
        },
        'Twilio API Key': {
            'pattern': r'SK[0-9a-fA-F]{32}',
            'severity': 'HIGH'
        },
        'SendGrid API Key': {
            'pattern': r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}',
            'severity': 'HIGH'
        },
        'Mailgun API Key': {
            'pattern': r'key-[0-9a-zA-Z]{32}',
            'severity': 'HIGH'
        },

        # Credentials
        'Generic Password': {
            'pattern': r'(?i)(?:password|passwd|pwd|pass)[\s]*[=:]+[\s]*[\'"]([^\'"]{8,})[\'"]',
            'severity': 'HIGH'
        },
        'Generic Secret': {
            'pattern': r'(?i)(?:secret|token|api[_\-]?key|apikey|auth[_\-]?token)[\s]*[=:]+[\s]*[\'"]([^\'"]{8,})[\'"]',
            'severity': 'HIGH'
        },
        'Basic Auth': {
            'pattern': r'(?i)basic\s+[a-zA-Z0-9+/=]{20,}',
            'severity': 'HIGH'
        },
        'Bearer Token': {
            'pattern': r'(?i)bearer\s+[a-zA-Z0-9\-_.]+',
            'severity': 'MEDIUM'
        },

        # Private Keys
        'RSA Private Key': {
            'pattern': r'-----BEGIN RSA PRIVATE KEY-----',
            'severity': 'CRITICAL'
        },
        'DSA Private Key': {
            'pattern': r'-----BEGIN DSA PRIVATE KEY-----',
            'severity': 'CRITICAL'
        },
        'EC Private Key': {
            'pattern': r'-----BEGIN EC PRIVATE KEY-----',
            'severity': 'CRITICAL'
        },
        'OpenSSH Private Key': {
            'pattern': r'-----BEGIN OPENSSH PRIVATE KEY-----',
            'severity': 'CRITICAL'
        },
        'PGP Private Key': {
            'pattern': r'-----BEGIN PGP PRIVATE KEY BLOCK-----',
            'severity': 'CRITICAL'
        },

        # Database Credentials
        'Database URL': {
            'pattern': r'(?i)(?:mysql|postgres|postgresql|mongodb|redis)://[^\s]+:[^\s]+@[^\s]+',
            'severity': 'CRITICAL'
        },
        'Connection String': {
            'pattern': r'(?i)(?:server|host)=[^;]+;.*(?:password|pwd)=[^;]+',
            'severity': 'HIGH'
        },

        # Cloud Provider
        'Azure Storage Key': {
            'pattern': r'(?i)AccountKey=[a-zA-Z0-9+/=]{88}',
            'severity': 'CRITICAL'
        },
        'Azure SAS Token': {
            'pattern': r'(?i)sig=[a-zA-Z0-9%]{43,}',
            'severity': 'HIGH'
        },
        'Heroku API Key': {
            'pattern': r'(?i)heroku[_\-\.]?api[_\-\.]?key[\s]*[=:]+[\s]*[\'"]?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})[\'"]?',
            'severity': 'HIGH'
        },

        # Other Secrets
        'JWT Token': {
            'pattern': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
            'severity': 'MEDIUM'
        },
        'NPM Token': {
            'pattern': r'//registry\.npmjs\.org/:_authToken=[a-f0-9-]{36}',
            'severity': 'HIGH'
        },
        'Private URL with Credentials': {
            'pattern': r'(?i)https?://[^\s:]+:[^\s@]+@[^\s]+',
            'severity': 'HIGH'
        },
        'IPv4 with Port': {
            'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b',
            'severity': 'LOW'
        }
    }

    # Files and directories to skip
    SKIP_DIRS = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',
        '.tox', '.pytest_cache', '.mypy_cache', 'dist', 'build', '.eggs'
    }

    SKIP_EXTENSIONS = {
        '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe', '.bin',
        '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.woff',
        '.woff2', '.ttf', '.eot', '.mp3', '.mp4', '.avi', '.mov',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.tar',
        '.gz', '.rar', '.7z'
    }

    def __init__(self):
        self.findings: List[SecretMatch] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile all patterns
        for name, config in self.SECRET_PATTERNS.items():
            try:
                self.compiled_patterns[name] = {
                    'regex': re.compile(config['pattern']),
                    'severity': config['severity']
                }
            except re.error as e:
                print(f"Warning: Invalid pattern for {name}: {e}")

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        # Skip by extension
        if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
            return True

        # Skip binary files
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                if b'\x00' in chunk:
                    return True
        except (IOError, OSError):
            return True

        return False

    def scan_file(self, file_path: Path) -> List[SecretMatch]:
        """Scan a single file for secrets."""
        matches = []

        if self.should_skip_file(file_path):
            return matches

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError) as e:
            return matches

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for secret_name, config in self.compiled_patterns.items():
                match = config['regex'].search(line)
                if match:
                    # Mask the actual secret in the output
                    matched_text = match.group(0)
                    if len(matched_text) > 10:
                        masked = matched_text[:4] + '*' * (len(matched_text) - 8) + matched_text[-4:]
                    else:
                        masked = '*' * len(matched_text)

                    finding = SecretMatch(
                        file_path=str(file_path),
                        line_number=line_num,
                        secret_type=secret_name,
                        matched_text=masked,
                        severity=config['severity'],
                        context=line.strip()[:100]
                    )
                    matches.append(finding)

        return matches

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[SecretMatch]:
        """Scan a directory for secrets."""
        all_matches = []

        if recursive:
            for root, dirs, files in os.walk(directory):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

                for file in files:
                    file_path = Path(root) / file
                    matches = self.scan_file(file_path)
                    all_matches.extend(matches)
        else:
            for item in directory.iterdir():
                if item.is_file():
                    matches = self.scan_file(item)
                    all_matches.extend(matches)

        self.findings = all_matches
        return all_matches

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_findings': len(self.findings),
            'files_scanned': self.files_scanned,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for finding in self.findings:
            summary['by_severity'][finding.severity] += 1
            if finding.secret_type not in summary['by_type']:
                summary['by_type'][finding.secret_type] = 0
            summary['by_type'][finding.secret_type] += 1

        return summary

    def print_report(self, verbose: bool = False):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("SECRETS SCAN REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Findings: {summary['total_findings']}")

        print("\nFindings by Severity:")
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = summary['by_severity'][severity]
            if count > 0:
                print(f"  {severity}: {count}")

        if summary['by_type']:
            print("\nFindings by Type:")
            for secret_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
                print(f"  {secret_type}: {count}")

        if self.findings:
            print("\n" + "-" * 70)
            print("DETAILED FINDINGS")
            print("-" * 70)

            # Sort by severity
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_findings = sorted(self.findings, key=lambda x: severity_order[x.severity])

            for finding in sorted_findings:
                print(f"\n[{finding.severity}] {finding.secret_type}")
                print(f"  File: {finding.file_path}:{finding.line_number}")
                print(f"  Match: {finding.matched_text}")
                if verbose:
                    print(f"  Context: {finding.context}")
        else:
            print("\n✓ No secrets found!")

        print("\n" + "=" * 70)

        # Return exit code
        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0

    def export_json(self, output_file: str):
        """Export findings to JSON."""
        import json

        data = {
            'summary': self.get_summary(),
            'findings': [
                {
                    'file': f.file_path,
                    'line': f.line_number,
                    'type': f.secret_type,
                    'severity': f.severity,
                    'match': f.matched_text
                }
                for f in self.findings
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\nResults exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Scan files for secrets and sensitive data'
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
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output with context'
    )
    parser.add_argument(
        '-o', '--output',
        help='Export results to JSON file'
    )

    args = parser.parse_args()
    scanner = SecretsScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    exit_code = scanner.print_report(verbose=args.verbose)

    if args.output:
        scanner.export_json(args.output)

    return exit_code


if __name__ == '__main__':
    exit(main())
