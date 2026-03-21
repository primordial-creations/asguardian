#!/usr/bin/env python3
"""
Insecure Deserialization Scanner
Detects unsafe deserialization vulnerabilities in source code.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class DeserializationIssue:
    """Represents an insecure deserialization vulnerability."""
    file_path: str
    line_number: int
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class DeserializationScanner:
    """Scans code for insecure deserialization vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'python': [
            {
                'pattern': r'pickle\.loads?\s*\(',
                'severity': 'CRITICAL',
                'type': 'pickle_load',
                'description': 'pickle deserialization allows arbitrary code execution',
                'recommendation': 'Use JSON or other safe serialization formats'
            },
            {
                'pattern': r'cPickle\.loads?\s*\(',
                'severity': 'CRITICAL',
                'type': 'cpickle_load',
                'description': 'cPickle is equally vulnerable as pickle',
                'recommendation': 'Use JSON or safe alternatives'
            },
            {
                'pattern': r'marshal\.loads?\s*\(',
                'severity': 'CRITICAL',
                'type': 'marshal_load',
                'description': 'marshal deserialization is unsafe',
                'recommendation': 'Use JSON for untrusted data'
            },
            {
                'pattern': r'shelve\.open\s*\(',
                'severity': 'HIGH',
                'type': 'shelve_open',
                'description': 'shelve uses pickle internally',
                'recommendation': 'Avoid shelve with untrusted data'
            },
            {
                'pattern': r'yaml\.load\s*\([^)]*\)(?!\s*,\s*Loader)',
                'severity': 'CRITICAL',
                'type': 'yaml_unsafe_load',
                'description': 'yaml.load without Loader is unsafe',
                'recommendation': 'Use yaml.safe_load() or specify SafeLoader'
            },
            {
                'pattern': r'yaml\.load\s*\([^)]*,\s*Loader\s*=\s*yaml\.(?:Full)?Loader',
                'severity': 'HIGH',
                'type': 'yaml_unsafe_loader',
                'description': 'yaml with FullLoader allows code execution',
                'recommendation': 'Use yaml.safe_load() or SafeLoader'
            },
            {
                'pattern': r'jsonpickle\.decode\s*\(',
                'severity': 'CRITICAL',
                'type': 'jsonpickle_decode',
                'description': 'jsonpickle can execute arbitrary code',
                'recommendation': 'Use standard json module'
            },
            {
                'pattern': r'dill\.loads?\s*\(',
                'severity': 'CRITICAL',
                'type': 'dill_load',
                'description': 'dill allows arbitrary code execution',
                'recommendation': 'Use JSON for untrusted data'
            },
        ],
        'javascript': [
            {
                'pattern': r'node-serialize|serialize-javascript.*unserialize',
                'severity': 'CRITICAL',
                'type': 'node_serialize',
                'description': 'node-serialize allows code execution',
                'recommendation': 'Use JSON.parse() instead'
            },
            {
                'pattern': r'eval\s*\(\s*JSON\.stringify',
                'severity': 'CRITICAL',
                'type': 'eval_json',
                'description': 'eval with JSON is dangerous',
                'recommendation': 'Use JSON.parse() directly'
            },
            {
                'pattern': r'Function\s*\(\s*[\'"]return\s+',
                'severity': 'HIGH',
                'type': 'function_constructor',
                'description': 'Function constructor can execute code',
                'recommendation': 'Use JSON.parse() for data'
            },
            {
                'pattern': r'js-yaml.*load\s*\([^)]*\{[^}]*unsafe',
                'severity': 'HIGH',
                'type': 'yaml_unsafe',
                'description': 'js-yaml with unsafe options',
                'recommendation': 'Use safeLoad() or DEFAULT_SAFE_SCHEMA'
            },
        ],
        'java': [
            {
                'pattern': r'ObjectInputStream\s*\([^)]*\)',
                'severity': 'CRITICAL',
                'type': 'object_input_stream',
                'description': 'Java ObjectInputStream allows arbitrary code execution',
                'recommendation': 'Use look-ahead deserialization or JSON'
            },
            {
                'pattern': r'\.readObject\s*\(\s*\)',
                'severity': 'CRITICAL',
                'type': 'read_object',
                'description': 'readObject() is vulnerable to deserialization attacks',
                'recommendation': 'Implement ObjectInputFilter or use safe formats'
            },
            {
                'pattern': r'XMLDecoder\s*\(',
                'severity': 'CRITICAL',
                'type': 'xml_decoder',
                'description': 'XMLDecoder allows arbitrary code execution',
                'recommendation': 'Use safe XML parsers or JSON'
            },
            {
                'pattern': r'XStream.*fromXML\s*\(',
                'severity': 'HIGH',
                'type': 'xstream_fromxml',
                'description': 'XStream deserialization can be exploited',
                'recommendation': 'Configure XStream allowlist'
            },
            {
                'pattern': r'(?:Yaml|SnakeYAML).*load\s*\(',
                'severity': 'HIGH',
                'type': 'yaml_load',
                'description': 'YAML deserialization may be unsafe',
                'recommendation': 'Use SafeConstructor'
            },
            {
                'pattern': r'Kryo.*readObject|Kryo.*readClassAndObject',
                'severity': 'HIGH',
                'type': 'kryo_deserialize',
                'description': 'Kryo deserialization can be exploited',
                'recommendation': 'Use registration and allowlisting'
            },
        ],
        'php': [
            {
                'pattern': r'unserialize\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
                'severity': 'CRITICAL',
                'type': 'unserialize_superglobal',
                'description': 'unserialize with user input allows code execution',
                'recommendation': 'Use JSON instead of PHP serialization'
            },
            {
                'pattern': r'unserialize\s*\(\s*\$',
                'severity': 'HIGH',
                'type': 'unserialize_variable',
                'description': 'unserialize with variable input',
                'recommendation': 'Validate input or use JSON'
            },
            {
                'pattern': r'unserialize\s*\([^)]*\)',
                'severity': 'MEDIUM',
                'type': 'unserialize_usage',
                'description': 'unserialize() is potentially dangerous',
                'recommendation': 'Consider using json_decode() instead'
            },
        ],
        'ruby': [
            {
                'pattern': r'Marshal\.load\s*\(',
                'severity': 'CRITICAL',
                'type': 'marshal_load',
                'description': 'Marshal.load allows arbitrary code execution',
                'recommendation': 'Use JSON for untrusted data'
            },
            {
                'pattern': r'YAML\.load\s*\([^)]*\)(?!\s*,\s*(?:safe|permitted))',
                'severity': 'CRITICAL',
                'type': 'yaml_load',
                'description': 'YAML.load allows code execution',
                'recommendation': 'Use YAML.safe_load()'
            },
            {
                'pattern': r'ERB\.new\s*\([^)]*\)\.result',
                'severity': 'HIGH',
                'type': 'erb_eval',
                'description': 'ERB template evaluation',
                'recommendation': 'Sanitize template input'
            },
        ],
        'csharp': [
            {
                'pattern': r'BinaryFormatter\s*\(\s*\)|BinaryFormatter\.Deserialize',
                'severity': 'CRITICAL',
                'type': 'binary_formatter',
                'description': 'BinaryFormatter allows arbitrary code execution',
                'recommendation': 'Use DataContractSerializer or JSON'
            },
            {
                'pattern': r'SoapFormatter\.Deserialize',
                'severity': 'CRITICAL',
                'type': 'soap_formatter',
                'description': 'SoapFormatter is vulnerable to RCE',
                'recommendation': 'Use safe serializers like JSON'
            },
            {
                'pattern': r'ObjectStateFormatter\.Deserialize',
                'severity': 'CRITICAL',
                'type': 'object_state_formatter',
                'description': 'ObjectStateFormatter allows RCE',
                'recommendation': 'Use safe serialization formats'
            },
            {
                'pattern': r'NetDataContractSerializer\.(?:ReadObject|Deserialize)',
                'severity': 'CRITICAL',
                'type': 'net_data_contract',
                'description': 'NetDataContractSerializer is unsafe',
                'recommendation': 'Use DataContractSerializer with known types'
            },
            {
                'pattern': r'LosFormatter\.Deserialize',
                'severity': 'CRITICAL',
                'type': 'los_formatter',
                'description': 'LosFormatter allows code execution',
                'recommendation': 'Use safe serialization formats'
            },
            {
                'pattern': r'JavaScriptSerializer\s*\(\s*\).*Deserialize',
                'severity': 'HIGH',
                'type': 'js_serializer',
                'description': 'JavaScriptSerializer with type handling is unsafe',
                'recommendation': 'Avoid type resolvers or use JSON.NET safely'
            },
        ],
        'go': [
            {
                'pattern': r'gob\.NewDecoder|gob\.Decode',
                'severity': 'MEDIUM',
                'type': 'gob_decode',
                'description': 'gob deserialization may be unsafe',
                'recommendation': 'Validate input and use with caution'
            },
            {
                'pattern': r'encoding/xml.*Unmarshal',
                'severity': 'MEDIUM',
                'type': 'xml_unmarshal',
                'description': 'XML unmarshaling (check for XXE)',
                'recommendation': 'Use secure XML configuration'
            },
        ]
    }

    def __init__(self):
        self.issues: List[DeserializationIssue] = []
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
            '.java': 'java',
            '.php': 'php',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.go': 'go'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[DeserializationIssue]:
        """Scan a single file for insecure deserialization."""
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
                    issue = DeserializationIssue(
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

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[DeserializationIssue]:
        """Scan directory for insecure deserialization."""
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
        print("INSECURE DESERIALIZATION SCAN")
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
            print("\n✓ No insecure deserialization detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for insecure deserialization vulnerabilities'
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
    scanner = DeserializationScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for insecure deserialization: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
