#!/usr/bin/env python3
"""
XSS Vulnerability Scanner
Scans source code for potential Cross-Site Scripting (XSS) vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class XSSIssue:
    """Represents a potential XSS vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class XSSScanner:
    """Scans code for XSS vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'javascript': [
            {
                'pattern': r'innerHTML\s*=\s*(?!.*sanitize|.*escape|.*encode)',
                'severity': 'HIGH',
                'type': 'innerHTML',
                'description': 'Direct assignment to innerHTML without sanitization',
                'recommendation': 'Use textContent, or sanitize input with DOMPurify'
            },
            {
                'pattern': r'outerHTML\s*=',
                'severity': 'HIGH',
                'type': 'outerHTML',
                'description': 'Direct assignment to outerHTML',
                'recommendation': 'Use safe DOM manipulation methods'
            },
            {
                'pattern': r'document\.write\s*\(',
                'severity': 'HIGH',
                'type': 'document_write',
                'description': 'document.write() can execute scripts',
                'recommendation': 'Use safe DOM methods like createElement()'
            },
            {
                'pattern': r'eval\s*\(',
                'severity': 'CRITICAL',
                'type': 'eval',
                'description': 'eval() executes arbitrary code',
                'recommendation': 'Avoid eval(); use JSON.parse() for data'
            },
            {
                'pattern': r'new\s+Function\s*\(',
                'severity': 'CRITICAL',
                'type': 'function_constructor',
                'description': 'Function constructor executes code like eval()',
                'recommendation': 'Avoid dynamic code execution'
            },
            {
                'pattern': r'setTimeout\s*\(\s*["\']',
                'severity': 'MEDIUM',
                'type': 'setTimeout_string',
                'description': 'setTimeout with string argument (eval-like)',
                'recommendation': 'Pass a function reference instead of string'
            },
            {
                'pattern': r'setInterval\s*\(\s*["\']',
                'severity': 'MEDIUM',
                'type': 'setInterval_string',
                'description': 'setInterval with string argument (eval-like)',
                'recommendation': 'Pass a function reference instead of string'
            },
            {
                'pattern': r'\.html\s*\(\s*(?!.*escape|.*sanitize)',
                'severity': 'HIGH',
                'type': 'jquery_html',
                'description': 'jQuery .html() without sanitization',
                'recommendation': 'Use .text() or sanitize content first'
            },
            {
                'pattern': r'dangerouslySetInnerHTML',
                'severity': 'HIGH',
                'type': 'react_dangerous',
                'description': 'React dangerouslySetInnerHTML',
                'recommendation': 'Sanitize content with DOMPurify before use'
            },
            {
                'pattern': r'\[innerHTML\]',
                'severity': 'HIGH',
                'type': 'angular_innerHTML',
                'description': 'Angular innerHTML binding',
                'recommendation': 'Use Angular DomSanitizer service'
            },
            {
                'pattern': r'v-html\s*=',
                'severity': 'HIGH',
                'type': 'vue_vhtml',
                'description': 'Vue v-html directive renders raw HTML',
                'recommendation': 'Sanitize content or use v-text'
            },
            {
                'pattern': r'\.insertAdjacentHTML\s*\(',
                'severity': 'HIGH',
                'type': 'insertAdjacentHTML',
                'description': 'insertAdjacentHTML parses HTML',
                'recommendation': 'Sanitize input before insertion'
            },
            {
                'pattern': r'location\s*=|location\.href\s*=',
                'severity': 'MEDIUM',
                'type': 'location_assignment',
                'description': 'JavaScript URL assignment (potential DOM XSS)',
                'recommendation': 'Validate URLs before assignment'
            }
        ],
        'python': [
            {
                'pattern': r'Markup\s*\(|mark_safe\s*\(',
                'severity': 'MEDIUM',
                'type': 'markup_safe',
                'description': 'Marking user content as safe HTML',
                'recommendation': 'Only use for trusted content, escape user input'
            },
            {
                'pattern': r'\|safe\s*\}',
                'severity': 'HIGH',
                'type': 'jinja_safe',
                'description': 'Jinja2 safe filter disables auto-escaping',
                'recommendation': 'Remove |safe or ensure content is sanitized'
            },
            {
                'pattern': r'autoescape\s*=\s*False',
                'severity': 'CRITICAL',
                'type': 'autoescape_disabled',
                'description': 'Template auto-escaping disabled',
                'recommendation': 'Enable autoescape and manually escape when needed'
            },
            {
                'pattern': r'render_template_string\s*\(',
                'severity': 'HIGH',
                'type': 'render_template_string',
                'description': 'Rendering user input as template',
                'recommendation': 'Use render_template() with predefined templates'
            }
        ],
        'php': [
            {
                'pattern': r'echo\s+\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'echo_superglobal',
                'description': 'Direct echo of user input',
                'recommendation': 'Use htmlspecialchars() or htmlentities()'
            },
            {
                'pattern': r'print\s+\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'print_superglobal',
                'description': 'Direct print of user input',
                'recommendation': 'Use htmlspecialchars() or htmlentities()'
            },
            {
                'pattern': r'<\?=\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'short_echo_superglobal',
                'description': 'Short echo tag with user input',
                'recommendation': 'Apply htmlspecialchars() to all user input'
            },
            {
                'pattern': r'echo\s+[^;]*\$(?!_)',
                'severity': 'MEDIUM',
                'type': 'echo_variable',
                'description': 'Echo of variable (check if user input)',
                'recommendation': 'Ensure all output is escaped with htmlspecialchars()'
            }
        ],
        'ruby': [
            {
                'pattern': r'\.html_safe',
                'severity': 'HIGH',
                'type': 'html_safe',
                'description': 'Marking content as HTML safe',
                'recommendation': 'Only use for trusted content'
            },
            {
                'pattern': r'raw\s*\(',
                'severity': 'HIGH',
                'type': 'raw_helper',
                'description': 'raw() helper outputs unescaped HTML',
                'recommendation': 'Use sanitize() or ensure content is trusted'
            },
            {
                'pattern': r'<%==',
                'severity': 'HIGH',
                'type': 'erb_unescaped',
                'description': 'ERB tag outputs unescaped content',
                'recommendation': 'Use <%= for auto-escaped output'
            }
        ],
        'java': [
            {
                'pattern': r'getWriter\(\)\.print(?:ln)?\s*\([^)]*getParameter',
                'severity': 'CRITICAL',
                'type': 'servlet_xss',
                'description': 'Direct output of request parameter',
                'recommendation': 'Encode output with OWASP ESAPI'
            },
            {
                'pattern': r'out\.print(?:ln)?\s*\([^)]*request\.getParameter',
                'severity': 'CRITICAL',
                'type': 'jsp_xss',
                'description': 'JSP direct output of parameter',
                'recommendation': 'Use <c:out> or fn:escapeXml()'
            }
        ],
        'html': [
            {
                'pattern': r'on\w+\s*=\s*["\'][^"\']*(?:location|document|window)',
                'severity': 'MEDIUM',
                'type': 'inline_handler',
                'description': 'Inline event handler with sensitive objects',
                'recommendation': 'Use addEventListener() instead of inline handlers'
            },
            {
                'pattern': r'javascript:',
                'severity': 'HIGH',
                'type': 'javascript_url',
                'description': 'JavaScript URL protocol',
                'recommendation': 'Avoid javascript: URLs, use event handlers'
            },
            {
                'pattern': r'<script[^>]*>\s*var\s+\w+\s*=\s*["\'][^"\']*\{\{',
                'severity': 'HIGH',
                'type': 'template_in_script',
                'description': 'Template variable in script tag',
                'recommendation': 'Use JSON encoding for data in scripts'
            }
        ]
    }

    def __init__(self):
        self.issues: List[XSSIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for lang, patterns in self.VULNERABILITY_PATTERNS.items():
            self.compiled_patterns[lang] = []
            for p in patterns:
                try:
                    self.compiled_patterns[lang].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'javascript',
            '.tsx': 'javascript',
            '.vue': 'javascript',
            '.svelte': 'javascript',
            '.py': 'python',
            '.php': 'php',
            '.rb': 'ruby',
            '.erb': 'ruby',
            '.java': 'java',
            '.jsp': 'java',
            '.html': 'html',
            '.htm': 'html',
            '.twig': 'html',
            '.hbs': 'html',
            '.ejs': 'html'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[XSSIssue]:
        """Scan a single file for XSS vulnerabilities."""
        issues = []
        language = self.get_language(file_path)

        if not language or language not in self.compiled_patterns:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for pattern_config in self.compiled_patterns[language]:
                if pattern_config['regex'].search(line):
                    issue = XSSIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=pattern_config['severity'],
                        pattern_type=pattern_config['type'],
                        code_snippet=line.strip()[:100],
                        description=pattern_config['description'],
                        recommendation=pattern_config['recommendation']
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[XSSIssue]:
        """Scan directory for XSS vulnerabilities."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor', 'dist', 'build', 'coverage'}

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
            if issue.pattern_type not in summary['by_type']:
                summary['by_type'][issue.pattern_type] = 0
            summary['by_type'][issue.pattern_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("XSS VULNERABILITY SCAN REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nIssues by Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\n" + "-" * 70)
            print("VULNERABILITIES FOUND")
            print("-" * 70)

            # Sort by severity
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.file_path}:{issue.line_number}")
                print(f"  Type: {issue.pattern_type}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No XSS vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for XSS vulnerabilities'
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
    scanner = XSSScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for XSS vulnerabilities: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
