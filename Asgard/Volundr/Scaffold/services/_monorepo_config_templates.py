from typing import List

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    ProjectConfig,
    CICDPlatform,
    ContainerOrchestration,
)


def root_readme(config: ProjectConfig) -> str:
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


def root_gitignore(config: ProjectConfig) -> str:
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


def makefile(config: ProjectConfig) -> str:
    services = " ".join([s.name for s in config.services])
    return f'''.PHONY: help build test dev clean deploy-dev deploy-staging deploy-prod

SERVICES := {services}

help:
\t@echo "Available targets:"
\t@echo "  build          - Build all services"
\t@echo "  test           - Run all tests"
\t@echo "  dev            - Start local development"
\t@echo "  clean          - Clean build artifacts"
\t@echo "  deploy-dev     - Deploy to development"
\t@echo "  deploy-staging - Deploy to staging"
\t@echo "  deploy-prod    - Deploy to production"

build:
\t@for svc in $(SERVICES); do \\
\t\techo "Building $$svc..."; \\
\t\tdocker build -t $$svc:latest services/$$svc; \\
\tdone

test:
\t@for svc in $(SERVICES); do \\
\t\techo "Testing $$svc..."; \\
\t\tcd services/$$svc && make test; \\
\tdone

dev:
\tdocker-compose up

clean:
\tdocker-compose down -v
\t@for svc in $(SERVICES); do \\
\t\trm -rf services/$$svc/dist services/$$svc/build; \\
\tdone

deploy-dev:
\tkubectl apply -k infrastructure/kubernetes/overlays/development

deploy-staging:
\tkubectl apply -k infrastructure/kubernetes/overlays/staging

deploy-prod:
\tkubectl apply -k infrastructure/kubernetes/overlays/production
'''


def pre_commit_config(config: ProjectConfig) -> str:
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


def editorconfig() -> str:
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


def root_docker_compose(config: ProjectConfig) -> str:
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
