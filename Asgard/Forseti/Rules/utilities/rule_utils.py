"""
Rule Utilities - fingerprints, location normalization, node hashing.
"""

import hashlib
import json
import re
from typing import Any, Optional


def normalize_location(file: Optional[str], json_path: str) -> str:
    """Normalize a finding location to `basename#json_path`."""
    base = file.replace("\\", "/").split("/")[-1] if file else ""
    return f"{base}#{json_path}"


def message_kind(message: str) -> str:
    """Collapse a message to its stable 'kind' (digits/quoted values stripped)."""
    kind = re.sub(r"'[^']*'|\"[^\"]*\"", "'*'", message)
    kind = re.sub(r"\d+", "#", kind)
    return kind.strip().lower()


def finding_fingerprint(rule_id: str, file: Optional[str], json_path: str, message: str) -> str:
    """Stable fingerprint: sha1(rule_id + normalized location + message kind)."""
    payload = f"{rule_id}|{normalize_location(file, json_path)}|{message_kind(message)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def navigate_json_path(document: Any, json_path: str) -> Any:
    """
    Navigate a simple slash-delimited pointer (e.g. '/paths/~1users/get').

    Supports JSON-pointer escapes (~0, ~1). Returns None when the path
    cannot be resolved.
    """
    if not json_path or json_path == "/":
        return document
    node = document
    for raw_token in json_path.strip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return None
            node = node[token]
        elif isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return node


def compute_node_hash(document: Any, json_path: str) -> str:
    """Content hash of the node at `json_path` (Boy-Scout revocation)."""
    node = navigate_json_path(document, json_path)
    if node is None:
        return ""
    try:
        blob = json.dumps(node, sort_keys=True, default=str)
    except (TypeError, ValueError):
        blob = str(node)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()
