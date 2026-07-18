"""
Heimdall Secrets Detection Service - Helper Functions

Standalone helper functions for false-positive filtering, confidence
calculation, severity comparison, and secret value sanitization.
"""

from typing import List, Optional

from Asgard.Heimdall.Security.models.security_models import SecretType, SecuritySeverity
from Asgard.Heimdall.Security.services._secret_patterns import (
    FALSE_POSITIVE_PATTERNS,
    SecretPattern,
)
from Asgard.Heimdall.Security.utilities.security_utils import mask_secret


def is_false_positive(
    secret_value: str,
    matched_text: str,
    content: str,
    match_start: int,
) -> bool:
    """
    Check if the matched VALUE itself is a placeholder/dummy secret and
    should be dropped outright (never reported).

    Adversarial-review fix (BLOCKER-3): this used to ALSO full-drop any
    match with "example"/"sample" wording or an os.environ/getenv call
    anywhere within a 100-char window of the match -- regardless of
    whether that context word/call had anything to do with the matched
    value. That silently dropped real secrets, e.g.:

        os.environ.get("DB_HOST")           # unrelated env lookup
        aws_secret_access_key = "wJalr..."  # real key, 100 chars later

    A docstring promise elsewhere in this module ("never disappears,
    floor keeps it visible") was being violated by this full-drop path.
    This function is now scoped to the VALUE only: it drops a match only
    when the matched value (or its own regex-matched text) literally
    looks like a placeholder/dummy (e.g. "your_key_here", "XXXX",
    "example_secret", a template `${VAR}` / `<PLACEHOLDER>` token, or a
    bare generic word like "password"). Proximity of an unrelated
    env-var call or the word "example"/"sample" *elsewhere* in the
    surrounding code is handled separately by
    `has_env_or_example_proximity`, which only DOWNGRADES confidence
    (see `secrets_detection_service.py`) -- it never drops a finding.

    Args:
        secret_value: The detected secret value
        matched_text: The full matched text

    Returns:
        True if the matched value itself is a placeholder/dummy and the
        finding should be dropped outright.
    """
    for fp_pattern in FALSE_POSITIVE_PATTERNS:
        if fp_pattern.search(secret_value):
            return True
        if fp_pattern.search(matched_text):
            return True

    return False


def has_env_or_example_proximity(
    content: str,
    match_start: int,
    matched_len: int,
) -> bool:
    """
    Check whether "example"/"sample" wording or an env-var read call
    (os.environ / process.env / getenv) appears near the match.

    This is a SOFT signal only (BLOCKER-3 fix): it does not by itself
    mean the matched value is safe -- a real hardcoded secret can sit a
    few lines away from an unrelated `os.environ.get(...)` call. Callers
    must use this to floor/downgrade confidence, never to drop the
    finding outright. Only a placeholder VALUE (see `is_false_positive`
    above) justifies a full drop.

    Args:
        content: Full file content
        match_start: Start position of the match
        matched_len: Length of the matched text

    Returns:
        True if "example"/"sample" wording or an env-read call appears
        within 100 chars of the match.
    """
    context_start = max(0, match_start - 100)
    context_end = min(len(content), match_start + matched_len + 100)
    context = content[context_start:context_end]

    if "example" in context.lower() or "sample" in context.lower():
        return True

    if "process.env" in context or "os.environ" in context or "getenv" in context:
        return True

    return False


def calculate_confidence(
    pattern: SecretPattern,
    secret_value: str,
    entropy: Optional[float],
) -> float:
    """
    Calculate confidence score for a finding.

    Args:
        pattern: The pattern that matched
        secret_value: The secret value detected
        entropy: Entropy of the secret (if calculated)

    Returns:
        Confidence score between 0 and 1
    """
    confidence = 0.7

    if pattern.secret_type in {SecretType.PRIVATE_KEY, SecretType.SSH_KEY}:
        confidence = 0.95

    if pattern.name.startswith("aws_") or pattern.name.startswith("github_"):
        confidence = 0.9

    if entropy:
        if entropy > 4.5:
            confidence = min(0.95, confidence + 0.1)
        elif entropy < 3.0:
            confidence = max(0.3, confidence - 0.2)

    if len(secret_value) > 32:
        confidence = min(0.95, confidence + 0.05)

    return round(confidence, 2)


def sanitize_line(line: str, secret_value: str) -> str:
    """
    Sanitize a line by masking the secret value.

    Args:
        line: The original line content
        secret_value: The secret value to mask

    Returns:
        Sanitized line with masked secret
    """
    if secret_value in line:
        return line.replace(secret_value, mask_secret(secret_value))
    return line


def severity_meets_threshold(severity: str, min_severity: str) -> bool:
    """
    Check if a severity level meets the configured threshold.

    Args:
        severity: The severity level to check
        min_severity: The minimum severity threshold

    Returns:
        True if the severity meets or exceeds the threshold
    """
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
    """
    Get sort order for severity (critical first).

    Args:
        severity: The severity level

    Returns:
        Sort order (lower = higher priority)
    """
    order = {
        SecuritySeverity.CRITICAL.value: 0,
        SecuritySeverity.HIGH.value: 1,
        SecuritySeverity.MEDIUM.value: 2,
        SecuritySeverity.LOW.value: 3,
        SecuritySeverity.INFO.value: 4,
    }
    return order.get(severity, 5)
