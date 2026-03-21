#!/usr/bin/env python3
"""
ReDoS (Regular Expression Denial of Service) Scanner
Detects regex patterns vulnerable to catastrophic backtracking.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class ReDoSIssue:
    """Represents a ReDoS vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    regex_pattern: str
    description: str
    recommendation: str


class ReDoSScanner:
    """Scans code for ReDoS vulnerabilities."""

    # Patterns that indicate ReDoS-vulnerable regex
    REDOS_INDICATORS = [
        # Nested quantifiers
        (r'\([^)]*[+*][^)]*\)[+*]', 'nested_quantifiers', 'CRITICAL',
         'Nested quantifiers (e.g., (a+)+)', 'Refactor to avoid nested quantifiers'),

        # Overlapping alternations with quantifiers
        (r'\([^)]*\|[^)]*\)[+*]', 'overlapping_alternation', 'HIGH',
         'Overlapping alternation with quantifier', 'Make alternations mutually exclusive'),

        # Adjacent repeated groups
        (r'(?:\([^)]+\)[+*]){2,}', 'adjacent_quantified_groups', 'HIGH',
         'Adjacent quantified groups', 'Combine or restructure groups'),

        # Repeated patterns that can match same input
        (r'\.\*.*\.\*|\.\+.*\.\+', 'multiple_wildcards', 'MEDIUM',
         'Multiple wildcards in pattern', 'Use atomic groups or possessive quantifiers'),

        # Exponential patterns
        (r'\([^)]*\([^)]*[+*][^)]*\)[+*][^)]*\)', 'exponential_pattern', 'CRITICAL',
         'Potentially exponential regex', 'Simplify nested structure'),

        # Optional groups followed by similar patterns
        (r'\([^)]+\)\?[^)]*\1', 'optional_followed_by_similar', 'MEDIUM',
         'Optional group followed by similar pattern', 'Restructure pattern'),
    ]

    # Common vulnerable patterns in different languages
    LANG_PATTERNS = {
        'python': [
            (r're\.(?:match|search|findall|finditer|sub|split)\s*\(\s*r?[\'"](.+?)[\'"]', 'regex_call'),
            (r're\.compile\s*\(\s*r?[\'"](.+?)[\'"]', 'compiled_regex'),
        ],
        'javascript': [
            (r'new\s+RegExp\s*\(\s*[\'"`](.+?)[\'"`]', 'regexp_constructor'),
            (r'/(.+?)/[gimsuy]*', 'regex_literal'),
            (r'\.(?:match|replace|search|split)\s*\(\s*/(.+?)/[gimsuy]*', 'string_method'),
        ],
        'java': [
            (r'Pattern\.compile\s*\(\s*"(.+?)"', 'pattern_compile'),
            (r'\.matches\s*\(\s*"(.+?)"', 'string_matches'),
            (r'\.split\s*\(\s*"(.+?)"', 'string_split'),
        ],
        'ruby': [
            (r'/(.+?)/[imxo]*', 'regex_literal'),
            (r'Regexp\.new\s*\(\s*[\'"](.+?)[\'"]', 'regexp_new'),
        ],
        'php': [
            (r'preg_(?:match|replace|split|grep)\s*\(\s*[\'"](.+?)[\'"]', 'preg_function'),
        ],
        'go': [
            (r'regexp\.(?:Compile|MustCompile)\s*\(\s*`(.+?)`', 'regexp_compile'),
            (r'regexp\.(?:Compile|MustCompile)\s*\(\s*"(.+?)"', 'regexp_compile_str'),
        ],
        'csharp': [
            (r'new\s+Regex\s*\(\s*@?"(.+?)"', 'regex_constructor'),
            (r'Regex\.(?:Match|Matches|IsMatch|Replace|Split)\s*\([^,]+,\s*@?"(.+?)"', 'regex_static'),
        ],
    }

    def __init__(self):
        self.issues: List[ReDoSIssue] = []
        self.files_scanned = 0

        # Compile ReDoS indicator patterns
        self.compiled_indicators = [
            (re.compile(pattern), ptype, severity, desc, rec)
            for pattern, ptype, severity, desc, rec in self.REDOS_INDICATORS
        ]

        # Compile language patterns
        self.compiled_lang_patterns = {}
        for lang, patterns in self.LANG_PATTERNS.items():
            self.compiled_lang_patterns[lang] = [
                (re.compile(pattern, re.IGNORECASE), ptype)
                for pattern, ptype in patterns
            ]

    def get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.java': 'java',
            '.rb': 'ruby',
            '.php': 'php',
            '.go': 'go',
            '.cs': 'csharp'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def check_regex_vulnerability(self, regex_pattern: str) -> List[Tuple[str, str, str, str]]:
        """Check if a regex pattern is potentially vulnerable to ReDoS."""
        vulnerabilities = []

        for compiled, ptype, severity, desc, rec in self.compiled_indicators:
            if compiled.search(regex_pattern):
                vulnerabilities.append((ptype, severity, desc, rec))

        # Additional heuristic checks

        # Check for evil regex patterns
        if self._has_nested_quantifiers(regex_pattern):
            vulnerabilities.append((
                'evil_regex', 'CRITICAL',
                'Evil regex pattern with nested quantifiers',
                'Rewrite pattern to avoid exponential backtracking'
            ))

        # Check for star height > 1
        if self._get_star_height(regex_pattern) > 1:
            vulnerabilities.append((
                'high_star_height', 'HIGH',
                'Regex with star height > 1',
                'Reduce nesting of quantifiers'
            ))

        return vulnerabilities

    def _has_nested_quantifiers(self, pattern: str) -> bool:
        """Check for nested quantifiers in regex."""
        # Simple heuristic: look for patterns like (a+)+ or (a*)*
        depth = 0
        in_quantified = False

        i = 0
        while i < len(pattern):
            char = pattern[i]

            if char == '\\':
                i += 2
                continue

            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if i + 1 < len(pattern) and pattern[i + 1] in '+*':
                    if in_quantified and depth >= 0:
                        return True
                    in_quantified = True
            elif char in '+*' and depth > 0:
                in_quantified = True

            i += 1

        return False

    def _get_star_height(self, pattern: str) -> int:
        """Calculate star height (max nesting level of quantifiers)."""
        max_height = 0
        current_height = 0

        i = 0
        while i < len(pattern):
            char = pattern[i]

            if char == '\\':
                i += 2
                continue

            if char == '(':
                current_height += 1
            elif char == ')':
                if i + 1 < len(pattern) and pattern[i + 1] in '+*?':
                    max_height = max(max_height, current_height)
                current_height = max(0, current_height - 1)
            elif char in '+*':
                max_height = max(max_height, current_height)

            i += 1

        return max_height

    def scan_file(self, file_path: Path) -> List[ReDoSIssue]:
        """Scan a single file for ReDoS vulnerabilities."""
        issues = []
        language = self.get_language(file_path)

        if not language or language not in self.compiled_lang_patterns:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        # Find all regex patterns in the file
        for regex_pattern, pattern_type in self.compiled_lang_patterns[language]:
            for match in regex_pattern.finditer(content):
                extracted_regex = match.group(1)

                # Find line number
                pos = match.start()
                line_num = content[:pos].count('\n') + 1

                # Check for vulnerabilities
                vulns = self.check_regex_vulnerability(extracted_regex)

                for vtype, severity, desc, rec in vulns:
                    issue = ReDoSIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=severity,
                        pattern_type=vtype,
                        regex_pattern=extracted_regex[:100] + ('...' if len(extracted_regex) > 100 else ''),
                        description=desc,
                        recommendation=rec
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[ReDoSIssue]:
        """Scan directory for ReDoS vulnerabilities."""
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
        print("ReDoS VULNERABILITY SCAN")
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
            print("VULNERABLE REGEX PATTERNS")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.pattern_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Regex: {issue.regex_pattern}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No ReDoS vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for ReDoS vulnerabilities'
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
    scanner = ReDoSScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for ReDoS vulnerabilities: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
