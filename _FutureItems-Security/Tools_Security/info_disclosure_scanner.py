#!/usr/bin/env python3
"""
Information Disclosure Scanner
Detects information disclosure vulnerabilities in code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class InfoDisclosureIssue:
    """Represents an information disclosure issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class InfoDisclosureScanner:
    """Scans for information disclosure vulnerabilities."""

    DISCLOSURE_PATTERNS = {
        'error_messages': [
            {
                'pattern': r'(?:catch|except)\s*[^{]*\{\s*[^}]*(?:res\.|response\.)?(?:send|json|write)\s*\(\s*(?:err|error|e)(?:\.message|\.stack)?',
                'severity': 'MEDIUM',
                'type': 'error_exposure',
                'description': 'Raw error sent to client',
                'recommendation': 'Return generic error messages'
            },
            {
                'pattern': r'(?:stack|stackTrace|traceback).*(?:res\.|response\.|print|console)',
                'severity': 'HIGH',
                'type': 'stack_trace',
                'description': 'Stack trace exposed',
                'recommendation': 'Never expose stack traces'
            },
            {
                'pattern': r'(?:console\.(?:log|error|warn)|print|System\.out)\s*\(\s*(?:err|error|exception)',
                'severity': 'LOW',
                'type': 'logged_errors',
                'description': 'Errors logged (may appear in client)',
                'recommendation': 'Ensure logs are server-side only'
            },
        ],
        'debug_info': [
            {
                'pattern': r'console\.(?:log|debug|trace)\s*\([^)]*(?:password|secret|token|key|auth)',
                'severity': 'HIGH',
                'type': 'logged_secrets',
                'description': 'Secrets logged to console',
                'recommendation': 'Never log sensitive data'
            },
            {
                'pattern': r'(?:debugger|console\.log|print)\s*\([^)]*(?:req\.|request\.|user\.|session\.)',
                'severity': 'MEDIUM',
                'type': 'request_logging',
                'description': 'Request/session data logged',
                'recommendation': 'Remove debug logging in production'
            },
        ],
        'comments': [
            {
                'pattern': r'(?://|#|/\*)\s*(?:TODO|FIXME|HACK|XXX|BUG).*(?:password|secret|key|token|auth)',
                'severity': 'MEDIUM',
                'type': 'sensitive_comment',
                'description': 'Sensitive data in comments',
                'recommendation': 'Remove sensitive comments'
            },
            {
                'pattern': r'(?://|#|/\*)\s*(?:password|secret|key|token)\s*(?:=|:)\s*\S+',
                'severity': 'HIGH',
                'type': 'credentials_comment',
                'description': 'Credentials in comments',
                'recommendation': 'Never put credentials in comments'
            },
        ],
        'version_info': [
            {
                'pattern': r'(?:X-Powered-By|Server|X-AspNet-Version|X-AspNetMvc-Version)',
                'severity': 'LOW',
                'type': 'server_version',
                'description': 'Server version header exposed',
                'recommendation': 'Remove version headers'
            },
            {
                'pattern': r'(?:version|VERSION)\s*(?:=|:)\s*[\'"`][\d.]+[\'"`].*(?:res\.|response\.)',
                'severity': 'LOW',
                'type': 'version_response',
                'description': 'Version info in response',
                'recommendation': 'Avoid exposing version info'
            },
        ],
        'source_maps': [
            {
                'pattern': r'sourceMappingURL\s*=',
                'severity': 'MEDIUM',
                'type': 'source_map',
                'description': 'Source map reference found',
                'recommendation': 'Disable source maps in production'
            },
        ],
        'internal_paths': [
            {
                'pattern': r'(?:/home/|/Users/|C:\\\\|/var/www/|/opt/)[^\s\'"`]+',
                'severity': 'MEDIUM',
                'type': 'internal_path',
                'description': 'Internal file path exposed',
                'recommendation': 'Use relative paths or configuration'
            },
            {
                'pattern': r'__(?:dirname|filename|file__|FILE__|DIR__)',
                'severity': 'LOW',
                'type': 'path_variable',
                'description': 'Path variable usage',
                'recommendation': 'Ensure not exposed to clients'
            },
        ],
        'database_info': [
            {
                'pattern': r'(?:table|column|schema|database)\s+(?:does not exist|not found)',
                'severity': 'MEDIUM',
                'type': 'db_structure',
                'description': 'Database structure in errors',
                'recommendation': 'Use generic database errors'
            },
            {
                'pattern': r'(?:SQL|query).*(?:error|failed|exception)',
                'severity': 'MEDIUM',
                'type': 'sql_error',
                'description': 'SQL errors exposed',
                'recommendation': 'Hide SQL errors from users'
            },
        ],
        'api_keys': [
            {
                'pattern': r'(?:api[_-]?key|apikey)\s*(?:=|:)\s*[\'"`][A-Za-z0-9_-]{16,}[\'"`]',
                'severity': 'CRITICAL',
                'type': 'exposed_api_key',
                'description': 'API key in source code',
                'recommendation': 'Use environment variables'
            },
        ],
        'user_enumeration': [
            {
                'pattern': r'(?:user|email|account)\s+(?:not found|does not exist|invalid)',
                'severity': 'MEDIUM',
                'type': 'user_enumeration',
                'description': 'User enumeration via error',
                'recommendation': 'Use generic auth error messages'
            },
        ],
        'verbose_responses': [
            {
                'pattern': r'(?:res\.|response\.)?(?:json|send)\s*\(\s*\{[^}]*(?:password|token|secret|ssn|credit)',
                'severity': 'HIGH',
                'type': 'sensitive_response',
                'description': 'Sensitive data in response',
                'recommendation': 'Filter sensitive fields from responses'
            },
            {
                'pattern': r'\.toJSON\s*\(\s*\)|JSON\.stringify\s*\(\s*(?:user|account|profile)\s*\)',
                'severity': 'MEDIUM',
                'type': 'full_object_response',
                'description': 'Full object serialization',
                'recommendation': 'Select specific fields to return'
            },
        ],
        'config_exposure': [
            {
                'pattern': r'(?:config|settings|env)\s*(?:=|:).*(?:res\.|response\.)',
                'severity': 'HIGH',
                'type': 'config_response',
                'description': 'Configuration in response',
                'recommendation': 'Never expose configuration'
            },
        ],
        'internal_ips': [
            {
                'pattern': r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b',
                'severity': 'LOW',
                'type': 'internal_ip',
                'description': 'Internal IP address',
                'recommendation': 'Use configuration for IPs'
            },
        ],
        'jwt_details': [
            {
                'pattern': r'(?:jwt|token).*(?:invalid|expired|malformed).*(?:res\.|response\.)',
                'severity': 'LOW',
                'type': 'jwt_error_detail',
                'description': 'Detailed JWT error',
                'recommendation': 'Use generic token errors'
            },
        ],
        'system_info': [
            {
                'pattern': r'(?:os|process|system)\.(?:platform|arch|version|env)',
                'severity': 'LOW',
                'type': 'system_info',
                'description': 'System information access',
                'recommendation': 'Ensure not exposed to clients'
            },
        ],
        'metadata': [
            {
                'pattern': r'(?:__proto__|constructor|prototype).*(?:res\.|response\.)',
                'severity': 'MEDIUM',
                'type': 'metadata_exposure',
                'description': 'Object metadata in response',
                'recommendation': 'Sanitize object responses'
            },
        ],
        'rate_limit_info': [
            {
                'pattern': r'(?:rate[_-]?limit|too many requests).*(?:try again in|retry after)',
                'severity': 'LOW',
                'type': 'rate_limit_detail',
                'description': 'Rate limit timing exposed',
                'recommendation': 'Avoid precise retry timing'
            },
        ],
    }

    def __init__(self):
        self.issues: List[InfoDisclosureIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for category, patterns in self.DISCLOSURE_PATTERNS.items():
            self.compiled_patterns[category] = []
            for p in patterns:
                try:
                    self.compiled_patterns[category].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def scan_file(self, file_path: Path) -> List[InfoDisclosureIssue]:
        """Scan a single file for information disclosure."""
        issues = []

        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.rb', '.php', '.java', '.go', '.cs', '.vue', '.svelte'}
        if file_path.suffix.lower() not in code_extensions:
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
                        issue = InfoDisclosureIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[InfoDisclosureIssue]:
        """Scan directory for information disclosure."""
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
        print("INFORMATION DISCLOSURE SCAN")
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
            print("INFORMATION DISCLOSURE ISSUES")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.category} - {issue.issue_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No information disclosure issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan for information disclosure vulnerabilities'
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
    scanner = InfoDisclosureScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for information disclosure: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
