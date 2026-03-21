"""
Heimdall Pattern Detector - Detection Helpers

Re-exports all detection functions from the creational, structural, and
behavioral sub-modules so callers can import from a single location.
"""

from Asgard.Heimdall.Architecture.services._pattern_detectors_creational import (
    detect_singleton,
    detect_factory,
    detect_builder,
)
from Asgard.Heimdall.Architecture.services._pattern_detectors_structural import (
    detect_adapter,
    detect_decorator,
    detect_facade,
)
from Asgard.Heimdall.Architecture.services._pattern_detectors_behavioral import (
    detect_strategy,
    detect_observer,
    detect_command,
)

__all__ = [
    "detect_singleton",
    "detect_factory",
    "detect_builder",
    "detect_adapter",
    "detect_decorator",
    "detect_facade",
    "detect_strategy",
    "detect_observer",
    "detect_command",
]
