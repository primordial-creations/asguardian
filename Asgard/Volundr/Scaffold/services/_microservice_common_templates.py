from typing import List

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    FileEntry,
    Language,
    ServiceConfig,
)


def common_readme(config: ServiceConfig) -> str:
    return f'''# {config.name}

{config.description}

## Quick Start

### Prerequisites

- Docker
- Make (optional)

### Running locally

```bash
# Using Docker
docker compose up

# Or run directly
{"uvicorn app.main:app --reload" if config.language == Language.PYTHON else "npm run dev" if config.language == Language.TYPESCRIPT else "go run ./cmd/server"}
```

### Running tests

```bash
{"pytest" if config.language == Language.PYTHON else "npm test" if config.language == Language.TYPESCRIPT else "go test ./..."}
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

## Configuration

Configuration is done via environment variables. See `.env.example` for available options.

## License

MIT
'''


def common_gitignore(config: ServiceConfig) -> str:
    ignores = [
        "# Environment",
        ".env",
        ".env.local",
        "",
        "# IDE",
        ".idea/",
        ".vscode/",
        "*.swp",
        "",
        "# OS",
        ".DS_Store",
        "Thumbs.db",
    ]

    if config.language == Language.PYTHON:
        ignores.extend([
            "",
            "# Python",
            "__pycache__/",
            "*.py[cod]",
            ".pytest_cache/",
            ".coverage",
            "htmlcov/",
            "dist/",
            "*.egg-info/",
            ".venv/",
            "venv/",
        ])
    elif config.language == Language.TYPESCRIPT:
        ignores.extend([
            "",
            "# Node",
            "node_modules/",
            "dist/",
            "coverage/",
            "*.log",
        ])
    elif config.language == Language.GO:
        ignores.extend([
            "",
            "# Go",
            "*.exe",
            "*.test",
            "*.out",
            "vendor/",
        ])

    return "\n".join(ignores) + "\n"


def common_env_example(config: ServiceConfig) -> str:
    env_vars = [
        f"PORT={config.port}",
        "ENV=development",
        "LOG_LEVEL=debug",
    ]
    env_vars.extend([f"{k}={v}" for k, v in config.env_vars.items()])
    return "\n".join(env_vars) + "\n"


def common_docker_compose(config: ServiceConfig) -> str:
    return f'''version: "3.8"

services:
  {config.name}:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "{config.port}:{config.port}"
    environment:
      - PORT={config.port}
      - ENV=development
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{config.port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
'''


def get_next_steps(config: ServiceConfig) -> List[str]:
    steps = [
        f"cd {config.name}",
    ]

    if config.language == Language.PYTHON:
        steps.extend([
            "python -m venv .venv",
            "source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows",
            "pip install -r requirements.txt",
            "uvicorn app.main:app --reload",
        ])
    elif config.language == Language.TYPESCRIPT:
        steps.extend([
            "npm install",
            "npm run dev",
        ])
    elif config.language == Language.GO:
        steps.extend([
            "go mod tidy",
            "go run ./cmd/server",
        ])

    steps.append("Visit http://localhost:" + str(config.port))

    return steps


def generate_generic_service(config: ServiceConfig) -> List[FileEntry]:
    files: List[FileEntry] = []

    files.append(FileEntry(
        path=f"{config.name}/README.md",
        content=f"# {config.name}\n\n{config.description}\n",
    ))

    return files


def generate_common_files(config: ServiceConfig) -> List[FileEntry]:
    files: List[FileEntry] = []

    files.append(FileEntry(
        path=f"{config.name}/README.md",
        content=common_readme(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/.gitignore",
        content=common_gitignore(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/.env.example",
        content=common_env_example(config),
    ))

    if config.include_docker:
        files.append(FileEntry(
            path=f"{config.name}/docker-compose.yaml",
            content=common_docker_compose(config),
        ))

    return files
