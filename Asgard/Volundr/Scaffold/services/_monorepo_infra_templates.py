from typing import List

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    ProjectConfig,
)


def root_pyproject(config: ProjectConfig) -> str:
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


def root_package_json(config: ProjectConfig) -> str:
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


def turbo_json(config: ProjectConfig) -> str:
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


def k8s_base_kustomization(config: ProjectConfig) -> str:
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


def k8s_namespace(config: ProjectConfig) -> str:
    return f'''apiVersion: v1
kind: Namespace
metadata:
  name: {config.name}
  labels:
    app.kubernetes.io/name: {config.name}
'''


def k8s_overlay_kustomization(config: ProjectConfig, env: str) -> str:
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


def terraform_main(config: ProjectConfig) -> str:
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


def terraform_variables(config: ProjectConfig) -> str:
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


def terraform_outputs(config: ProjectConfig) -> str:
    return '''output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.main.metadata[0].name
}
'''


def github_actions_ci(config: ProjectConfig) -> str:
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


def github_actions_cd(config: ProjectConfig) -> str:
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


def gitlab_ci(config: ProjectConfig) -> str:
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


def codeowners(config: ProjectConfig) -> str:
    return f'''# Default owners
* @{config.author or "team"}

# Infrastructure
/infrastructure/ @{config.author or "platform-team"}

# Services
/services/ @{config.author or "backend-team"}
'''


def pr_template() -> str:
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


def get_next_steps(config: ProjectConfig) -> List[str]:
    steps: List[str] = [
        f"cd {config.name}",
        "git init",
        "make dev",
        "Open http://localhost:<port> for each service",
    ]
    if config.include_pre_commit:
        steps.insert(2, "pre-commit install")
    return steps
