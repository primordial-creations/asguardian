"""L0 tests: Freya Config subpackage (Plan 06 §3.1)."""

import os

import pytest
from pydantic import ValidationError

from Asgard.Freya.Config.models.config_models import FreyaConfig, RouteBudgetRef, VisualConfig
from Asgard.Freya.Config.services.config_loader import (
    DEFAULT_FREYARC_TEMPLATE,
    discover_config_path,
    load_config,
    merge_cli_overrides,
    write_default_config,
)


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestFreyaConfigModel:
    def test_defaults(self):
        config = FreyaConfig()
        assert config.wcag_level == "AA"
        assert config.output_format == "text"
        assert config.crawl is None
        assert "accessibility" in config.categories
        assert config.gate.fail_on
        assert isinstance(config.visual, VisualConfig)

    def test_construct_with_nested_overrides(self):
        config = FreyaConfig(
            wcag_level="AAA",
            budgets={"/docs/**": RouteBudgetRef(archetype="document")},
        )
        assert config.wcag_level == "AAA"
        assert config.budgets["/docs/**"].archetype == "document"

    def test_invalid_wcag_level_type_rejected(self):
        with pytest.raises(ValidationError):
            FreyaConfig(categories="not-a-list-but-a-string-is-iterable")  # str coerces oddly; use dict instead
        # Use a clearly invalid type instead (dict where list expected)
        with pytest.raises(ValidationError):
            FreyaConfig(categories={"a": 1})


class TestDiscovery:
    def test_no_config_file_returns_none(self, isolated_cwd):
        assert discover_config_path(None) is None

    def test_explicit_path_missing_raises(self, isolated_cwd):
        with pytest.raises(FileNotFoundError):
            discover_config_path(str(isolated_cwd / "nope.yaml"))

    def test_freyarc_discovered_over_freya_yaml(self, isolated_cwd):
        (isolated_cwd / "freya.yaml").write_text("wcag_level: A\n")
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\n")
        path = discover_config_path(None)
        assert path.name == ".freyarc"

    def test_freya_yaml_used_when_no_freyarc(self, isolated_cwd):
        (isolated_cwd / "freya.yaml").write_text("wcag_level: A\n")
        path = discover_config_path(None)
        assert path.name == "freya.yaml"

    def test_explicit_path_wins_over_both(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\n")
        explicit = isolated_cwd / "custom.yaml"
        explicit.write_text("wcag_level: A\n")
        path = discover_config_path(str(explicit))
        assert path == explicit


class TestLoadConfig:
    def test_load_with_no_file_returns_defaults(self, isolated_cwd):
        result = load_config(None)
        assert result.config.wcag_level == "AA"
        assert result.source_path is None
        assert result.sourced_fields == {}

    def test_load_from_freyarc(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\noutput_format: json\n")
        result = load_config(None)
        assert result.config.wcag_level == "AAA"
        assert result.config.output_format == "json"
        assert "wcag_level" in result.sourced_fields
        assert result.source_path.name == ".freyarc"

    def test_load_nested_crawl_config(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text(
            "crawl:\n  start_url: https://example.com\n  max_depth: 2\n  concurrency: 8\n"
        )
        result = load_config(None)
        assert result.config.crawl is not None
        assert result.config.crawl.max_depth == 2
        assert result.config.crawl.concurrency == 8

    def test_invalid_yaml_raises_value_error(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("wcag_level: [unterminated\n")
        with pytest.raises(ValueError):
            load_config(None)

    def test_invalid_schema_raises_validation_error(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("categories: {not: a-list}\n")
        with pytest.raises(ValidationError):
            load_config(None)

    def test_top_level_non_mapping_raises(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError):
            load_config(None)

    def test_explicit_missing_path_raises(self, isolated_cwd):
        with pytest.raises(FileNotFoundError):
            load_config(str(isolated_cwd / "missing.yaml"))


class TestMergeCliOverrides:
    def test_cli_flag_overrides_file_value(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AA\n")
        result = load_config(None)
        merged = merge_cli_overrides(result, {"wcag_level": "AAA"})
        assert merged.config.wcag_level == "AAA"
        assert merged.sourced_fields["wcag_level"] == "CLI flag"

    def test_none_overrides_are_ignored(self, isolated_cwd):
        (isolated_cwd / ".freyarc").write_text("wcag_level: AAA\n")
        result = load_config(None)
        merged = merge_cli_overrides(result, {"wcag_level": None, "output_format": "json"})
        assert merged.config.wcag_level == "AAA"
        assert merged.config.output_format == "json"

    def test_merge_with_no_file_uses_defaults_plus_overrides(self, isolated_cwd):
        result = load_config(None)
        merged = merge_cli_overrides(result, {"output_format": "html"})
        assert merged.config.output_format == "html"
        assert merged.config.wcag_level == "AA"


class TestWriteDefaultConfig:
    def test_init_writes_freyarc(self, isolated_cwd):
        path = write_default_config()
        assert path.name == ".freyarc"
        assert path.exists()
        assert path.read_text() == DEFAULT_FREYARC_TEMPLATE

    def test_init_round_trips_through_loader(self, isolated_cwd):
        write_default_config()
        result = load_config(None)
        assert result.config.wcag_level == "AA"
        assert result.source_path.name == ".freyarc"

    def test_init_custom_path(self, isolated_cwd):
        target = isolated_cwd / "custom" / ".freyarc"
        target.parent.mkdir()
        path = write_default_config(str(target))
        assert path == target
        assert path.exists()

    def test_template_is_valid_yaml_and_loads(self, isolated_cwd):
        write_default_config()
        result = load_config(None)
        # gate.warn_on is documentation-only (not a modeled field); should
        # not raise even though it's present in the written template.
        assert result.config.gate.fail_on
