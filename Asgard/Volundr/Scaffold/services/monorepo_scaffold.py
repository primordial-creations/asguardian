"""
Monorepo Scaffold Service

Generates monorepo project structures with shared
infrastructure and multiple services.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    ProjectConfig,
    ScaffoldReport,
    FileEntry,
    Language,
    CICDPlatform,
    ContainerOrchestration,
)
from Asgard.Volundr.Scaffold.services.microservice_scaffold import MicroserviceScaffold
from Asgard.Volundr.Scaffold.services.monorepo_scaffold_helpers import (
    root_readme,
    root_gitignore,
    makefile,
    pre_commit_config,
    editorconfig,
    root_docker_compose,
    root_pyproject,
    root_package_json,
    turbo_json,
    k8s_base_kustomization,
    k8s_namespace,
    k8s_overlay_kustomization,
    terraform_main,
    terraform_variables,
    terraform_outputs,
    github_actions_ci,
    github_actions_cd,
    gitlab_ci,
    codeowners,
    pr_template,
    get_next_steps,
)


class MonorepoScaffold:
    """Generates monorepo project structures."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "."
        self.microservice_scaffold = MicroserviceScaffold()

    def generate(self, config: ProjectConfig) -> ScaffoldReport:
        scaffold_id = hashlib.sha256(config.model_dump_json().encode()).hexdigest()[:16]

        files: List[FileEntry] = []
        directories: List[str] = []
        messages: List[str] = []

        directories.extend([
            config.name,
            f"{config.name}/services",
            f"{config.name}/packages",
            f"{config.name}/infrastructure",
            f"{config.name}/infrastructure/kubernetes",
            f"{config.name}/infrastructure/terraform",
            f"{config.name}/scripts",
            f"{config.name}/docs",
        ])

        files.extend(self._generate_root_files(config))
        files.extend(self._generate_infrastructure_files(config))
        directories.extend(self._get_infrastructure_directories(config))

        if config.cicd_platform != CICDPlatform.NONE:
            files.extend(self._generate_cicd_files(config))
            directories.extend(self._get_cicd_directories(config))

        for service in config.services:
            service_report = self.microservice_scaffold.generate(service)

            for file_entry in service_report.files:
                files.append(FileEntry(
                    path=f"{config.name}/services/{file_entry.path}",
                    content=file_entry.content,
                    executable=file_entry.executable,
                ))

            for directory in service_report.directories:
                directories.append(f"{config.name}/services/{directory}")

        next_steps = get_next_steps(config)

        return ScaffoldReport(
            id=f"monorepo-{scaffold_id}",
            project_name=config.name,
            project_type="monorepo",
            files=files,
            directories=directories,
            total_files=len(files),
            total_directories=len(directories),
            created_at=datetime.now(),
            messages=messages,
            next_steps=next_steps,
        )

    def _generate_root_files(self, config: ProjectConfig) -> List[FileEntry]:
        files: List[FileEntry] = []

        files.append(FileEntry(path=f"{config.name}/README.md", content=root_readme(config)))
        files.append(FileEntry(path=f"{config.name}/.gitignore", content=root_gitignore(config)))

        if config.include_makefile:
            files.append(FileEntry(path=f"{config.name}/Makefile", content=makefile(config)))

        if config.include_pre_commit:
            files.append(FileEntry(
                path=f"{config.name}/.pre-commit-config.yaml",
                content=pre_commit_config(config),
            ))

        files.append(FileEntry(path=f"{config.name}/.editorconfig", content=editorconfig()))
        files.append(FileEntry(
            path=f"{config.name}/docker-compose.yaml",
            content=root_docker_compose(config),
        ))

        primary_lang = self._get_primary_language(config)
        if primary_lang == Language.PYTHON:
            files.append(FileEntry(
                path=f"{config.name}/pyproject.toml",
                content=root_pyproject(config),
            ))
        elif primary_lang == Language.TYPESCRIPT:
            files.append(FileEntry(
                path=f"{config.name}/package.json",
                content=root_package_json(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/turbo.json",
                content=turbo_json(config),
            ))

        return files

    def _generate_infrastructure_files(self, config: ProjectConfig) -> List[FileEntry]:
        files: List[FileEntry] = []

        if config.orchestration == ContainerOrchestration.KUBERNETES:
            files.append(FileEntry(
                path=f"{config.name}/infrastructure/kubernetes/base/kustomization.yaml",
                content=k8s_base_kustomization(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/infrastructure/kubernetes/base/namespace.yaml",
                content=k8s_namespace(config),
            ))

            for env in ["development", "staging", "production"]:
                files.append(FileEntry(
                    path=f"{config.name}/infrastructure/kubernetes/overlays/{env}/kustomization.yaml",
                    content=k8s_overlay_kustomization(config, env),
                ))

        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/main.tf",
            content=terraform_main(config),
        ))
        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/variables.tf",
            content=terraform_variables(config),
        ))
        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/outputs.tf",
            content=terraform_outputs(config),
        ))

        return files

    def _get_infrastructure_directories(self, config: ProjectConfig) -> List[str]:
        return [
            f"{config.name}/infrastructure/kubernetes/base",
            f"{config.name}/infrastructure/kubernetes/overlays/development",
            f"{config.name}/infrastructure/kubernetes/overlays/staging",
            f"{config.name}/infrastructure/kubernetes/overlays/production",
        ]

    def _generate_cicd_files(self, config: ProjectConfig) -> List[FileEntry]:
        files: List[FileEntry] = []

        if config.cicd_platform == CICDPlatform.GITHUB_ACTIONS:
            files.append(FileEntry(
                path=f"{config.name}/.github/workflows/ci.yaml",
                content=github_actions_ci(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/workflows/cd.yaml",
                content=github_actions_cd(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/CODEOWNERS",
                content=codeowners(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/pull_request_template.md",
                content=pr_template(),
            ))

        elif config.cicd_platform == CICDPlatform.GITLAB_CI:
            files.append(FileEntry(
                path=f"{config.name}/.gitlab-ci.yml",
                content=gitlab_ci(config),
            ))

        return files

    def _get_cicd_directories(self, config: ProjectConfig) -> List[str]:
        dirs = []
        if config.cicd_platform == CICDPlatform.GITHUB_ACTIONS:
            dirs.append(f"{config.name}/.github/workflows")
        return dirs

    def _get_primary_language(self, config: ProjectConfig) -> Language:
        if not config.services:
            return Language.PYTHON
        lang_counts: Dict[Language, int] = {}
        for service in config.services:
            lang_counts[service.language] = lang_counts.get(service.language, 0) + 1
        return max(lang_counts, key=lambda k: lang_counts[k])

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
