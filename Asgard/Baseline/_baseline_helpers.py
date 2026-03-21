"""
Baseline Manager - Helper Functions

Standalone helper functions used by BaselineManager.
"""

import hashlib
from pathlib import Path
from typing import Any


def relative_path(project_path: Path, path: str) -> str:
    """Convert absolute path to relative path."""
    try:
        return str(Path(path).relative_to(project_path))
    except ValueError:
        return path


def get_violation_message(violation: Any) -> str:
    """Extract message from violation object."""
    for attr in ['message', 'description', 'import_statement', 'code_snippet']:
        if hasattr(violation, attr):
            return str(getattr(violation, attr, ''))
    return ""


def generate_violation_id(
    file_path: str,
    line_number: int,
    violation_type: str,
    message: str,
) -> str:
    """Generate a unique ID for a violation."""
    content = f"{file_path}:{line_number}:{violation_type}:{message}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]
