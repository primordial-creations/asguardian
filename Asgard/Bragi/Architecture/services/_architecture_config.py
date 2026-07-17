from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class RulesConfig:
    """Optional top-level `rules:` block (Plan 03 schema)."""

    max_module_fan_out: Optional[int] = None
    detect_module_cycles: bool = True


@dataclass
class LayerConfig:
    name: str
    path_patterns: list[str]
    allowed_imports: list[str]
    forbidden_imports: list[str]
    # --- Plan 03 extensions (all optional, backward compatible) ---
    level: Optional[int] = None
    suffixes: list[str] = field(default_factory=list)
    external_imports: list[str] = field(default_factory=list)


@dataclass
class ArchitectureConfig:
    layers: list[LayerConfig] = field(default_factory=list)
    language: str = "python"
    rules: RulesConfig = field(default_factory=RulesConfig)

    @property
    def has_level_inference(self) -> bool:
        """True when at least one layer declares a `level:` — enables the
        CSP layer-inference engine. False keeps the original glob-only
        classification path (old schema)."""
        return any(layer.level is not None for layer in self.layers)


def _parse_layer(layer: dict) -> LayerConfig:
    heuristics = layer.get("heuristics") or {}
    # New schema nests path patterns/suffixes/external anchors under
    # `heuristics:`; old schema keeps `path_patterns` at the layer's top
    # level. Support both — heuristics.paths wins if both are present.
    path_patterns = heuristics.get("paths") or layer.get("path_patterns", [])
    suffixes = heuristics.get("suffixes", [])
    external_imports = heuristics.get("external_imports", [])

    return LayerConfig(
        name=layer["name"],
        path_patterns=path_patterns,
        allowed_imports=layer.get("allowed_imports", []),
        forbidden_imports=layer.get("forbidden_imports", []),
        level=layer.get("level"),
        suffixes=suffixes,
        external_imports=external_imports,
    )


def load_architecture_config(config_path: str) -> ArchitectureConfig:
    if not os.path.exists(config_path):
        return default_architecture_config()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return default_architecture_config()

    # New schema nests metadata under `architecture:` with a sibling
    # top-level `layers:`/`rules:`; old schema puts `layers:` at the root
    # with no `architecture:` key. Both are accepted.
    layers_data = data.get("layers", [])
    rules_data = data.get("rules") or {}
    language = data.get("language") or (data.get("architecture") or {}).get("language", "python")

    layers = [_parse_layer(layer) for layer in layers_data]

    rules = RulesConfig(
        max_module_fan_out=rules_data.get("max_module_fan_out"),
        detect_module_cycles=rules_data.get("detect_module_cycles", True),
    )

    return ArchitectureConfig(
        layers=layers,
        language=language,
        rules=rules,
    )


def default_architecture_config() -> ArchitectureConfig:
    """Zero-config default: sensible layer inference with no
    architecture.yml present. Levels are set so CSP inference is active
    by default (Plan 03's "no architecture.yml" requirement)."""
    return ArchitectureConfig(
        language="python",
        layers=[
            LayerConfig(
                name="domain",
                path_patterns=["*/domain/*", "*/models/*"],
                allowed_imports=[],
                forbidden_imports=["infrastructure", "adapters"],
                level=0,
                suffixes=["Entity", "ValueObject", "Model"],
            ),
            LayerConfig(
                name="ports",
                path_patterns=["*/ports/*"],
                allowed_imports=["domain"],
                forbidden_imports=["infrastructure"],
                level=0,
            ),
            LayerConfig(
                name="application",
                path_patterns=["*/services/*", "*/use_cases/*"],
                allowed_imports=["domain", "ports"],
                forbidden_imports=["infrastructure"],
                level=1,
                suffixes=["UseCase", "Service", "Handler"],
            ),
            LayerConfig(
                name="infrastructure",
                path_patterns=["*/infrastructure/*", "*/adapters/*", "*/repositories/*"],
                allowed_imports=["domain", "ports", "application"],
                forbidden_imports=[],
                level=2,
                external_imports=[
                    "sqlalchemy", "psycopg2", "requests", "boto3", "django.db",
                ],
            ),
        ],
        rules=RulesConfig(max_module_fan_out=12, detect_module_cycles=True),
    )
