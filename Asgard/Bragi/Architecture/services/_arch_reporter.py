"""
Heimdall Architecture Analyzer Report Generation

Re-exports all report generation functions from their domain-specific modules.
"""

from Asgard.Bragi.Architecture.services._arch_reporter_json import (
    generate_json_report,
)
from Asgard.Bragi.Architecture.services._arch_reporter_markdown import (
    generate_markdown_report,
)
from Asgard.Bragi.Architecture.services._arch_reporter_text import (
    generate_recommendations,
    generate_text_report,
)

__all__ = [
    "generate_recommendations",
    "generate_text_report",
    "generate_json_report",
    "generate_markdown_report",
]
