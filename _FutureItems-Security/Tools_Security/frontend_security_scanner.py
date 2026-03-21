#!/usr/bin/env python3
"""
Frontend Security Scanner
Detects client-side security vulnerabilities in frontend code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class FrontendSecurityIssue:
    """Represents a frontend security issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class FrontendSecurityScanner:
    """Scans frontend code for client-side security vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'dom_xss': [
            {
                'pattern': r'(?:location|document\.URL|document\.documentURI|document\.referrer|window\.name).*(?:innerHTML|outerHTML|document\.write)',
                'severity': 'CRITICAL',
                'type': 'dom_xss_source_sink',
                'description': 'DOM XSS: tainted source flows to dangerous sink',
                'recommendation': 'Sanitize data before inserting into DOM'
            },
            {
                'pattern': r'(?:location\.hash|location\.search|location\.href).*(?:eval|setTimeout|setInterval|Function)',
                'severity': 'CRITICAL',
                'type': 'dom_xss_code_exec',
                'description': 'DOM XSS: URL data used in code execution',
                'recommendation': 'Never execute code from URL parameters'
            },
            {
                'pattern': r'document\.write\s*\(\s*(?:location|document\.URL|unescape|decodeURI)',
                'severity': 'CRITICAL',
                'type': 'document_write_tainted',
                'description': 'document.write with tainted data',
                'recommendation': 'Use safe DOM manipulation methods'
            },
        ],
        'prototype_pollution': [
            {
                'pattern': r'Object\.assign\s*\(\s*\{\s*\}\s*,.*(?:req\.|request\.|params\.|body\.)',
                'severity': 'HIGH',
                'type': 'object_assign_pollution',
                'description': 'Object.assign with user input (prototype pollution)',
                'recommendation': 'Validate keys, filter __proto__ and constructor'
            },
            {
                'pattern': r'(?:merge|extend|deepCopy|clone)\s*\([^)]*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'deep_merge_pollution',
                'description': 'Deep merge with user input',
                'recommendation': 'Use libraries with prototype pollution protection'
            },
            {
                'pattern': r'\[(?:key|prop|name|k)\]\s*=.*(?:req\.|request\.|params\.)',
                'severity': 'MEDIUM',
                'type': 'dynamic_property_assignment',
                'description': 'Dynamic property assignment with user input',
                'recommendation': 'Validate property names against allowlist'
            },
            {
                'pattern': r'__proto__|constructor\s*\[|prototype\s*\[',
                'severity': 'HIGH',
                'type': 'direct_prototype_access',
                'description': 'Direct prototype access detected',
                'recommendation': 'Avoid direct prototype manipulation'
            },
        ],
        'postmessage': [
            {
                'pattern': r'addEventListener\s*\(\s*[\'"]message[\'"].*(?!.*origin)',
                'severity': 'HIGH',
                'type': 'postmessage_no_origin',
                'description': 'postMessage listener without origin check',
                'recommendation': 'Always verify event.origin'
            },
            {
                'pattern': r'postMessage\s*\([^)]*,\s*[\'"]\*[\'"]',
                'severity': 'HIGH',
                'type': 'postmessage_wildcard',
                'description': 'postMessage with wildcard origin',
                'recommendation': 'Specify exact target origin'
            },
            {
                'pattern': r'addEventListener\s*\(\s*[\'"]message[\'"].*(?:eval|innerHTML|document\.write)',
                'severity': 'CRITICAL',
                'type': 'postmessage_dangerous_sink',
                'description': 'postMessage data used in dangerous sink',
                'recommendation': 'Validate and sanitize message data'
            },
        ],
        'storage_security': [
            {
                'pattern': r'localStorage\.setItem\s*\([^)]*(?:password|token|secret|key|session|auth)',
                'severity': 'HIGH',
                'type': 'sensitive_localstorage',
                'description': 'Sensitive data in localStorage',
                'recommendation': 'Use HttpOnly cookies for sensitive data'
            },
            {
                'pattern': r'sessionStorage\.setItem\s*\([^)]*(?:password|token|secret|key|auth)',
                'severity': 'MEDIUM',
                'type': 'sensitive_sessionstorage',
                'description': 'Sensitive data in sessionStorage',
                'recommendation': 'Consider HttpOnly cookies instead'
            },
            {
                'pattern': r'(?:localStorage|sessionStorage)\.getItem.*(?:eval|innerHTML|document\.write)',
                'severity': 'HIGH',
                'type': 'storage_to_sink',
                'description': 'Storage data used in dangerous sink',
                'recommendation': 'Sanitize data from storage before use'
            },
        ],
        'unsafe_redirects': [
            {
                'pattern': r'(?:location\.href|location\.replace|location\.assign|window\.open)\s*=?\s*(?:\(?\s*)?(?:params\.|query\.|req\.|request\.)',
                'severity': 'HIGH',
                'type': 'open_redirect',
                'description': 'Open redirect vulnerability',
                'recommendation': 'Validate URLs against allowlist'
            },
            {
                'pattern': r'(?:location\.href|window\.location)\s*=\s*(?:document\.URL|location\.hash|location\.search)',
                'severity': 'MEDIUM',
                'type': 'url_redirect',
                'description': 'Redirect using URL components',
                'recommendation': 'Validate redirect destinations'
            },
        ],
        'unsafe_html': [
            {
                'pattern': r'\.innerHTML\s*=\s*(?!.*(?:sanitize|escape|encode|DOMPurify))',
                'severity': 'HIGH',
                'type': 'innerhtml_assignment',
                'description': 'innerHTML assignment without sanitization',
                'recommendation': 'Use textContent or sanitize with DOMPurify'
            },
            {
                'pattern': r'\.outerHTML\s*=',
                'severity': 'HIGH',
                'type': 'outerhtml_assignment',
                'description': 'outerHTML assignment',
                'recommendation': 'Use safe DOM methods'
            },
            {
                'pattern': r'document\.write\s*\(|document\.writeln\s*\(',
                'severity': 'MEDIUM',
                'type': 'document_write',
                'description': 'document.write usage',
                'recommendation': 'Use DOM manipulation methods'
            },
            {
                'pattern': r'insertAdjacentHTML\s*\(',
                'severity': 'MEDIUM',
                'type': 'insert_adjacent_html',
                'description': 'insertAdjacentHTML usage',
                'recommendation': 'Sanitize content before insertion'
            },
        ],
        'eval_usage': [
            {
                'pattern': r'eval\s*\(',
                'severity': 'HIGH',
                'type': 'eval',
                'description': 'eval() usage',
                'recommendation': 'Avoid eval, use JSON.parse for data'
            },
            {
                'pattern': r'new\s+Function\s*\(',
                'severity': 'HIGH',
                'type': 'function_constructor',
                'description': 'Function constructor usage',
                'recommendation': 'Avoid dynamic code generation'
            },
            {
                'pattern': r'setTimeout\s*\(\s*[\'"`]|setInterval\s*\(\s*[\'"`]',
                'severity': 'MEDIUM',
                'type': 'timer_string',
                'description': 'setTimeout/setInterval with string',
                'recommendation': 'Pass function reference instead'
            },
        ],
        'cors_issues': [
            {
                'pattern': r'Access-Control-Allow-Origin.*\*',
                'severity': 'MEDIUM',
                'type': 'cors_wildcard',
                'description': 'CORS wildcard origin',
                'recommendation': 'Specify allowed origins explicitly'
            },
            {
                'pattern': r'credentials:\s*[\'"]include[\'"].*mode:\s*[\'"]cors[\'"]',
                'severity': 'MEDIUM',
                'type': 'cors_credentials',
                'description': 'CORS request with credentials',
                'recommendation': 'Ensure server validates origin'
            },
        ],
        'clickjacking': [
            {
                'pattern': r'(?:top|parent|self)\s*(?:!==|!=|===|==)\s*(?:top|parent|self)',
                'severity': 'LOW',
                'type': 'frame_busting',
                'description': 'JavaScript frame busting (can be bypassed)',
                'recommendation': 'Use X-Frame-Options or CSP frame-ancestors'
            },
        ],
        'sensitive_exposure': [
            {
                'pattern': r'(?:api[_-]?key|apikey|secret|password|token|auth).*[\'"`][A-Za-z0-9+/=_-]{20,}[\'"`]',
                'severity': 'CRITICAL',
                'type': 'hardcoded_secret',
                'description': 'Hardcoded secret in frontend code',
                'recommendation': 'Never expose secrets in client-side code'
            },
            {
                'pattern': r'console\.(?:log|info|debug|warn)\s*\([^)]*(?:password|token|secret|key|auth)',
                'severity': 'MEDIUM',
                'type': 'sensitive_console',
                'description': 'Sensitive data in console output',
                'recommendation': 'Remove sensitive logging in production'
            },
        ],
        'third_party': [
            {
                'pattern': r'<script[^>]+src\s*=\s*[\'"](?:http:|\/\/)[^\'"]+[\'"][^>]*(?!integrity)',
                'severity': 'MEDIUM',
                'type': 'no_sri',
                'description': 'External script without SRI',
                'recommendation': 'Add integrity attribute for external scripts'
            },
            {
                'pattern': r'(?:cdn|unpkg|jsdelivr|cloudflare).*(?!integrity)',
                'severity': 'LOW',
                'type': 'cdn_no_sri',
                'description': 'CDN resource without integrity check',
                'recommendation': 'Use Subresource Integrity (SRI)'
            },
        ],
        'react_specific': [
            {
                'pattern': r'dangerouslySetInnerHTML',
                'severity': 'HIGH',
                'type': 'react_dangerous_html',
                'description': 'React dangerouslySetInnerHTML',
                'recommendation': 'Sanitize with DOMPurify before use'
            },
            {
                'pattern': r'href\s*=\s*\{.*(?:user|input|params|query)',
                'severity': 'MEDIUM',
                'type': 'react_href_injection',
                'description': 'Dynamic href in React (potential XSS)',
                'recommendation': 'Validate URLs, block javascript: protocol'
            },
        ],
        'angular_specific': [
            {
                'pattern': r'bypassSecurityTrust(?:Html|Script|Style|Url|ResourceUrl)',
                'severity': 'HIGH',
                'type': 'angular_bypass_security',
                'description': 'Angular security bypass',
                'recommendation': 'Avoid bypassing Angular sanitization'
            },
            {
                'pattern': r'\[innerHTML\]\s*=',
                'severity': 'MEDIUM',
                'type': 'angular_innerhtml',
                'description': 'Angular innerHTML binding',
                'recommendation': 'Use DomSanitizer properly'
            },
        ],
        'vue_specific': [
            {
                'pattern': r'v-html\s*=',
                'severity': 'HIGH',
                'type': 'vue_vhtml',
                'description': 'Vue v-html directive',
                'recommendation': 'Sanitize content or use v-text'
            },
            {
                'pattern': r':href\s*=.*(?:user|input|params)',
                'severity': 'MEDIUM',
                'type': 'vue_dynamic_href',
                'description': 'Vue dynamic href binding',
                'recommendation': 'Validate URL before binding'
            },
        ],
    }

    def __init__(self):
        self.issues: List[FrontendSecurityIssue] = []
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

    def is_frontend_file(self, file_path: Path) -> bool:
        """Check if file is a frontend file."""
        frontend_extensions = {
            '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
            '.html', '.htm', '.ejs', '.hbs', '.pug'
        }
        return file_path.suffix.lower() in frontend_extensions

    def scan_file(self, file_path: Path) -> List[FrontendSecurityIssue]:
        """Scan a single file for frontend security issues."""
        issues = []

        if not self.is_frontend_file(file_path):
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
                        issue = FrontendSecurityIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[FrontendSecurityIssue]:
        """Scan directory for frontend security issues."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', 'coverage'}

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
        print("FRONTEND SECURITY SCAN")
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
            print("\n✓ No frontend security issues detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan frontend code for client-side security issues'
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
    scanner = FrontendSecurityScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning frontend security: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
