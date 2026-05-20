"""
Tests for Heimdall ProfileManager Service

Unit tests for quality profile management: listing, loading, saving, and
assigning profiles to projects.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import Asgard.Shared.Profiles.services.profile_manager as profile_manager_module
from Asgard.Shared.Profiles.models.profile_models import (
    QualityProfile,
    RuleConfig,
)
from Asgard.Shared.Profiles.services.profile_manager import ProfileManager


class TestProfileManagerListProfiles:
    """Tests for ProfileManager.list_profiles()."""

    def test_list_profiles_includes_asgard_way_python(self):
        """list_profiles returns the Asgard Way - Python built-in profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profiles = manager.list_profiles()
                names = [p.name for p in profiles]
                assert "Asgard Way - Python" in names

    def test_list_profiles_includes_asgard_way_strict(self):
        """list_profiles returns the Asgard Way - Strict built-in profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profiles = manager.list_profiles()
                names = [p.name for p in profiles]
                assert "Asgard Way - Strict" in names

    def test_list_profiles_returns_at_least_two(self):
        """list_profiles returns at least two profiles (the two built-ins)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profiles = manager.list_profiles()
                assert len(profiles) >= 2

    def test_list_profiles_sorted_by_name(self):
        """list_profiles returns profiles sorted alphabetically by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profiles = manager.list_profiles()
                names = [p.name for p in profiles]
                assert names == sorted(names)

    def test_list_profiles_includes_custom_profiles(self):
        """list_profiles includes user-defined custom profiles alongside built-ins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            profiles_dir = tmpdir_path / "profiles"
            with patch.object(profile_manager_module, "_PROFILES_DIR", profiles_dir), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                custom = QualityProfile(
                    name="Custom Team Profile",
                    language="python",
                    description="A custom team profile",
                    rules=[],
                )
                manager.save_profile(custom)
                profiles = manager.list_profiles()
                names = [p.name for p in profiles]
                assert "Custom Team Profile" in names


