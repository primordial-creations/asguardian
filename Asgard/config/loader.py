"""
Asgard Configuration Loader

Loads configuration from multiple sources with precedence:
1. Environment variables (ASGARD_*)
2. CLI arguments
3. asgard.yaml
4. pyproject.toml [tool.asgard]
5. .asgardrc
6. Default values
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, cast

import yaml  # type: ignore[import-untyped]

import tomllib  # type: ignore[import]

from Asgard.config.models import AsgardConfig
from Asgard.config.defaults import DEFAULT_CONFIG


class AsgardConfigLoader:
    """
    Loader for Asgard configuration.

    Supports loading from multiple sources with cascading precedence.
    """

    CONFIG_FILE_NAMES = ["asgard.yaml", "asgard.yml", ".asgardrc"]
    PYPROJECT_FILE = "pyproject.toml"
    ENV_PREFIX = "ASGARD_"

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the configuration loader.

        Args:
            project_root: Root directory to search for config files.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self._config_cache: Optional[AsgardConfig] = None
        self._config_file_path: Optional[Path] = None

    def load(self, cli_overrides: Optional[Dict[str, Any]] = None) -> AsgardConfig:
        """
        Load configuration from all sources.

        Args:
            cli_overrides: Dictionary of CLI argument overrides.

        Returns:
            Merged AsgardConfig instance.
        """
        # Start with defaults
        config_dict = DEFAULT_CONFIG.model_dump(by_alias=True)

        # Load from .asgardrc (lowest priority file config)
        rc_config = self._load_asgardrc()
        if rc_config:
            config_dict = self._deep_merge(config_dict, rc_config)

        # Load from pyproject.toml
        toml_config = self._load_pyproject_toml()
        if toml_config:
            config_dict = self._deep_merge(config_dict, toml_config)

        # Load from asgard.yaml (highest priority file config)
        yaml_config = self._load_yaml_config()
        if yaml_config:
            config_dict = self._deep_merge(config_dict, yaml_config)

        # Apply CLI overrides
        if cli_overrides:
            config_dict = self._deep_merge(config_dict, cli_overrides)

        # Apply environment variable overrides (highest priority)
        env_config = self._load_env_overrides()
        if env_config:
            config_dict = self._deep_merge(config_dict, env_config)

        # Create and cache the config
        self._config_cache = AsgardConfig(**config_dict)
        return self._config_cache

    def _find_config_file(self, filenames: list) -> Optional[Path]:
        """Find the first existing config file from the list."""
        for filename in filenames:
            config_path = self.project_root / str(filename)
            if config_path.exists():
                return config_path
        return None

    def _load_yaml_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file."""
        config_path = self._find_config_file(["asgard.yaml", "asgard.yml"])
        if not config_path:
            return None

        self._config_file_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else None

    def _load_asgardrc(self) -> Optional[Dict[str, Any]]:
        """Load configuration from .asgardrc file (JSON format)."""
        config_path = self.project_root / ".asgardrc"
        if not config_path.exists():
            return None

        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            try:
                return cast(Dict[str, Any], json.loads(content))
            except json.JSONDecodeError:
                # Try YAML format
                return cast(Dict[str, Any], yaml.safe_load(content))

    def _load_pyproject_toml(self) -> Optional[Dict[str, Any]]:
        """Load configuration from pyproject.toml [tool.asgard] section."""
        pyproject_path = self.project_root / self.PYPROJECT_FILE
        if not pyproject_path.exists():
            return None

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        return cast(Optional[Dict[str, Any]], data.get("tool", {}).get("asgard", None))

    def _load_env_overrides(self) -> Dict[str, Any]:
        """
        Load configuration overrides from environment variables.

        Environment variables use the pattern:
        ASGARD_<SECTION>_<KEY>=value
        ASGARD_GLOBAL_VERBOSE=true
        ASGARD_HEIMDALL_QUALITY_CYCLOMATIC_COMPLEXITY_THRESHOLD=15
        """
        overrides: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(self.ENV_PREFIX):
                continue

            # Remove prefix and split into parts
            parts = key[len(self.ENV_PREFIX):].lower().split("_")
            if not parts:
                continue

            # Build nested dictionary
            current = overrides
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set the value with type conversion
            current[parts[-1]] = self._convert_env_value(value)

        return overrides

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # List (comma-separated)
        if "," in value:
            return [v.strip() for v in value.split(",")]

        return value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with override taking precedence.

        Args:
            base: Base dictionary.
            override: Dictionary with values to override.

        Returns:
            Merged dictionary.
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_config(self) -> AsgardConfig:
        """
        Get the cached configuration or load it.

        Returns:
            Cached or freshly loaded AsgardConfig.
        """
        if self._config_cache is None:
            return self.load()
        return self._config_cache

    def get_config_file_path(self) -> Optional[Path]:
        """Get the path to the loaded config file, if any."""
        return self._config_file_path

    def reload(self, cli_overrides: Optional[Dict[str, Any]] = None) -> AsgardConfig:
        """
        Force reload configuration from all sources.

        Args:
            cli_overrides: Dictionary of CLI argument overrides.

        Returns:
            Fresh AsgardConfig instance.
        """
        self._config_cache = None
        self._config_file_path = None
        return self.load(cli_overrides)

    @classmethod
    def generate_default_yaml(cls) -> str:
        """Generate default configuration as YAML string."""
        return cast(str, DEFAULT_CONFIG.to_yaml())

    @classmethod
    def generate_default_toml(cls) -> str:
        """Generate default configuration as TOML string for pyproject.toml."""
        return cast(str, DEFAULT_CONFIG.to_toml())

    @classmethod
    def generate_default_json(cls) -> str:
        """Generate default configuration as JSON string."""
        return cast(str, DEFAULT_CONFIG.model_dump_json(indent=2, by_alias=True))
