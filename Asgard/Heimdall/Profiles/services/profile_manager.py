"""
Heimdall Profile Manager Service

Manages quality profiles: listing, loading, saving, and resolving inherited profiles.
Built-in profiles are code-defined and cannot be overwritten by user saves.
User-defined profiles are persisted as JSON files under ~/.asgard/profiles/.
Project-to-profile assignments are stored in ~/.asgard/profile_assignments.json.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from Asgard.Heimdall.Profiles.builtin import BUILTIN_PROFILES
from Asgard.Heimdall.Profiles.models.profile_models import (
    ProfileAssignment,
    QualityProfile,
    RuleConfig,
)

_PROFILES_DIR = Path.home() / ".asgard" / "profiles"
_ASSIGNMENTS_FILE = Path.home() / ".asgard" / "profile_assignments.json"


class ProfileManager:
    """
    Manages quality profiles for the Heimdall analysis system.

    Built-in profiles are always available and cannot be overwritten.
    User-defined profiles are loaded from and saved to ~/.asgard/profiles/.

    Usage:
        manager = ProfileManager()
        profiles = manager.list_profiles()
        effective = manager.get_effective_profile("Asgard Way - Strict")
        manager.assign_to_project("/path/to/project", "Asgard Way - Python")
    """

    def list_profiles(self) -> List[QualityProfile]:
        """
        Return all available quality profiles (built-in and user-defined).

        Returns:
            List of QualityProfile objects sorted by name.
        """
        profiles: Dict[str, QualityProfile] = {}

        for name, profile in BUILTIN_PROFILES.items():
            profiles[name] = profile

        _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        for json_file in sorted(_PROFILES_DIR.glob("*.json")):
            try:
                profile = self._load_profile_file(json_file)
                if profile.name not in BUILTIN_PROFILES:
                    profiles[profile.name] = profile
            except (OSError, ValueError, KeyError):
                pass

        return sorted(profiles.values(), key=lambda p: p.name)

    def get_profile(self, name: str) -> Optional[QualityProfile]:
        """
        Return the profile with the given name, or None if not found.

        Args:
            name: Profile name to look up.

        Returns:
            QualityProfile or None.
        """
        if name in BUILTIN_PROFILES:
            return BUILTIN_PROFILES[name]

        profile_file = _PROFILES_DIR / f"{self._safe_filename(name)}.json"
        if profile_file.exists():
            try:
                return self._load_profile_file(profile_file)
            except (OSError, ValueError, KeyError):
                return None

        return None

    def get_effective_profile(self, name: str) -> QualityProfile:
        """
        Return the effective profile with all inherited rules resolved.

        For a profile with a parent, the effective profile contains the parent's
        rules as the base, overridden by any rules defined in the child profile.
        Rules are merged by rule_id: child rules take precedence over parent rules.

        Args:
            name: Profile name to resolve.

        Returns:
            Resolved QualityProfile with merged rules.

        Raises:
            ValueError: If the profile or its parent cannot be found.
        """
        profile = self.get_profile(name)
        if profile is None:
            raise ValueError(f"Profile not found: '{name}'")

        if not profile.parent_profile:
            return profile

        parent = self.get_profile(profile.parent_profile)
        if parent is None:
            raise ValueError(
                f"Parent profile '{profile.parent_profile}' not found for profile '{name}'"
            )

        parent_effective = self.get_effective_profile(profile.parent_profile)

        merged_rules: Dict[str, RuleConfig] = {}
        for rule in parent_effective.rules:
            merged_rules[rule.rule_id] = rule
        for rule in profile.rules:
            merged_rules[rule.rule_id] = rule

        return QualityProfile(
            name=profile.name,
            language=profile.language,
            description=profile.description,
            parent_profile=profile.parent_profile,
            rules=list(merged_rules.values()),
            created_at=profile.created_at,
            is_builtin=profile.is_builtin,
        )

    def save_profile(self, profile: QualityProfile) -> None:
        """
        Save a user-defined profile to ~/.asgard/profiles/<name>.json.

        Built-in profiles cannot be saved (raises ValueError).

        Args:
            profile: The profile to persist.

        Raises:
            ValueError: If trying to overwrite a built-in profile.
        """
        if profile.name in BUILTIN_PROFILES:
            raise ValueError(
                f"Cannot overwrite built-in profile '{profile.name}'"
            )

        _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        profile_file = _PROFILES_DIR / f"{self._safe_filename(profile.name)}.json"

        data = {
            "name": profile.name,
            "language": profile.language,
            "description": profile.description,
            "parent_profile": profile.parent_profile,
            "is_builtin": False,
            "created_at": profile.created_at.isoformat(),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "enabled": r.enabled,
                    "severity": r.severity,
                    "threshold": r.threshold,
                    "extra_config": r.extra_config,
                }
                for r in profile.rules
            ],
        }

        with open(profile_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def load_profile_from_file(self, path: Path) -> QualityProfile:
        """
        Load a quality profile from an arbitrary JSON file path.

        Args:
            path: Path to the JSON profile file.

        Returns:
            Parsed QualityProfile.

        Raises:
            OSError: If the file cannot be read.
            ValueError: If the file content is invalid.
        """
        return self._load_profile_file(path)

    def assign_to_project(self, project_path: str, profile_name: str) -> None:
        """
        Assign a named profile to a project path.

        The assignment is persisted in ~/.asgard/profile_assignments.json.

        Args:
            project_path: Absolute path to the project root.
            profile_name: Name of the profile to assign.

        Raises:
            ValueError: If the profile does not exist.
        """
        if self.get_profile(profile_name) is None:
            raise ValueError(f"Profile not found: '{profile_name}'")

        assignments = self._load_assignments()
        assignments[str(Path(project_path).resolve())] = {
            "project_path": str(Path(project_path).resolve()),
            "profile_name": profile_name,
            "assigned_at": datetime.now().isoformat(),
        }
        self._save_assignments(assignments)

    def get_project_profile(self, project_path: str) -> Optional[QualityProfile]:
        """
        Return the quality profile assigned to a project, or None if not assigned.

        Args:
            project_path: Absolute path to the project root.

        Returns:
            Assigned QualityProfile or None.
        """
        assignments = self._load_assignments()
        key = str(Path(project_path).resolve())
        assignment_data = assignments.get(key)

        if assignment_data is None:
            return None

        profile_name = assignment_data.get("profile_name")
        if not profile_name:
            return None

        return self.get_profile(profile_name)

    def _load_profile_file(self, path: Path) -> QualityProfile:
        """Parse a QualityProfile from a JSON file."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        rules = [
            RuleConfig(
                rule_id=r["rule_id"],
                enabled=r.get("enabled", True),
                severity=r.get("severity", "warning"),
                threshold=r.get("threshold"),
                extra_config=r.get("extra_config", {}),
            )
            for r in data.get("rules", [])
        ]

        created_at_raw = data.get("created_at")
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except (ValueError, TypeError):
                created_at = datetime.now()
        else:
            created_at = datetime.now()

        return QualityProfile(
            name=data["name"],
            language=data.get("language", "python"),
            description=data.get("description", ""),
            parent_profile=data.get("parent_profile"),
            rules=rules,
            created_at=created_at,
            is_builtin=data.get("is_builtin", False),
        )

    def _load_assignments(self) -> dict:
        """Load project-to-profile assignments from disk."""
        if not _ASSIGNMENTS_FILE.exists():
            return {}
        try:
            with open(_ASSIGNMENTS_FILE, "r", encoding="utf-8") as fh:
                return cast(Dict[Any, Any], json.load(fh))
        except (OSError, ValueError):
            return {}

    def _save_assignments(self, assignments: dict) -> None:
        """Persist project-to-profile assignments to disk."""
        _ASSIGNMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_ASSIGNMENTS_FILE, "w", encoding="utf-8") as fh:
            json.dump(assignments, fh, indent=2)

    def _safe_filename(self, name: str) -> str:
        """Convert a profile name to a safe filename."""
        safe = name.lower()
        for char in (" ", "/", "\\", ":", "*", "?", '"', "<", ">", "|"):
            safe = safe.replace(char, "_")
        return safe
