"""Tests for the Plan 05 language-profile fallback chain."""

import textwrap

import pytest

from Asgard.Bragi.Calibration.services.profile_service import LanguageProfileService


class TestFallbackChain:
    def test_known_language_resolves(self):
        service = LanguageProfileService()
        profile = service.resolve("python")
        assert profile.language == "python"
        assert "cyclomatic_complexity" in profile.thresholds

    def test_unknown_language_falls_back_to_generic_never_keyerror(self):
        service = LanguageProfileService()
        profile = service.resolve("cobol")
        assert profile.language == "cobol"
        assert "cyclomatic_complexity" in profile.thresholds  # inherited from generic

    def test_threshold_lookup_never_raises_for_known_metric(self):
        service = LanguageProfileService()
        spec = service.threshold("python", "cyclomatic_complexity")
        assert spec.warn == 10

    def test_threshold_lookup_raises_for_truly_unknown_metric(self):
        service = LanguageProfileService()
        with pytest.raises(KeyError):
            service.threshold("python", "nonexistent_metric_xyz")

    def test_scalar_lookup_returns_default_when_absent(self):
        service = LanguageProfileService()
        assert service.scalar("python", "nonexistent_scalar", default=42.0) == 42.0

    def test_go_has_wider_thresholds_than_python(self):
        service = LanguageProfileService()
        go_cc = service.threshold("go", "cyclomatic_complexity")
        py_cc = service.threshold("python", "cyclomatic_complexity")
        assert go_cc.warn > py_cc.warn


class TestLocalOverride:
    def test_local_profile_overrides_language_profile(self, tmp_path):
        cache_dir = tmp_path / ".asgard_cache"
        cache_dir.mkdir()
        (cache_dir / "bragi_local_profile.yaml").write_text(textwrap.dedent("""\
            language: local
            provenance: "local P95, 2026-01-01, n=500"
            thresholds:
              cyclomatic_complexity: {warn: 8, fail: 16}
        """))
        service = LanguageProfileService(project_path=tmp_path)
        profile = service.resolve("python")
        assert profile.thresholds["cyclomatic_complexity"].warn == 8
        assert "local P95" in profile.provenance
        # Untouched metrics still inherit from the language profile.
        assert "cognitive_complexity" in profile.thresholds

    def test_no_local_profile_is_a_noop(self, tmp_path):
        service = LanguageProfileService(project_path=tmp_path)
        profile = service.resolve("python")
        assert profile.thresholds["cyclomatic_complexity"].warn == 10
