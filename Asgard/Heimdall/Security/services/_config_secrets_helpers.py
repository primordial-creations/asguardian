"""
Heimdall Config Secrets Scanner - pure helper functions.

Standalone utilities for placeholder detection, entropy calculation,
value masking, key classification, and data structure flattening.
These have no dependency on scanner state.
"""

import math
from typing import Any, Dict, Iterator, List, Tuple


# Values that look like placeholders and should be ignored
PLACEHOLDER_FRAGMENTS = [
    "${", "{{", "<", "changeme", "todo", "replace", "your-", "your_",
    "example", "placeholder", "xxxxx", "00000", "insert",
]


def is_placeholder(value: str) -> bool:
    """Return True if a string looks like a placeholder, not a real secret."""
    if not value:
        return True
    value_lower = value.lower()
    for fragment in PLACEHOLDER_FRAGMENTS:
        if fragment in value_lower:
            return True
    return False


def shannon_entropy(text: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not text:
        return 0.0
    freq: Dict[str, int] = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    return entropy


def mask_value(value: str) -> str:
    """Return a masked version of the value for safe display."""
    if len(value) <= 4:
        return "****"
    visible = max(2, len(value) // 6)
    return value[:visible] + "****" + value[-visible:]


def is_credential_key(key: str, credential_key_names: List[str]) -> bool:
    """Return True if the key name suggests it holds a credential."""
    key_lower = key.lower()
    for fragment in credential_key_names:
        if fragment in key_lower:
            return True
    return False


def flatten_dict(
    data: Any, prefix: str = ""
) -> Iterator[Tuple[str, str, Any]]:
    """
    Recursively yield (context_path, key, value) tuples from a nested dict/list structure.

    Args:
        data: The data structure to flatten
        prefix: Dot-notation path prefix for context
    """
    if isinstance(data, dict):
        for key, value in data.items():
            full_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                yield from flatten_dict(value, full_path)
            else:
                yield full_path, key, value
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            full_path = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)):
                yield from flatten_dict(item, full_path)
            else:
                yield full_path, str(idx), item
