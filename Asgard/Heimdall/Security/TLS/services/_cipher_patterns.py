"""
Heimdall Cipher Pattern Definitions

Pattern definitions for detecting weak cipher suite usage.
"""

import re
from typing import List

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class CipherPattern:
    """Defines a pattern for detecting weak cipher suites."""

    def __init__(
        self,
        name: str,
        pattern: str,
        cipher_name: str,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.85,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.cipher_name = cipher_name
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


CIPHER_PATTERNS: List[CipherPattern] = [
    CipherPattern(
        name="des_cipher",
        pattern=r'["\'](?:[^"\']*:)?DES(?:-CBC)?(?::[^"\']*)?["\']',
        cipher_name="DES",
        severity=SecuritySeverity.CRITICAL,
        title="DES Cipher Suite Used",
        description="DES is a weak cipher with only 56-bit key length and is easily broken.",
        cwe_id="CWE-327",
        remediation="Use AES-GCM or ChaCha20-Poly1305 cipher suites instead.",
        confidence=0.9,
    ),
    CipherPattern(
        name="3des_cipher",
        pattern=r'["\'](?:[^"\']*:)?3DES(?:-CBC)?(?::[^"\']*)?["\']',
        cipher_name="3DES",
        severity=SecuritySeverity.HIGH,
        title="3DES Cipher Suite Used",
        description="3DES is deprecated due to its 64-bit block size vulnerability (Sweet32 attack).",
        cwe_id="CWE-327",
        remediation="Use AES-GCM or ChaCha20-Poly1305 cipher suites instead.",
        confidence=0.9,
    ),
    CipherPattern(
        name="des_cbc3_cipher",
        pattern=r'["\'](?:[^"\']*:)?DES-CBC3(?::[^"\']*)?["\']',
        cipher_name="DES-CBC3",
        severity=SecuritySeverity.HIGH,
        title="DES-CBC3 Cipher Suite Used",
        description="DES-CBC3 (Triple DES) is deprecated and vulnerable to Sweet32 attack.",
        cwe_id="CWE-327",
        remediation="Use AES-GCM or ChaCha20-Poly1305 cipher suites instead.",
        confidence=0.9,
    ),
    CipherPattern(
        name="rc4_cipher",
        pattern=r'["\'](?:[^"\']*:)?RC4(?:-(?:SHA|MD5))?(?::[^"\']*)?["\']',
        cipher_name="RC4",
        severity=SecuritySeverity.CRITICAL,
        title="RC4 Cipher Suite Used",
        description="RC4 is broken and must not be used. Multiple attacks exist against it.",
        cwe_id="CWE-327",
        remediation="Use AES-GCM or ChaCha20-Poly1305 cipher suites instead.",
        confidence=0.95,
    ),
    CipherPattern(
        name="rc2_cipher",
        pattern=r'["\'](?:[^"\']*:)?RC2(?::[^"\']*)?["\']',
        cipher_name="RC2",
        severity=SecuritySeverity.CRITICAL,
        title="RC2 Cipher Suite Used",
        description="RC2 is a weak legacy cipher that should never be used.",
        cwe_id="CWE-327",
        remediation="Use AES-GCM or ChaCha20-Poly1305 cipher suites instead.",
        confidence=0.9,
    ),
    CipherPattern(
        name="null_cipher",
        # Match NULL/eNULL only in TLS cipher contexts - require colon prefix/suffix or eNULL form
        # Must have cipher-like context (uppercase letters with colons) to avoid matching 'null' strings
        pattern=r'["\'](?:[A-Z0-9!+@-]+:)+(?:eNULL|!?NULL)(?::[A-Z0-9!+@-]+)*["\']|["\'](?:eNULL|!?NULL)(?::[A-Z0-9!+@-]+)+["\']',
        cipher_name="NULL",
        severity=SecuritySeverity.CRITICAL,
        title="NULL Cipher Suite Used",
        description="NULL cipher provides no encryption, traffic is sent in plaintext.",
        cwe_id="CWE-319",
        remediation="Never use NULL ciphers. Use AES-GCM or ChaCha20-Poly1305 instead.",
        confidence=0.95,
    ),
    CipherPattern(
        name="export_cipher",
        # Match EXP-/EXPORT only in TLS cipher contexts (with colons or starting with EXP-)
        pattern=r'["\'](?:[A-Z0-9!+:-]*:)?(?:EXP-[A-Z0-9-]+|!?EXPORT)(?::[A-Z0-9!+:-]*)?["\']',
        cipher_name="EXPORT",
        severity=SecuritySeverity.CRITICAL,
        title="Export Cipher Suite Used",
        description="Export ciphers use weak 40-bit or 56-bit keys and are trivially breakable.",
        cwe_id="CWE-327",
        remediation="Never use export ciphers. Use modern cipher suites with 128+ bit keys.",
        confidence=0.95,
    ),
    CipherPattern(
        name="anon_cipher",
        pattern=r'["\'](?:[^"\']*:)?(?:aNULL|ADH|AECDH|anon)(?::[^"\']*)?["\']',
        cipher_name="Anonymous",
        severity=SecuritySeverity.CRITICAL,
        title="Anonymous Cipher Suite Used",
        description="Anonymous cipher suites provide no authentication, enabling MITM attacks.",
        cwe_id="CWE-287",
        remediation="Use authenticated cipher suites with proper certificate verification.",
        confidence=0.9,
    ),
    CipherPattern(
        name="md5_mac",
        pattern=r'["\'](?:[^"\']*:)?(?:[^"\']*-MD5)(?::[^"\']*)?["\']',
        cipher_name="MD5",
        severity=SecuritySeverity.HIGH,
        title="MD5 MAC Used in Cipher Suite",
        description="MD5 is cryptographically broken and should not be used for MAC.",
        cwe_id="CWE-328",
        remediation="Use cipher suites with SHA-256 or SHA-384 for message authentication.",
        confidence=0.85,
    ),
    CipherPattern(
        name="weak_dh",
        pattern=r'["\'](?:[^"\']*:)?(?:DHE?-(?:RSA|DSS)-(?:DES|3DES|RC4))(?::[^"\']*)?["\']',
        cipher_name="Weak DH",
        severity=SecuritySeverity.HIGH,
        title="Weak Diffie-Hellman Cipher Suite",
        description="Diffie-Hellman with weak underlying cipher or small parameters.",
        cwe_id="CWE-326",
        remediation="Use ECDHE with AES-GCM or ChaCha20-Poly1305.",
        confidence=0.85,
    ),
    CipherPattern(
        name="set_ciphers_weak",
        pattern=r'set_ciphers\s*\(\s*["\'][^"\']*(?:DES|3DES|RC4|RC2|NULL|EXPORT|anon)',
        cipher_name="Weak cipher in set_ciphers",
        severity=SecuritySeverity.HIGH,
        title="Weak Cipher in set_ciphers Call",
        description="SSL context set_ciphers includes weak cipher suites.",
        cwe_id="CWE-327",
        remediation="Use only strong ciphers: ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20",
        confidence=0.9,
    ),
]
