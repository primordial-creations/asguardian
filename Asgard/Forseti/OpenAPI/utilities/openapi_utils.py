"""
OpenAPI Utilities - Helper functions for OpenAPI specification handling.
"""

import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from Asgard.Forseti.OpenAPI.models.openapi_models import OpenAPIVersion
from Asgard.Forseti.OpenAPI.utilities._openapi_io_utils import (
    detect_openapi_version,
    load_spec_file,
    save_spec_file,
)
from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import (
    compare_specs,
    count_operations,
    find_unused_schemas,
    get_all_refs,
    merge_specs,
    resolve_references,
)


def normalize_path(path: str) -> str:
    """
    Normalize an API path.

    - Ensures path starts with /
    - Removes trailing slashes
    - Normalizes path parameters

    Args:
        path: API path string.

    Returns:
        Normalized path string.
    """
    if not path.startswith("/"):
        path = "/" + path

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    path = re.sub(r"\{([^}]+)\}", lambda m: "{" + m.group(1).strip() + "}", path)

    return path


def validate_url(url: str) -> bool:
    """
    Validate a URL string.

    Args:
        url: URL string to validate.

    Returns:
        True if valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) or url.startswith("/")
    except Exception:
        return False


def extract_ref_name(ref: str) -> Optional[str]:
    """
    Extract the component name from a $ref string.

    Args:
        ref: Reference string (e.g., "#/components/schemas/User").

    Returns:
        Component name or None if invalid.
    """
    if not ref.startswith("#/"):
        return None

    parts = ref.split("/")
    if len(parts) >= 2:
        return parts[-1]
    return None


__all__ = [
    "compare_specs",
    "count_operations",
    "detect_openapi_version",
    "extract_ref_name",
    "find_unused_schemas",
    "get_all_refs",
    "load_spec_file",
    "merge_specs",
    "normalize_path",
    "resolve_references",
    "save_spec_file",
    "validate_url",
]
