#!/usr/bin/env python3
"""
Authentication and Session Security Scanner
Detects authentication and session management vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class AuthSecurityIssue:
    """Represents an authentication or session security issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class AuthSecurityScanner:
    """Scans code for authentication and session security issues."""

    VULNERABILITY_PATTERNS = {
        'authentication': [
            {
                'pattern': r'(?:password|passwd|pwd)\s*(?:==|===|\.equals|\.compareTo)\s*[\'"][^\'"]+[\'"]',
                'severity': 'CRITICAL',
                'type': 'hardcoded_password',
                'description': 'Hardcoded password comparison',
                'recommendation': 'Use secure password hashing with bcrypt/argon2'
            },
            {
                'pattern': r'(?:md5|sha1)\s*\(\s*(?:password|passwd|pwd)',
                'severity': 'HIGH',
                'type': 'weak_password_hash',
                'description': 'Weak hash algorithm for password',
                'recommendation': 'Use bcrypt, argon2, or scrypt for passwords'
            },
            {
                'pattern': r'(?:password|passwd|pwd)\s*(?:==|===)\s*(?:request\.|req\.|params\.)',
                'severity': 'HIGH',
                'type': 'timing_attack',
                'description': 'Potential timing attack in password comparison',
                'recommendation': 'Use constant-time comparison function'
            },
            {
                'pattern': r'(?:admin|root)\s*(?:==|===)\s*[\'"](?:admin|root|password|123)',
                'severity': 'CRITICAL',
                'type': 'default_credentials',
                'description': 'Default/weak credentials detected',
                'recommendation': 'Remove default credentials, enforce strong passwords'
            },
            {
                'pattern': r'(?:login|auth).*(?:or\s+[\'"]?1[\'"]?\s*=\s*[\'"]?1|--)',
                'severity': 'CRITICAL',
                'type': 'auth_bypass_sqli',
                'description': 'Potential SQL injection auth bypass',
                'recommendation': 'Use parameterized queries'
            },
            {
                'pattern': r'verify.*=\s*false|validate.*=\s*false',
                'severity': 'HIGH',
                'type': 'verification_disabled',
                'description': 'Verification/validation disabled',
                'recommendation': 'Enable security verification'
            },
        ],
        'session': [
            {
                'pattern': r'session\.?(?:id|token)\s*=\s*(?:request\.|req\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'session_fixation',
                'description': 'Potential session fixation vulnerability',
                'recommendation': 'Regenerate session ID after authentication'
            },
            {
                'pattern': r'(?:setcookie|set_cookie|cookie)\s*\([^)]*(?!HttpOnly|httponly)',
                'severity': 'MEDIUM',
                'type': 'missing_httponly',
                'description': 'Cookie may be missing HttpOnly flag',
                'recommendation': 'Set HttpOnly flag on session cookies'
            },
            {
                'pattern': r'(?:setcookie|set_cookie|cookie)\s*\([^)]*(?!Secure|secure)',
                'severity': 'MEDIUM',
                'type': 'missing_secure',
                'description': 'Cookie may be missing Secure flag',
                'recommendation': 'Set Secure flag for HTTPS-only cookies'
            },
            {
                'pattern': r'session.*(?:timeout|expir).*(?:0|null|false|never)',
                'severity': 'HIGH',
                'type': 'no_session_timeout',
                'description': 'Session timeout disabled or infinite',
                'recommendation': 'Set appropriate session timeout'
            },
            {
                'pattern': r'(?:localStorage|sessionStorage)\.setItem\s*\([^)]*(?:token|session|auth)',
                'severity': 'HIGH',
                'type': 'token_in_storage',
                'description': 'Auth token stored in localStorage/sessionStorage',
                'recommendation': 'Use HttpOnly cookies for auth tokens'
            },
            {
                'pattern': r'document\.cookie\s*=.*(?:token|session|auth)',
                'severity': 'HIGH',
                'type': 'js_cookie_access',
                'description': 'Auth token set via JavaScript',
                'recommendation': 'Set tokens server-side with HttpOnly'
            },
        ],
        'jwt': [
            {
                'pattern': r'algorithm\s*[=:]\s*[\'"]none[\'"]',
                'severity': 'CRITICAL',
                'type': 'jwt_none_algorithm',
                'description': 'JWT none algorithm vulnerability',
                'recommendation': 'Always specify and validate algorithm'
            },
            {
                'pattern': r'(?:jwt|jsonwebtoken).*(?:verify|decode).*(?:false|ignore)',
                'severity': 'CRITICAL',
                'type': 'jwt_verification_disabled',
                'description': 'JWT signature verification disabled',
                'recommendation': 'Always verify JWT signatures'
            },
            {
                'pattern': r'(?:secret|key)\s*[=:]\s*[\'"][^\'"]{1,20}[\'"]',
                'severity': 'HIGH',
                'type': 'weak_jwt_secret',
                'description': 'JWT secret may be too short/weak',
                'recommendation': 'Use at least 256-bit secret'
            },
            {
                'pattern': r'(?:jwt|token).*expiresIn.*(?:365d|[0-9]{5,})',
                'severity': 'MEDIUM',
                'type': 'long_jwt_expiry',
                'description': 'JWT expiration too long',
                'recommendation': 'Use short-lived tokens with refresh'
            },
        ],
        'oauth': [
            {
                'pattern': r'(?:client_secret|clientSecret)\s*[=:]\s*[\'"][^\'"]+[\'"]',
                'severity': 'HIGH',
                'type': 'hardcoded_client_secret',
                'description': 'Hardcoded OAuth client secret',
                'recommendation': 'Store secrets in environment variables'
            },
            {
                'pattern': r'(?:redirect_uri|redirectUri).*(?:request\.|req\.|params\.)',
                'severity': 'HIGH',
                'type': 'open_redirect',
                'description': 'Dynamic redirect URI (open redirect)',
                'recommendation': 'Whitelist allowed redirect URIs'
            },
            {
                'pattern': r'state\s*[=:]\s*(?:null|undefined|false|\'\'|"")',
                'severity': 'HIGH',
                'type': 'missing_oauth_state',
                'description': 'OAuth state parameter missing/disabled',
                'recommendation': 'Always use CSRF-preventing state parameter'
            },
        ],
        'crypto': [
            {
                'pattern': r'(?:generateToken|randomToken)\s*.*(?:Math\.random|random\.random)',
                'severity': 'CRITICAL',
                'type': 'weak_token_generation',
                'description': 'Weak random for security token',
                'recommendation': 'Use cryptographically secure random'
            },
            {
                'pattern': r'(?:api_key|apiKey|api-key)\s*[=:]\s*[\'"][^\'"]+[\'"]',
                'severity': 'HIGH',
                'type': 'hardcoded_api_key',
                'description': 'Hardcoded API key',
                'recommendation': 'Use environment variables'
            },
            {
                'pattern': r'(?:private_key|privateKey)\s*[=:]\s*[\'"]-----BEGIN',
                'severity': 'CRITICAL',
                'type': 'hardcoded_private_key',
                'description': 'Hardcoded private key',
                'recommendation': 'Store keys securely, use key management'
            },
        ],
        'rate_limiting': [
            {
                'pattern': r'(?:login|auth|signin).*(?!rate|limit|throttle)',
                'severity': 'MEDIUM',
                'type': 'no_rate_limiting',
                'description': 'Auth endpoint may lack rate limiting',
                'recommendation': 'Implement rate limiting on auth endpoints'
            },
        ],
        'mfa': [
            {
                'pattern': r'(?:2fa|mfa|totp).*(?:skip|bypass|disable)',
                'severity': 'HIGH',
                'type': 'mfa_bypass',
                'description': 'MFA bypass option detected',
                'recommendation': 'Ensure MFA cannot be bypassed'
            },
        ],
    }

    def __init__(self):
        self.issues: List[AuthSecurityIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for category, patterns in self.VULNERABILITY_PATTERNS.items():
            self.compiled_patterns[category] = []
            for p in patterns:
                try:
                    self.compiled_patterns[category].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def scan_file(self, file_path: Path) -> List[AuthSecurityIssue]:
        """Scan a single file for auth/session issues."""
        issues = []

        # Skip non-code files
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.java', '.rb', '.cs', '.go'}
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
                        issue = AuthSecurityIssue(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=pattern_config['severity'],
                            category=category,
                            pattern_type=pattern_config['type'],
                            code_snippet=line.strip()[:150],
                            description=pattern_config['description'],
                            recommendation=pattern_config['recommendation']
                        )
                        issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[AuthSecurityIssue]:
        """Scan directory for auth/session issues."""
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
            'by_category': {},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.category not in summary['by_category']:
                summary['by_category'][issue.category] = 0
            summary['by_category'][issue.category] += 1
            if issue.pattern_type not in summary['by_type']:
                summary['by_type'][issue.pattern_type] = 0
            summary['by_type'][issue.pattern_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("AUTHENTICATION & SESSION SECURITY SCAN")
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
            print("SECURITY ISSUES FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.category} - {issue.pattern_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No authentication/session security issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for authentication and session security issues'
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
    scanner = AuthSecurityScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for auth/session issues: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
