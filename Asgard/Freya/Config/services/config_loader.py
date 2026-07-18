"""
Freya Config Loader

Discovery order: `--config PATH` > `./.freyarc` > `./freya.yaml` > defaults.
CLI flags always override file values (the CLI handlers layer flag
overrides on top of what this loader returns; this module only handles
file discovery/parse/merge-of-file-with-defaults).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import ValidationError

from Asgard.Freya.Config.models.config_models import FreyaConfig

DEFAULT_CONFIG_FILENAMES = (".freyarc", "freya.yaml")

DEFAULT_FREYARC_TEMPLATE = """\
# .freyarc — Freya configuration
# Discovery order: --config PATH > ./.freyarc > ./freya.yaml > built-in defaults.
# CLI flags always override values set here.

wcag_level: AA          # Target WCAG conformance level
output_format: text     # text | json | html | junit

# crawl:
#   start_url: https://example.com
#   max_depth: 2
#   max_pages: 100
#   concurrency: 4              # bounded worker concurrency for the test phase
#   concurrency_discovery: 2    # bounded sibling-fetch concurrency during discovery
#   min_request_interval_ms: 500  # per-host politeness interval

categories:
  - accessibility
  - visual
  - responsive
  # - performance
  # - security
  # - links

# budgets:
#   "/docs/**": {archetype: document}
#   "/checkout": {archetype: transactional}

gate:
  fail_on: [blocker, critical]
  warn_on: [major]
  min_grade: null

visual:
  allow_env_mismatch: false
"""


class ConfigLoadResult:
    """Loaded config plus provenance info for `config show`."""

    def __init__(
        self,
        config: FreyaConfig,
        source_path: Optional[Path],
        sourced_fields: Dict[str, str],
    ):
        self.config = config
        self.source_path = source_path
        self.sourced_fields = sourced_fields  # dotted field path -> source label


def discover_config_path(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Find the config file to load, per the discovery order."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {explicit_path}")
        return path

    for filename in DEFAULT_CONFIG_FILENAMES:
        candidate = Path.cwd() / filename
        if candidate.is_file():
            return candidate

    return None


def _flatten_keys(data: Dict[str, Any], prefix: str = "") -> List[str]:
    """List dotted keys present in a raw (pre-validation) config dict."""
    keys: List[str] = []
    for key, value in data.items():
        dotted = f"{prefix}{key}"
        keys.append(dotted)
        if isinstance(value, dict):
            keys.extend(_flatten_keys(value, prefix=f"{dotted}."))
    return keys


def load_config(explicit_path: Optional[str] = None) -> ConfigLoadResult:
    """
    Load and validate the effective FreyaConfig.

    Raises FileNotFoundError if `--config PATH` names a missing file, or
    pydantic.ValidationError (re-raised) if the file content is invalid.
    """
    path = discover_config_path(explicit_path)

    if path is None:
        return ConfigLoadResult(FreyaConfig(), None, {})

    raw_text = path.read_text(encoding="utf-8")
    try:
        raw_data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping at the top level")

    try:
        config = FreyaConfig(**raw_data)
    except ValidationError:
        raise

    sourced_fields = {key: str(path) for key in _flatten_keys(raw_data)}
    return ConfigLoadResult(config, path, sourced_fields)


def merge_cli_overrides(
    result: ConfigLoadResult,
    overrides: Dict[str, Any],
) -> ConfigLoadResult:
    """
    Apply CLI-flag overrides on top of a loaded config (flags always win).

    `overrides` is a flat dict of top-level FreyaConfig field names to
    override values; None values are ignored (not explicitly set on the CLI).
    """
    data = result.config.model_dump()
    sourced = dict(result.sourced_fields)
    for key, value in overrides.items():
        if value is None:
            continue
        data[key] = value
        sourced[key] = "CLI flag"

    merged = FreyaConfig(**data)
    return ConfigLoadResult(merged, result.source_path, sourced)


def write_default_config(path: Optional[str] = None) -> Path:
    """Write the commented default `.freyarc` template. Returns the path written."""
    target = Path(path) if path else Path.cwd() / ".freyarc"
    target.write_text(DEFAULT_FREYARC_TEMPLATE, encoding="utf-8")
    return target


def describe_field_source(result: ConfigLoadResult, field_path: str, default: Any) -> Tuple[Any, str]:
    """Return (value, source_label) for `config show` annotations."""
    source = result.sourced_fields.get(field_path)
    if source is None:
        return default, "default"
    return default, f"from {Path(source).name}"
