"""
Heimdall CLI - Security subparser setup.
"""

import argparse

from Asgard.Heimdall.cli.common import (
    add_security_args,
    add_config_secrets_args,
    add_hotspots_args,
    add_compliance_args,
    add_taint_args,
)


def setup_security_commands(subparsers) -> None:
    """Set up security command group."""
    security_parser = subparsers.add_parser(
        "security",
        help="Security vulnerability analysis (secrets, injections, crypto, auth, config, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security scan ./src\n"
            "  heimdall security secrets ./src --severity high\n"
            "  heimdall security config-secrets ./src --entropy-threshold 4.0\n"
            "  heimdall security vulnerabilities ./src --format json\n"
        ),
    )
    security_subparsers = security_parser.add_subparsers(dest="security_command", help="Security subcommand to run")

    for cmd, desc in [
        ("scan", "Run all security checks across all categories"),
        ("secrets", "Detect hardcoded secrets, tokens, and credentials in source code"),
        ("dependencies", "Scan third-party dependencies for known CVEs and vulnerabilities"),
        ("vulnerabilities", "Detect injection vulnerabilities (SQL, command, path traversal, etc.)"),
        ("crypto", "Validate cryptographic implementations for weak algorithms or misuse"),
        ("access", "Analyze access control patterns for missing or incorrectly applied checks"),
        ("auth", "Analyze authentication flows for common weaknesses"),
        ("headers", "Check HTTP response header configuration for security best practices"),
        ("tls", "Analyze TLS/SSL configuration for weak protocols or cipher suites"),
        ("container", "Audit container configuration for security misconfigurations"),
        ("infra", "Analyze infrastructure-as-code for security misconfigurations"),
    ]:
        sub = security_subparsers.add_parser(cmd, help=desc)
        add_security_args(sub)

    # Security config-secrets
    security_config_secrets = security_subparsers.add_parser(
        "config-secrets",
        help="Detect secrets, API keys, and sensitive values in config files using pattern matching and entropy analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security config-secrets ./src\n"
            "  heimdall security config-secrets ./src --severity high\n"
            "  heimdall security config-secrets ./src --entropy-threshold 4.0 --entropy-min-length 16\n"
            "  heimdall security config-secrets ./src --format json\n"
        ),
    )
    add_config_secrets_args(security_config_secrets)

    # Security hotspots
    security_hotspots = security_subparsers.add_parser(
        "hotspots",
        help="Detect security-sensitive code patterns requiring manual review (OWASP hotspot categories)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security hotspots ./src\n"
            "  heimdall security hotspots ./src --priority high\n"
            "  heimdall security hotspots ./src --format json\n"
        ),
    )
    add_hotspots_args(security_hotspots)

    # Security compliance
    security_compliance = security_subparsers.add_parser(
        "compliance",
        help="Generate OWASP Top 10 and CWE Top 25 compliance reports from security analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security compliance ./src\n"
            "  heimdall security compliance ./src --no-cwe\n"
            "  heimdall security compliance ./src --format markdown\n"
        ),
    )
    add_compliance_args(security_compliance)

    # Security taint
    security_taint = security_subparsers.add_parser(
        "taint",
        help="Perform taint analysis to track untrusted data to dangerous sinks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security taint ./src\n"
            "  heimdall security taint ./src --severity high\n"
            "  heimdall security taint ./src --format json\n"
        ),
    )
    add_taint_args(security_taint)
