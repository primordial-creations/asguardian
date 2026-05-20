"""
Built-in Quality Profiles for the Asgard Way standard.
"""

from Asgard.Shared.Profiles.builtin.asgard_way_python import ASGARD_WAY_PYTHON
from Asgard.Shared.Profiles.builtin.asgard_way_strict import ASGARD_WAY_STRICT

BUILTIN_PROFILES = {
    ASGARD_WAY_PYTHON.name: ASGARD_WAY_PYTHON,
    ASGARD_WAY_STRICT.name: ASGARD_WAY_STRICT,
}

__all__ = [
    "ASGARD_WAY_PYTHON",
    "ASGARD_WAY_STRICT",
    "BUILTIN_PROFILES",
]