class TestProfileManagerGetProfile:
    """Tests for ProfileManager.get_profile()."""

    def test_get_profile_returns_asgard_way_python(self):
        """get_profile returns the correct profile for 'Asgard Way - Python'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profile = manager.get_profile("Asgard Way - Python")
                assert profile is not None
                assert profile.name == "Asgard Way - Python"

    def test_get_profile_returns_asgard_way_strict(self):
        """get_profile returns the correct profile for 'Asgard Way - Strict'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profile = manager.get_profile("Asgard Way - Strict")
                assert profile is not None
                assert profile.name == "Asgard Way - Strict"

    def test_get_profile_builtin_is_builtin(self):
        """Built-in profiles have is_builtin set to True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                profile = manager.get_profile("Asgard Way - Python")
                assert profile.is_builtin is True

    def test_get_profile_returns_none_for_unknown(self):
        """get_profile returns None for an unknown profile name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                result = manager.get_profile("Nonexistent Profile That Does Not Exist")
                assert result is None

    def test_get_profile_returns_saved_custom_profile(self):
        """get_profile returns a previously saved custom profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            profiles_dir = tmpdir_path / "profiles"
            with patch.object(profile_manager_module, "_PROFILES_DIR", profiles_dir), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                custom = QualityProfile(
                    name="My Custom Profile",
                    language="python",
                    description="Custom description",
                    rules=[
                        RuleConfig(
                            rule_id="quality.cyclomatic_complexity",
                            severity="error",
                            threshold=8.0,
                        )
                    ],
                )
                manager.save_profile(custom)
                retrieved = manager.get_profile("My Custom Profile")
                assert retrieved is not None
                assert retrieved.name == "My Custom Profile"
                assert retrieved.description == "Custom description"


class TestProfileManagerSaveProfile:
    """Tests for ProfileManager.save_profile()."""

    def test_save_profile_persists_to_disk(self):
        """save_profile writes a JSON file to the profiles directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            profiles_dir = tmpdir_path / "profiles"
            with patch.object(profile_manager_module, "_PROFILES_DIR", profiles_dir), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                custom = QualityProfile(
                    name="Persisted Profile",
                    language="python",
                    description="Persisted",
                    rules=[],
                )
                manager.save_profile(custom)
                json_files = list(profiles_dir.glob("*.json"))
                assert len(json_files) == 1

    def test_save_profile_raises_for_builtin(self):
        """save_profile raises ValueError when trying to overwrite a built-in profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                builtin_profile = manager.get_profile("Asgard Way - Python")
                with pytest.raises(ValueError, match="Cannot overwrite built-in profile"):
                    manager.save_profile(builtin_profile)

    def test_save_profile_roundtrip_preserves_rules(self):
        """save_profile and get_profile preserve rule configurations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            profiles_dir = tmpdir_path / "profiles"
            with patch.object(profile_manager_module, "_PROFILES_DIR", profiles_dir), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                custom = QualityProfile(
                    name="Rules Profile",
                    language="python",
                    description="Has rules",
                    rules=[
                        RuleConfig(
                            rule_id="quality.cyclomatic_complexity",
                            severity="warning",
                            threshold=10.0,
                        ),
                        RuleConfig(
                            rule_id="security.hardcoded_secrets",
                            severity="error",
                            threshold=None,
                        ),
                    ],
                )
                manager.save_profile(custom)
                retrieved = manager.get_profile("Rules Profile")
                assert retrieved is not None
                assert len(retrieved.rules) == 2
                rule_ids = [r.rule_id for r in retrieved.rules]
                assert "quality.cyclomatic_complexity" in rule_ids
                assert "security.hardcoded_secrets" in rule_ids

    def test_save_profile_creates_profiles_dir_if_missing(self):
        """save_profile creates the profiles directory automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            profiles_dir = tmpdir_path / "new_profiles_dir"
            assert not profiles_dir.exists()
            with patch.object(profile_manager_module, "_PROFILES_DIR", profiles_dir), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                custom = QualityProfile(
                    name="Dir Creation Test",
                    language="python",
                    description="",
                    rules=[],
                )
                manager.save_profile(custom)
                assert profiles_dir.exists()


class TestProfileManagerAssignAndGet:
    """Tests for ProfileManager.assign_to_project() and get_project_profile()."""

    def test_assign_profile_creates_assignment(self):
        """assign_to_project creates an assignment for the given project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            project_path = str(tmpdir_path / "my_project")
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                manager.assign_to_project(project_path, "Asgard Way - Python")
                assignments_file = tmpdir_path / "assignments.json"
                assert assignments_file.exists()
                with open(assignments_file, "r") as fh:
                    data = json.load(fh)
                assert len(data) == 1

    def test_get_project_profile_retrieves_assignment(self):
        """get_project_profile returns the profile assigned to a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            project_path = str(tmpdir_path / "my_project")
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                manager.assign_to_project(project_path, "Asgard Way - Python")
                retrieved = manager.get_project_profile(project_path)
                assert retrieved is not None
                assert retrieved.name == "Asgard Way - Python"

    def test_get_project_profile_returns_none_for_unassigned(self):
        """get_project_profile returns None when no profile has been assigned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            project_path = str(tmpdir_path / "unassigned_project")
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                result = manager.get_project_profile(project_path)
                assert result is None

    def test_assign_profile_raises_for_unknown_profile(self):
        """assign_to_project raises ValueError when the profile does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            project_path = str(tmpdir_path / "my_project")
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                with pytest.raises(ValueError, match="Profile not found"):
                    manager.assign_to_project(project_path, "Nonexistent Profile")

    def test_assign_profile_overwrites_previous_assignment(self):
        """assign_to_project replaces any previous assignment for a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            project_path = str(tmpdir_path / "my_project")
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                manager.assign_to_project(project_path, "Asgard Way - Python")
                manager.assign_to_project(project_path, "Asgard Way - Strict")
                retrieved = manager.get_project_profile(project_path)
                assert retrieved is not None
                assert retrieved.name == "Asgard Way - Strict"


class TestProfileManagerEffectiveProfile:
    """Tests for ProfileManager.get_effective_profile()."""

    def test_get_effective_profile_for_builtin_no_parent(self):
        """get_effective_profile on Asgard Way - Python returns the profile unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                effective = manager.get_effective_profile("Asgard Way - Python")
                assert effective.name == "Asgard Way - Python"

    def test_get_effective_profile_strict_inherits_from_python(self):
        """get_effective_profile on Asgard Way - Strict resolves parent rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                effective = manager.get_effective_profile("Asgard Way - Strict")
                assert effective.name == "Asgard Way - Strict"
                assert len(effective.rules) > 0

    def test_get_effective_profile_raises_for_unknown(self):
        """get_effective_profile raises ValueError for an unknown profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with patch.object(profile_manager_module, "_PROFILES_DIR", tmpdir_path / "profiles"), \
                 patch.object(profile_manager_module, "_ASSIGNMENTS_FILE", tmpdir_path / "assignments.json"):
                manager = ProfileManager()
                with pytest.raises(ValueError, match="Profile not found"):
                    manager.get_effective_profile("Does Not Exist")
