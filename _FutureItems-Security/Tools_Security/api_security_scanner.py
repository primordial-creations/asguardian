#!/usr/bin/env python3
"""
API Security Scanner
Detects security vulnerabilities in REST and GraphQL APIs.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class APISecurityIssue:
    """Represents an API security issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class APISecurityScanner:
    """Scans code for API security vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'authentication': [
            {
                'pattern': r'@(?:app\.route|router\.(?:get|post|put|delete)|Get|Post|Put|Delete)\s*\([^)]+\)(?!.*(?:auth|login|jwt|token|bearer))',
                'severity': 'MEDIUM',
                'type': 'no_auth_check',
                'description': 'API endpoint may lack authentication',
                'recommendation': 'Add authentication middleware'
            },
            {
                'pattern': r'(?:api|endpoint|route).*(?:public|open|unauth)',
                'severity': 'LOW',
                'type': 'public_endpoint',
                'description': 'Explicitly public endpoint',
                'recommendation': 'Verify endpoint should be public'
            },
        ],
        'authorization': [
            {
                'pattern': r'(?:user_id|userId|user\.id)\s*=\s*(?:req\.|request\.|params\.|body\.)',
                'severity': 'HIGH',
                'type': 'idor',
                'description': 'Potential IDOR - user ID from request',
                'recommendation': 'Use authenticated user ID from session/token'
            },
            {
                'pattern': r'(?:findById|find_by_id|get)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'MEDIUM',
                'type': 'direct_object_ref',
                'description': 'Direct object reference from user input',
                'recommendation': 'Verify user has access to resource'
            },
            {
                'pattern': r'(?:admin|role|permission)\s*(?:=|:)\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'privilege_escalation',
                'description': 'Role/permission from user input',
                'recommendation': 'Never trust client-supplied roles'
            },
        ],
        'mass_assignment': [
            {
                'pattern': r'(?:create|update|save)\s*\(\s*(?:req\.body|request\.body|params)',
                'severity': 'HIGH',
                'type': 'mass_assignment',
                'description': 'Mass assignment vulnerability',
                'recommendation': 'Whitelist allowed fields explicitly'
            },
            {
                'pattern': r'Object\.assign\s*\([^,]+,\s*(?:req\.body|request\.body)',
                'severity': 'HIGH',
                'type': 'object_assign_body',
                'description': 'Direct object assignment from request body',
                'recommendation': 'Pick specific allowed fields'
            },
            {
                'pattern': r'\{\s*\.\.\.\s*(?:req\.body|request\.body|params)',
                'severity': 'HIGH',
                'type': 'spread_body',
                'description': 'Spread operator with request body',
                'recommendation': 'Destructure only allowed fields'
            },
        ],
        'rate_limiting': [
            {
                'pattern': r'@(?:app\.route|router)\s*\([^)]*(?:login|auth|password|reset|signup|register)',
                'severity': 'MEDIUM',
                'type': 'auth_no_ratelimit',
                'description': 'Auth endpoint may lack rate limiting',
                'recommendation': 'Add rate limiting to prevent brute force'
            },
        ],
        'data_exposure': [
            {
                'pattern': r'(?:res\.json|response\.json|send)\s*\(\s*(?:user|account|profile)(?!\s*\.\s*(?:toJSON|select|pick))',
                'severity': 'MEDIUM',
                'type': 'excessive_data',
                'description': 'May expose excessive user data',
                'recommendation': 'Select only necessary fields'
            },
            {
                'pattern': r'(?:password|secret|token|ssn|credit).*(?:res\.json|response\.send)',
                'severity': 'CRITICAL',
                'type': 'sensitive_response',
                'description': 'Sensitive data in API response',
                'recommendation': 'Never return sensitive data in responses'
            },
            {
                'pattern': r'\.select\s*\(\s*[\'"]\*[\'"]',
                'severity': 'MEDIUM',
                'type': 'select_all',
                'description': 'Selecting all fields from database',
                'recommendation': 'Select only required fields'
            },
        ],
        'graphql': [
            {
                'pattern': r'introspection\s*:\s*true',
                'severity': 'MEDIUM',
                'type': 'graphql_introspection',
                'description': 'GraphQL introspection enabled',
                'recommendation': 'Disable in production'
            },
            {
                'pattern': r'(?:depthLimit|queryComplexity)\s*:\s*(?:null|undefined|false)',
                'severity': 'HIGH',
                'type': 'graphql_no_limits',
                'description': 'GraphQL without query limits',
                'recommendation': 'Set depth and complexity limits'
            },
            {
                'pattern': r'@(?:Query|Mutation)\s*\([^)]*\)(?!.*@(?:Auth|Authorized|Guard))',
                'severity': 'MEDIUM',
                'type': 'graphql_no_auth',
                'description': 'GraphQL resolver without auth',
                'recommendation': 'Add authorization guards'
            },
        ],
        'input_validation': [
            {
                'pattern': r'(?:req\.body|req\.query|req\.params)\s*\.\s*\w+(?!\s*\.\s*(?:validate|sanitize|trim|escape))',
                'severity': 'LOW',
                'type': 'no_validation',
                'description': 'Input used without visible validation',
                'recommendation': 'Validate and sanitize all input'
            },
            {
                'pattern': r'parseInt\s*\(\s*(?:req\.|request\.|params\.)(?!.*(?:\|\||??|:))',
                'severity': 'LOW',
                'type': 'unsafe_parseint',
                'description': 'parseInt without fallback',
                'recommendation': 'Provide default value or validate'
            },
        ],
        'error_handling': [
            {
                'pattern': r'catch\s*\([^)]*\)\s*\{[^}]*(?:res\.json|send)\s*\(\s*(?:err|error)',
                'severity': 'MEDIUM',
                'type': 'error_disclosure',
                'description': 'Raw error sent to client',
                'recommendation': 'Return generic error messages'
            },
            {
                'pattern': r'stack.*(?:res\.|response\.)',
                'severity': 'HIGH',
                'type': 'stack_trace_exposure',
                'description': 'Stack trace exposed to client',
                'recommendation': 'Never expose stack traces'
            },
        ],
        'cors': [
            {
                'pattern': r'(?:cors|Access-Control-Allow-Origin).*(?:\*|true)',
                'severity': 'MEDIUM',
                'type': 'cors_permissive',
                'description': 'Permissive CORS configuration',
                'recommendation': 'Whitelist specific origins'
            },
            {
                'pattern': r'Access-Control-Allow-Credentials.*true.*Access-Control-Allow-Origin.*(?:req\.|origin)',
                'severity': 'HIGH',
                'type': 'cors_credentials_dynamic',
                'description': 'CORS credentials with dynamic origin',
                'recommendation': 'Validate origin against whitelist'
            },
        ],
        'versioning': [
            {
                'pattern': r'(?:app|router)\.(?:get|post|put|delete)\s*\(\s*[\'"]/(?!v\d|api/v)',
                'severity': 'LOW',
                'type': 'no_api_versioning',
                'description': 'API endpoint without versioning',
                'recommendation': 'Version APIs (e.g., /api/v1/)'
            },
        ],
        'security_headers': [
            {
                'pattern': r'res\.set\s*\(\s*[\'"](?!X-Content-Type|X-Frame|Content-Security|Strict-Transport)',
                'severity': 'LOW',
                'type': 'missing_security_headers',
                'description': 'Custom headers without security headers',
                'recommendation': 'Add security headers (use helmet.js)'
            },
        ],
        'file_upload': [
            {
                'pattern': r'(?:multer|upload|formidable)(?!.*(?:fileFilter|limits|allowedTypes))',
                'severity': 'HIGH',
                'type': 'unsafe_upload',
                'description': 'File upload without restrictions',
                'recommendation': 'Validate file type, size, and name'
            },
            {
                'pattern': r'(?:filename|originalname).*(?:path\.join|writeFile)',
                'severity': 'HIGH',
                'type': 'path_traversal_upload',
                'description': 'Original filename in path (traversal risk)',
                'recommendation': 'Generate safe filenames'
            },
        ],
    }

    def __init__(self):
        self.issues: List[APISecurityIssue] = []
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

    def is_api_file(self, file_path: Path) -> bool:
        """Check if file likely contains API code."""
        api_indicators = ['route', 'controller', 'api', 'endpoint', 'handler', 'resolver']
        name_lower = file_path.stem.lower()

        if any(ind in name_lower for ind in api_indicators):
            return True

        code_extensions = {'.js', '.ts', '.py', '.rb', '.java', '.go', '.php'}
        return file_path.suffix.lower() in code_extensions

    def scan_file(self, file_path: Path) -> List[APISecurityIssue]:
        """Scan a single file for API security issues."""
        issues = []

        if not self.is_api_file(file_path):
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
                        issue = APISecurityIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[APISecurityIssue]:
        """Scan directory for API security issues."""
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
        print("API SECURITY SCAN")
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
            print("API SECURITY ISSUES FOUND")
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
            print("\n✓ No API security issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for API security vulnerabilities'
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
    scanner = APISecurityScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning API security: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
