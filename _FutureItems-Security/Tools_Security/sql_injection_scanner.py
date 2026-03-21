#!/usr/bin/env python3
"""
SQL Injection Scanner
Scans source code for potential SQL injection vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SQLInjectionIssue:
    """Represents a potential SQL injection vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class SQLInjectionScanner:
    """Scans code for SQL injection vulnerabilities."""

    # Patterns for different languages
    VULNERABILITY_PATTERNS = {
        'python': [
            {
                'pattern': r'cursor\.execute\s*\(\s*["\'].*%s.*["\'].*%',
                'severity': 'CRITICAL',
                'type': 'string_formatting',
                'description': 'SQL query with string formatting (%s operator)',
                'recommendation': 'Use parameterized queries: cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))'
            },
            {
                'pattern': r'cursor\.execute\s*\(\s*f["\']',
                'severity': 'CRITICAL',
                'type': 'f_string',
                'description': 'SQL query using f-string interpolation',
                'recommendation': 'Use parameterized queries instead of f-strings'
            },
            {
                'pattern': r'cursor\.execute\s*\(\s*["\'].*\+.*["\']',
                'severity': 'CRITICAL',
                'type': 'string_concat',
                'description': 'SQL query with string concatenation',
                'recommendation': 'Use parameterized queries instead of concatenation'
            },
            {
                'pattern': r'\.execute\s*\(\s*["\'].*\.format\s*\(',
                'severity': 'CRITICAL',
                'type': 'format_method',
                'description': 'SQL query using .format() method',
                'recommendation': 'Use parameterized queries instead of .format()'
            },
            {
                'pattern': r'(?:SELECT|INSERT|UPDATE|DELETE|DROP).*\+\s*(?:request\.|input\(|sys\.argv)',
                'severity': 'CRITICAL',
                'type': 'user_input_concat',
                'description': 'Direct concatenation of user input in SQL',
                'recommendation': 'Never concatenate user input in SQL queries'
            },
            {
                'pattern': r'raw\s*\(\s*["\'](?:SELECT|INSERT|UPDATE|DELETE)',
                'severity': 'HIGH',
                'type': 'django_raw',
                'description': 'Django raw SQL query',
                'recommendation': 'Use ORM methods or ensure proper parameterization'
            }
        ],
        'javascript': [
            {
                'pattern': r'query\s*\(\s*[`"\'].*\$\{',
                'severity': 'CRITICAL',
                'type': 'template_literal',
                'description': 'SQL query with template literal interpolation',
                'recommendation': 'Use parameterized queries with placeholders'
            },
            {
                'pattern': r'query\s*\(\s*["\'].*\+.*req\.',
                'severity': 'CRITICAL',
                'type': 'request_concat',
                'description': 'SQL query concatenated with request data',
                'recommendation': 'Use parameterized queries with prepared statements'
            },
            {
                'pattern': r'(?:mysql|pg|sqlite)\.query\s*\([^,\)]*\+',
                'severity': 'HIGH',
                'type': 'db_query_concat',
                'description': 'Database query with string concatenation',
                'recommendation': 'Use query parameterization'
            },
            {
                'pattern': r'\.exec\s*\(\s*["\'](?:SELECT|INSERT|UPDATE|DELETE).*\+',
                'severity': 'CRITICAL',
                'type': 'exec_concat',
                'description': 'exec() with concatenated SQL',
                'recommendation': 'Use parameterized queries'
            }
        ],
        'php': [
            {
                'pattern': r'mysqli?_query\s*\([^,]*,\s*["\'].*\$',
                'severity': 'CRITICAL',
                'type': 'variable_in_query',
                'description': 'PHP variable directly in SQL query',
                'recommendation': 'Use prepared statements with mysqli_prepare()'
            },
            {
                'pattern': r'\$(?:pdo|conn|db)->query\s*\(["\'].*\$',
                'severity': 'CRITICAL',
                'type': 'pdo_unsafe_query',
                'description': 'PDO query with variable interpolation',
                'recommendation': 'Use PDO prepared statements with bindParam()'
            },
            {
                'pattern': r'mysql_query\s*\(',
                'severity': 'HIGH',
                'type': 'deprecated_mysql',
                'description': 'Deprecated mysql_* function (removed in PHP 7)',
                'recommendation': 'Use PDO or mysqli with prepared statements'
            },
            {
                'pattern': r'(?:SELECT|INSERT|UPDATE|DELETE).*\.\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'superglobal_concat',
                'description': 'Direct use of $_GET/$_POST in SQL',
                'recommendation': 'Always validate, sanitize, and use prepared statements'
            }
        ],
        'java': [
            {
                'pattern': r'Statement.*\.execute(?:Query|Update)\s*\([^?]*\+',
                'severity': 'CRITICAL',
                'type': 'statement_concat',
                'description': 'Statement with string concatenation',
                'recommendation': 'Use PreparedStatement with parameterized queries'
            },
            {
                'pattern': r'createStatement\s*\(\s*\).*execute',
                'severity': 'MEDIUM',
                'type': 'create_statement',
                'description': 'createStatement() usage (vulnerable to SQL injection)',
                'recommendation': 'Use prepareStatement() instead'
            },
            {
                'pattern': r'String\s+\w+\s*=\s*["\'](?:SELECT|INSERT|UPDATE|DELETE).*\+',
                'severity': 'HIGH',
                'type': 'sql_string_concat',
                'description': 'SQL string with concatenation',
                'recommendation': 'Use PreparedStatement with ? placeholders'
            }
        ],
        'csharp': [
            {
                'pattern': r'SqlCommand\s*\([^,]*\+',
                'severity': 'CRITICAL',
                'type': 'sqlcommand_concat',
                'description': 'SqlCommand with string concatenation',
                'recommendation': 'Use SqlParameter for parameterized queries'
            },
            {
                'pattern': r'ExecuteReader\s*\([^)]*\+',
                'severity': 'HIGH',
                'type': 'execute_reader_concat',
                'description': 'ExecuteReader with concatenation',
                'recommendation': 'Use parameterized queries with SqlParameter'
            },
            {
                'pattern': r'\$"(?:SELECT|INSERT|UPDATE|DELETE).*\{',
                'severity': 'CRITICAL',
                'type': 'interpolated_sql',
                'description': 'SQL in interpolated string',
                'recommendation': 'Use parameterized queries'
            }
        ],
        'ruby': [
            {
                'pattern': r'(?:find_by_sql|execute)\s*\(["\'].*#\{',
                'severity': 'CRITICAL',
                'type': 'interpolation',
                'description': 'SQL query with Ruby interpolation',
                'recommendation': 'Use ActiveRecord parameterization or sanitize_sql'
            },
            {
                'pattern': r'\.where\s*\(["\'].*#\{',
                'severity': 'HIGH',
                'type': 'where_interpolation',
                'description': 'ActiveRecord where with interpolation',
                'recommendation': 'Use hash conditions: where(id: user_input)'
            }
        ]
    }

    def __init__(self):
        self.issues: List[SQLInjectionIssue] = []
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
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.php': 'php',
            '.java': 'java',
            '.cs': 'csharp',
            '.rb': 'ruby'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[SQLInjectionIssue]:
        """Scan a single file for SQL injection vulnerabilities."""
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
                    issue = SQLInjectionIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[SQLInjectionIssue]:
        """Scan directory for SQL injection vulnerabilities."""
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
        print("SQL INJECTION VULNERABILITY SCAN REPORT")
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
            print("\n✓ No SQL injection vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for SQL injection vulnerabilities'
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
    scanner = SQLInjectionScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for SQL injection vulnerabilities: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
