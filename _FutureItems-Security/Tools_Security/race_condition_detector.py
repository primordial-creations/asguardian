#!/usr/bin/env python3
"""
Race Condition Detector
Detects potential race conditions and TOCTOU vulnerabilities in code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class RaceConditionIssue:
    """Represents a race condition issue."""
    file_path: str
    line_number: int
    severity: str
    category: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class RaceConditionDetector:
    """Detects potential race conditions in code."""

    RACE_PATTERNS = {
        'toctou_file': [
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:os\.path\.exists|Path.*\.exists|fs\.exists|File\.exists)\s*\([^)]+\)(?:.*\n.*)?(?:open|read|write|unlink|remove|delete)',
                'severity': 'HIGH',
                'type': 'toctou_exists',
                'description': 'TOCTOU: Check-then-use on file existence',
                'recommendation': 'Use atomic operations or file locking'
            },
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:os\.access|access)\s*\([^)]+\)(?:.*\n.*)?(?:open|read|write)',
                'severity': 'HIGH',
                'type': 'toctou_access',
                'description': 'TOCTOU: Check-then-use on file access',
                'recommendation': 'Use try/except instead of access check'
            },
            {
                'pattern': r'(?:os\.stat|stat|fs\.stat)\s*\([^)]+\)(?:.*\n.*)?(?:open|read|write|unlink)',
                'severity': 'MEDIUM',
                'type': 'toctou_stat',
                'description': 'TOCTOU: Stat-then-use pattern',
                'recommendation': 'Use fstat on open file descriptor'
            },
        ],
        'toctou_dir': [
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:os\.path\.isdir|isdir|fs\.isDirectory)\s*\([^)]+\)(?:.*\n.*)?(?:mkdir|rmdir|listdir)',
                'severity': 'MEDIUM',
                'type': 'toctou_isdir',
                'description': 'TOCTOU: Directory check-then-use',
                'recommendation': 'Use atomic operations with error handling'
            },
        ],
        'double_checked_locking': [
            {
                'pattern': r'if\s*\(\s*\w+\s*==\s*(?:null|None|nil)\s*\).*\n.*(?:synchronized|lock|mutex).*\n.*if\s*\(\s*\w+\s*==\s*(?:null|None|nil)\s*\)',
                'severity': 'HIGH',
                'type': 'double_checked_locking',
                'description': 'Double-checked locking anti-pattern',
                'recommendation': 'Use proper singleton pattern or atomic operations'
            },
        ],
        'shared_state': [
            {
                'pattern': r'(?:global|static)\s+\w+\s*=\s*(?:\[\]|\{\}|0|None|null)',
                'severity': 'MEDIUM',
                'type': 'shared_mutable_state',
                'description': 'Shared mutable state',
                'recommendation': 'Use thread-safe data structures or locks'
            },
            {
                'pattern': r'(?:class|def|function)\s+\w+.*\n(?:.*\n)*.*(?:cls\.|self\.|this\.)\w+\s*(?:\+\+|--|\+=|-=)',
                'severity': 'MEDIUM',
                'type': 'shared_counter',
                'description': 'Non-atomic counter operation',
                'recommendation': 'Use atomic operations or locks'
            },
        ],
        'async_issues': [
            {
                'pattern': r'(?:async\s+)?(?:def|function)\s+\w+.*\n(?:.*\n)*.*(?:await|\.then)\s*\([^)]*\)(?:.*\n.*)?(?:\w+\s*=)',
                'severity': 'MEDIUM',
                'type': 'async_state_mutation',
                'description': 'State mutation after async operation',
                'recommendation': 'Ensure atomic updates in async code'
            },
            {
                'pattern': r'Promise\.all\s*\(\s*\[[^\]]*\w+\s*(?:\+\+|--|\+=)',
                'severity': 'HIGH',
                'type': 'concurrent_mutation',
                'description': 'Concurrent mutation in Promise.all',
                'recommendation': 'Use proper synchronization'
            },
        ],
        'database': [
            {
                'pattern': r'(?:SELECT|select).*(?:WHERE|where).*\n(?:.*\n)*.*(?:UPDATE|update|INSERT|insert)',
                'severity': 'HIGH',
                'type': 'read_modify_write',
                'description': 'Read-modify-write without transaction',
                'recommendation': 'Use transactions with appropriate isolation'
            },
            {
                'pattern': r'(?:findOne|find_one|get)\s*\([^)]+\)(?:.*\n.*)?(?:save|update|delete)',
                'severity': 'MEDIUM',
                'type': 'orm_race',
                'description': 'ORM read-modify-write pattern',
                'recommendation': 'Use optimistic locking or transactions'
            },
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:count|exists)\s*\([^)]+\)(?:.*\n.*)?(?:insert|create|save)',
                'severity': 'HIGH',
                'type': 'check_then_insert',
                'description': 'Check-then-insert pattern',
                'recommendation': 'Use INSERT...ON CONFLICT or UPSERT'
            },
        ],
        'cache': [
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:cache\.get|redis\.get|memcached\.get)\s*\([^)]+\)\s*(?:==|is)\s*(?:None|null|nil)(?:.*\n.*)?(?:cache\.set|redis\.set)',
                'severity': 'MEDIUM',
                'type': 'cache_stampede',
                'description': 'Cache stampede vulnerability',
                'recommendation': 'Use lock or probabilistic early expiration'
            },
        ],
        'resource_management': [
            {
                'pattern': r'(?:if\s*\(?\s*)?(?:pool|connection).*(?:available|free)(?:.*\n.*)?(?:acquire|get|borrow)',
                'severity': 'MEDIUM',
                'type': 'resource_check',
                'description': 'Resource availability check-then-use',
                'recommendation': 'Use blocking acquire with timeout'
            },
        ],
        'counter_operations': [
            {
                'pattern': r'\w+\s*=\s*\w+\s*\+\s*1|\w+\s*\+\+|\w+\s*\+=\s*1',
                'severity': 'LOW',
                'type': 'non_atomic_increment',
                'description': 'Potentially non-atomic increment',
                'recommendation': 'Use atomic increment if shared'
            },
        ],
        'lazy_init': [
            {
                'pattern': r'if\s*\(\s*(?:self\.|this\.|cls\.)\w+\s*(?:==|is)\s*(?:None|null|nil)\s*\).*\n.*(?:self\.|this\.|cls\.)\w+\s*=',
                'severity': 'MEDIUM',
                'type': 'lazy_init_race',
                'description': 'Lazy initialization race condition',
                'recommendation': 'Use double-checked locking properly or lock'
            },
        ],
        'signal_handling': [
            {
                'pattern': r'signal\.(?:signal|SIGTERM|SIGINT).*\n(?:.*\n)*.*(?:global|shared)\s+\w+',
                'severity': 'MEDIUM',
                'type': 'signal_race',
                'description': 'Signal handler accessing shared state',
                'recommendation': 'Use signal-safe operations only'
            },
        ],
        'thread_unsafe': [
            {
                'pattern': r'(?:datetime\.now|time\.time|random\.)\s*\(\s*\)',
                'severity': 'LOW',
                'type': 'time_of_check',
                'description': 'Time-based check may have race',
                'recommendation': 'Consider monotonic time for intervals'
            },
        ],
        'file_operations': [
            {
                'pattern': r'(?:tempfile|mktemp)\s*\([^)]*\)(?:.*\n.*)?(?:open|write)',
                'severity': 'MEDIUM',
                'type': 'temp_file_race',
                'description': 'Temp file creation race',
                'recommendation': 'Use mkstemp or tempfile with context manager'
            },
        ],
        'balance_operations': [
            {
                'pattern': r'(?:balance|credits?|points?|stock|inventory)\s*(?:>=|<=|>|<|==)(?:.*\n.*)?(?:balance|credits?|points?|stock|inventory)\s*(?:-=|\+=|=)',
                'severity': 'HIGH',
                'type': 'balance_race',
                'description': 'Balance check-then-modify race',
                'recommendation': 'Use atomic compare-and-swap or transactions'
            },
        ],
    }

    def __init__(self):
        self.issues: List[RaceConditionIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for category, patterns in self.RACE_PATTERNS.items():
            self.compiled_patterns[category] = []
            for p in patterns:
                try:
                    self.compiled_patterns[category].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE | re.MULTILINE),
                        **p
                    })
                except re.error:
                    pass

    def scan_file(self, file_path: Path) -> List[RaceConditionIssue]:
        """Scan a single file for race conditions."""
        issues = []

        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs', '.c', '.cpp'}
        if file_path.suffix.lower() not in code_extensions:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        # Check multiline patterns against full content
        for category, patterns in self.compiled_patterns.items():
            for pattern_config in patterns:
                for match in pattern_config['regex'].finditer(content):
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    snippet = match.group(0).split('\n')[0][:150]

                    issue = RaceConditionIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=pattern_config['severity'],
                        category=category,
                        issue_type=pattern_config['type'],
                        code_snippet=snippet,
                        description=pattern_config['description'],
                        recommendation=pattern_config['recommendation']
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[RaceConditionIssue]:
        """Scan directory for race conditions."""
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
        print("RACE CONDITION DETECTION SCAN")
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
            print("POTENTIAL RACE CONDITIONS")
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
            print("\n✓ No race conditions detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Detect potential race conditions in code'
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
    detector = RaceConditionDetector()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for race conditions: {target.absolute()}")

    if target.is_file():
        detector.scan_file(target)
    else:
        recursive = not args.no_recursive
        detector.scan_directory(target, recursive=recursive)

    return detector.print_report()


if __name__ == '__main__':
    exit(main())
