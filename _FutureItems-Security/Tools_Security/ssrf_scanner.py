#!/usr/bin/env python3
"""
SSRF and XXE Vulnerability Scanner
Detects Server-Side Request Forgery and XML External Entity vulnerabilities.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SSRFXXEIssue:
    """Represents an SSRF or XXE vulnerability."""
    file_path: str
    line_number: int
    vulnerability_type: str
    severity: str
    pattern_type: str
    code_snippet: str
    description: str
    recommendation: str


class SSRFXXEScanner:
    """Scans code for SSRF and XXE vulnerabilities."""

    VULNERABILITY_PATTERNS = {
        'python': {
            'ssrf': [
                {
                    'pattern': r'requests\.(?:get|post|put|delete|head|patch)\s*\(\s*(?:f[\'"]|[\'"][^\'"]*[\'"].*\+|\+.*[\'"]|[^\'"]*%|[^\'"]*\.format\s*\()',
                    'severity': 'HIGH',
                    'type': 'requests_dynamic_url',
                    'description': 'Dynamic URL in requests library',
                    'recommendation': 'Validate and whitelist allowed URLs/domains'
                },
                {
                    'pattern': r'urllib\.request\.urlopen\s*\(\s*(?:request\.|args\.|params\.|input)',
                    'severity': 'CRITICAL',
                    'type': 'urllib_user_input',
                    'description': 'urllib with user-controlled URL',
                    'recommendation': 'Validate URLs against allowlist'
                },
                {
                    'pattern': r'(?:requests|urllib|httplib|http\.client).*(?:request\.|args\.|params\.|input\()',
                    'severity': 'HIGH',
                    'type': 'http_user_input',
                    'description': 'HTTP request with user input',
                    'recommendation': 'Implement URL validation and allowlisting'
                },
            ],
            'xxe': [
                {
                    'pattern': r'(?:xml\.etree|lxml).*(?:parse|fromstring)\s*\(',
                    'severity': 'MEDIUM',
                    'type': 'xml_parse',
                    'description': 'XML parsing (check for XXE protection)',
                    'recommendation': 'Use defusedxml library instead'
                },
                {
                    'pattern': r'xml\.sax\.parseString|xml\.dom\.minidom\.parse',
                    'severity': 'HIGH',
                    'type': 'unsafe_xml_parse',
                    'description': 'Unsafe XML parser',
                    'recommendation': 'Use defusedxml.sax or defusedxml.minidom'
                },
                {
                    'pattern': r'XMLParser\s*\([^)]*resolve_entities\s*=\s*True',
                    'severity': 'CRITICAL',
                    'type': 'xxe_enabled',
                    'description': 'XML entity resolution enabled',
                    'recommendation': 'Set resolve_entities=False'
                },
            ]
        },
        'javascript': {
            'ssrf': [
                {
                    'pattern': r'(?:axios|fetch|request|got|node-fetch)\s*(?:\(|\.(?:get|post))\s*(?:`[^`]*\$\{|[\'"][^\'"]*[\'"]\s*\+)',
                    'severity': 'HIGH',
                    'type': 'dynamic_url',
                    'description': 'Dynamic URL construction',
                    'recommendation': 'Validate and allowlist URLs'
                },
                {
                    'pattern': r'(?:axios|fetch|request)\s*\(\s*(?:req\.|request\.|params\.|query\.)',
                    'severity': 'CRITICAL',
                    'type': 'user_controlled_url',
                    'description': 'User-controlled URL in request',
                    'recommendation': 'Validate URL against allowlist'
                },
                {
                    'pattern': r'http\.(?:get|request)\s*\(\s*(?:req\.|options\.|params\.)',
                    'severity': 'HIGH',
                    'type': 'http_user_input',
                    'description': 'HTTP module with user input',
                    'recommendation': 'Validate and sanitize URL input'
                },
            ],
            'xxe': [
                {
                    'pattern': r'DOMParser\s*\(\s*\).*parseFromString',
                    'severity': 'MEDIUM',
                    'type': 'dom_parser',
                    'description': 'DOMParser usage (check DTD handling)',
                    'recommendation': 'Disable DTD processing'
                },
                {
                    'pattern': r'libxmljs|xml2js|fast-xml-parser',
                    'severity': 'MEDIUM',
                    'type': 'xml_library',
                    'description': 'XML parsing library',
                    'recommendation': 'Ensure external entities are disabled'
                },
            ]
        },
        'php': {
            'ssrf': [
                {
                    'pattern': r'(?:file_get_contents|fopen|curl_exec|curl_setopt)\s*\([^)]*\$_(?:GET|POST|REQUEST)',
                    'severity': 'CRITICAL',
                    'type': 'url_superglobal',
                    'description': 'URL function with superglobal',
                    'recommendation': 'Validate URLs against allowlist'
                },
                {
                    'pattern': r'curl_setopt\s*\([^,]+,\s*CURLOPT_URL\s*,\s*\$',
                    'severity': 'HIGH',
                    'type': 'curl_dynamic_url',
                    'description': 'cURL with variable URL',
                    'recommendation': 'Validate URL before use'
                },
            ],
            'xxe': [
                {
                    'pattern': r'(?:simplexml_load_string|simplexml_load_file|DOMDocument)\s*\(',
                    'severity': 'MEDIUM',
                    'type': 'xml_load',
                    'description': 'XML loading function',
                    'recommendation': 'Disable external entities: libxml_disable_entity_loader(true)'
                },
                {
                    'pattern': r'LIBXML_NOENT|LIBXML_DTDLOAD',
                    'severity': 'CRITICAL',
                    'type': 'xxe_enabled',
                    'description': 'XXE-enabling libxml flag',
                    'recommendation': 'Remove LIBXML_NOENT and LIBXML_DTDLOAD flags'
                },
            ]
        },
        'java': {
            'ssrf': [
                {
                    'pattern': r'new\s+URL\s*\([^)]*\+|URL.*request\.getParameter',
                    'severity': 'HIGH',
                    'type': 'url_user_input',
                    'description': 'URL with user input',
                    'recommendation': 'Validate URL against allowlist'
                },
                {
                    'pattern': r'HttpURLConnection|HttpClient.*request\.getParameter',
                    'severity': 'HIGH',
                    'type': 'http_user_input',
                    'description': 'HTTP connection with user input',
                    'recommendation': 'Implement URL validation'
                },
            ],
            'xxe': [
                {
                    'pattern': r'DocumentBuilderFactory\.newInstance\s*\(\s*\)',
                    'severity': 'MEDIUM',
                    'type': 'xml_factory',
                    'description': 'DocumentBuilderFactory without XXE protection',
                    'recommendation': 'Disable DTD and external entities'
                },
                {
                    'pattern': r'SAXParserFactory\.newInstance\s*\(\s*\)',
                    'severity': 'MEDIUM',
                    'type': 'sax_factory',
                    'description': 'SAXParserFactory without XXE protection',
                    'recommendation': 'Disable external entities'
                },
                {
                    'pattern': r'XMLInputFactory\.newInstance\s*\(\s*\)',
                    'severity': 'MEDIUM',
                    'type': 'stax_factory',
                    'description': 'XMLInputFactory without XXE protection',
                    'recommendation': 'Set supportDTD to false'
                },
                {
                    'pattern': r'setFeature\s*\(\s*[\'"]http://xml\.org.*[\'"]\s*,\s*true\s*\)',
                    'severity': 'HIGH',
                    'type': 'xxe_enabled',
                    'description': 'XML feature enabling external entities',
                    'recommendation': 'Set external entity features to false'
                },
            ]
        },
        'csharp': {
            'ssrf': [
                {
                    'pattern': r'(?:WebClient|HttpClient|WebRequest).*Request\[',
                    'severity': 'HIGH',
                    'type': 'http_user_input',
                    'description': 'HTTP client with user input',
                    'recommendation': 'Validate URL against allowlist'
                },
                {
                    'pattern': r'new\s+Uri\s*\([^)]*Request\[',
                    'severity': 'HIGH',
                    'type': 'uri_user_input',
                    'description': 'URI constructed from user input',
                    'recommendation': 'Validate and allowlist URLs'
                },
            ],
            'xxe': [
                {
                    'pattern': r'XmlDocument\s*\(\s*\)|XmlReader\.Create',
                    'severity': 'MEDIUM',
                    'type': 'xml_reader',
                    'description': 'XML parsing (check DTD settings)',
                    'recommendation': 'Set DtdProcessing to Prohibit'
                },
                {
                    'pattern': r'DtdProcessing\s*=\s*DtdProcessing\.Parse',
                    'severity': 'CRITICAL',
                    'type': 'dtd_enabled',
                    'description': 'DTD processing enabled',
                    'recommendation': 'Set DtdProcessing to Prohibit'
                },
                {
                    'pattern': r'XmlReaderSettings.*ProhibitDtd\s*=\s*false',
                    'severity': 'CRITICAL',
                    'type': 'xxe_enabled',
                    'description': 'XXE protection disabled',
                    'recommendation': 'Set ProhibitDtd to true'
                },
            ]
        },
        'ruby': {
            'ssrf': [
                {
                    'pattern': r'(?:open-uri|Net::HTTP|HTTParty|Faraday).*(?:params\[|request\.)',
                    'severity': 'HIGH',
                    'type': 'http_user_input',
                    'description': 'HTTP library with user input',
                    'recommendation': 'Validate URLs against allowlist'
                },
                {
                    'pattern': r'URI\.parse\s*\(\s*params\[',
                    'severity': 'HIGH',
                    'type': 'uri_user_input',
                    'description': 'URI parsed from user input',
                    'recommendation': 'Validate URL before parsing'
                },
            ],
            'xxe': [
                {
                    'pattern': r'Nokogiri::XML\s*\(',
                    'severity': 'MEDIUM',
                    'type': 'nokogiri_xml',
                    'description': 'Nokogiri XML parsing',
                    'recommendation': 'Use Nokogiri::XML::ParseOptions::NONET'
                },
                {
                    'pattern': r'REXML::Document\.new',
                    'severity': 'MEDIUM',
                    'type': 'rexml',
                    'description': 'REXML document parsing',
                    'recommendation': 'Disable external entity expansion'
                },
            ]
        }
    }

    def __init__(self):
        self.issues: List[SSRFXXEIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for lang, vuln_types in self.VULNERABILITY_PATTERNS.items():
            self.compiled_patterns[lang] = {'ssrf': [], 'xxe': []}
            for vuln_type in ['ssrf', 'xxe']:
                for p in vuln_types.get(vuln_type, []):
                    try:
                        self.compiled_patterns[lang][vuln_type].append({
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

    def scan_file(self, file_path: Path) -> List[SSRFXXEIssue]:
        """Scan a single file for SSRF and XXE vulnerabilities."""
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
            for vuln_type in ['ssrf', 'xxe']:
                for pattern_config in self.compiled_patterns[language][vuln_type]:
                    if pattern_config['regex'].search(line):
                        issue = SSRFXXEIssue(
                            file_path=str(file_path),
                            line_number=line_num,
                            vulnerability_type=vuln_type.upper(),
                            severity=pattern_config['severity'],
                            pattern_type=pattern_config['type'],
                            code_snippet=line.strip()[:150],
                            description=pattern_config['description'],
                            recommendation=pattern_config['recommendation']
                        )
                        issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[SSRFXXEIssue]:
        """Scan directory for SSRF and XXE vulnerabilities."""
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
            'by_vuln_type': {'SSRF': 0, 'XXE': 0},
            'by_pattern': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            summary['by_vuln_type'][issue.vulnerability_type] += 1
            if issue.pattern_type not in summary['by_pattern']:
                summary['by_pattern'][issue.pattern_type] = 0
            summary['by_pattern'][issue.pattern_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("SSRF & XXE VULNERABILITY SCAN")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nBy Vulnerability Type:")
            for vuln_type, count in summary['by_vuln_type'].items():
                if count > 0:
                    print(f"  {vuln_type}: {count}")

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
                print(f"\n[{issue.severity}] {issue.vulnerability_type} - {issue.pattern_type}")
                print(f"  File: {issue.file_path}:{issue.line_number}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No SSRF or XXE vulnerabilities detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan code for SSRF and XXE vulnerabilities'
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
    scanner = SSRFXXEScanner()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Scanning for SSRF/XXE: {target.absolute()}")

    if target.is_file():
        scanner.scan_file(target)
    else:
        recursive = not args.no_recursive
        scanner.scan_directory(target, recursive=recursive)

    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
