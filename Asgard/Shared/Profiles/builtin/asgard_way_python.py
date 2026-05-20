"""
Built-in Quality Profile: Asgard Way - Python

The standard quality profile for Python projects in the GAIA ecosystem.
Covers the full range of quality, security, and reliability checks offered
by the Heimdall analysis suite.
"""

from datetime import datetime

from Asgard.Shared.Profiles.models.profile_models import QualityProfile, RuleConfig

ASGARD_WAY_PYTHON = QualityProfile(
    name="Asgard Way - Python",
    language="python",
    description=(
        "Standard quality profile for Python projects. "
        "Covers quality, security, and reliability rules aligned with GAIA coding standards."
    ),
    parent_profile=None,
    is_builtin=True,
    created_at=datetime(2026, 1, 1),
    rules=[
        RuleConfig(rule_id="quality.file_length", enabled=True, severity="warning", threshold=500.0),
        RuleConfig(rule_id="quality.cyclomatic_complexity", enabled=True, severity="error", threshold=10.0),
        RuleConfig(rule_id="quality.cognitive_complexity", enabled=True, severity="warning", threshold=15.0),
        RuleConfig(rule_id="quality.duplication", enabled=True, severity="warning", threshold=3.0),
        RuleConfig(rule_id="quality.long_function", enabled=True, severity="warning", threshold=50.0),
        RuleConfig(rule_id="quality.comment_density", enabled=True, severity="info", threshold=10.0),
        RuleConfig(rule_id="quality.api_documentation", enabled=True, severity="warning", threshold=70.0),
        RuleConfig(rule_id="quality.naming_conventions", enabled=True, severity="warning"),
        RuleConfig(rule_id="quality.lazy_imports", enabled=True, severity="error"),
        RuleConfig(rule_id="quality.env_fallbacks", enabled=True, severity="error"),
        RuleConfig(rule_id="security.secrets", enabled=True, severity="error"),
        RuleConfig(rule_id="security.injection", enabled=True, severity="error"),
        RuleConfig(rule_id="security.crypto", enabled=True, severity="error"),
        RuleConfig(rule_id="security.hotspots", enabled=True, severity="warning"),
    ],
)
