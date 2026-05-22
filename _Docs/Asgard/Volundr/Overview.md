# Volundr - Infrastructure Generation Package

## Overview

Volundr is GAIA's infrastructure generation package. Named after the legendary Norse master smith (equivalent to Hephaestus in Greek mythology), Volundr forges infrastructure configurations from templates with precision and best practices.

## Why Volundr?

- **Master Smith** - Creates/forges infrastructure like the legendary craftsman
- **Legendary artifacts** - Analogous to well-crafted infrastructure templates
- **Precision craftsmanship** - High-quality, best-practice configurations
- **Norse mythology** - Matches Asgard's naming theme
- **Single deity name** - Matches existing GAIA patterns (Iris, Athena, Themis)

## Package Structure

```
Asgard/
└── Volundr/
    ├── setup.py
    ├── pyproject.toml
    ├── README.md
    └── Volundr/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        │
        ├── Kubernetes/                    # Kubernetes Manifest Generation
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── kubernetes_models.py   # ManifestConfig, WorkloadType, etc.
        │   └── services/
        │       ├── __init__.py
        │       └── manifest_generator.py  # ManifestGenerator service
        │
        ├── Terraform/                     # Terraform Module Generation
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── terraform_models.py    # ModuleConfig, CloudProvider, etc.
        │   └── services/
        │       ├── __init__.py
        │       └── module_builder.py      # ModuleBuilder service
        │
        ├── Docker/                        # Docker Configuration Generation
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── docker_models.py       # DockerfileConfig, ComposeConfig
        │   └── services/
        │       ├── __init__.py
        │       ├── dockerfile_generator.py
        │       └── compose_generator.py
        │
        └── CICD/                          # CI/CD Pipeline Generation
            ├── __init__.py
            ├── models/
            │   ├── __init__.py
            │   └── cicd_models.py         # PipelineConfig, CICDPlatform
            └── services/
                ├── __init__.py
                └── pipeline_generator.py  # PipelineGenerator service
```

## Submodule Overview

| Submodule | Purpose | Output |
|-----------|---------|--------|
| Kubernetes | Manifest generation | Deployments, Services, ConfigMaps, Secrets, NetworkPolicies, PDBs |
| Terraform | Module generation | main.tf, variables.tf, outputs.tf, versions.tf, locals.tf, README.md |
| Docker | Container configuration | Dockerfile, docker-compose.yml |
| CICD | Pipeline generation | GitHub Actions, GitLab CI, Azure DevOps, Jenkins |

---

## Kubernetes Module

Generates production-ready Kubernetes manifests:
- **Deployments** - Rolling updates, resource limits, security contexts
- **StatefulSets** - For stateful applications
- **DaemonSets** - For node-level services
- **Jobs/CronJobs** - Batch and scheduled workloads
- **Services** - ClusterIP, NodePort, LoadBalancer
- **ConfigMaps/Secrets** - Configuration management
- **NetworkPolicies** - Network segmentation
- **PodDisruptionBudgets** - High availability

See [02-Kubernetes-Module.md](02-Kubernetes-Module.md) for details.

---

## Terraform Module

Generates multi-cloud Terraform modules:
- **AWS** - VPC, EKS, RDS, S3, Lambda, IAM
- **Azure** - VNet, AKS, SQL, Blob, Functions
- **GCP** - VPC, GKE, Cloud SQL, Storage, Cloud Functions
- **Multi-file Structure** - main.tf, variables.tf, outputs.tf, versions.tf, locals.tf
- **Documentation** - Auto-generated README.md with examples

See [03-Terraform-Module.md](03-Terraform-Module.md) for details.

---

## Docker Module

Generates container configurations:
- **Dockerfiles** - Multi-stage builds, security best practices
- **docker-compose.yml** - Multi-container orchestration
- **Build optimization** - Layer caching, minimal images
- **Security** - Non-root users, read-only filesystems

See [04-Docker-Module.md](04-Docker-Module.md) for details.

---

## CICD Module

