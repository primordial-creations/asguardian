"""
Kustomize Base Generator Service

Generates Kustomize base configurations with resources,
transformers, and generators.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, Optional

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    KustomizeConfig,
)
from Asgard.Volundr.Kustomize.services.base_generator_helpers import (
    calculate_best_practice_score,  # noqa: F401  (deprecated, kept for API compat)
    generate_base_kustomization,
    generate_deployment,
    generate_hpa,
    generate_networkpolicy,
    generate_service,
    kustomization_findings,
    validate_base,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine


class BaseGenerator:
    """Generates Kustomize base configurations."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "kustomize"

    def generate(self, config: KustomizeConfig) -> GeneratedKustomization:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        kustomization_id = f"{config.base.name}-{config_hash}"

        files: Dict[str, str] = {}

        if config.generate_deployment:
            files["base/deployment.yaml"] = generate_deployment(config)

        if config.generate_service:
            files["base/service.yaml"] = generate_service(config)

        if config.generate_hpa:
            files["base/hpa.yaml"] = generate_hpa(config)

        if config.generate_networkpolicy:
            files["base/networkpolicy.yaml"] = generate_networkpolicy(config)

        files["base/kustomization.yaml"] = generate_base_kustomization(config, files)

        validation_results = validate_base(files, config)

        # Adversarial validation + composite scoring (plan 07) over the
        # RENDERED files: K8s manifests through the shared engine, the
        # kustomization through the v5-semantics checks.
        engine = ValidationEngine()
        findings = []
        for path, content in files.items():
            if path.endswith("kustomization.yaml"):
                findings.extend(kustomization_findings(content, path))
            else:
                findings.extend(engine.validate_kubernetes(content, source=path).results)
        validation_results.extend(f"{r.rule_id}: {r.message}" for r in findings)
        score_report = ScoringEngine().score(findings, resources=list(files))

        return GeneratedKustomization(
            id=kustomization_id,
            config_hash=config_hash,
            files=files,
            validation_results=validation_results,
            best_practice_score=score_report.composite,
            created_at=datetime.now(),
        )

    def save_to_directory(
        self, kustomization: GeneratedKustomization, output_dir: Optional[str] = None
    ) -> str:
        target_dir = output_dir or self.output_dir

        for file_path, content in kustomization.files.items():
            full_path = os.path.join(target_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
