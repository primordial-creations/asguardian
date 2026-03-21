"""
Asgard Dashboard HTML Helpers

Utility functions for generating HTML fragments in the web dashboard.
"""

from pathlib import Path


def truncate_path(file_path: str, components: int = 3) -> str:
    """Return the last N path components of a file path."""
    parts = Path(file_path).parts
    if len(parts) <= components:
        return file_path
    return "/".join(parts[-components:])


def rating_badge(letter: str) -> str:
    """Return an HTML rating badge for a letter grade."""
    safe = letter.upper() if letter and letter.upper() in ("A", "B", "C", "D", "E") else "unknown"
    return f'<span class="rating-badge rating-{safe}">{letter or "?"}</span>'


def severity_badge(severity: str) -> str:
    """Return an HTML severity badge."""
    low = severity.lower()
    return f'<span class="sev-badge sev-{low}">{severity.upper()}</span>'


def status_badge(status: str) -> str:
    """Return an HTML status badge."""
    low = status.lower()
    label = status.replace("_", " ").title()
    return f'<span class="status-badge status-{low}">{label}</span>'


def gate_badge(status: str) -> str:
    """Return an HTML quality gate badge."""
    low = (status or "unknown").lower()
    label = (status or "Unknown").upper()
    return f'<span class="gate-badge gate-{low}">{label}</span>'


def rating_to_score(letter: str) -> int:
    """Convert a letter rating to a numeric score for charting."""
    mapping = {"A": 100, "B": 80, "C": 60, "D": 40, "E": 20}
    return mapping.get((letter or "").upper(), 0)
