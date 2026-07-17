"""
Compatibility Base Models - core enums of the unified compatibility engine.

Grounded in input contravariance / output covariance (DEEPTHINK_01) and
Confluent-style directionality + temporal depth (RESEARCH_02).
"""

from enum import Enum


class Direction(str, Enum):
    """Role of the schema node being evaluated."""

    INPUT = "input"    # contravariant: new must accept a superset
    OUTPUT = "output"  # covariant: new must emit a subset


class AbstractViolation(str, Enum):
    """Format-agnostic violation taxonomy every rule projects onto."""

    INPUT_CONTRAVARIANCE_VIOLATION = "input_contravariance_violation"
    OUTPUT_COVARIANCE_VIOLATION = "output_covariance_violation"
    OUTPUT_COVARIANCE_MODIFIED = "output_covariance_modified"  # default-bridged; semantic hazard
    ROUTING_BREAK = "routing_break"                            # removed path / RPC / channel
    TYPE_CONTRADICTION = "type_contradiction"


class TierVerdict(str, Enum):
    """Verdict of one impact tier."""

    PASS = "pass"
    HAZARD = "hazard"
    FAIL = "fail"


class EmpiricalVerdict(str, Enum):
    """Telemetry-informed verdict (phase 4)."""

    SAFE_UNUSED = "safe_unused"
    ACTIVE = "active"
    UNKNOWN = "unknown"


class CompatMode(str, Enum):
    """Compatibility mode: directionality x temporal depth (RESEARCH_02)."""

    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    BACKWARD_TRANSITIVE = "backward_transitive"
    FORWARD_TRANSITIVE = "forward_transitive"
    FULL_TRANSITIVE = "full_transitive"

    @property
    def is_transitive(self) -> bool:
        """Whether the mode checks against the entire version history."""
        return self.value.endswith("_transitive")

    @property
    def pairwise(self) -> "CompatMode":
        """The non-transitive base mode."""
        return CompatMode(self.value.replace("_transitive", ""))


class CompatStatus(str, Enum):
    """Overall gate status of a compatibility check."""

    PASSED = "passed"
    CONDITIONALLY_PASSED = "conditionally_passed"
    FAILED = "failed"
