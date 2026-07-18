"""
Kustomize Component Generator (RESEARCH_09) — cross-cutting mix-ins.

Emits ``kind: Component`` kustomizations
(``kustomize.config.k8s.io/v1alpha1``) under ``components/<name>/`` that
bases and overlays opt into via their ``components:`` field.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    KustomizeComponent,
)
from Asgard.Volundr.Kustomize.services.base_generator_helpers import (
    kustomization_findings,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine


class ComponentGenerator:
    """Generates Kustomize Components."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "kustomize"

    def generate(self, component: KustomizeComponent) -> GeneratedKustomization:
        config_json = component.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]

        kustomization: Dict[str, Any] = {
            "apiVersion": "kustomize.config.k8s.io/v1alpha1",
            "kind": "Component",
        }
        if component.resources:
            kustomization["resources"] = list(component.resources)
        if component.patches:
            patches = []
            for patch in component.patches:
                entry: Dict[str, Any] = {}
                if patch.patch_content:
                    entry["patch"] = patch.patch_content
                else:
                    entry["path"] = f"{patch.name}.yaml"
                if patch.target is not None:
                    target = {"kind": patch.target.kind, "name": patch.target.name}
                    if patch.target.group:
                        target["group"] = patch.target.group
                    if patch.target.namespace:
                        target["namespace"] = patch.target.namespace
                    entry["target"] = target
                patches.append(entry)
            kustomization["patches"] = patches
        if component.config_map_generators:
            kustomization["configMapGenerator"] = [
                {"name": cm.name, **({"literals": cm.literals} if cm.literals else {}),
                 **({"files": cm.files} if cm.files else {})}
                for cm in component.config_map_generators
            ]
        if component.secret_generators:
            kustomization["secretGenerator"] = [
                {"name": s.name, "type": s.type,
                 **({"literals": s.literals} if s.literals else {}),
                 **({"files": s.files} if s.files else {})}
                for s in component.secret_generators
            ]

        content = cast(
            str, yaml.dump(kustomization, default_flow_style=False, sort_keys=False)
        )
        path = f"components/{component.name}/kustomization.yaml"
        files = {path: content}

        findings = kustomization_findings(content, path)
        score_report = ScoringEngine().score(findings, resources=[path])

        return GeneratedKustomization(
            id=f"{component.name}-component-{config_hash}",
            config_hash=config_hash,
            files=files,
            validation_results=[f"{r.rule_id}: {r.message}" for r in findings],
            best_practice_score=score_report.composite,
            created_at=datetime.now(),
        )
