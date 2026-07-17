"""Tests for validation profiles and `.forseti.yaml` config (plan 02)."""

from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.models.rule_models import PathOverride, Profile, RuleMeta
from Asgard.Forseti.Rules.services.profile_service import (
    BUILTIN_PROFILES,
    effective_severity,
    load_config,
    resolve_profile,
    select_rules,
)
from Asgard.Forseti.Rules.services.rule_registry_service import RuleRegistry


def _meta(rule_id="test.rule", **overrides) -> RuleMeta:
    base = dict(
        rule_id=rule_id,
        formats={SchemaFormat.OPENAPI},
        cost=Cost.ON,
        confidence=Confidence.DETERMINISTIC,
        severity=Severity.WARNING,
        category=RuleCategory.STYLE,
    )
    base.update(overrides)
    return RuleMeta(**base)


class TestBuiltinProfiles:
    def test_four_builtin_profiles_exist(self):
        assert set(BUILTIN_PROFILES) == {"ide", "pre-commit", "ci", "audit"}

    def test_ide_never_blocks_and_fails_open(self):
        ide = BUILTIN_PROFILES["ide"]
        assert ide.blocking == "never" and ide.fail_open and ide.budget_ms == 200

    def test_precommit_selects_cheap_deterministic_only(self):
        registry = RuleRegistry()
        registry.register(_meta("det.on", cost=Cost.ON))
        registry.register(_meta("det.net", cost=Cost.NETWORK))
        registry.register(_meta("heur", confidence=Confidence.HEURISTIC,
                                severity=Severity.INFO))
        selected = select_rules(registry, BUILTIN_PROFILES["pre-commit"])
        assert [r.meta.rule_id for r in selected] == ["det.on"]

    def test_ci_is_fail_closed_hard_blocking(self):
        ci = BUILTIN_PROFILES["ci"]
        assert ci.blocking == "hard" and not ci.fail_open


class TestEffectiveSeverity:
    def test_no_override_keeps_fixed_severity(self):
        assert effective_severity(_meta(), Profile(name="p")) == Severity.WARNING

    def test_non_core_rule_can_be_disabled(self):
        profile = Profile(name="p", rule_overrides={"test.rule": "off"})
        assert effective_severity(_meta(), profile) is None

    def test_core_rule_survives_off_override(self):
        profile = Profile(name="p", rule_overrides={"core.rule": "off"})
        meta = _meta("core.rule", core=True, severity=Severity.ERROR,
                     category=RuleCategory.STRUCTURE)
        assert effective_severity(meta, profile) == Severity.ERROR

    def test_core_rule_cannot_be_downgraded(self):
        profile = Profile(name="p", rule_overrides={"core.rule": "hint"})
        meta = _meta("core.rule", core=True, severity=Severity.ERROR)
        assert effective_severity(meta, profile) == Severity.ERROR

    def test_non_core_may_be_strengthened(self):
        profile = Profile(name="p", rule_overrides={"test.rule": "error"})
        assert effective_severity(_meta(), profile) == Severity.ERROR

    def test_heuristic_promotion_to_error_is_clamped(self):
        profile = Profile(name="p", rule_overrides={"test.rule": "error"})
        meta = _meta(confidence=Confidence.HEURISTIC, severity=Severity.INFO)
        assert effective_severity(meta, profile) == Severity.WARNING

    def test_glob_override_matches(self):
        profile = Profile(name="p", rule_overrides={"test.*": "off"})
        assert effective_severity(_meta(), profile) is None

    def test_path_scoped_override(self):
        profile = Profile(name="p", path_overrides=[
            PathOverride(path="legacy/*", rules={"test.rule": "off"}),
        ])
        assert effective_severity(_meta(), profile, "legacy/old.yaml") is None
        assert effective_severity(_meta(), profile, "src/new.yaml") == Severity.WARNING


class TestConfigLoading:
    def test_missing_config_returns_none(self, tmp_path):
        assert load_config(tmp_path) is None

    def test_load_and_resolve(self, tmp_path):
        (tmp_path / ".forseti.yaml").write_text(
            "version: 1\n"
            "ruleset_version: '1.0.0'\n"
            "profile: pre-commit\n"
            "rules:\n"
            "  oas.style.kebab-case-paths: off\n"
            "overrides:\n"
            "  - path: 'legacy/**'\n"
            "    rules: {'oas.docs.*': off}\n"
        )
        config = load_config(tmp_path)
        assert config.profile == "pre-commit"
        assert config.ruleset_version == "1.0.0"
        profile = resolve_profile(None, config)
        assert profile.name == "pre-commit"
        assert profile.rule_overrides == {"oas.style.kebab-case-paths": "off"}
        assert profile.path_overrides[0].path == "legacy/**"

    def test_explicit_name_wins_over_config(self, tmp_path):
        (tmp_path / ".forseti.yaml").write_text("profile: ide\n")
        config = load_config(tmp_path)
        assert resolve_profile("audit", config).name == "audit"
