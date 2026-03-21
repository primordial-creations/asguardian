#!/usr/bin/env python3
"""
Security Toolkit
Unified interface for all security checking tools.
"""

import argparse
import sys
import importlib.util
from pathlib import Path
from datetime import datetime


class SecurityToolkit:
    """Main interface for security tools."""

    TOOLS = {
        'password': {
            'module': 'password_strength_checker',
            'name': 'Password Strength Checker',
            'description': 'Analyze password strength and security',
            'category': 'Credentials'
        },
        'secrets': {
            'module': 'secrets_scanner',
            'name': 'Secrets Scanner',
            'description': 'Scan for exposed secrets and API keys',
            'category': 'Credentials'
        },
        'integrity': {
            'module': 'file_integrity_checker',
            'name': 'File Integrity Checker',
            'description': 'Create and verify file checksums',
            'category': 'File Security'
        },
        'permissions': {
            'module': 'permission_auditor',
            'name': 'Permission Auditor',
            'description': 'Audit file and directory permissions',
            'category': 'File Security'
        },
        'dependencies': {
            'module': 'dependency_checker',
            'name': 'Dependency Checker',
            'description': 'Check dependencies for vulnerabilities',
            'category': 'Code Security'
        },
        'sqli': {
            'module': 'sql_injection_scanner',
            'name': 'SQL Injection Scanner',
            'description': 'Scan code for SQL injection vulnerabilities',
            'category': 'Code Security'
        },
        'xss': {
            'module': 'xss_scanner',
            'name': 'XSS Scanner',
            'description': 'Scan code for XSS vulnerabilities',
            'category': 'Code Security'
        },
        'crypto': {
            'module': 'encryption_analyzer',
            'name': 'Encryption Analyzer',
            'description': 'Find weak cryptographic implementations',
            'category': 'Cryptography'
        },
        'hash': {
            'module': 'hash_cracker',
            'name': 'Hash Analyzer',
            'description': 'Identify and analyze password hashes',
            'category': 'Cryptography'
        },
        'ports': {
            'module': 'port_scanner',
            'name': 'Port Scanner',
            'description': 'Scan for open ports on hosts',
            'category': 'Network'
        },
        'ssl': {
            'module': 'ssl_checker',
            'name': 'SSL/TLS Checker',
            'description': 'Analyze SSL certificate security',
            'category': 'Network'
        },
        'headers': {
            'module': 'http_security_headers',
            'name': 'HTTP Security Headers',
            'description': 'Check HTTP security headers',
            'category': 'Web Security'
        },
        'cors': {
            'module': 'cors_checker',
            'name': 'CORS Checker',
            'description': 'Test for CORS misconfigurations',
            'category': 'Web Security'
        },
        'dns': {
            'module': 'dns_security_checker',
            'name': 'DNS Security Checker',
            'description': 'Analyze DNS security configuration',
            'category': 'Network'
        },
        'logs': {
            'module': 'log_analyzer',
            'name': 'Log Analyzer',
            'description': 'Analyze logs for security events',
            'category': 'Monitoring'
        },
        # Advanced Defensive Security Tools
        'malware': {
            'module': 'malware_scanner',
            'name': 'Malware Scanner',
            'description': 'Detect malware signatures and suspicious patterns',
            'category': 'Malware Detection'
        },
        'exfil': {
            'module': 'data_exfil_detector',
            'name': 'Data Exfiltration Detector',
            'description': 'Detect data exfiltration patterns',
            'category': 'Malware Detection'
        },
        'backdoor': {
            'module': 'backdoor_detector',
            'name': 'Backdoor Detector',
            'description': 'Detect backdoors and web shells',
            'category': 'Malware Detection'
        },
        'cmdi': {
            'module': 'command_injection_scanner',
            'name': 'Command Injection Scanner',
            'description': 'Detect OS command injection vulnerabilities',
            'category': 'Code Security'
        },
        'ssrf': {
            'module': 'ssrf_scanner',
            'name': 'SSRF/XXE Scanner',
            'description': 'Detect SSRF and XXE vulnerabilities',
            'category': 'Code Security'
        },
        'deserial': {
            'module': 'deserialization_scanner',
            'name': 'Deserialization Scanner',
            'description': 'Detect insecure deserialization',
            'category': 'Code Security'
        },
        'auth': {
            'module': 'auth_security_scanner',
            'name': 'Auth Security Scanner',
            'description': 'Detect authentication/session issues',
            'category': 'Authentication'
        },
        'container': {
            'module': 'container_security_scanner',
            'name': 'Container Security Scanner',
            'description': 'Scan Docker/K8s configs for issues',
            'category': 'Container Security'
        },
        'traversal': {
            'module': 'path_traversal_scanner',
            'name': 'Path Traversal Scanner',
            'description': 'Detect directory traversal vulnerabilities',
            'category': 'Code Security'
        },
        # E2E Codebase Security Tools
        'frontend': {
            'module': 'frontend_security_scanner',
            'name': 'Frontend Security Scanner',
            'description': 'Scan for DOM XSS, prototype pollution, postMessage issues',
            'category': 'Web Security'
        },
        'api': {
            'module': 'api_security_scanner',
            'name': 'API Security Scanner',
            'description': 'Detect REST/GraphQL security issues',
            'category': 'Web Security'
        },
        'sensitive': {
            'module': 'sensitive_data_scanner',
            'name': 'Sensitive Data Scanner',
            'description': 'Detect exposed PII and sensitive data',
            'category': 'Data Protection'
        },
        'redos': {
            'module': 'redos_scanner',
            'name': 'ReDoS Scanner',
            'description': 'Detect regex denial of service vulnerabilities',
            'category': 'Code Security'
        },
        'misconfig': {
            'module': 'security_misconfig_scanner',
            'name': 'Security Misconfiguration Scanner',
            'description': 'Detect security misconfigurations',
            'category': 'Configuration'
        },
        'validation': {
            'module': 'input_validation_scanner',
            'name': 'Input Validation Scanner',
            'description': 'Detect missing input validation',
            'category': 'Code Security'
        },
        'disclosure': {
            'module': 'info_disclosure_scanner',
            'name': 'Information Disclosure Scanner',
            'description': 'Detect information disclosure vulnerabilities',
            'category': 'Data Protection'
        },
        'race': {
            'module': 'race_condition_detector',
            'name': 'Race Condition Detector',
            'description': 'Detect race conditions and TOCTOU issues',
            'category': 'Code Security'
        },
        'git': {
            'module': 'git_security_scanner',
            'name': 'Git Security Scanner',
            'description': 'Scan git repos for security issues',
            'category': 'Repository Security'
        }
    }

    def __init__(self):
        self.tools_dir = Path(__file__).parent

    def list_tools(self):
        """List all available tools."""
        print("\n" + "=" * 70)
        print("SECURITY TOOLKIT - AVAILABLE TOOLS")
        print("=" * 70)

        # Group by category
        categories = {}
        for tool_id, tool_info in self.TOOLS.items():
            category = tool_info['category']
            if category not in categories:
                categories[category] = []
            categories[category].append((tool_id, tool_info))

        for category in sorted(categories.keys()):
            print(f"\n{category}:")
            print("-" * 40)
            for tool_id, tool_info in categories[category]:
                print(f"  {tool_id:<15} {tool_info['name']}")
                print(f"  {' '*15} {tool_info['description']}")
                print()

        print("=" * 70)
        print("\nUsage: python security_toolkit.py <tool> [options]")
        print("Example: python security_toolkit.py secrets .")
        print("         python security_toolkit.py ssl example.com")
        print("\nFor tool-specific help: python security_toolkit.py <tool> --help")
        print("=" * 70)

    def run_tool(self, tool_id: str, args: list):
        """Run a specific tool with arguments."""
        if tool_id not in self.TOOLS:
            print(f"Error: Unknown tool '{tool_id}'")
            print(f"Run 'python security_toolkit.py --list' to see available tools")
            return 1

        tool_info = self.TOOLS[tool_id]
        module_name = tool_info['module']
        module_path = self.tools_dir / f"{module_name}.py"

        if not module_path.exists():
            print(f"Error: Tool module not found: {module_path}")
            return 1

        # Load and run the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)

        # Set up sys.argv for the tool
        old_argv = sys.argv
        sys.argv = [str(module_path)] + args

        try:
            spec.loader.exec_module(module)
            if hasattr(module, 'main'):
                return module.main()
        except SystemExit as e:
            return e.code if e.code is not None else 0
        finally:
            sys.argv = old_argv

        return 0

    def run_audit(self, target_path: str):
        """Run a comprehensive security audit."""
        print("\n" + "=" * 70)
        print("COMPREHENSIVE SECURITY AUDIT")
        print("=" * 70)
        print(f"\nTarget: {target_path}")
        print(f"Started: {datetime.now().isoformat()}")

        results = {}
        audit_tools = [
            ('secrets', 'Scanning for secrets...'),
            ('sensitive', 'Scanning for sensitive data exposure...'),
            ('permissions', 'Auditing permissions...'),
            ('dependencies', 'Checking dependencies...'),
            ('sqli', 'Scanning for SQL injection...'),
            ('xss', 'Scanning for XSS...'),
            ('frontend', 'Scanning frontend for security issues...'),
            ('api', 'Scanning API for security issues...'),
            ('cmdi', 'Scanning for command injection...'),
            ('ssrf', 'Scanning for SSRF/XXE...'),
            ('deserial', 'Scanning for insecure deserialization...'),
            ('traversal', 'Scanning for path traversal...'),
            ('validation', 'Scanning for input validation issues...'),
            ('auth', 'Scanning for auth/session issues...'),
            ('crypto', 'Analyzing encryption...'),
            ('malware', 'Scanning for malware...'),
            ('backdoor', 'Scanning for backdoors...'),
            ('exfil', 'Scanning for data exfiltration...'),
            ('redos', 'Scanning for ReDoS vulnerabilities...'),
            ('race', 'Detecting race conditions...'),
            ('misconfig', 'Scanning for misconfigurations...'),
            ('disclosure', 'Scanning for information disclosure...'),
            ('git', 'Scanning git repository for security issues...'),
        ]

        for tool_id, message in audit_tools:
            print(f"\n{message}")
            print("-" * 40)
            try:
                exit_code = self.run_tool(tool_id, [target_path])
                results[tool_id] = {
                    'status': 'PASS' if exit_code == 0 else 'ISSUES',
                    'exit_code': exit_code
                }
            except Exception as e:
                results[tool_id] = {
                    'status': 'ERROR',
                    'error': str(e)
                }

        # Print summary
        print("\n" + "=" * 70)
        print("AUDIT SUMMARY")
        print("=" * 70)

        total_issues = 0
        for tool_id, result in results.items():
            status = result['status']
            status_symbol = '✓' if status == 'PASS' else '✗' if status == 'ISSUES' else '!'
            tool_name = self.TOOLS[tool_id]['name']
            print(f"{status_symbol} {tool_name}: {status}")
            if result.get('exit_code', 0) > 0:
                total_issues += 1

        print("\n" + "=" * 70)
        print(f"Completed: {datetime.now().isoformat()}")

        if total_issues == 0:
            print("\n✓ All security checks passed!")
        else:
            print(f"\n⚠ {total_issues} tool(s) found security issues")

        return 1 if total_issues > 0 else 0


def main():
    parser = argparse.ArgumentParser(
        description='Security Toolkit - Unified security checking tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python security_toolkit.py --list              List all tools
  python security_toolkit.py secrets .           Scan for secrets
  python security_toolkit.py ssl example.com     Check SSL certificate
  python security_toolkit.py --audit .           Run full security audit
        '''
    )
    parser.add_argument(
        'tool',
        nargs='?',
        help='Tool to run'
    )
    parser.add_argument(
        'args',
        nargs='*',
        help='Arguments to pass to the tool'
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all available tools'
    )
    parser.add_argument(
        '--audit',
        metavar='PATH',
        help='Run comprehensive security audit on path'
    )

    # Parse only known args to allow tool-specific args to pass through
    args, unknown = parser.parse_known_args()
    toolkit = SecurityToolkit()

    if args.list:
        toolkit.list_tools()
        return 0

    if args.audit:
        return toolkit.run_audit(args.audit)

    if not args.tool:
        toolkit.list_tools()
        return 0

    # Combine args and unknown for tool
    tool_args = args.args + unknown

    return toolkit.run_tool(args.tool, tool_args)


if __name__ == '__main__':
    sys.exit(main())
