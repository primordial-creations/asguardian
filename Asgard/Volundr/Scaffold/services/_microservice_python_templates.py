from typing import List, Tuple

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    FileEntry,
    Framework,
    ServiceConfig,
)


def python_pyproject_toml(config: ServiceConfig) -> str:
    return f'''[project]
name = "{config.name}"
version = "0.1.0"
description = "{config.description}"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
'''


def python_requirements(config: ServiceConfig) -> str:
    deps = []
    if config.framework == Framework.FASTAPI:
        deps.extend(["fastapi>=0.109.0", "uvicorn[standard]>=0.27.0"])
    deps.extend(["pydantic>=2.5.0", "pydantic-settings>=2.1.0"])
    if config.include_logging:
        deps.append("structlog>=24.1.0")
    if config.include_tests:
        deps.extend(["pytest>=7.4.0", "pytest-asyncio>=0.23.0", "httpx>=0.26.0"])
    return "\n".join(deps) + "\n"


def python_fastapi_main(config: ServiceConfig) -> str:
    imports = "from fastapi import FastAPI"
    if config.include_healthcheck:
        imports += "\nfrom app.routers import health"

    routers = ""
    if config.include_healthcheck:
        routers = '\napp.include_router(health.router, prefix="/health", tags=["health"])'

    return f'''{imports}

app = FastAPI(
    title="{config.name}",
    description="{config.description}",
    version="0.1.0",
)
{routers}

@app.get("/")
async def root():
    return {{"message": "Welcome to {config.name}"}}
'''


def python_generic_main(config: ServiceConfig) -> str:
    return f'''"""
{config.name} - Main Application
"""


def main():
    print("Starting {config.name}")


if __name__ == "__main__":
    main()
'''


def python_settings(config: ServiceConfig) -> str:
    return f'''from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "{config.name}"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = {config.port}

    class Config:
        env_file = ".env"


settings = Settings()
'''


def python_health_router(config: ServiceConfig) -> str:
    return '''from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check():
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    return {"status": "alive"}
'''


def python_conftest(config: ServiceConfig) -> str:
    return '''import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
'''


def python_test_health(config: ServiceConfig) -> str:
    return '''def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_check(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
'''


def python_dockerfile(config: ServiceConfig) -> str:
    return f'''FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE {config.port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{config.port}/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{config.port}"]
'''


def generate_python_service(config: ServiceConfig) -> Tuple[List[FileEntry], List[str]]:
    files: List[FileEntry] = []
    directories: List[str] = [
        f"{config.name}",
        f"{config.name}/app",
        f"{config.name}/app/routers",
        f"{config.name}/app/services",
        f"{config.name}/app/models",
        f"{config.name}/app/config",
    ]

    if config.include_tests:
        directories.append(f"{config.name}/tests")
        directories.append(f"{config.name}/tests/unit")
        directories.append(f"{config.name}/tests/integration")

    files.append(FileEntry(
        path=f"{config.name}/pyproject.toml",
        content=python_pyproject_toml(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/requirements.txt",
        content=python_requirements(config),
    ))

    if config.framework == Framework.FASTAPI:
        files.append(FileEntry(
            path=f"{config.name}/app/main.py",
            content=python_fastapi_main(config),
        ))
    else:
        files.append(FileEntry(
            path=f"{config.name}/app/main.py",
            content=python_generic_main(config),
        ))

    for d in ["app", "app/routers", "app/services", "app/models", "app/config"]:
        files.append(FileEntry(
            path=f"{config.name}/{d}/__init__.py",
            content="",
        ))

    files.append(FileEntry(
        path=f"{config.name}/app/config/settings.py",
        content=python_settings(config),
    ))

    if config.include_healthcheck:
        files.append(FileEntry(
            path=f"{config.name}/app/routers/health.py",
            content=python_health_router(config),
        ))

    if config.include_tests:
        files.append(FileEntry(path=f"{config.name}/tests/__init__.py", content=""))
        files.append(FileEntry(
            path=f"{config.name}/tests/conftest.py",
            content=python_conftest(config),
        ))
        files.append(FileEntry(path=f"{config.name}/tests/unit/__init__.py", content=""))
        files.append(FileEntry(
            path=f"{config.name}/tests/unit/test_health.py",
            content=python_test_health(config),
        ))

    if config.include_docker:
        files.append(FileEntry(
            path=f"{config.name}/Dockerfile",
            content=python_dockerfile(config),
        ))

    return files, directories
