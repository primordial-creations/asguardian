from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class LayerConfig:
    name: str
    path_patterns: list[str]
    allowed_imports: list[str]
    forbidden_imports: list[str]


@dataclass
class ArchitectureConfig:
    layers: list[LayerConfig] = field(default_factory=list)
    language: str = "python"


def load_architecture_config(config_path: str) -> ArchitectureConfig:
    if not os.path.exists(config_path):
        return default_architecture_config()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return default_architecture_config()

    layers = [
        LayerConfig(
            name=layer["name"],
            path_patterns=layer.get("path_patterns", []),
            allowed_imports=layer.get("allowed_imports", []),
            forbidden_imports=layer.get("forbidden_imports", []),
        )
        for layer in data.get("layers", [])
    ]

    return ArchitectureConfig(
        layers=layers,
        language=data.get("language", "python"),
    )


def default_architecture_config() -> ArchitectureConfig:
    return ArchitectureConfig(
        language="python",
        layers=[
            LayerConfig(
                name="domain",
                path_patterns=["*/domain/*", "*/models/*"],
                allowed_imports=[],
                forbidden_imports=["infrastructure", "adapters"],
            ),
            LayerConfig(
                name="ports",
                path_patterns=["*/ports/*"],
                allowed_imports=["domain"],
                forbidden_imports=["infrastructure"],
            ),
            LayerConfig(
                name="application",
                path_patterns=["*/services/*", "*/use_cases/*"],
                allowed_imports=["domain", "ports"],
                forbidden_imports=["infrastructure"],
            ),
            LayerConfig(
                name="infrastructure",
                path_patterns=["*/infrastructure/*", "*/adapters/*", "*/repositories/*"],
                allowed_imports=["domain", "ports", "application"],
                forbidden_imports=[],
            ),
        ],
    )
