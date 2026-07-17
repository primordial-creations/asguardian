"""
Terraform Module Builder Service

Generates comprehensive Terraform modules with best practices,
documentation, testing frameworks, and multi-cloud provider support.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional

from Asgard.Volundr.Terraform.models.terraform_models import (
    CloudProvider,
    GeneratedModule,
    ModuleComplexity,
    ModuleConfig,
)
from Asgard.Volundr.Terraform.services.module_builder_helpers import (
    PROVIDER_SOURCES,
    generate_data_source_block,
    generate_documentation,
    generate_examples,
    generate_locals_tf,
    generate_main_tf,
    generate_outputs_tf,
    generate_resource_block,
    generate_tests,
    generate_variables_tf,
    generate_versions_tf,
    validate_module,
)
from Asgard.Volundr.Validation.models.suppression_models import SuppressionSet
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine
from Asgard.Volundr.Validation.services.suppression_engine import (
    SuppressionEngine,
    append_comment_receipts,
)
from Asgard.Volundr.Validation.services.terraform_validator import TerraformValidator


class ModuleBuilder:
    """Generates Terraform modules from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "modules"

    def generate(self, config: ModuleConfig) -> GeneratedModule:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        module_id = f"{config.name}-{config_hash}"

        module_files: Dict[str, str] = {}
        module_files["main.tf"] = generate_main_tf(config)
        module_files["variables.tf"] = generate_variables_tf(config)
        module_files["outputs.tf"] = generate_outputs_tf(config)
        module_files["versions.tf"] = generate_versions_tf(config)

        if config.locals:
            module_files["locals.tf"] = generate_locals_tf(config)

        # Render -> validate -> score (plan 02 §4; same decoupled pipeline
        # as Kubernetes/Docker generators — never grade the generator's own
        # config, only the rendered HCL, per the "Collusion Problem"
        # (DEEPTHINK_05 §1A)).
        structural_issues = validate_module(module_files, config)

        rendered_hcl = "\n\n".join(
            module_files[fname]
            for fname in ("main.tf", "variables.tf", "outputs.tf", "versions.tf")
            if fname in module_files
        )
        raw_report = TerraformValidator().validate_content(rendered_hcl, file_path="main.tf")

        user_engine = SuppressionEngine(SuppressionSet(suppressions=config.suppressions))
        outcome = user_engine.apply(list(raw_report.results))
        final_results = outcome.results + outcome.hygiene
        applied = outcome.applied

        if applied:
            seen_rules = set()
            unique_suppressions = []
            for s, _ in applied:
                if s.rule not in seen_rules:
                    seen_rules.add(s.rule)
                    unique_suppressions.append(s)
            unique_suppressions.sort(key=lambda s: s.rule)
            module_files["main.tf"] = append_comment_receipts(
                module_files["main.tf"], unique_suppressions
            )

        score_report = ScoringEngine().score(
            final_results,
            environment=config.environment_profile,
            suppressed=applied,
        )
        best_practice_score = score_report.composite

        validation_results = structural_issues + [
            f"[{r.rule_id}] {r.severity.value}: {r.message}" for r in final_results
        ]

        documentation = generate_documentation(config)
        module_files["README.md"] = documentation

        examples = generate_examples(config)
        tests = generate_tests(config)

        return GeneratedModule(
            id=module_id,
            config_hash=config_hash,
            module_files=module_files,
            documentation=documentation,
            examples=examples,
            tests=tests,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
            score_report=score_report,
            applied_suppressions=sorted({s.rule for s, _ in applied}),
        )

    def save_to_directory(self, module: GeneratedModule, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        module_dir = os.path.join(target_dir, module.id)
        os.makedirs(module_dir, exist_ok=True)

        for filename, content in module.module_files.items():
            file_path = os.path.join(module_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        if module.examples:
            examples_dir = os.path.join(module_dir, "examples")
            os.makedirs(examples_dir, exist_ok=True)
            for example_name, content in module.examples.items():
                example_dir = os.path.join(examples_dir, example_name)
                os.makedirs(example_dir, exist_ok=True)
                with open(os.path.join(example_dir, "main.tf"), "w", encoding="utf-8") as f:
                    f.write(content)

        if module.tests:
            tests_dir = os.path.join(module_dir, "test")
            os.makedirs(tests_dir, exist_ok=True)
            for test_name, content in module.tests.items():
                if test_name == "terratest":
                    with open(os.path.join(tests_dir, "main_test.go"), "w", encoding="utf-8") as f:
                        f.write(content)
                elif test_name == "kitchen":
                    with open(os.path.join(tests_dir, ".kitchen.yml"), "w", encoding="utf-8") as f:
                        f.write(content)

        return module_dir
