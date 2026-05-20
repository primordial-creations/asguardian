"""
Heimdall Profiles - Quality Profile Management

A Quality Profile is a named collection of rules with configured severity thresholds.
Profiles can be assigned to projects and can inherit from parent profiles, enabling
teams to define organisation-wide standards with project-specific overrides.

Built-in profiles:
- "Asgard Way - Python": Standard Python profile covering quality and security rules.
- "Asgard Way - Strict": Inherits from Python profile with tighter thresholds.

User-defined profiles are stored in ~/.asgard/profiles/ as JSON files.

Usage:
    from Asgard.Shared.Profiles import ProfileManager, QualityProfile, RuleConfig

    manager = ProfileManager()

    # List all profiles
    for profile in manager.list_profiles():
        print(f"{profile.name} ({'builtin' if profile.is_builtin else 'custom'})")

    # Get effective profile with inheritance resolved
    effective = manager.get_effective_profile("Asgard Way - Strict")
    for rule in effective.rules:
        print(f"  {rule.rule_id}: {rule.severity}")

    # Assign to project
    manager.assign_to_project("/path/to/project", "Asgard Way - Python")

    # Create a custom profile
    profile = QualityProfile(
        name="My Team Profile",
        language="python",
        parent_profile="Asgard Way - Python",
        rules=[
            RuleConfig(rule_id="quality.cyclomatic_complexity", severity="warning", threshold=8.0),
        ],
    )
    manager.save_profile(profile)
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Shared.Profiles.models.profile_models import (
    ProfileAssignment,
    QualityProfile,
    RuleCategory,
    RuleConfig,
)
from Asgard.Shared.Profiles.services.profile_manager import ProfileManager
from Asgard.Shared.Profiles.builtin import BUILTIN_PROFILES

__all__ = [
    "ProfileAssignment",
    "ProfileManager",
    "QualityProfile",
    "RuleCategory",
    "RuleConfig",
    "BUILTIN_PROFILES",
]
