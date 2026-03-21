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
    calculate_best_practice_score,
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

        documentation = generate_documentation(config)
        module_files["README.md"] = documentation

        examples = generate_examples(config)
        tests = generate_tests(config)

        validation_results = validate_module(module_files, config)
        best_practice_score = calculate_best_practice_score(module_files, config)

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