Generates CI/CD pipelines for multiple platforms:
- **GitHub Actions** - Workflows with jobs and steps
- **GitLab CI** - .gitlab-ci.yml with stages
- **Azure DevOps** - azure-pipelines.yml
- **Jenkins** - Declarative Jenkinsfile

See [05-CICD-Module.md](05-CICD-Module.md) for details.

---

## CLI Interface

```bash
# Main entry point
python -m Volundr <command> [options]

# Kubernetes manifest generation
python -m Volundr kubernetes generate --name myapp --image nginx:latest
python -m Volundr k8s generate --name api --image myregistry/api:v1.0 --replicas 3

# Terraform module generation
python -m Volundr terraform generate --name vpc --provider aws --category networking
python -m Volundr tf generate --name storage --provider gcp --category storage

# Docker configuration generation
python -m Volundr docker dockerfile --name myapp --base python:3.12-slim
python -m Volundr docker compose --name myapp

# CI/CD pipeline generation
python -m Volundr cicd generate --name ci-pipeline --platform github_actions
python -m Volundr cicd generate --name deploy --platform gitlab_ci
```

See [06-CLI-Reference.md](06-CLI-Reference.md) for complete CLI documentation.

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | COMPLETE | Foundation, package structure |
| Phase 2 | COMPLETE | Kubernetes module |
| Phase 3 | COMPLETE | Terraform module |
| Phase 4 | COMPLETE | Docker module |
| Phase 5 | COMPLETE | CICD module and CLI |

---

## Quick Start

### Installation

```bash
# From GAIA root directory
pip install -e ./Asgard/Volundr
```

### Basic Usage

```bash
# Generate Kubernetes deployment
python -m Volundr k8s generate --name myapp --image nginx:latest

# Generate Terraform VPC module
python -m Volundr tf generate --name vpc --provider aws --category networking

# Generate Dockerfile
python -m Volundr docker dockerfile --name myapp --base python:3.12-slim

# Generate GitHub Actions workflow
python -m Volundr cicd generate --name ci --platform github_actions
```

### Programmatic Usage

```python
from Volundr import (
    # Kubernetes
    ManifestConfig, ManifestGenerator, WorkloadType,
    # Terraform
    ModuleConfig, ModuleBuilder, CloudProvider, ResourceCategory,
    # Docker
    DockerfileConfig, DockerfileGenerator,
    # CICD
    PipelineConfig, PipelineGenerator, CICDPlatform
)

# Generate Kubernetes deployment
k8s_config = ManifestConfig(name="myapp", image="nginx:latest")
k8s_generator = ManifestGenerator()
manifest = k8s_generator.generate(k8s_config)
print(manifest.yaml_content)

# Generate Terraform module
tf_config = ModuleConfig(
    name="vpc",
    provider=CloudProvider.AWS,
    category=ResourceCategory.NETWORKING
)
tf_builder = ModuleBuilder()
module = tf_builder.generate(tf_config)
tf_builder.save_to_directory(module)
```

---

## Best Practice Scoring

Each generator calculates a best practice compliance score (0-100) based on:

| Module | Scoring Criteria |
|--------|------------------|
| Kubernetes | Resource limits, security contexts, probes, network policies, PDBs |
| Terraform | Variables, outputs, locals, versioning, documentation, examples |
| Docker | Multi-stage builds, non-root user, healthchecks, minimal base images |
| CICD | Triggers, stages, caching, environments, timeouts |

---

## Integration with Other Asgard Tools

Volundr works alongside other Asgard tools:

| Tool | Integration |
|------|-------------|
| **Heimdall** | Analyze generated code for quality issues |
| **Freya** | Test generated Docker configurations visually |
| **Verdandi** | Monitor deployed infrastructure |

---

## Related Documentation

- [02-Kubernetes-Module.md](02-Kubernetes-Module.md) - Kubernetes module details
- [03-Terraform-Module.md](03-Terraform-Module.md) - Terraform module details
- [04-Docker-Module.md](04-Docker-Module.md) - Docker module details
- [05-CICD-Module.md](05-CICD-Module.md) - CICD module details
- [06-CLI-Reference.md](06-CLI-Reference.md) - CLI command reference
