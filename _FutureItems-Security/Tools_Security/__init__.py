"""
Security Tools Suite
A comprehensive collection of cybersecurity checking tools.
"""

__version__ = "1.0.0"
__author__ = "Security Tools Suite"

from pathlib import Path

TOOLS_DIR = Path(__file__).parent

# Available tools
AVAILABLE_TOOLS = [
    'password_strength_checker',
    'secrets_scanner',
    'file_integrity_checker',
    'permission_auditor',
    'dependency_checker',
    'sql_injection_scanner',
    'xss_scanner',
    'encryption_analyzer',
    'hash_cracker',
    'port_scanner',
    'ssl_checker',
    'http_security_headers',
    'cors_checker',
    'dns_security_checker',
    'log_analyzer',
    'security_toolkit'
]
