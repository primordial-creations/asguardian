#!/usr/bin/env python3
"""
Path Traversal Scanner
Detects directory traversal and local file inclusion vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class PathTraversalIssue:
    """Represents a path traversal vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class PathTraversalScanner:
    """Scans code for path traversal vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'python': [
            {
                'pattern': r'open\s*\(\s*(?:request\.|args\.|params\.|input\()',
                'severity': 'CRITICAL',
                'type': 'open_user_input',
                'description': 'File open with user-controlled path',
                'recommendation': 'Validate path and use os.path.basename()'
            },
            {
                'pattern': r'(?:os\.path\.join|pathlib\.Path)\s*\([^)]*(?:request\.|args\.|params\.)',
                'severity': 'HIGH',
                'type': 'path_join_input',
                'description': 'Path construction with user input',
                'recommendation': 'Validate and sanitize path components'
            },
            {
                'pattern': r'send_file\s*\(\s*(?:request\.|args\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'send_file_input',
                'description': 'send_file with user-controlled path',
                'recommendation': 'Use safe_join() and validate file access'
            },
            {
                'pattern': r'(?:shutil\.copy|shutil\.move)\s*\([^)]*(?:request\.|args\.|params\.)',
                'severity': 'HIGH',
                'type': 'file_ops_input',
                'description': 'File operation with user input',
                'recommendation': 'Validate paths before file operations'
            },
            {
                'pattern': r'__file__.*(?:request\.|args\.|params\.)',
                'severity': 'HIGH',
                'type': 'relative_path_input',
                'description': 'Relative path with user input',
                'recommendation': 'Use absolute paths and validate'
            },
        ],
        'javascript': [
            {
                'pattern': r'(?:fs\.readFile|fs\.readFileSync|fs\.createReadStream)\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'fs_read_input',
                'description': 'File read with user-controlled path',
                'recommendation': 'Use path.basename() and validate'
            },
            {
                'pattern': r'path\.(?:join|resolve)\s*\([^)]*(?:req\.|request\.|params\.)',
                'severity': 'HIGH',
                'type': 'path_join_input',
                'description': 'Path construction with user input',
                'recommendation': 'Validate path components'
            },
            {
                'pattern': r'res\.sendFile\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'sendfile_input',
                'description': 'sendFile with user-controlled path',
                'recommendation': 'Use express.static() or validate paths'
            },
            {
                'pattern': r'require\s*\(\s*(?:req\.|request\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'require_input',
                'description': 'Dynamic require with user input',
                'recommendation': 'Never use user input in require()'
            },
            {
                'pattern': r'(?:fs\.unlink|fs\.rmdir)\s*\([^)]*(?:req\.|params\.)',
                'severity': 'CRITICAL',
                'type': 'delete_input',
                'description': 'File deletion with user input',
                'recommendation': 'Strictly validate before deletion'
            },
        ],
        'php': [
            {
                'pattern': r'(?:include|require|include_once|require_once)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'lfi_superglobal',
                'description': 'Local file inclusion vulnerability',
                'recommendation': 'Never include files from user input'
            },
            {
                'pattern': r'(?:file_get_contents|file_put_contents|readfile|fopen)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'file_ops_superglobal',
                'description': 'File operation with superglobal',
                'recommendation': 'Validate and sanitize file paths'
            },
            {
                'pattern': r'(?:copy|rename|unlink|rmdir)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'CRITICAL',
                'type': 'dangerous_file_ops',
                'description': 'Dangerous file operation with user input',
                'recommendation': 'Use basename() and validate paths'
            },
            {
                'pattern': r'(?:include|require)\s*\(\s*\$',
                'severity': 'HIGH',
                'type': 'dynamic_include',
                'description': 'Dynamic file inclusion',
                'recommendation': 'Whitelist allowed files'
            },
            {
                'pattern': r'(?:glob|scandir|opendir)\s*\(\s*\$_(?:GET|POST|REQUEST)',
                'severity': 'HIGH',
                'type': 'directory_listing',
                'description': 'Directory listing with user input',
                'recommendation': 'Restrict to allowed directories'
            },
        ],
        'java': [
            {
                'pattern': r'new\s+(?:File|FileInputStream|FileReader)\s*\([^)]*request\.getParameter',
                'severity': 'CRITICAL',
                'type': 'file_path_input',
                'description': 'File path from request parameter',
                'recommendation': 'Validate path and use canonical path checking'
            },
            {
                'pattern': r'Paths\.get\s*\([^)]*request\.getParameter',
                'severity': 'CRITICAL',
                'type': 'paths_get_input',
                'description': 'Path from user input',
                'recommendation': 'Validate and canonicalize paths'
            },
            {
                'pattern': r'getResourceAsStream\s*\([^)]*request\.getParameter',
                'severity': 'HIGH',
                'type': 'resource_stream_input',
                'description': 'Resource loading with user input',
                'recommendation': 'Whitelist allowed resources'
            },
        ],
        'ruby': [
            {
                'pattern': r'(?:File\.read|File\.open|IO\.read)\s*\(\s*params\[',
                'severity': 'CRITICAL',
                'type': 'file_read_params',
                'description': 'File read with params input',
                'recommendation': 'Use File.basename() and validate'
            },
            {
                'pattern': r'send_file\s*\(\s*params\[',
                'severity': 'CRITICAL',
                'type': 'send_file_params',
                'description': 'send_file with user input',
                'recommendation': 'Validate path within allowed directory'
            },
            {
                'pattern': r'(?:load|require)\s*\(\s*params\[',
                'severity': 'CRITICAL',
                'type': 'dynamic_load',
                'description': 'Dynamic code loading with user input',
                'recommendation': 'Never load files from user input'
            },
        ],
        'csharp': [
            {
                'pattern': r'(?:File\.ReadAllText|File\.ReadAllBytes|StreamReader)\s*\([^)]*Request\[',
                'severity': 'CRITICAL',
                'type': 'file_read_request',
                'description': 'File read with request input',
                'recommendation': 'Validate and canonicalize paths'
            },
            {
                'pattern': r'Path\.Combine\s*\([^)]*Request\[',
                'severity': 'HIGH',
                'type': 'path_combine_input',
                'description': 'Path combination with user input',
                'recommendation': 'Validate path components'
            },
            {
                'pattern': r'Server\.MapPath\s*\([^)]*Request\[',
                'severity': 'HIGH',
                'type': 'mappath_input',
                'description': 'MapPath with user input',
                'recommendation': 'Validate and restrict to web root'
            },
        ],
    }

    def __init__(self):
        self.issues: List[PathTraversalIssue] = []
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
            '.rb': 'ruby',
            '.cs': 'csharp'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[PathTraversalIssue]:
        """Scan a single file for path traversal vulnerabilities."""
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
                    issue = PathTraversalIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=pattern_config['severity'],
                        pattern_type=pattern_config['type'],
                        code_snippet=line.strip()[:150],
                        description=pattern_config['description'],
                        recommendation=pattern_config['recommendation']
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[PathTraversalIssue]:
        """Scan directory for path traversal vulnerabilities."""
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
        print("PATH TRAVERSAL VULNERABILITY SCAN")
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
            print("VULNERABILITIES FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.file_path}:{issue.line_number}")
                print(f"  Type: {issue.pattern_type}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No path traversal vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for path traversal vulnerabilities'
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
    scanner = PathTraversalScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for path traversal: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
