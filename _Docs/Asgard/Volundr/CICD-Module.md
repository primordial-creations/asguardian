# Volundr - CICD Module

## Overview

The CICD module generates CI/CD pipeline configurations for multiple platforms including GitHub Actions, GitLab CI, Azure DevOps, and Jenkins.

## Models

### CICDPlatform

Supported platforms:
- `GITHUB_ACTIONS` - GitHub Actions workflows
- `GITLAB_CI` - GitLab CI/CD pipelines
- `AZURE_DEVOPS` - Azure Pipelines
- `JENKINS` - Jenkinsfile (declarative)
- `CIRCLECI` - CircleCI config

### DeploymentStrategy

Deployment strategies:
- `ROLLING` - Rolling updates (default)
- `BLUE_GREEN` - Blue-green deployment
- `CANARY` - Canary releases
- `RECREATE` - Replace all at once
- `A_B_TESTING` - A/B testing deployment

### TriggerType

Pipeline triggers:
- `PUSH` - On code push
- `PULL_REQUEST` - On PR events
- `TAG` - On tag creation
- `SCHEDULE` - Cron schedule
- `MANUAL` - Manual dispatch
- `WORKFLOW_DISPATCH` - GitHub workflow dispatch

### PipelineConfig

Main configuration model:

```python
from Volundr.CICD import (
    PipelineConfig, PipelineStage, StepConfig,
    TriggerConfig, TriggerType, CICDPlatform, DeploymentStrategy
)

config = PipelineConfig(
    name="CI/CD Pipeline",
    platform=CICDPlatform.GITHUB_ACTIONS,

    # Triggers
    triggers=[
        TriggerConfig(
            type=TriggerType.PUSH,
            branches=["main", "develop"],
            paths=["src/**", "tests/**"]
        ),
        TriggerConfig(
            type=TriggerType.PULL_REQUEST,
            branches=["main"]
        ),
        TriggerConfig(
            type=TriggerType.WORKFLOW_DISPATCH
        )
    ],

    # Stages
    stages=[
        PipelineStage(
            name="Build",
            runs_on="ubuntu-latest",
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(
                    name="Setup Python",
                    uses="actions/setup-python@v5",
                    with_params={"python-version": "3.12"}
                ),
                StepConfig(
                    name="Install dependencies",
                    run="pip install -r requirements.txt"
                ),
                StepConfig(name="Build", run="make build")
            ]
        ),
        PipelineStage(
            name="Test",
            runs_on="ubuntu-latest",
            needs=["Build"],
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(name="Run tests", run="pytest --cov")
            ],
            services={
                "postgres": {
                    "image": "postgres:15",
                    "env": {"POSTGRES_PASSWORD": "test"}
                }
            }
        ),
        PipelineStage(
            name="Deploy",
            runs_on="ubuntu-latest",
            needs=["Test"],
            environment="production",
            if_condition="github.ref == 'refs/heads/main'",
            steps=[
                StepConfig(name="Deploy", run="./deploy.sh")
            ]
        )
    ],

    # Global environment
    env={"NODE_ENV": "production"},

    # Concurrency
    concurrency={"group": "${{ github.workflow }}", "cancel-in-progress": True},

    # Secrets required
    secrets=["AWS_ACCESS_KEY", "AWS_SECRET_KEY"],

    # Deployment settings
    deployment_strategy=DeploymentStrategy.ROLLING,
    docker_registry="ghcr.io/org",
    kubernetes_cluster="production"
)
```

## Service: PipelineGenerator

```python
from Volundr.CICD import PipelineConfig, PipelineGenerator, CICDPlatform

config = PipelineConfig(
    name="CI Pipeline",
    platform=CICDPlatform.GITHUB_ACTIONS,
    triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
    stages=[
        PipelineStage(
            name="Build",
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(name="Build", run="make build")
            ]
        )
    ]
)

generator = PipelineGenerator()
pipeline = generator.generate(config)

print(pipeline.pipeline_content)
print(f"File path: {pipeline.file_path}")
print(f"Score: {pipeline.best_practice_score}/100")
print(f"Issues: {pipeline.validation_results}")

generator.save_to_file(pipeline, output_dir="./")
```

## Platform-Specific Output

### GitHub Actions

```yaml
name: CI/CD Pipeline

on:
  push:
    branches:
      - main
      - develop
    paths:
      - src/**
      - tests/**
  pull_request:
    branches:
      - main
  workflow_dispatch:

env:
  NODE_ENV: production

concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Build
        run: make build

  test:
    runs-on: ubuntu-latest
    needs: build
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run tests
        run: pytest --cov

  deploy:
    runs-on: ubuntu-latest
    needs: test
    environment: production
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy
        run: ./deploy.sh
```

### GitLab CI

```yaml
stages:
  - build
  - test
  - deploy

variables:
  NODE_ENV: production

build:
  stage: build
  image: ubuntu:latest
  script:
    - pip install -r requirements.txt
    - make build

test:
  stage: test
  image: ubuntu:latest
  needs:
    - build
  services:
    - postgres:15
  script:
    - pytest --cov

deploy:
  stage: deploy
  image: ubuntu:latest
  needs:
    - test
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    - ./deploy.sh
```

### Azure DevOps

```yaml
name: CI/CD Pipeline

trigger:
  branches:
    include:
      - main
      - develop

variables:
  NODE_ENV: production

stages:
  - stage: Build
    displayName: Build
    jobs:
      - job: Build
        displayName: Build
        pool:
          vmImage: ubuntu-latest
        steps:
          - script: pip install -r requirements.txt
            displayName: Install dependencies
          - script: make build
            displayName: Build

  - stage: Test
    displayName: Test
    dependsOn:
      - Build
    jobs:
      - job: Test
        displayName: Test
        pool:
          vmImage: ubuntu-latest
        steps:
          - script: pytest --cov
            displayName: Run tests

  - stage: Deploy
    displayName: Deploy
    dependsOn:
      - Test
    jobs:
      - job: Deploy
        displayName: Deploy
        pool:
          vmImage: ubuntu-latest
        steps:
          - script: ./deploy.sh
            displayName: Deploy
```

### Jenkins

```groovy
pipeline {
    agent any

    environment {
        NODE_ENV = 'production'
    }

    stages {
        stage('Build') {
            steps {
                sh '''pip install -r requirements.txt'''
                sh '''make build'''
            }
        }
        stage('Test') {
            steps {
                sh '''pytest --cov'''
            }
        }
        stage('Deploy') {
            steps {
                sh '''./deploy.sh'''
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
```

## Best Practice Score

| Criteria | Weight | Description |
|----------|--------|-------------|
| Triggers | 20 | Pipeline has defined triggers |
| Multiple stages | 20 | More than one stage/job |
| Concurrency | 15 | Concurrency control configured |
| Caching | 15 | Uses caching actions |
| Environments | 15 | Deployment environments defined |
| Timeouts | 15 | Stage timeouts configured |

## CLI Usage

```bash
# GitHub Actions
python -m Volundr cicd generate --name ci --platform github_actions

# GitLab CI
python -m Volundr cicd generate --name ci --platform gitlab_ci

# Azure DevOps
python -m Volundr cicd generate --name ci --platform azure_devops

# Jenkins
python -m Volundr cicd generate --name ci --platform jenkins

# With options
python -m Volundr cicd generate \
  --name ci-pipeline \
  --platform github_actions \
  --output ./
```

## Related

- [01-Overview.md](01-Overview.md) - Package overview
- [06-CLI-Reference.md](06-CLI-Reference.md) - CLI commands
