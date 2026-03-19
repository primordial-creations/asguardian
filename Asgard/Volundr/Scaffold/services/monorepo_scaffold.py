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


class MonorepoScaffold:
    """Generates monorepo project structures."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the monorepo scaffold.

        Args:
            output_dir: Directory for saving generated projects
        """
        self.output_dir = output_dir or "."
        self.microservice_scaffold = MicroserviceScaffold()

    def generate(self, config: ProjectConfig) -> ScaffoldReport:
        """
        Generate a monorepo project structure.

        Args:
            config: Project configuration

        Returns:
            ScaffoldReport with generated files
        """
        scaffold_id = hashlib.sha256(config.model_dump_json().encode()).hexdigest()[:16]

        files: List[FileEntry] = []
        directories: List[str] = []
        messages: List[str] = []

        # Root directories
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

        # Generate root files
        files.extend(self._generate_root_files(config))

        # Generate infrastructure files
        files.extend(self._generate_infrastructure_files(config))
        directories.extend(self._get_infrastructure_directories(config))

        # Generate CI/CD configuration
        if config.cicd_platform != CICDPlatform.NONE:
            files.extend(self._generate_cicd_files(config))
            directories.extend(self._get_cicd_directories(config))

        # Generate services
        for service in config.services:
            service_report = self.microservice_scaffold.generate(service)

            # Adjust paths for monorepo structure
            for file_entry in service_report.files:
                files.append(FileEntry(
                    path=f"{config.name}/services/{file_entry.path}",
                    content=file_entry.content,
                    executable=file_entry.executable,
                ))

            for directory in service_report.directories:
                directories.append(f"{config.name}/services/{directory}")

        next_steps = self._get_next_steps(config)

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
        """Generate root-level files."""
        files: List[FileEntry] = []

        # Root README
        files.append(FileEntry(
            path=f"{config.name}/README.md",
            content=self._root_readme(config),
        ))

        # Root .gitignore
        files.append(FileEntry(
            path=f"{config.name}/.gitignore",
            content=self._root_gitignore(config),
        ))

        # Makefile
        if config.include_makefile:
            files.append(FileEntry(
                path=f"{config.name}/Makefile",
                content=self._makefile(config),
            ))

        # Pre-commit config
        if config.include_pre_commit:
            files.append(FileEntry(
                path=f"{config.name}/.pre-commit-config.yaml",
                content=self._pre_commit_config(config),
            ))

        # EditorConfig
        files.append(FileEntry(
            path=f"{config.name}/.editorconfig",
            content=self._editorconfig(),
        ))

        # Docker Compose for local development
        files.append(FileEntry(
            path=f"{config.name}/docker-compose.yaml",
            content=self._root_docker_compose(config),
        ))

        # Root package files based on primary language
        primary_lang = self._get_primary_language(config)
        if primary_lang == Language.PYTHON:
            files.append(FileEntry(
                path=f"{config.name}/pyproject.toml",
                content=self._root_pyproject(config),
            ))
        elif primary_lang == Language.TYPESCRIPT:
            files.append(FileEntry(
                path=f"{config.name}/package.json",
                content=self._root_package_json(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/turbo.json",
                content=self._turbo_json(config),
            ))

        return files

    def _generate_infrastructure_files(self, config: ProjectConfig) -> List[FileEntry]:
        """Generate infrastructure configuration files."""
        files: List[FileEntry] = []

        if config.orchestration == ContainerOrchestration.KUBERNETES:
            # Kubernetes base kustomization
            files.append(FileEntry(
                path=f"{config.name}/infrastructure/kubernetes/base/kustomization.yaml",
                content=self._k8s_base_kustomization(config),
            ))

            # Namespace
            files.append(FileEntry(
                path=f"{config.name}/infrastructure/kubernetes/base/namespace.yaml",
                content=self._k8s_namespace(config),
            ))

            # Environment overlays
            for env in ["development", "staging", "production"]:
                files.append(FileEntry(
                    path=f"{config.name}/infrastructure/kubernetes/overlays/{env}/kustomization.yaml",
                    content=self._k8s_overlay_kustomization(config, env),
                ))

        # Terraform scaffolding
        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/main.tf",
            content=self._terraform_main(config),
        ))
        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/variables.tf",
            content=self._terraform_variables(config),
        ))
        files.append(FileEntry(
            path=f"{config.name}/infrastructure/terraform/outputs.tf",
            content=self._terraform_outputs(config),
        ))

        return files

    def _get_infrastructure_directories(self, config: ProjectConfig) -> List[str]:
        """Get infrastructure directories."""
        dirs = [
            f"{config.name}/infrastructure/kubernetes/base",
            f"{config.name}/infrastructure/kubernetes/overlays/development",
            f"{config.name}/infrastructure/kubernetes/overlays/staging",
            f"{config.name}/infrastructure/kubernetes/overlays/production",
        ]
        return dirs

    def _generate_cicd_files(self, config: ProjectConfig) -> List[FileEntry]:
        """Generate CI/CD configuration files."""
        files: List[FileEntry] = []

        if config.cicd_platform == CICDPlatform.GITHUB_ACTIONS:
            files.append(FileEntry(
                path=f"{config.name}/.github/workflows/ci.yaml",
                content=self._github_actions_ci(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/workflows/cd.yaml",
                content=self._github_actions_cd(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/CODEOWNERS",
                content=self._codeowners(config),
            ))
            files.append(FileEntry(
                path=f"{config.name}/.github/pull_request_template.md",
                content=self._pr_template(),
            ))

        elif config.cicd_platform == CICDPlatform.GITLAB_CI:
            files.append(FileEntry(
                path=f"{config.name}/.gitlab-ci.yml",
                content=self._gitlab_ci(config),
            ))

        return files

    def _get_cicd_directories(self, config: ProjectConfig) -> List[str]:
        """Get CI/CD directories."""
        dirs = []
        if config.cicd_platform == CICDPlatform.GITHUB_ACTIONS:
            dirs.append(f"{config.name}/.github/workflows")
        return dirs

    def _get_primary_language(self, config: ProjectConfig) -> Language:
        """Get the primary language from services."""
        if not config.services:
            return Language.PYTHON
        # Count language occurrences
        lang_counts: Dict[Language, int] = {}
        for service in config.services:
            lang_counts[service.language] = lang_counts.get(service.language, 0) + 1
        return max(lang_counts, key=lambda k: lang_counts[k])

    # Template methods
    def _root_readme(self, config: ProjectConfig) -> str:
        services_list = "\n".join([f"- `{s.name}` - {s.description}" for s in config.services])
        return f'''# {config.name}

{config.description}

## Project Structure

```
{config.name}/
  services/           # Microservices
  packages/           # Shared packages/libraries
  infrastructure/     # Infrastructure as code
    kubernetes/       # Kubernetes manifests
    terraform/        # Terraform configurations
  scripts/            # Utility scripts
  docs/               # Documentation
```

## Services

{services_list}

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make
- Kubernetes cluster (for deployment)

### Local Development

```bash
# Start all services locally
make dev

# Or start specific service
make dev-<service-name>
```

### Running Tests

```bash
# Run all tests
make test

# Run tests for specific service
make test-<service-name>
```

### Deployment

```bash
# Deploy to development
make deploy-dev

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

## Infrastructure

### Kubernetes

Kubernetes manifests are managed using Kustomize with environment-specific overlays.

### Terraform

Terraform configurations for cloud infrastructure provisioning.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

## License

{config.license}
'''

    def _root_gitignore(self, config: ProjectConfig) -> str:
        return '''# Environment
.env
.env.*
!.env.example

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/
.venv/
venv/

# Node
node_modules/
dist/
coverage/
*.log

# Go
*.exe
*.test
*.out
vendor/

# Terraform
.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl

# Build artifacts
build/
out/
'''

    def _makefile(self, config: ProjectConfig) -> str:
        services = " ".join([s.name for s in config.services])
        return f'''.PHONY: help build test dev clean deploy-dev deploy-staging deploy-prod

SERVICES := {services}

help:
	@echo "Available targets:"
	@echo "  build          - Build all services"
	@echo "  test           - Run all tests"
	@echo "  dev            - Start local development"
	@echo "  clean          - Clean build artifacts"
	@echo "  deploy-dev     - Deploy to development"
	@echo "  deploy-staging - Deploy to staging"
	@echo "  deploy-prod    - Deploy to production"

build:
	@for svc in $(SERVICES); do \\
		echo "Building $$svc..."; \\
		docker build -t $$svc:latest services/$$svc; \\
	done

test:
	@for svc in $(SERVICES); do \\
		echo "Testing $$svc..."; \\
		cd services/$$svc && make test; \\
	done

dev:
	docker-compose up

clean:
	docker-compose down -v
	@for svc in $(SERVICES); do \\
		rm -rf services/$$svc/dist services/$$svc/build; \\
	done

deploy-dev:
	kubectl apply -k infrastructure/kubernetes/overlays/development

deploy-staging:
	kubectl apply -k infrastructure/kubernetes/overlays/staging

deploy-prod:
	kubectl apply -k infrastructure/kubernetes/overlays/production
'''

    def _pre_commit_config(self, config: ProjectConfig) -> str:
        return '''repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        types_or: [javascript, typescript, json, yaml]
'''

    def _editorconfig(self) -> str:
        return '''root = true

[*]
indent_style = space
indent_size = 2
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.py]
indent_size = 4

[*.go]
indent_style = tab
indent_size = 4

[Makefile]
indent_style = tab
'''

    def _root_docker_compose(self, config: ProjectConfig) -> str:
        services_yaml = ""
        for service in config.services:
            services_yaml += f'''
  {service.name}:
    build:
      context: ./services/{service.name}
      dockerfile: Dockerfile
    ports:
      - "{service.port}:{service.port}"
    environment:
      - ENV=development
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{service.port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
'''

        return f'''version: "3.8"

services:{services_yaml}
'''

    def _root_pyproject(self, config: ProjectConfig) -> str:
        return f'''[project]
name = "{config.name}"
version = "{config.version}"
description = "{config.description}"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
testpaths = ["services/*/tests"]
asyncio_mode = "auto"
'''

    def _root_package_json(self, config: ProjectConfig) -> str:
        return f'''{{
  "name": "{config.name}",
  "version": "{config.version}",
  "private": true,
  "workspaces": [
    "services/*",
    "packages/*"
  ],
  "scripts": {{
    "build": "turbo run build",
    "test": "turbo run test",
    "lint": "turbo run lint",
    "dev": "turbo run dev --parallel"
  }},
  "devDependencies": {{
    "turbo": "^1.12.0"
  }}
}}
'''

    def _turbo_json(self, config: ProjectConfig) -> str:
        return '''{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "lint": {},
    "dev": {
      "cache": false,
      "persistent": true
    }
  }
}
'''

    def _k8s_base_kustomization(self, config: ProjectConfig) -> str:
        resources = "\n".join([f"  - {s.name}/" for s in config.services])
        return f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: {config.name}

resources:
  - namespace.yaml
{resources}

commonLabels:
  app.kubernetes.io/part-of: {config.name}
'''

    def _k8s_namespace(self, config: ProjectConfig) -> str:
        return f'''apiVersion: v1
kind: Namespace
metadata:
  name: {config.name}
  labels:
    app.kubernetes.io/name: {config.name}
'''

    def _k8s_overlay_kustomization(self, config: ProjectConfig, env: str) -> str:
        return f'''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: {config.name}-{env}

commonLabels:
  environment: {env}

images:
{chr(10).join([f"  - name: {s.name}{chr(10)}    newTag: {env}-latest" for s in config.services])}
'''

    def _terraform_main(self, config: ProjectConfig) -> str:
        return f'''terraform {{
  required_version = ">= 1.0"

  required_providers {{
    kubernetes = {{
      source  = "hashicorp/kubernetes"
      version = ">= 2.0"
    }}
  }}
}}

# Provider configuration
provider "kubernetes" {{
  config_path = var.kubeconfig_path
}}

# Namespace
resource "kubernetes_namespace" "main" {{
  metadata {{
    name = var.namespace

    labels = {{
      app        = "{config.name}"
      managed-by = "terraform"
    }}
  }}
}}
'''

    def _terraform_variables(self, config: ProjectConfig) -> str:
        return f'''variable "namespace" {{
  description = "Kubernetes namespace"
  type        = string
  default     = "{config.name}"
}}

variable "kubeconfig_path" {{
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}}

variable "environment" {{
  description = "Environment name"
  type        = string
  default     = "development"
}}
'''

    def _terraform_outputs(self, config: ProjectConfig) -> str:
        return '''output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.main.metadata[0].name
}
'''

    def _github_actions_ci(self, config: ProjectConfig) -> str:
        return f'''name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run linters
        run: make lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        service: [{", ".join([s.name for s in config.services])}]
    steps:
      - uses: actions/checkout@v4

      - name: Run tests
        run: |
          cd services/${{{{ matrix.service }}}}
          make test

  build:
    runs-on: ubuntu-latest
    needs: test
    strategy:
      matrix:
        service: [{", ".join([s.name for s in config.services])}]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t ${{{{ matrix.service }}}}:${{{{ github.sha }}}} services/${{{{ matrix.service }}}}
'''

    def _github_actions_cd(self, config: ProjectConfig) -> str:
        return f'''name: CD

on:
  push:
    branches: [main]
    tags: ["v*"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{{{ github.ref == 'refs/heads/main' && 'development' || 'production' }}}}
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Kubernetes
        run: |
          kubectl apply -k infrastructure/kubernetes/overlays/$ENVIRONMENT
        env:
          ENVIRONMENT: ${{{{ github.ref == 'refs/heads/main' && 'development' || 'production' }}}}
'''

    def _gitlab_ci(self, config: ProjectConfig) -> str:
        return f'''stages:
  - lint
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2

lint:
  stage: lint
  script:
    - make lint

test:
  stage: test
  parallel:
    matrix:
      - SERVICE: [{", ".join([s.name for s in config.services])}]
  script:
    - cd services/$SERVICE && make test

build:
  stage: build
  parallel:
    matrix:
      - SERVICE: [{", ".join([s.name for s in config.services])}]
  script:
    - docker build -t $SERVICE:$CI_COMMIT_SHA services/$SERVICE

deploy-dev:
  stage: deploy
  environment: development
  only:
    - main
  script:
    - kubectl apply -k infrastructure/kubernetes/overlays/development

deploy-prod:
  stage: deploy
  environment: production
  only:
    - tags
  script:
    - kubectl apply -k infrastructure/kubernetes/overlays/production
'''

    def _codeowners(self, config: ProjectConfig) -> str:
        return f'''# Default owners
* @{config.author or "team"}

# Infrastructure
/infrastructure/ @{config.author or "platform-team"}

# Services
/services/ @{config.author or "backend-team"}
'''

    def _pr_template(self) -> str:
        return '''## Description

<!-- Describe your changes -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Checklist

- [ ] Tests pass locally
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated (if applicable)
'''

    def _get_next_steps(self, config: ProjectConfig) -> List[str]:
        """Get next steps for the generated monorepo."""
        steps: List[str] = [
            f"cd {config.name}",
            "git init",
            "make dev",
            "Open http://localhost:<port> for each service",
        ]
        if config.include_pre_commit:
            steps.insert(2, "pre-commit install")
        return steps

    def save_to_directory(
        self, report: ScaffoldReport, output_dir: Optional[str] = None
    ) -> str:
        """
        Save generated monorepo to directory.

        Args:
            report: Scaffold report with files
            output_dir: Override output directory

        Returns:
            Path to the saved project
        """
        target_dir = output_dir or self.output_dir

        # Create directories
        for directory in report.directories:
            dir_path = os.path.join(target_dir, directory)
            os.makedirs(dir_path, exist_ok=True)

        # Create files
        for file_entry in report.files:
            file_path = os.path.join(target_dir, file_entry.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_entry.content)
            if file_entry.executable:
                os.chmod(file_path, 0o755)

        return os.path.join(target_dir, report.project_name)
