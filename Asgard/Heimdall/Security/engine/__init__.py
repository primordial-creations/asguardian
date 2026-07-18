"""
Unified security dispatch engine (layered rule economics, DEEPTHINK_01).

Layer 1: regex sweep over raw text (secrets, key prefixes) -- always runs.
Layer 2: single AST parse -- structural rules + trigger-node scan with
         alias-resolved names.
Layer 3: lazy taint -- only functions containing trigger nodes get taint
         state built.
"""

from Asgard.Heimdall.Security.engine.dispatch import (
    DispatchEngine,
    DispatchResult,
    StructuralFinding,
)

__all__ = ["DispatchEngine", "DispatchResult", "StructuralFinding"]
