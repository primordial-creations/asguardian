#!/usr/bin/env python3
"""
Security Tools API
Programmatic interface with JSON/SARIF output for CI/CD integration.
"""

import json
import argparse
import importlib.util
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ScanResult:
    """Standardized scan result."""
    tool: str
    file_path: str
    line_number: int
    severity: str
    issue_type: str
    description: str
    recommendation: str
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ScanReport:
    """Complete scan report."""
    tool: str
    target: str
    timestamp: str
    duration_ms: int
    total_issues: int
    by_severity: Dict[str, int]
    issues: List[Dict]

    def to_dict(self) -> Dict:
        return asdict(self)


class SecurityAPI:
    """Programmatic API for security scanning tools."""

    TOOLS = {
        'sqli': 'sql_injection_scanner',
        'xss': 'xss_scanner',
        'secrets': 'secrets_scanner',
        'cmdi': 'command_injection_scanner',
        'sensitive': 'sensitive_data_scanner',
        'redos': 'redos_scanner',
        'misconfig': 'security_misconfig_scanner',
        'validation': 'input_validation_scanner',
        'disclosure': 'info_disclosure_scanner',
        'race': 'race_condition_detector',
        'api': 'api_security_scanner',
        'frontend': 'frontend_security_scanner',
        'traversal': 'path_traversal_scanner',
        'ssrf': 'ssrf_scanner',
        'deserial': 'deserialization_scanner',
        'auth': 'auth_security_scanner',
        'malware': 'malware_scanner',
        'backdoor': 'backdoor_detector',
        'exfil': 'data_exfil_detector',
        'crypto': 'encryption_analyzer',
        'git': 'git_security_scanner',
    }

    def __init__(self):
        self.tools_dir = Path(__file__).parent

    def scan(self, tool: str, target: str) -> ScanReport:
        """
        Run a security scan and return structured results.

        Args:
            tool: Tool identifier (e.g., 'sqli', 'xss')
            target: File or directory path to scan

        Returns:
            ScanReport with all findings
        """
        if tool not in self.TOOLS:
            raise ValueError(f"Unknown tool: {tool}. Available: {list(self.TOOLS.keys())}")

        start_time = datetime.now()
        module_name = self.TOOLS[tool]

        # Load scanner module
        scanner = self._load_scanner(module_name)

        # Run scan
        target_path = Path(target)
        if target_path.is_file():
            issues = scanner.scan_file(target_path)
        else:
            issues = scanner.scan_directory(target_path)

        # Convert to standardized format
        standardized_issues = self._standardize_issues(tool, issues)

        # Calculate duration
        duration = int((datetime.now() - start_time).total_seconds() * 1000)

        # Build severity summary
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for issue in standardized_issues:
            severity = issue.get('severity', 'LOW')
            if severity in severity_counts:
                severity_counts[severity] += 1

        return ScanReport(
            tool=tool,
            target=str(target),
            timestamp=datetime.now().isoformat(),
            duration_ms=duration,
            total_issues=len(standardized_issues),
            by_severity=severity_counts,
            issues=standardized_issues
        )

    def scan_all(self, target: str, tools: Optional[List[str]] = None) -> Dict[str, ScanReport]:
        """
        Run multiple security scans.

        Args:
            target: File or directory path to scan
            tools: List of tools to run (default: all)

        Returns:
            Dictionary of tool -> ScanReport
        """
        if tools is None:
            tools = list(self.TOOLS.keys())

        results = {}
        for tool in tools:
            try:
                results[tool] = self.scan(tool, target)
            except Exception as e:
                results[tool] = ScanReport(
                    tool=tool,
                    target=str(target),
                    timestamp=datetime.now().isoformat(),
                    duration_ms=0,
                    total_issues=0,
                    by_severity={'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
                    issues=[{'error': str(e)}]
                )

        return results

    def _load_scanner(self, module_name: str):
        """Load a scanner module and return scanner instance."""
        module_path = self.tools_dir / f"{module_name}.py"

        if not module_path.exists():
            raise FileNotFoundError(f"Scanner module not found: {module_path}")

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find scanner class
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and name.endswith('Scanner') or name.endswith('Detector'):
                return obj()

        raise ValueError(f"No scanner class found in {module_name}")

    def _standardize_issues(self, tool: str, issues: List) -> List[Dict]:
        """Convert scanner-specific issues to standardized format."""
        standardized = []

        for issue in issues:
            std_issue = {
                'tool': tool,
                'file_path': getattr(issue, 'file_path', ''),
                'line_number': getattr(issue, 'line_number', 0),
                'severity': getattr(issue, 'severity', 'LOW'),
            }

            # Map various issue type fields
            for field in ['issue_type', 'pattern_type', 'secret_type', 'category']:
                if hasattr(issue, field):
                    std_issue['issue_type'] = getattr(issue, field)
                    break

            # Map description fields
            for field in ['description', 'message']:
                if hasattr(issue, field):
                    std_issue['description'] = getattr(issue, field)
                    break

            # Map recommendation fields
            for field in ['recommendation', 'fix', 'remediation']:
                if hasattr(issue, field):
                    std_issue['recommendation'] = getattr(issue, field)
                    break

            # Map code snippet
            for field in ['code_snippet', 'line', 'match']:
                if hasattr(issue, field):
                    std_issue['code_snippet'] = getattr(issue, field)
                    break

            standardized.append(std_issue)

        return standardized

    def to_json(self, report: ScanReport) -> str:
        """Convert report to JSON string."""
        return json.dumps(report.to_dict(), indent=2)

    def to_sarif(self, report: ScanReport) -> str:
        """
        Convert report to SARIF format for GitHub integration.

        SARIF (Static Analysis Results Interchange Format) is supported
        by GitHub Code Scanning.
        """
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": f"security-toolkit-{report.tool}",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/your-org/security-toolkit",
                        "rules": []
                    }
                },
                "results": []
            }]
        }

        rules = {}
        results = []

        for issue in report.issues:
            rule_id = issue.get('issue_type', 'unknown')

            # Add rule if not exists
            if rule_id not in rules:
                rules[rule_id] = {
                    "id": rule_id,
                    "shortDescription": {"text": issue.get('description', '')},
                    "helpUri": f"https://github.com/your-org/security-toolkit/wiki/{rule_id}",
                    "properties": {
                        "security-severity": self._severity_to_score(issue.get('severity', 'LOW'))
                    }
                }

            # Add result
            result = {
                "ruleId": rule_id,
                "level": self._severity_to_sarif_level(issue.get('severity', 'LOW')),
                "message": {
                    "text": f"{issue.get('description', '')}. {issue.get('recommendation', '')}"
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": issue.get('file_path', ''),
                            "uriBaseId": "%SRCROOT%"
                        },
                        "region": {
                            "startLine": issue.get('line_number', 1)
                        }
                    }
                }]
            }
            results.append(result)

        sarif["runs"][0]["tool"]["driver"]["rules"] = list(rules.values())
        sarif["runs"][0]["results"] = results

        return json.dumps(sarif, indent=2)

    def _severity_to_sarif_level(self, severity: str) -> str:
        """Convert severity to SARIF level."""
        mapping = {
            'CRITICAL': 'error',
            'HIGH': 'error',
            'MEDIUM': 'warning',
            'LOW': 'note'
        }
        return mapping.get(severity, 'note')

    def _severity_to_score(self, severity: str) -> str:
        """Convert severity to security score (0-10)."""
        mapping = {
            'CRITICAL': '9.0',
            'HIGH': '7.0',
            'MEDIUM': '5.0',
            'LOW': '3.0'
        }
        return mapping.get(severity, '3.0')


