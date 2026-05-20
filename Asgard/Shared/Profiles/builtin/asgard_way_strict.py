"""
Built-in Quality Profile: Asgard Way - Strict

Inherits all rules from 'Asgard Way - Python' and tightens thresholds for
documentation coverage and cyclomatic complexity. Intended for critical services
or libraries where higher quality standards are required.
"""

from datetime import datetime

from Asgard.Shared.Profiles.models.profile_models import QualityProfile, RuleConfig

ASGARD_WAY_STRICT = QualityProfile(
    name="Asgard Way - Strict",
    language="python",
    description=(
        "Strict quality profile for Python projects that require higher standards. "
        "Inherits from 'Asgard Way - Python' with tighter thresholds for "
        "documentation and complexity."
    ),
    parent_profile="Asgard Way - Python",
    is_builtin=True,
    created_at=datetime(2026, 1, 1),
    rules=[
        RuleConfig(rule_id="quality.comment_density", enabled=True, severity="warning", threshold=20.0),
        RuleConfig(rule_id="quality.api_documentation", enabled=True, severity="error", threshold=90.0),
        RuleConfig(rule_id="quality.cyclomatic_complexity", enabled=True, severity="error", threshold=7.0),
    ],
)
