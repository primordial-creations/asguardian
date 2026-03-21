"""
Heimdall Protocol Pattern Definitions

Pattern definitions for detecting deprecated TLS/SSL protocol usage.
"""

import re
from typing import List

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class ProtocolPattern:
    """Defines a pattern for detecting deprecated TLS/SSL protocols."""

    def __init__(
        self,
        name: str,
        pattern: str,
        protocol_version: str,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.85,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.protocol_version = protocol_version
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


PROTOCOL_PATTERNS: List[ProtocolPattern] = [
    ProtocolPattern(
        name="sslv2_usage",
        pattern=r'ssl\.PROTOCOL_SSLv2',
        protocol_version="SSLv2",
        severity=SecuritySeverity.CRITICAL,
        title="SSLv2 Protocol Used",
        description="SSLv2 is severely broken and should never be used. It is vulnerable to multiple attacks.",
        cwe_id="CWE-327",
        remediation="Use TLS 1.2 or TLS 1.3 instead. Remove all SSLv2 references.",
        confidence=0.95,
    ),
    ProtocolPattern(
        name="sslv3_usage",
        pattern=r'ssl\.PROTOCOL_SSLv3',
        protocol_version="SSLv3",
        severity=SecuritySeverity.CRITICAL,
        title="SSLv3 Protocol Used",
        description="SSLv3 is vulnerable to POODLE attack and other security issues.",
        cwe_id="CWE-327",
        remediation="Use TLS 1.2 or TLS 1.3 instead. Remove all SSLv3 references.",
        confidence=0.95,
    ),
    ProtocolPattern(
        name="tlsv1_usage",
        pattern=r'ssl\.PROTOCOL_TLSv1\b',
        protocol_version="TLSv1.0",
        severity=SecuritySeverity.HIGH,
        title="TLS 1.0 Protocol Used",
        description="TLS 1.0 is deprecated and vulnerable to BEAST and other attacks.",
        cwe_id="CWE-327",
        remediation="Use TLS 1.2 or TLS 1.3 instead. TLS 1.0 is deprecated by RFC 8996.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="tlsv1_1_usage",
        pattern=r'ssl\.PROTOCOL_TLSv1_1',
        protocol_version="TLSv1.1",
        severity=SecuritySeverity.HIGH,
        title="TLS 1.1 Protocol Used",
        description="TLS 1.1 is deprecated and no longer considered secure.",
        cwe_id="CWE-327",
        remediation="Use TLS 1.2 or TLS 1.3 instead. TLS 1.1 is deprecated by RFC 8996.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="tls_version_tlsv1",
        pattern=r'ssl\.TLSVersion\.TLSv1\b',
        protocol_version="TLSv1.0",
        severity=SecuritySeverity.HIGH,
        title="TLS 1.0 Version Specified",
        description="TLS 1.0 is deprecated and should not be used.",
        cwe_id="CWE-327",
        remediation="Use TLSVersion.TLSv1_2 or TLSVersion.TLSv1_3 instead.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="tls_version_tlsv1_1",
        pattern=r'ssl\.TLSVersion\.TLSv1_1',
        protocol_version="TLSv1.1",
        severity=SecuritySeverity.HIGH,
        title="TLS 1.1 Version Specified",
        description="TLS 1.1 is deprecated and should not be used.",
        cwe_id="CWE-327",
        remediation="Use TLSVersion.TLSv1_2 or TLSVersion.TLSv1_3 instead.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="minimum_version_tlsv1",
        pattern=r'minimum_version\s*=\s*ssl\.TLSVersion\.TLSv1\b',
        protocol_version="TLSv1.0",
        severity=SecuritySeverity.HIGH,
        title="Minimum TLS Version Set to 1.0",
        description="Minimum TLS version is set to deprecated TLS 1.0.",
        cwe_id="CWE-327",
        remediation="Set minimum_version to TLSVersion.TLSv1_2 or higher.",
        confidence=0.95,
    ),
    ProtocolPattern(
        name="minimum_version_tlsv1_1",
        pattern=r'minimum_version\s*=\s*ssl\.TLSVersion\.TLSv1_1',
        protocol_version="TLSv1.1",
        severity=SecuritySeverity.HIGH,
        title="Minimum TLS Version Set to 1.1",
        description="Minimum TLS version is set to deprecated TLS 1.1.",
        cwe_id="CWE-327",
        remediation="Set minimum_version to TLSVersion.TLSv1_2 or higher.",
        confidence=0.95,
    ),
    ProtocolPattern(
        name="pyopenssl_sslv2",
        pattern=r'SSLv2_METHOD',
        protocol_version="SSLv2",
        severity=SecuritySeverity.CRITICAL,
        title="OpenSSL SSLv2 Method Used",
        description="SSLv2 method from PyOpenSSL is critically insecure.",
        cwe_id="CWE-327",
        remediation="Use TLS_METHOD or TLS_CLIENT_METHOD with modern TLS versions.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="pyopenssl_sslv3",
        pattern=r'SSLv3_METHOD',
        protocol_version="SSLv3",
        severity=SecuritySeverity.CRITICAL,
        title="OpenSSL SSLv3 Method Used",
        description="SSLv3 method from PyOpenSSL is vulnerable to POODLE.",
        cwe_id="CWE-327",
        remediation="Use TLS_METHOD or TLS_CLIENT_METHOD with modern TLS versions.",
        confidence=0.9,
    ),
    ProtocolPattern(
        name="pyopenssl_tlsv1",
        pattern=r'TLSv1_METHOD\b',
        protocol_version="TLSv1.0",
        severity=SecuritySeverity.HIGH,
        title="OpenSSL TLSv1 Method Used",
        description="TLSv1 method from PyOpenSSL uses deprecated TLS 1.0.",
        cwe_id="CWE-327",
        remediation="Use TLS_METHOD with minimum version set to TLS 1.2.",
        confidence=0.85,
    ),
]
