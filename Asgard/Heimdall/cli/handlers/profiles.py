import argparse
import json
from pathlib import Path

from Asgard.Heimdall.Profiles.services.profile_manager import ProfileManager
from Asgard.Heimdall.Profiles.models.profile_models import QualityProfile, RuleConfig


def run_profiles_command(args: argparse.Namespace, verbose: bool = False) -> int:
    profiles_command = getattr(args, "profiles_command", None)
    manager = ProfileManager()

    if profiles_command == "list":
        return _run_profiles_list(args, manager, verbose)
    elif profiles_command == "show":
        return _run_profiles_show(args, manager, verbose)
    elif profiles_command == "assign":
        return _run_profiles_assign(args, manager, verbose)
    elif profiles_command == "create":
        return _run_profiles_create(args, manager, verbose)
    else:
        print("Error: Please specify a profiles subcommand.")
        print("  list     List all available quality profiles")
        print("  show     Show details for a specific profile")
        print("  assign   Assign a profile to a project")
        print("  create   Create a new custom profile")
        return 1


def _run_profiles_list(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    profiles = manager.list_profiles()
    output_format = getattr(args, "format", "text")

    if output_format == "json":
        data = [
            {
                "name": p.name,
                "language": p.language,
                "description": p.description,
                "parent_profile": p.parent_profile,
                "is_builtin": p.is_builtin,
                "rule_count": len(p.rules),
            }
            for p in profiles
        ]
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print("  HEIMDALL QUALITY PROFILES")
    print("=" * 70)
    print("")

    if not profiles:
        print("  No profiles found.")
    else:
        for profile in profiles:
            builtin_marker = "[builtin]" if profile.is_builtin else "[custom]"
            parent_str = f" (inherits: {profile.parent_profile})" if profile.parent_profile else ""
            print(f"  {builtin_marker:10s} {profile.name}{parent_str}")
            if verbose and profile.description:
                print(f"             {profile.description}")
            print(f"             Language: {profile.language}  |  Rules: {len(profile.rules)}")
            print("")

    print("=" * 70)
    return 0


def _run_profiles_show(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    name = getattr(args, "name", None)
    if not name:
        print("Error: Profile name is required. Usage: heimdall profiles show <name>")
        return 1

    try:
        effective = manager.get_effective_profile(name)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    output_format = getattr(args, "format", "text")

    if output_format == "json":
        data = {
            "name": effective.name,
            "language": effective.language,
            "description": effective.description,
            "parent_profile": effective.parent_profile,
            "is_builtin": effective.is_builtin,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "enabled": r.enabled,
                    "severity": r.severity,
                    "threshold": r.threshold,
                    "extra_config": r.extra_config,
                }
                for r in effective.rules
            ],
        }
        print(json.dumps(data, indent=2))
        return 0

    print("")
    print("=" * 70)
    print(f"  PROFILE: {effective.name}")
    print("=" * 70)
    print("")
    print(f"  Language:   {effective.language}")
    if effective.parent_profile:
        print(f"  Inherits:   {effective.parent_profile}")
    if effective.description:
        print(f"  Description: {effective.description}")
    print("")
    print("  Rules:")
    print(f"  {'Rule ID':<45} {'Severity':<10} {'Threshold'}")
    print("  " + "-" * 65)
    for rule in effective.rules:
        status = "" if rule.enabled else "[disabled] "
        threshold_str = str(rule.threshold) if rule.threshold is not None else ""
        print(f"  {status}{rule.rule_id:<45} {rule.severity:<10} {threshold_str}")
    print("")
    print("=" * 70)
    return 0


def _run_profiles_assign(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    project_path = getattr(args, "project_path", None)
    profile_name = getattr(args, "profile_name", None)

    if not project_path or not profile_name:
        print("Error: Both project_path and profile_name are required.")
        print("Usage: heimdall profiles assign <project_path> <profile_name>")
        return 1

    try:
        manager.assign_to_project(project_path, profile_name)
        print(f"Profile '{profile_name}' assigned to project: {Path(project_path).resolve()}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1


def _run_profiles_create(args: argparse.Namespace, manager: ProfileManager, verbose: bool) -> int:
    name = getattr(args, "name", None)
    parent = getattr(args, "parent", None)
    language = getattr(args, "language", "python")
    from_file = getattr(args, "from_file", None)
    description = getattr(args, "description", "")

    if not name:
        print("Error: Profile name is required. Usage: heimdall profiles create <name>")
        return 1

    if from_file:
        try:
            profile = manager.load_profile_from_file(Path(from_file))
            profile_data = QualityProfile(
                name=name,
                language=profile.language,
                description=description or profile.description,
                parent_profile=parent or profile.parent_profile,
                rules=profile.rules,
            )
            manager.save_profile(profile_data)
            print(f"Profile '{name}' created from '{from_file}'.")
            return 0
        except (OSError, ValueError) as exc:
            print(f"Error loading profile from file: {exc}")
            return 1

    new_profile = QualityProfile(
        name=name,
        language=language,
        description=description,
        parent_profile=parent,
        rules=[],
    )

    try:
        manager.save_profile(new_profile)
        print(f"Profile '{name}' created successfully.")
        if parent:
            print(f"  Inherits from: {parent}")
        print(f"  Stored at: ~/.asgard/profiles/")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
