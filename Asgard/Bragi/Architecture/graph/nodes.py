"""
Level-bound node model for the architecture layer-inference CSP
(DEEPTHINK_03 top-level, Heimdall Plan 03 §3).

Each module in the import graph carries a `[min_level, max_level]` bound
that is tightened by Topological Bound Propagation until fixpoint. The
final classification is:

    min == max  -> assigned layer, confidence 1.0
    min <  max  -> "bridge" file, assigned min, confidence < 1.0
    min >  max  -> Architecture Drift Violation (paradox)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LevelBounds:
    """Inferred concentric-layer bounds for one module."""

    module: str
    min_level: int
    max_level: int
    base_level: Optional[int] = None   # heuristic-matched level, None if unmatched
    matched: bool = False              # True if a path/suffix heuristic pinned a base level
    pinned_by: List[str] = field(default_factory=list)  # human-readable explanation trail

    @property
    def is_drift(self) -> bool:
        """min > max: the bound paradox — file intrinsically looks like one
        layer but behaves (via its dependencies) like a deeper one."""
        return self.min_level > self.max_level

    @property
    def is_bridge(self) -> bool:
        return self.min_level < self.max_level

    @property
    def assigned_level(self) -> Optional[int]:
        """The level to report/use for violation checks. None only when a
        drift paradox makes the level meaningless without resolution."""
        if self.is_drift:
            return None
        return self.min_level

    def confidence(self, max_levels: int) -> float:
        """1.0 when fully pinned; degrades with bound spread."""
        if self.is_drift:
            return 0.0
        if max_levels <= 0:
            return 1.0
        spread = self.max_level - self.min_level
        return max(0.0, 1.0 - (spread / float(max_levels)))
