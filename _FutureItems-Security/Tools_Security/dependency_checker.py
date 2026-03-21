#!/usr/bin/env python3
"""
Dependency Vulnerability Checker
Checks project dependencies for known vulnerabilities.
"""

import json
import os
import re
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Vulnerability:
    """Represents a dependency vulnerability."""
    package: str
    version: str
    vulnerability_id: str
    severity: str
    description: str
    fixed_version: Optional[str]


class DependencyChecker:
    """Checks dependencies for vulnerabilities."""

    def __init__(self):
        self.vulnerabilities: List[Vulnerability] = []
        self.dependencies: Dict[str, str] = {}
        self.project_type = None

    def detect_project_type(self, directory: Path) -> Optional[str]:
        """Detect the project type based on config files."""
        files = list(directory.iterdir())
        file_names = [f.name for f in files]

        if 'package.json' in file_names:
            return 'nodejs'
        elif 'requirements.txt' in file_names:
            return 'python-requirements'
        elif 'Pipfile' in file_names:
            return 'python-pipenv'
        elif 'pyproject.toml' in file_names:
            return 'python-poetry'
        elif 'Gemfile' in file_names:
            return 'ruby'
        elif 'go.mod' in file_names:
            return 'go'
        elif 'Cargo.toml' in file_names:
            return 'rust'
        elif 'composer.json' in file_names:
            return 'php'

        return None

    def parse_requirements_txt(self, file_path: Path) -> Dict[str, str]:
        """Parse Python requirements.txt file."""
        deps = {}

        try:
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue

                    # Parse package==version
                    match = re.match(r'^([a-zA-Z0-9_-]+)==([^\s;]+)', line)
                    if match:
                        deps[match.group(1).lower()] = match.group(2)
                    else:
                        # Package without version
                        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                        if match:
                            deps[match.group(1).lower()] = 'unknown'
        except IOError:
            pass

        return deps

    def parse_package_json(self, file_path: Path) -> Dict[str, str]:
        """Parse Node.js package.json file."""
        deps = {}

        try:
            with open(file_path) as f:
                data = json.load(f)

            # Combine dependencies and devDependencies
            for dep_type in ['dependencies', 'devDependencies']:
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        # Clean version string
                        version = version.lstrip('^~>=<')
                        deps[name.lower()] = version
        except (IOError, json.JSONDecodeError):
            pass

        return deps

    def parse_pipfile(self, file_path: Path) -> Dict[str, str]:
        """Parse Python Pipfile."""
        deps = {}

        try:
            with open(file_path) as f:
                content = f.read()

            # Simple TOML-like parsing for Pipfile
            in_packages = False
            for line in content.split('\n'):
                line = line.strip()
                if line == '[packages]' or line == '[dev-packages]':
                    in_packages = True
                    continue
                elif line.startswith('['):
                    in_packages = False
                    continue

                if in_packages and '=' in line:
                    parts = line.split('=', 1)
                    name = parts[0].strip().strip('"\'')
                    version = parts[1].strip().strip('"\'')
                    if version == '*':
                        version = 'latest'
                    deps[name.lower()] = version
        except IOError:
            pass

        return deps

    def load_dependencies(self, directory: Path) -> Dict[str, str]:
        """Load dependencies from project files."""
        self.project_type = self.detect_project_type(directory)

        if self.project_type == 'python-requirements':
            self.dependencies = self.parse_requirements_txt(directory / 'requirements.txt')
        elif self.project_type == 'nodejs':
            self.dependencies = self.parse_package_json(directory / 'package.json')
        elif self.project_type == 'python-pipenv':
            self.dependencies = self.parse_pipfile(directory / 'Pipfile')
        else:
            # Try common files
            for dep_file in ['requirements.txt', 'package.json', 'Pipfile']:
                dep_path = directory / dep_file
                if dep_path.exists():
                    if dep_file == 'requirements.txt':
                        self.dependencies = self.parse_requirements_txt(dep_path)
                        self.project_type = 'python-requirements'
                    elif dep_file == 'package.json':
                        self.dependencies = self.parse_package_json(dep_path)
                        self.project_type = 'nodejs'
                    elif dep_file == 'Pipfile':
                        self.dependencies = self.parse_pipfile(dep_path)
                        self.project_type = 'python-pipenv'
                    break

        return self.dependencies

    def check_npm_audit(self, directory: Path) -> List[Vulnerability]:
        """Run npm audit for Node.js projects."""
        vulns = []

        try:
            result = subprocess.run(
                ['npm', 'audit', '--json'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.stdout:
                data = json.loads(result.stdout)

                if 'vulnerabilities' in data:
                    for name, info in data['vulnerabilities'].items():
                        vuln = Vulnerability(
                            package=name,
                            version=info.get('range', 'unknown'),
                            vulnerability_id=info.get('via', [{}])[0].get('url', 'Unknown') if isinstance(info.get('via', [{}])[0], dict) else 'Unknown',
                            severity=info.get('severity', 'unknown').upper(),
                            description=info.get('via', [{}])[0].get('title', 'No description') if isinstance(info.get('via', [{}])[0], dict) else str(info.get('via', ['No description'])[0]),
                            fixed_version=info.get('fixAvailable', {}).get('version') if isinstance(info.get('fixAvailable'), dict) else None
                        )
                        vulns.append(vuln)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        return vulns

    def check_pip_audit(self, directory: Path) -> List[Vulnerability]:
        """Run pip-audit for Python projects (if available)."""
        vulns = []

        try:
            result = subprocess.run(
                ['pip-audit', '--format', 'json'],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.stdout:
                data = json.loads(result.stdout)

                for item in data:
                    for vuln_info in item.get('vulns', []):
                        vuln = Vulnerability(
                            package=item.get('name', 'unknown'),
                            version=item.get('version', 'unknown'),
                            vulnerability_id=vuln_info.get('id', 'Unknown'),
                            severity=vuln_info.get('severity', 'UNKNOWN').upper(),
                            description=vuln_info.get('description', 'No description')[:200],
                            fixed_version=vuln_info.get('fix_versions', [None])[0] if vuln_info.get('fix_versions') else None
                        )
                        vulns.append(vuln)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        return vulns

    def check_known_vulnerabilities(self) -> List[Vulnerability]:
        """Check against a basic list of known vulnerable packages."""
        vulns = []

        # Known vulnerable packages (simplified list)
        known_vulns = {
            # Python
            'django': {
                'versions': ['1.11', '2.0', '2.1'],
                'severity': 'HIGH',
                'description': 'Multiple security vulnerabilities in older Django versions',
                'fixed': '3.2+'
            },
            'flask': {
                'versions': ['0.12', '0.11', '0.10'],
                'severity': 'MEDIUM',
                'description': 'Security issues in older Flask versions',
                'fixed': '1.0+'
            },
            'requests': {
                'versions': ['2.19', '2.18', '2.17'],
                'severity': 'MEDIUM',
                'description': 'Potential security vulnerabilities',
                'fixed': '2.20+'
            },
            'pyyaml': {
                'versions': ['3.13', '3.12', '5.1'],
                'severity': 'CRITICAL',
                'description': 'Arbitrary code execution via yaml.load()',
                'fixed': '5.4+'
            },
            'urllib3': {
                'versions': ['1.24', '1.23', '1.22'],
                'severity': 'HIGH',
                'description': 'CRLF injection vulnerability',
                'fixed': '1.25+'
            },
            'pillow': {
                'versions': ['6.2', '5.4', '5.3'],
                'severity': 'HIGH',
                'description': 'Multiple buffer overflow vulnerabilities',
                'fixed': '7.1+'
            },
            # Node.js
            'lodash': {
                'versions': ['4.17.11', '4.17.10', '4.17.4'],
                'severity': 'HIGH',
                'description': 'Prototype pollution vulnerability',
                'fixed': '4.17.21+'
            },
            'axios': {
                'versions': ['0.18', '0.17', '0.16'],
                'severity': 'MEDIUM',
                'description': 'Server-Side Request Forgery',
                'fixed': '0.21+'
            },
            'minimist': {
                'versions': ['0.2.0', '0.1.0', '1.2.0'],
                'severity': 'MEDIUM',
                'description': 'Prototype pollution',
                'fixed': '1.2.6+'
            },
            'node-fetch': {
                'versions': ['2.6.0', '2.5.0'],
                'severity': 'MEDIUM',
                'description': 'Exposure of sensitive information',
                'fixed': '2.6.1+'
            }
        }

        for pkg_name, version in self.dependencies.items():
            if pkg_name in known_vulns:
                vuln_info = known_vulns[pkg_name]
                # Simple version check
                for vuln_version in vuln_info['versions']:
                    if version.startswith(vuln_version):
                        vuln = Vulnerability(
                            package=pkg_name,
                            version=version,
                            vulnerability_id=f'KNOWN-{pkg_name.upper()}',
                            severity=vuln_info['severity'],
                            description=vuln_info['description'],
                            fixed_version=vuln_info['fixed']
                        )
                        vulns.append(vuln)
                        break

        return vulns

    def check_dependencies(self, directory: Path) -> List[Vulnerability]:
        """Run all vulnerability checks."""
        self.load_dependencies(directory)
        all_vulns = []

        # Run project-specific checks
        if self.project_type == 'nodejs':
            all_vulns.extend(self.check_npm_audit(directory))
        elif self.project_type and 'python' in self.project_type:
            all_vulns.extend(self.check_pip_audit(directory))

        # Always check known vulnerabilities
        all_vulns.extend(self.check_known_vulnerabilities())

        # Deduplicate
        seen = set()
        unique_vulns = []
        for vuln in all_vulns:
            key = (vuln.package, vuln.version, vuln.vulnerability_id)
            if key not in seen:
                seen.add(key)
                unique_vulns.append(vuln)

        self.vulnerabilities = unique_vulns
        return unique_vulns

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_dependencies': len(self.dependencies),
            'total_vulnerabilities': len(self.vulnerabilities),
            'project_type': self.project_type,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'UNKNOWN': 0}
        }

        for vuln in self.vulnerabilities:
            severity = vuln.severity if vuln.severity in summary['by_severity'] else 'UNKNOWN'
            summary['by_severity'][severity] += 1

        return summary

    def print_report(self):
        """Print vulnerability report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("DEPENDENCY VULNERABILITY REPORT")
        print("=" * 70)

        print(f"\nProject Type: {summary['project_type'] or 'Unknown'}")
        print(f"Total Dependencies: {summary['total_dependencies']}")
        print(f"Vulnerabilities Found: {summary['total_vulnerabilities']}")

        if summary['total_vulnerabilities'] > 0:
            print("\nBy Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\n" + "-" * 70)
            print("VULNERABILITIES")
            print("-" * 70)

            # Sort by severity
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'UNKNOWN': 4}
            sorted_vulns = sorted(self.vulnerabilities, key=lambda x: severity_order.get(x.severity, 4))

            for vuln in sorted_vulns:
                print(f"\n[{vuln.severity}] {vuln.package}@{vuln.version}")
                print(f"  ID: {vuln.vulnerability_id}")
                print(f"  Description: {vuln.description}")
                if vuln.fixed_version:
                    print(f"  Fixed in: {vuln.fixed_version}")
        else:
            print("\n✓ No known vulnerabilities found!")

        if self.dependencies:
            print("\n" + "-" * 70)
            print("DEPENDENCIES CHECKED")
            print("-" * 70)
            for pkg, ver in sorted(self.dependencies.items()):
                print(f"  {pkg}: {ver}")

        print("\n" + "=" * 70)

        # Return exit code
        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Check dependencies for known vulnerabilities'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Project directory to check (default: current directory)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Export results to JSON file'
    )

    args = parser.parse_args()
    checker = DependencyChecker()

    directory = Path(args.path)
    if not directory.exists():
        print(f"Error: Directory not found: {args.path}")
        return 1

    print(f"Checking dependencies in: {directory.absolute()}")

    checker.check_dependencies(directory)
    exit_code = checker.print_report()

    if args.output:
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': checker.get_summary(),
            'vulnerabilities': [
                {
                    'package': v.package,
                    'version': v.version,
                    'id': v.vulnerability_id,
                    'severity': v.severity,
                    'description': v.description,
                    'fixed_version': v.fixed_version
                }
                for v in checker.vulnerabilities
            ]
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nResults exported to: {args.output}")

    return exit_code


if __name__ == '__main__':
    exit(main())
