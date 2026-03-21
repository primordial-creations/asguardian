"""
Progress Reporting Infrastructure - Types

Enum and configuration dataclass for the progress reporting system.
"""

from dataclasses import dataclass
from enum import Enum


class ProgressStyle(str, Enum):
    """Progress indicator styles."""
    SPINNER = "spinner"
    BAR = "bar"
    DOTS = "dots"
    NONE = "none"


@dataclass
class ProgressConfig:
    """Configuration for progress reporting."""
    enabled: bool = True
    style: ProgressStyle = ProgressStyle.SPINNER
    show_count: bool = True
    show_percentage: bool = True
    show_elapsed: bool = True
    refresh_rate: float = 0.1  # seconds
    bar_width: int = 40