def main():
    parser = argparse.ArgumentParser(
        description='Security Tools API - JSON/SARIF output for CI/CD'
    )
    parser.add_argument(
        'tool',
        nargs='?',
        help='Tool to run (or "all" for all tools)'
    )
    parser.add_argument(
        'target',
        nargs='?',
        default='.',
        help='File or directory to scan'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'sarif'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file (default: stdout)'
    )
    parser.add_argument(
        '--tools',
        help='Comma-separated list of tools for "all" scan'
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List available tools'
    )
    parser.add_argument(
        '--min-severity',
        choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
        default='LOW',
        help='Minimum severity to report'
    )

    args = parser.parse_args()
    api = SecurityAPI()

    if args.list:
        print("Available tools:")
        for tool_id in sorted(api.TOOLS.keys()):
            print(f"  {tool_id}")
        return 0

    if not args.tool:
        parser.print_help()
        return 1

    # Run scan(s)
    if args.tool == 'all':
        tools = args.tools.split(',') if args.tools else None
        results = api.scan_all(args.target, tools)

        # Combine all results
        combined = {
            'timestamp': datetime.now().isoformat(),
            'target': args.target,
            'scans': {k: v.to_dict() for k, v in results.items()}
        }
        output = json.dumps(combined, indent=2)
    else:
        report = api.scan(args.tool, args.target)

        if args.format == 'sarif':
            output = api.to_sarif(report)
        else:
            output = api.to_json(report)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Results written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
