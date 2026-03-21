#!/usr/bin/env python3
"""
Input Validation Scanner
Detects missing or improper input validation vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ValidationIssue:
    """Represents an input validation issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class InputValidationScanner:
    """Scans for input validation vulnerabilities."""

    VALIDATION_PATTERNS = {
        'type_coercion': [
            {
                'pattern': r'parseInt\s*\(\s*(?:req\.|request\.|params\.|body\.|query\.)[^,)]+\s*\)',
                'severity': 'MEDIUM',
                'type': 'unsafe_parseint',
                'description': 'parseInt without radix or validation',
                'recommendation': 'Add radix parameter and validate input'
            },
            {
                'pattern': r'Number\s*\(\s*(?:req\.|request\.|params\.|body\.)',
                'severity': 'MEDIUM',
                'type': 'unsafe_number_coercion',
                'description': 'Number coercion without validation',
                'recommendation': 'Validate numeric input before coercion'
            },
            {
                'pattern': r'(?:JSON\.parse|json\.loads)\s*\(\s*(?:req\.|request\.|body\.|params\.)',
                'severity': 'HIGH',
                'type': 'unsafe_json_parse',
                'description': 'JSON parsing without try-catch',
                'recommendation': 'Wrap JSON parsing in try-catch'
            },
        ],
        'array_access': [
            {
                'pattern': r'\[\s*(?:req\.|request\.|params\.|query\.|body\.)[^\]]+\s*\]',
                'severity': 'MEDIUM',
                'type': 'unvalidated_array_index',
                'description': 'Array access with user input',
                'recommendation': 'Validate array index bounds'
            },
        ],
        'string_operations': [
            {
                'pattern': r'\.substring\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'LOW',
                'type': 'unvalidated_substring',
                'description': 'substring with user-controlled index',
                'recommendation': 'Validate string indices'
            },
            {
                'pattern': r'\.split\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'LOW',
                'type': 'user_controlled_split',
                'description': 'split with user-controlled delimiter',
                'recommendation': 'Sanitize delimiter input'
            },
        ],
        'regex_input': [
            {
                'pattern': r'(?:new\s+RegExp|re\.compile)\s*\(\s*(?:req\.|request\.|params\.|body\.)',
                'severity': 'HIGH',
                'type': 'user_controlled_regex',
                'description': 'Regex created from user input',
                'recommendation': 'Sanitize or avoid user-controlled regex'
            },
        ],
        'file_operations': [
            {
                'pattern': r'(?:readFile|writeFile|open|fopen)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'path_from_input',
                'description': 'File path from user input',
                'recommendation': 'Validate and sanitize file paths'
            },
            {
                'pattern': r'path\.join\s*\([^)]*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'path_join_input',
                'description': 'path.join with user input',
                'recommendation': 'Validate path components'
            },
        ],
        'url_operations': [
            {
                'pattern': r'(?:redirect|location\.href|window\.location)\s*=\s*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'open_redirect',
                'description': 'Redirect to user-controlled URL',
                'recommendation': 'Validate redirect URLs against whitelist'
            },
            {
                'pattern': r'(?:fetch|axios|http\.get|requests\.get)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'ssrf_potential',
                'description': 'HTTP request to user-controlled URL',
                'recommendation': 'Validate and whitelist URLs'
            },
        ],
        'database_queries': [
            {
                'pattern': r'(?:find|findOne|where|query)\s*\(\s*\{\s*[^}]*:\s*(?:req\.|request\.|params\.)',
                'severity': 'MEDIUM',
                'type': 'nosql_injection',
                'description': 'NoSQL query with user input',
                'recommendation': 'Sanitize MongoDB/NoSQL queries'
            },
            {
                'pattern': r'(?:ORDER BY|GROUP BY|LIMIT|OFFSET)\s+[\'"`]?\s*\+\s*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'sql_clause_injection',
                'description': 'SQL clause with user input',
                'recommendation': 'Use parameterized queries'
            },
        ],
        'command_execution': [
            {
                'pattern': r'(?:exec|spawn|system|popen)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'command_injection',
                'description': 'Command execution with user input',
                'recommendation': 'Never pass user input to shell commands'
            },
        ],
        'html_output': [
            {
                'pattern': r'(?:innerHTML|outerHTML|document\.write)\s*=\s*(?:req\.|request\.|params\.|data\.)',
                'severity': 'HIGH',
                'type': 'xss_dom',
                'description': 'DOM manipulation with user data',
                'recommendation': 'Use textContent or sanitize HTML'
            },
            {
                'pattern': r'(?:render|send|write)\s*\([^)]*(?:req\.|request\.|params\.)(?![^)]*(?:escape|sanitize|encode))',
                'severity': 'MEDIUM',
                'type': 'potential_xss',
                'description': 'Output may contain unsanitized input',
                'recommendation': 'Escape output for context'
            },
        ],
        'length_validation': [
            {
                'pattern': r'(?:password|email|username|name)\s*=\s*(?:req\.|request\.|body\.)(?![^;]*(?:length|trim|slice))',
                'severity': 'LOW',
                'type': 'no_length_check',
                'description': 'String input without length validation',
                'recommendation': 'Validate minimum and maximum length'
            },
        ],
        'type_checking': [
            {
                'pattern': r'(?:if|while|for)\s*\([^)]*(?:req\.|request\.|params\.)\w+(?!\s*(?:===|!==|typeof))',
                'severity': 'LOW',
                'type': 'loose_comparison',
                'description': 'Loose comparison with user input',
                'recommendation': 'Use strict equality operators'
            },
        ],
        'buffer_operations': [
            {
                'pattern': r'Buffer\.(?:alloc|from)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'buffer_from_input',
                'description': 'Buffer created from user input',
                'recommendation': 'Validate buffer size limits'
            },
        ],
        'deserialization': [
            {
                'pattern': r'(?:pickle\.loads|yaml\.load|unserialize)\s*\(\s*(?:req\.|request\.|body\.)',
                'severity': 'CRITICAL',
                'type': 'unsafe_deserialization',
                'description': 'Deserialization of user input',
                'recommendation': 'Use safe deserialization methods'
            },
        ],
        'template_injection': [
            {
                'pattern': r'(?:Template|render_template_string|Jinja2)\s*\(\s*(?:req\.|request\.|body\.)',
                'severity': 'CRITICAL',
                'type': 'template_injection',
                'description': 'Template with user-controlled input',
                'recommendation': 'Never use user input in templates'
            },
        ],
        'email_validation': [
            {
                'pattern': r'(?:sendmail|send_mail|smtp)\s*\([^)]*(?:req\.|request\.|body\.)(?![^)]*(?:validate|sanitize))',
                'severity': 'MEDIUM',
                'type': 'email_injection',
                'description': 'Email with unvalidated input',
                'recommendation': 'Validate email addresses and content'
            },
        ],
    }

    def __init__(self):
        self.issues: List[ValidationIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for category, patterns in self.VALIDATION_PATTERNS.items():
            self.compiled_patterns[category] = []
            for p in patterns:
                try:
                    self.compiled_patterns[category].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def scan_file(self, file_path: Path) -> List[ValidationIssue]:
        """Scan a single file for validation issues."""
        issues = []

        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.rb', '.php', '.java', '.go', '.cs'}
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
                        issue = ValidationIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[ValidationIssue]:
        """Scan directory for validation issues."""
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
        print("INPUT VALIDATION SCAN")
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
            print("INPUT VALIDATION ISSUES")
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
            print("\n✓ No input validation issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan for input validation vulnerabilities'
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
    scanner = InputValidationScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for input validation issues: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
