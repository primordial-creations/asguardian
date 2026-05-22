# Heimdall Profiles Module

## Overview

The Profiles module manages named, configurable rule sets (quality profiles) that can be assigned to projects. A profile controls which Heimdall rules are active and their severity thresholds. Profiles support inheritance: a custom profile can extend a built-in profile and override specific rules.

## Built-in Profiles

| Profile Name | Description |
|--------------|-------------|
| `Asgard Way - Python` | Default Python profile with all rules enabled at standard thresholds |
| `Asgard Way - Strict` | Stricter thresholds; lower duplication tolerance, higher documentation requirements |
| `Asgard Way - Minimal` | Reduced rule set for legacy codebases; security rules only at error level |

## Profile Storage

- Built-in profiles are code-defined and read-only.
- User-defined profiles are persisted as JSON files at `~/.asgard/profiles/<name>.json`.
- Project-to-profile assignments are stored at `~/.asgard/profile_assignments.json`.

## Programmatic Usage

```python
from Asgard.Heimdall.Profiles import ProfileManager
from Asgard.Heimdall.Profiles.models import QualityProfile, RuleConfig

manager = ProfileManager()

# List all profiles
profiles = manager.list_profiles()
for p in profiles:
    print(f"{p.name} ({'built-in' if p.is_builtin else 'custom'})")

# Get a profile (with inherited rules resolved)
profile = manager.get_effective_profile("Asgard Way - Python")

# Create a custom profile extending a built-in
custom = QualityProfile(
    name="My Project Profile",
    parent="Asgard Way - Python",
    description="Extended profile for my project",
    rules={
        "max_function_lines": RuleConfig(enabled=True, threshold=30),
        "max_cyclomatic_complexity": RuleConfig(enabled=True, threshold=8),
        "sql_injection": RuleConfig(enabled=True, severity="critical"),
    },
)
manager.save_profile(custom)

# Assign a profile to a project
manager.assign_to_project("/path/to/project", "My Project Profile")

# Get the profile assigned to a project
assignment = manager.get_project_assignment("/path/to/project")
print(f"Active profile: {assignment.profile_name}")

# Get the effective profile for a project (resolves assignment + inheritance)
effective = manager.get_effective_profile_for_project("/path/to/project")
```

## RuleConfig Fields

| Field | Description |
|-------|-------------|
| `enabled` | Whether the rule is active |
| `threshold` | Numeric threshold override (if applicable) |
| `severity` | Severity override (`critical`, `high`, `medium`, `low`, `info`) |
| `parameters` | Dict of additional rule-specific parameters |

## Profile Inheritance

A profile with a `parent` field inherits all rule configurations from the parent. Explicitly defined rules in the child profile override parent values. This allows creating focused overrides without redefining every rule.

```python
# Example: strict security, relaxed quality for a legacy module
legacy_profile = QualityProfile(
    name="Legacy Module",
    parent="Asgard Way - Minimal",
    rules={
        "max_file_lines": RuleConfig(enabled=True, threshold=2000),  # Override
        "sql_injection": RuleConfig(enabled=True, severity="critical"),  # Kept strict
    },
)
```

## CLI Usage

```bash
python -m Heimdall profiles list                    # List all profiles
python -m Heimdall profiles show <name>             # Show profile rules
python -m Heimdall profiles create <name>           # Interactive profile creation
python -m Heimdall profiles assign <path> <name>    # Assign profile to project
python -m Heimdall profiles current <path>          # Show assigned profile
```
