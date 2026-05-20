"""
Heimdall Environment Variable Fallback Scanner - pure helper functions.

Standalone utilities for credential key name and value classification.
These have no dependency on AST visitor state.
"""

from typing import Optional


CREDENTIAL_KEY_FRAGMENTS = frozenset({
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "auth", "credential", "credentials", "private_key", "privatekey",
    "access_key", "accesskey",
})

CREDENTIAL_PLACEHOLDER_FRAGMENTS = frozenset({
    "${", "{{", "<", "changeme", "todo", "replace", "your-", "your_",
    "example", "placeholder", "xxxxx",
})


def is_credential_key_name(var_name: Optional[str]) -> bool:
    """Return True if the env var name looks like a credential key."""
    if not var_name:
        return False
    name_lower = var_name.lower()
    for fragment in CREDENTIAL_KEY_FRAGMENTS:
        if fragment in name_lower:
            return True
    return False


def is_credential_like_value(value_repr: Optional[str]) -> bool:
    """
    Return True if the default value looks like a real credential
    (not a placeholder or empty value).
    """
    if not value_repr:
        return False
    value = value_repr.strip("'\"")
    if not value:
        return False
    value_lower = value.lower()
    for fragment in CREDENTIAL_PLACEHOLDER_FRAGMENTS:
        if fragment in value_lower:
            return False
    return True
