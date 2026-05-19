"""Tests for AsgardConfigLoader."""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from Asgard.config.loader import AsgardConfigLoader
from Asgard.config.models import AsgardConfig


class TestAsgardConfigLoaderInstantiation:
    def test_loader_can_be_instantiated(self):
        loader = AsgardConfigLoader()
        assert loader is not None

    def test_loader_accepts_explicit_project_root(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        assert loader.project_root == tmp_path

    def test_loader_defaults_project_root_to_cwd(self):
        loader = AsgardConfigLoader()
        assert loader.project_root == Path.cwd()


class TestAsgardConfigLoaderCleanPath:
    def test_load_returns_asgard_config_with_no_files(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        config = loader.load()
        assert isinstance(config, AsgardConfig)

    def test_load_from_yaml_file(self, tmp_path):
        yaml_content = "global:\n  verbose: true\n"
        (tmp_path / "asgard.yaml").write_text(yaml_content)
        loader = AsgardConfigLoader(project_root=tmp_path)
        config = loader.load()
        assert isinstance(config, AsgardConfig)
        assert config.global_config.verbose is True

    def test_load_from_asgardrc_json(self, tmp_path):
        rc_content = json.dumps({"global": {"verbose": False}})
        (tmp_path / ".asgardrc").write_text(rc_content)
        loader = AsgardConfigLoader(project_root=tmp_path)
        config = loader.load()
        assert isinstance(config, AsgardConfig)

    def test_generate_default_yaml_returns_string(self):
        result = AsgardConfigLoader.generate_default_yaml()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_default_toml_returns_string(self):
        result = AsgardConfigLoader.generate_default_toml()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_default_json_returns_string(self):
        result = AsgardConfigLoader.generate_default_json()
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_get_config_uses_cache(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        config1 = loader.get_config()
        config2 = loader.get_config()
        assert config1 is config2

    def test_reload_invalidates_cache(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        config1 = loader.load()
        config2 = loader.reload()
        assert config1 is not config2

    def test_env_override_verbose(self, tmp_path):
        with patch.dict(os.environ, {"ASGARD_GLOBAL_VERBOSE": "true"}):
            loader = AsgardConfigLoader(project_root=tmp_path)
            config = loader.load()
            assert isinstance(config, AsgardConfig)

    def test_cli_override_applied(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        config = loader.load(cli_overrides={"global": {"verbose": True}})
        assert isinstance(config, AsgardConfig)

    def test_get_config_file_path_none_when_no_file(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        loader.load()
        assert loader.get_config_file_path() is None

    def test_get_config_file_path_set_when_yaml_present(self, tmp_path):
        (tmp_path / "asgard.yaml").write_text("global:\n  verbose: false\n")
        loader = AsgardConfigLoader(project_root=tmp_path)
        loader.load()
        assert loader.get_config_file_path() is not None


class TestAsgardConfigLoaderEdgeCases:
    def test_empty_asgardrc_returns_defaults(self, tmp_path):
        (tmp_path / ".asgardrc").write_text("")
        loader = AsgardConfigLoader(project_root=tmp_path)
        config = loader.load()
        assert isinstance(config, AsgardConfig)

    def test_convert_env_value_true(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        assert loader._convert_env_value("true") is True
        assert loader._convert_env_value("yes") is True
        assert loader._convert_env_value("1") is True

    def test_convert_env_value_false(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        assert loader._convert_env_value("false") is False
        assert loader._convert_env_value("no") is False
        assert loader._convert_env_value("0") is False

    def test_convert_env_value_int(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        assert loader._convert_env_value("42") == 42

    def test_convert_env_value_float(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        assert loader._convert_env_value("3.14") == pytest.approx(3.14)

    def test_convert_env_value_list(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        result = loader._convert_env_value("a,b,c")
        assert result == ["a", "b", "c"]

    def test_deep_merge_overrides_scalar(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        merged = loader._deep_merge({"a": 1, "b": 2}, {"b": 99})
        assert merged == {"a": 1, "b": 99}

    def test_deep_merge_recursive_dicts(self, tmp_path):
        loader = AsgardConfigLoader(project_root=tmp_path)
        merged = loader._deep_merge({"x": {"y": 1, "z": 2}}, {"x": {"z": 99}})
        assert merged["x"]["y"] == 1
        assert merged["x"]["z"] == 99
