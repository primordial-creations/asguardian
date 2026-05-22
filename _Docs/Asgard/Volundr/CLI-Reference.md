# Volundr - CLI Reference

## Overview

Volundr provides a command-line interface for generating infrastructure configurations. The CLI uses a consistent command structure across all modules.

## Installation

```bash
# Install Volundr package
pip install -e ./Asgard/Volundr

# Verify installation
python -m Volundr --help
```

## General Syntax

```bash
python -m Volundr <module> <command> [options]
```

Or using the console script:

```bash
volundr <module> <command> [options]
```

## Modules

| Module | Aliases | Description |
|--------|---------|-------------|
| kubernetes | k8s | Kubernetes manifest generation |
| terraform | tf | Terraform module generation |
| docker | - | Dockerfile and docker-compose generation |
| cicd | - | CI/CD pipeline generation |

---

## Kubernetes Commands

### Generate Manifest

```bash
python -m Volundr kubernetes generate [options]
python -m Volundr k8s generate [options]
```

**Required Options:**
| Option | Description |
|--------|-------------|
| `--name NAME` | Application name |
| `--image IMAGE` | Container image |

**Optional Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--replicas N` | 1 | Number of replicas |
| `--namespace NS` | default | Kubernetes namespace |
| `--type TYPE` | deployment | Workload type (deployment, statefulset, daemonset, job, cronjob) |
| `--port PORT` | - | Container port |
| `--service-port PORT` | - | Service port |
| `--cpu-request CPU` | 100m | CPU request |
| `--memory-request MEM` | 128Mi | Memory request |
| `--cpu-limit CPU` | 500m | CPU limit |
| `--memory-limit MEM` | 512Mi | Memory limit |
| `--output DIR` | . | Output directory |
| `--format FMT` | yaml | Output format (yaml, json) |

**Examples:**

```bash
# Basic deployment
python -m Volundr k8s generate --name myapp --image nginx:latest

# Production deployment
python -m Volundr kubernetes generate \
  --name api \
  --image myregistry/api:v1.0 \
  --replicas 3 \
  --namespace production \
  --port 8080 \
  --service-port 80 \
  --cpu-limit 1000m \
  --memory-limit 1Gi \
  --output ./k8s
```

---

## Terraform Commands

### Generate Module

```bash
python -m Volundr terraform generate [options]
python -m Volundr tf generate [options]
```

**Required Options:**
| Option | Description |
|--------|-------------|
| `--name NAME` | Module name |
| `--provider PROVIDER` | Cloud provider (aws, azure, gcp, generic) |
| `--category CATEGORY` | Resource category (compute, networking, storage, database, security, monitoring) |

**Optional Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--description DESC` | - | Module description |
| `--complexity LEVEL` | standard | Complexity level (simple, standard, advanced) |
| `--version VER` | >=1.5.0 | Terraform version constraint |
| `--examples` | false | Include example configurations |
| `--tests` | false | Include Terratest files |
| `--output DIR` | . | Output directory |

**Examples:**

```bash
# Basic VPC module
python -m Volundr tf generate --name vpc --provider aws --category networking

# Full module with examples and tests
python -m Volundr terraform generate \
  --name vpc \
  --provider aws \
  --category networking \
  --description "Production VPC with multi-AZ subnets" \
  --complexity advanced \
  --examples \
  --tests \
  --output ./terraform/modules
```

---

## Docker Commands

### Generate Dockerfile

```bash
python -m Volundr docker dockerfile [options]
```

**Required Options:**
| Option | Description |
|--------|-------------|
| `--name NAME` | Application name |
| `--base IMAGE` | Base image |

**Optional Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--workdir DIR` | /app | Working directory |
| `--port PORT` | - | Port to expose |
| `--user USER` | - | Non-root user |
| `--multi-stage` | false | Enable multi-stage build |
| `--output DIR` | . | Output directory |

**Examples:**

```bash
# Basic Dockerfile
python -m Volundr docker dockerfile --name myapp --base python:3.12-slim

# Production Dockerfile
python -m Volundr docker dockerfile \
  --name myapp \
  --base python:3.12-slim \
  --workdir /app \
  --port 8000 \
  --user appuser \
  --multi-stage \
  --output ./docker
```

### Generate docker-compose

```bash
python -m Volundr docker compose [options]
```

**Required Options:**
| Option | Description |
|--------|-------------|
| `--name NAME` | Stack name |

**Optional Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--services SVCS` | - | Comma-separated service names |
| `--version VER` | 3.8 | Compose file version |
| `--output DIR` | . | Output directory |

**Examples:**

```bash
# Basic compose file
python -m Volundr docker compose --name mystack

# With services
python -m Volundr docker compose \
  --name mystack \
  --services api,db,redis \
  --output ./docker
```

---

## CICD Commands

### Generate Pipeline

```bash
python -m Volundr cicd generate [options]
```

**Required Options:**
| Option | Description |
|--------|-------------|
| `--name NAME` | Pipeline name |
| `--platform PLATFORM` | CI/CD platform |

**Platform Values:**
- `github_actions` - GitHub Actions
- `gitlab_ci` - GitLab CI/CD
- `azure_devops` - Azure Pipelines
- `jenkins` - Jenkinsfile
- `circleci` - CircleCI

**Optional Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--output DIR` | . | Output directory |

**Examples:**

```bash
# GitHub Actions workflow
python -m Volundr cicd generate --name ci --platform github_actions

# GitLab CI pipeline
python -m Volundr cicd generate --name ci --platform gitlab_ci

# Azure Pipelines
python -m Volundr cicd generate --name ci --platform azure_devops

# Jenkinsfile
python -m Volundr cicd generate --name ci --platform jenkins
```

---

## Global Options

| Option | Description |
|--------|-------------|
| `--help`, `-h` | Show help message |
| `--version`, `-v` | Show version |
| `--verbose` | Enable verbose output |
| `--quiet`, `-q` | Suppress output |

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | File I/O error |

---

## Related

- [01-Overview.md](01-Overview.md) - Package overview
- [02-Kubernetes-Module.md](02-Kubernetes-Module.md) - Kubernetes details
- [03-Terraform-Module.md](03-Terraform-Module.md) - Terraform details
- [04-Docker-Module.md](04-Docker-Module.md) - Docker details
- [05-CICD-Module.md](05-CICD-Module.md) - CICD details
