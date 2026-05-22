# Volundr - Docker Module

## Overview

The Docker module generates production-ready Dockerfiles and docker-compose configurations with multi-stage builds, security best practices, and optimization for minimal image sizes.

## Models

### DockerfileConfig

Configuration for Dockerfile generation:

```python
from Volundr.Docker import DockerfileConfig, BuildStage

config = DockerfileConfig(
    name="myapp",
    base_image="python:3.12-slim",
    working_dir="/app",

    # Build stages for multi-stage builds
    build_stages=[
        BuildStage(
            name="builder",
            base_image="python:3.12",
            commands=[
                "pip install --no-cache-dir poetry",
                "poetry export -f requirements.txt -o requirements.txt"
            ]
        )
    ],

    # Files to copy
    copy_files=[
        {"src": "requirements.txt", "dst": "/app/"},
        {"src": ".", "dst": "/app"}
    ],

    # Commands
    run_commands=[
        "pip install --no-cache-dir -r requirements.txt",
        "adduser --disabled-password --gecos '' appuser"
    ],

    # Expose ports
    expose_ports=[8000],

    # Entry point and command
    entrypoint=["python", "-m"],
    cmd=["myapp"],

    # Environment variables
    env={"PYTHONUNBUFFERED": "1"},

    # User to run as (non-root)
    user="appuser",

    # Labels
    labels={
        "org.opencontainers.image.source": "https://github.com/org/myapp",
        "org.opencontainers.image.version": "1.0.0"
    },

    # Health check
    healthcheck={
        "cmd": "curl -f http://localhost:8000/health || exit 1",
        "interval": "30s",
        "timeout": "10s",
        "retries": 3
    },

    # Enable multi-stage build
    multi_stage=True
)
```

### ComposeConfig

Configuration for docker-compose generation:

```python
from Volundr.Docker import ComposeConfig, ComposeServiceConfig, NetworkConfig, VolumeConfig

config = ComposeConfig(
    name="mystack",
    version="3.8",

    services=[
        ComposeServiceConfig(
            name="api",
            image="myapp:latest",
            build={"context": ".", "dockerfile": "Dockerfile"},
            ports=["8000:8000"],
            environment={"DATABASE_URL": "${DATABASE_URL}"},
            depends_on=["db", "redis"],
            volumes=["./data:/app/data"],
            networks=["backend"],
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3
            },
            deploy={
                "replicas": 2,
                "resources": {
                    "limits": {"cpus": "0.5", "memory": "512M"}
                }
            }
        ),
        ComposeServiceConfig(
            name="db",
            image="postgres:15",
            volumes=["postgres_data:/var/lib/postgresql/data"],
            environment={"POSTGRES_PASSWORD": "${DB_PASSWORD}"},
            networks=["backend"]
        ),
        ComposeServiceConfig(
            name="redis",
            image="redis:7-alpine",
            networks=["backend"]
        )
    ],

    networks=[
        NetworkConfig(name="backend", driver="bridge")
    ],

    volumes=[
        VolumeConfig(name="postgres_data")
    ]
)
```

## Services

### DockerfileGenerator

```python
from Volundr.Docker import DockerfileConfig, DockerfileGenerator

config = DockerfileConfig(
    name="myapp",
    base_image="python:3.12-slim",
    working_dir="/app",
    expose_ports=[8000],
    cmd=["python", "-m", "myapp"]
)

generator = DockerfileGenerator()
result = generator.generate(config)

print(result.dockerfile_content)
print(f"Score: {result.best_practice_score}/100")

generator.save_to_file(result, output_dir="./docker")
```

### ComposeGenerator

```python
from Volundr.Docker import ComposeConfig, ComposeGenerator, ComposeServiceConfig

config = ComposeConfig(
    name="mystack",
    services=[
        ComposeServiceConfig(name="api", image="myapp:latest", ports=["8000:8000"]),
        ComposeServiceConfig(name="db", image="postgres:15")
    ]
)

generator = ComposeGenerator()
result = generator.generate(config)

print(result.compose_content)
generator.save_to_file(result, output_dir="./docker")
```

## Generated Output Examples

### Dockerfile (Multi-stage)

```dockerfile
# Stage 1: Builder
FROM python:3.12 AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

# Labels
LABEL org.opencontainers.image.source="https://github.com/org/myapp"
LABEL org.opencontainers.image.version="1.0.0"
LABEL generated-by="volundr"

# Create non-root user
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application
COPY --chown=appuser:appuser . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser

# Entry point
ENTRYPOINT ["python", "-m"]
CMD ["myapp"]
```

### docker-compose.yml

```yaml
version: "3.8"

services:
  api:
    image: myapp:latest
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
    depends_on:
      - db
      - redis
    volumes:
      - ./data:/app/data
    networks:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    networks:
      - backend

  redis:
    image: redis:7-alpine
    networks:
      - backend

networks:
  backend:
    driver: bridge

volumes:
  postgres_data:
```

## Best Practice Score

### Dockerfile Scoring

| Criteria | Weight | Description |
|----------|--------|-------------|
| Multi-stage build | 20 | Separate build and runtime stages |
| Non-root user | 20 | Run as non-root user |
| Healthcheck | 15 | Container health monitoring |
| Labels | 10 | OCI-compliant labels |
| Minimal base | 15 | Slim/Alpine base images |
| Layer optimization | 10 | Efficient COPY ordering |
| No cache | 10 | --no-cache-dir for pip |

### docker-compose Scoring

| Criteria | Weight | Description |
|----------|--------|-------------|
| Health checks | 20 | Service health monitoring |
| Networks | 15 | Explicit network configuration |
| Resource limits | 20 | Memory and CPU limits |
| Dependencies | 15 | Proper depends_on ordering |
| Volumes | 15 | Named volumes for persistence |
| Environment | 15 | Variable substitution |

## CLI Usage

```bash
# Generate Dockerfile
python -m Volundr docker dockerfile --name myapp --base python:3.12-slim

# With options
python -m Volundr docker dockerfile \
  --name myapp \
  --base python:3.12-slim \
  --port 8000 \
  --user appuser \
  --multi-stage \
  --output ./docker

# Generate docker-compose
python -m Volundr docker compose --name mystack

# With options
python -m Volundr docker compose \
  --name mystack \
  --services api,db,redis \
  --output ./docker
```

## Related

- [01-Overview.md](01-Overview.md) - Package overview
- [06-CLI-Reference.md](06-CLI-Reference.md) - CLI commands
