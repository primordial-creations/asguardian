"""
Architecture Drift Paradox detection (DEEPTHINK_03 §3, Heimdall Plan 03).

A module whose heuristic-matched layer (`min == base`) sits at a *shallower*
level than what its dependencies force it to be (`max` pulled below `min`)
is architecturally lying about its own placement — e.g. a file physically
under `domain/` that imports `sqlalchemy`. `min > max` is the bound paradox
that flags this: the single highest-value new finding class in Plan 03.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from Asgard.Bragi.Architecture.graph.nodes import LevelBounds


@dataclass
class ArchitectureDriftViolation:
    """A file whose intrinsic (path/suffix) layer contradicts the layer
    implied by its actual dependencies."""

    module: str
    intrinsic_level: int
    effective_level: int
    effective_max_level: int
    message: str
    pinned_by: List[str] = field(default_factory=list)


def detect_drift(bounds: Dict[str, LevelBounds]) -> List[ArchitectureDriftViolation]:
    """Report every module in a `min > max` paradox state."""
    violations: List[ArchitectureDriftViolation] = []
    for module, b in sorted(bounds.items()):
        if not b.is_drift:
            continue
        intrinsic = b.base_level if b.base_level is not None else 0
        violations.append(
            ArchitectureDriftViolation(
                module=module,
                intrinsic_level=intrinsic,
                effective_level=b.min_level,
                effective_max_level=b.max_level,
                message=(
                    f"File '{module}' intrinsically looks like level {intrinsic} "
                    f"but acts as level {b.min_level} (its dependencies pull it no "
                    f"shallower than {b.min_level}, while its own bound admits at "
                    f"most level {b.max_level}) — architecture drift."
                ),
                pinned_by=list(b.pinned_by),
            )
        )
    return violations
