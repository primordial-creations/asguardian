"""
Heimdall Security TLS SSL Utilities

Helper functions for TLS/SSL security analysis.
"""

import re
from typing import List, Optional, Tuple


def find_ssl_context_creation(content: str) -> List[Tuple[int, str, str]]:
    """
    Find SSL context creation patterns in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, context_type, matched_text) tuples
    """
    patterns = [
        (r'ssl\.SSLContext\s*\([^)]*', "ssl_context"),
        (r'ssl\.create_default_context\s*\([^)]*', "default_context"),
        (r'ssl\.wrap_socket\s*\([^)]*', "wrap_socket"),
        (r'ssl\._create_unverified_context\s*\([^)]*', "unverified_context"),
        (r'ssl\._create_default_https_context\s*=', "https_context_override"),
        (r'urllib3\.disable_warnings\s*\([^)]*', "urllib3_warnings_disabled"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, context_type in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                matches.append((i, context_type, match.group(0)))

    return matches


def find_verify_false_patterns(content: str) -> List[Tuple[int, str, str]]:
    """
    Find patterns where SSL/TLS verification is disabled.

    Args:
        content: Source code content

    Returns:
        List of (line_number, pattern_type, context) tuples
    """
    patterns = [
        (r'verify\s*=\s*False', "verify_false"),
        (r'verify_ssl\s*=\s*False', "verify_ssl_false"),
        (r'ssl_verify\s*=\s*False', "ssl_verify_false"),
        (r'cert_reqs\s*=\s*ssl\.CERT_NONE', "cert_none"),
        (r'cert_reqs\s*=\s*CERT_NONE', "cert_none"),
        (r'check_hostname\s*=\s*False', "hostname_check_false"),
        (r'verify_mode\s*=\s*ssl\.CERT_NONE', "verify_mode_none"),
        (r'ssl\._create_unverified_context', "unverified_context"),
        (r'InsecureRequestWarning', "insecure_warning_suppressed"),
        (r'urllib3\.disable_warnings', "warnings_disabled"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, pattern_type in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 2)
                context = "\n".join(lines[context_start:context_end])
                matches.append((i, pattern_type, context))

    return matches


def find_tls_version_usage(content: str) -> List[Tuple[int, str, str]]:
    """
    Find TLS/SSL version specifications in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, version, context) tuples
    """
    version_patterns = [
        (r'ssl\.PROTOCOL_SSLv2', "SSLv2"),
        (r'ssl\.PROTOCOL_SSLv3', "SSLv3"),
        (r'ssl\.PROTOCOL_SSLv23', "SSLv23"),
        (r'ssl\.PROTOCOL_TLS', "TLS"),
        (r'ssl\.PROTOCOL_TLSv1\b', "TLSv1.0"),
        (r'ssl\.PROTOCOL_TLSv1_1', "TLSv1.1"),
        (r'ssl\.PROTOCOL_TLSv1_2', "TLSv1.2"),
        (r'ssl\.TLSVersion\.TLSv1\b', "TLSv1.0"),
        (r'ssl\.TLSVersion\.TLSv1_1', "TLSv1.1"),
        (r'ssl\.TLSVersion\.TLSv1_2', "TLSv1.2"),
        (r'ssl\.TLSVersion\.TLSv1_3', "TLSv1.3"),
        (r'TLS_1_0\b', "TLSv1.0"),
        (r'TLS_1_1\b', "TLSv1.1"),
        (r'TLS_1_2\b', "TLSv1.2"),
        (r'TLS_1_3\b', "TLSv1.3"),
        (r'minimum_version\s*=\s*ssl\.TLSVersion\.TLSv1\b', "TLSv1.0"),
        (r'minimum_version\s*=\s*ssl\.TLSVersion\.TLSv1_1', "TLSv1.1"),
        (r'tls_version\s*=\s*["\']TLSv1\b', "TLSv1.0"),
        (r'tls_version\s*=\s*["\']TLSv1\.0', "TLSv1.0"),
        (r'tls_version\s*=\s*["\']TLSv1\.1', "TLSv1.1"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, version in version_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                matches.append((i, version, line.strip()))

    return matches


def find_cipher_suite_usage(content: str) -> List[Tuple[int, str, str]]:
    """
    Find cipher suite specifications in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, cipher, context) tuples
    """
    cipher_patterns = [
        r'set_ciphers\s*\(["\']([^"\']+)["\']',
        r'ciphers\s*=\s*["\']([^"\']+)["\']',
        r'cipher_list\s*=\s*["\']([^"\']+)["\']',
        r'ssl_cipher\s*=\s*["\']([^"\']+)["\']',
        r'SSL_CIPHER\s*=\s*["\']([^"\']+)["\']',
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern in cipher_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                cipher_string = match.group(1)
                matches.append((i, cipher_string, line.strip()))

    return matches


def is_weak_cipher(cipher_string: str) -> Tuple[bool, List[str]]:
    """
    Check if a cipher string contains weak ciphers.

    Args:
        cipher_string: Cipher suite specification string

    Returns:
        Tuple of (is_weak, list of weak ciphers found)
    """
    weak_patterns = [
        "DES",
        "3DES",
        "RC4",
        "RC2",
        "MD5",
        "NULL",
        "EXPORT",
        "anon",
        "ADH",
        "AECDH",
        "DES-CBC",
        "DES-CBC3",
        "RC4-SHA",
        "RC4-MD5",
        "EXP-",
        "eNULL",
        "aNULL",
    ]

    weak_found = []
    cipher_upper = cipher_string.upper()

    for weak in weak_patterns:
        if weak.upper() in cipher_upper:
            weak_found.append(weak)

    return len(weak_found) > 0, weak_found


def is_deprecated_protocol(version: str) -> bool:
    """
    Check if a TLS/SSL version is deprecated.

    Args:
        version: Protocol version string

    Returns:
        True if the protocol is deprecated
    """
    deprecated = {
        "SSLv2",
        "SSLv3",
        "SSLv23",
        "TLSv1",
        "TLSv1.0",
        "TLSv1.1",
        "TLS_1_0",
        "TLS_1_1",
    }

    return version in deprecated


def find_certificate_patterns(content: str) -> List[Tuple[int, str, str]]:
    """
    Find certificate-related patterns in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, pattern_type, context) tuples
    """
    patterns = [
        (r'load_cert_chain\s*\([^)]*', "load_cert_chain"),
        (r'load_verify_locations\s*\([^)]*', "load_verify_locations"),
        (r'ca_certs\s*=\s*["\'][^"\']+["\']', "ca_certs"),
        (r'certfile\s*=\s*["\'][^"\']+["\']', "certfile"),
        (r'keyfile\s*=\s*["\'][^"\']+["\']', "keyfile"),
        (r'-----BEGIN CERTIFICATE-----', "inline_certificate"),
        (r'-----BEGIN RSA PRIVATE KEY-----', "inline_private_key"),
        (r'-----BEGIN PRIVATE KEY-----', "inline_private_key"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, pattern_type in patterns:
            match = re.search(pattern, line)
            if match:
                matches.append((i, pattern_type, line.strip()))

    return matches


def extract_protocol_from_context(code: str) -> Optional[str]:
    """
    Extract the protocol version from an SSL context creation.

    Args:
        code: Code snippet containing SSL context

    Returns:
        Protocol version if found, None otherwise
    """
    protocol_patterns = [
        r'ssl\.PROTOCOL_(\w+)',
        r'ssl\.TLSVersion\.(\w+)',
        r'protocol\s*=\s*ssl\.PROTOCOL_(\w+)',
        r'ssl_version\s*=\s*ssl\.PROTOCOL_(\w+)',
    ]

    for pattern in protocol_patterns:
        match = re.search(pattern, code, re.IGNORECASE)
        if match:
            return match.group(1)

    return None
