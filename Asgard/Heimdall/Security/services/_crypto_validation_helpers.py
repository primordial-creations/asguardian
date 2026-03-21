"""
Heimdall Cryptographic Validation Service - Helper Functions

Standalone helper functions for false-positive filtering, severity
comparison, and secure cryptographic recommendations.
"""

import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


def is_in_test_context(
    file_path: Path,
    lines: List[str],
    line_number: int,
) -> bool:
    """
    Check if a finding is in a test context.

    Some weak crypto usage is acceptable in tests.

    Args:
        file_path: Path to the file
        lines: File content lines
        line_number: Line number of the finding

    Returns:
        True if the finding is in a test context
    """
    file_name = file_path.name.lower()
    if "test" in file_name or "_test" in file_name or "spec" in file_name:
        return False

    return False


def is_iv_nonce_false_positive(
    content: str,
    match_start: int,
    lines: List[str],
    line_number: int,
) -> bool:
    """
    Check if a static IV/nonce match is a false positive.

    Args:
        content: Full file content
        match_start: Start position of the match
        lines: File content as lines
        line_number: Line number of the match

    Returns:
        True if this appears to be a false positive
    """
    context_start = max(0, match_start - 200)
    context_end = min(len(content), match_start + 200)
    context = content[context_start:context_end]

    validation_patterns = [
        r"includes\s*\(",
        r"contains\s*\(",
        r"validate",
        r"check",
        r"verify",
        r"match\s*\(",
        r"test\s*\(",
        r"search\s*\(",
        r"indexOf\s*\(",
    ]

    for pattern in validation_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return True

    if re.search(r'\$\{[^}]+\}', context):
        return True

    if re.search(r'\{[a-z_][a-z_0-9]*\}', context, re.IGNORECASE):
        return True

    line = lines[line_number - 1] if line_number <= len(lines) else ""
    if re.search(r'(?:random|generate|create|crypto\.)', line, re.IGNORECASE):
        return True

    for i in range(line_number - 1, max(0, line_number - 20), -1):
        if i < len(lines):
            fn_line = lines[i].strip()
            if fn_line.startswith("def ") or fn_line.startswith("function ") or "=>" in fn_line:
                if re.search(r'generate|create|random', fn_line, re.IGNORECASE):
                    return True
                break

    return False


def severity_meets_threshold(severity: str, min_severity: str) -> bool:
    """Check if a severity level meets the configured threshold."""
    severity_order = {
        SecuritySeverity.INFO.value: 0,
        SecuritySeverity.LOW.value: 1,
        SecuritySeverity.MEDIUM.value: 2,
        SecuritySeverity.HIGH.value: 3,
        SecuritySeverity.CRITICAL.value: 4,
    }

    min_level = severity_order.get(min_severity, 1)
    finding_level = severity_order.get(severity, 1)

    return finding_level >= min_level


def severity_order(severity: str) -> int:
    """Get sort order for severity (critical first)."""
    order = {
        SecuritySeverity.CRITICAL.value: 0,
        SecuritySeverity.HIGH.value: 1,
        SecuritySeverity.MEDIUM.value: 2,
        SecuritySeverity.LOW.value: 3,
        SecuritySeverity.INFO.value: 4,
    }
    return order.get(severity, 5)


def get_secure_recommendations() -> dict:
    """
    Get recommendations for secure cryptographic implementations.

    Returns:
        Dictionary of recommendations by category
    """
    return {
        "hashing": {
            "general": "SHA-256 or SHA-3",
            "passwords": "Argon2id (preferred), bcrypt, or scrypt",
            "avoid": ["MD5", "SHA-1"],
        },
        "symmetric_encryption": {
            "recommended": "AES-256-GCM or ChaCha20-Poly1305",
            "key_size": "256 bits minimum",
            "mode": "GCM, CCM, or CBC with HMAC",
            "avoid": ["DES", "3DES", "ECB mode", "RC4"],
        },
        "asymmetric_encryption": {
            "rsa": "RSA-2048 minimum, RSA-4096 preferred",
            "ecc": "P-256, P-384, or Ed25519",
            "avoid": ["RSA-1024 or smaller", "DSA"],
        },
        "random_numbers": {
            "python": "secrets module",
            "javascript": "crypto.randomBytes or crypto.getRandomValues",
            "java": "SecureRandom",
            "avoid": ["random module", "Math.random()"],
        },
        "tls": {
            "minimum_version": "TLS 1.2",
            "preferred_version": "TLS 1.3",
            "verify_certificates": True,
            "avoid": ["SSL 2.0", "SSL 3.0", "TLS 1.0", "TLS 1.1"],
        },
        "jwt": {
            "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            "secret_size": "256 bits minimum for HS256",
            "avoid": ["none algorithm", "HS256 with weak secrets"],
        },
    }
