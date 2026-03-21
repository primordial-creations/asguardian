"""
Heimdall CLI - Management and utility subparser setup.

Re-exports all setup functions from _management_a and _management_b.
"""

from Asgard.Heimdall.cli.subparsers._management_a import (
    setup_baseline_commands,
    setup_init_linter_command,
    setup_ratings_command,
    setup_gate_command,
    setup_profiles_commands,
)
from Asgard.Heimdall.cli.subparsers._management_b import (
    setup_history_commands,
    setup_new_code_commands,
    setup_issues_command,
    setup_sbom_command,
    setup_codefix_command,
    setup_mcp_server_command,
    setup_dashboard_command,
)

__all__ = [
    "setup_baseline_commands",
    "setup_init_linter_command",
    "setup_ratings_command",
    "setup_gate_command",
    "setup_profiles_commands",
    "setup_history_commands",
    "setup_new_code_commands",
    "setup_issues_command",
    "setup_sbom_command",
    "setup_codefix_command",
    "setup_mcp_server_command",
    "setup_dashboard_command",
]
