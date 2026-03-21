"""
Microservice Scaffold Service

Generates complete microservice project structures with
best practices for various languages and frameworks.
"""

import hashlib
import os
from datetime import datetime
from typing import List, Optional

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    FileEntry,
    Framework,
    Language,
    ProjectType,
    ScaffoldReport,
    ServiceConfig,
)
from Asgard.Volundr.Scaffold.services.microservice_scaffold_helpers import (
    generate_common_files,
    generate_generic_service,
    generate_go_service,
    generate_python_service,
    generate_typescript_service,
    get_next_steps,
)


class MicroserviceScaffold:
    """Generates microservice project structures."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "."

    def generate(self, config: ServiceConfig) -> ScaffoldReport:
        scaffold_id = hashlib.sha256(config.model_dump_json().encode()).hexdigest()[:16]

        files: List[FileEntry] = []
        directories: List[str] = []
        messages: List[str] = []

        if config.language == Language.PYTHON:
            files, directories = generate_python_service(config)
        elif config.language == Language.TYPESCRIPT:
            files, directories = generate_typescript_service(config)
        elif config.language == Language.GO:
            files, directories = generate_go_service(config)
        else:
            messages.append(f"Language {config.language.value} scaffolding not yet implemented")
            files, directories = generate_generic_service(config)

        files.extend(generate_common_files(config))

        next_steps = get_next_steps(config)

        return ScaffoldReport(
            id=f"microservice-{scaffold_id}",
            project_name=config.name,
            project_type=config.project_type.value,
            files=files,
            directories=directories,
            total_files=len(files),
            total_directories=len(directories),
            created_at=datetime.now(),
            messages=messages,
            next_steps=next_steps,
        )

    def save_to_directory(
        self, report: ScaffoldReport, output_dir: Optional[str] = None
    ) -> str:
        target_dir = output_dir or self.output_dir

        for directory in report.directories:
            dir_path = os.path.join(target_dir, directory)
            os.makedirs(dir_path, exist_ok=True)

        for file_entry in report.files:
            file_path = os.path.join(target_dir, file_entry.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_entry.content)
            if file_entry.executable:
                os.chmod(file_path, 0o755)

        return os.path.join(target_dir, report.project_name)
