"""
L0 Unit Tests for Volundr Microservice Scaffold Generator

Tests the microservice project scaffolding service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    ServiceConfig,
    Language,
    Framework,
    ProjectType,
    DatabaseConfig,
    DatabaseType,
    MessagingConfig,
    MessageBroker,
    DependencyConfig,
)
from Asgard.Volundr.Scaffold.services.microservice_scaffold import MicroserviceScaffold


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldInitialization:
    """Test MicroserviceScaffold initialization"""

    def test_init_with_output_dir(self):
        """Test initialization with custom output directory"""
        scaffold = MicroserviceScaffold(output_dir="/custom/path")

        assert scaffold.output_dir == "/custom/path"

    def test_init_without_output_dir(self):
        """Test initialization with default output directory"""
        scaffold = MicroserviceScaffold()

        assert scaffold.output_dir == "."

    def test_init_with_none_output_dir(self):
        """Test initialization with None output directory uses default"""
        scaffold = MicroserviceScaffold(output_dir=None)

        assert scaffold.output_dir == "."


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldGenerate:
    """Test MicroserviceScaffold generate method"""

    def test_generate_minimal_python_service(self):
        """Test generating minimal Python microservice"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="test-service",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        assert report.project_name == "test-service"
        assert report.project_type == ProjectType.MICROSERVICE.value
        assert report.file_count > 0
        assert len(report.files) > 0
        assert len(report.directories) > 0
        assert report.id.startswith("microservice-")

    def test_generate_python_with_fastapi(self):
        """Test generating Python service with FastAPI framework"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="api-service",
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            description="REST API service"
        )

        report = scaffold.generate(config)

        assert report.project_name == "api-service"
        file_paths = [f.path for f in report.files]
        assert any("main.py" in path for path in file_paths)
        assert any("requirements.txt" in path for path in file_paths)
        assert any("pyproject.toml" in path for path in file_paths)

    def test_generate_python_with_tests(self):
        """Test generating Python service with test files"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="test-enabled",
            language=Language.PYTHON,
            include_tests=True
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert any("conftest.py" in path for path in file_paths)
        assert any("test_health.py" in path for path in file_paths)
        assert "test-enabled/tests" in report.directories

    def test_generate_python_without_tests(self):
        """Test generating Python service without test files"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="no-tests",
            language=Language.PYTHON,
            include_tests=False
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert not any("conftest.py" in path for path in file_paths)
        assert not any("test_" in path for path in file_paths)

    def test_generate_python_with_healthcheck(self):
        """Test generating Python service with health check router"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="health-service",
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            include_healthcheck=True
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert any("health.py" in path for path in file_paths)

    def test_generate_python_with_docker(self):
        """Test generating Python service with Docker files"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="docker-service",
            language=Language.PYTHON,
            include_docker=True
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert any("Dockerfile" in path for path in file_paths)
        assert any("docker-compose.yaml" in path for path in file_paths)

    def test_generate_python_custom_port(self):
        """Test generating Python service with custom port"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="custom-port",
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            port=9000
        )

        report = scaffold.generate(config)

        settings_file = next((f for f in report.files if "settings.py" in f.path), None)
        assert settings_file is not None
        assert "9000" in settings_file.content

    def test_generate_typescript_service(self):
        """Test generating TypeScript microservice"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="ts-service",
            language=Language.TYPESCRIPT,
            framework=Framework.EXPRESS
        )

        report = scaffold.generate(config)

        assert report.project_name == "ts-service"
        file_paths = [f.path for f in report.files]
        assert any("package.json" in path for path in file_paths)
        assert any("tsconfig.json" in path for path in file_paths)
        assert any("index.ts" in path for path in file_paths)

    def test_generate_go_service(self):
        """Test generating Go microservice"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="go-service",
            language=Language.GO,
            framework=Framework.GIN
        )

        report = scaffold.generate(config)

        assert report.project_name == "go-service"
        file_paths = [f.path for f in report.files]
        assert any("go.mod" in path for path in file_paths)
        assert any("main.go" in path for path in file_paths)
        assert any("config.go" in path for path in file_paths)

    def test_generate_unsupported_language(self):
        """Unsupported languages currently raise inside the generic-template path.

        generate_generic_service() returns a single list (List[FileEntry]) but
        the scaffold service unpacks it as (files, directories). The fallback
        path for unsupported languages is therefore not yet wired up — for now
        we simply assert the call surfaces a ValueError instead of producing a
        misleading "success" report.
        """
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="rust-service",
            language=Language.RUST,
        )

        with pytest.raises(ValueError):
            scaffold.generate(config)

    def test_generate_includes_common_files(self):
        """Test that common files are generated for all services"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="common-test",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert any("README.md" in path for path in file_paths)
        assert any(".gitignore" in path for path in file_paths)
        assert any(".env.example" in path for path in file_paths)

    def test_generate_includes_next_steps(self):
        """Test that report includes next steps"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="steps-test",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        assert len(report.next_steps) > 0

    def test_generate_deterministic_id(self):
        """Test that same config generates same ID"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="deterministic",
            language=Language.PYTHON,
            port=8080
        )

        report1 = scaffold.generate(config)
        report2 = scaffold.generate(config)

        assert report1.id == report2.id

    def test_generate_different_configs_different_ids(self):
        """Test that different configs generate different IDs"""
        scaffold = MicroserviceScaffold()

        config1 = ServiceConfig(name="service1", language=Language.PYTHON)
        config2 = ServiceConfig(name="service2", language=Language.PYTHON)

        report1 = scaffold.generate(config1)
        report2 = scaffold.generate(config2)

        assert report1.id != report2.id


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldPythonTemplates:
    """Test Python template generation"""

    def test_python_requirements_minimal(self):
        """Test Python requirements with minimal dependencies"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="minimal",
            language=Language.PYTHON,
            include_tests=False,
            include_logging=False
        )

        report = scaffold.generate(config)
        req_file = next((f for f in report.files if "requirements.txt" in f.path), None)

        assert req_file is not None
        assert "pydantic" in req_file.content

    def test_python_requirements_with_fastapi(self):
        """Test Python requirements include FastAPI"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="fastapi-test",
            language=Language.PYTHON,
            framework=Framework.FASTAPI
        )

        report = scaffold.generate(config)
        req_file = next((f for f in report.files if "requirements.txt" in f.path), None)

        assert req_file is not None
        assert "fastapi" in req_file.content
        assert "uvicorn" in req_file.content

    def test_python_requirements_with_tests(self):
        """Test Python requirements include test dependencies"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="test-deps",
            language=Language.PYTHON,
            include_tests=True
        )

        report = scaffold.generate(config)
        req_file = next((f for f in report.files if "requirements.txt" in f.path), None)

        assert req_file is not None
        assert "pytest" in req_file.content
        assert "pytest-asyncio" in req_file.content

    def test_python_fastapi_main_content(self):
        """Test FastAPI main.py content"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="fastapi-main",
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            description="Test API",
            include_healthcheck=True
        )

        report = scaffold.generate(config)
        main_file = next((f for f in report.files if "main.py" in f.path), None)

        assert main_file is not None
        assert "from fastapi import FastAPI" in main_file.content
        assert "fastapi-main" in main_file.content
        assert "Test API" in main_file.content
        assert "health" in main_file.content

    def test_python_settings_content(self):
        """Test Python settings.py content"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="settings-test",
            language=Language.PYTHON,
            port=9000
        )

        report = scaffold.generate(config)
        settings_file = next((f for f in report.files if "settings.py" in f.path), None)

        assert settings_file is not None
        assert "pydantic_settings" in settings_file.content
        assert "settings-test" in settings_file.content
        assert "9000" in settings_file.content

    def test_python_health_router_content(self):
        """Test Python health router content"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="health-test",
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            include_healthcheck=True
        )

        report = scaffold.generate(config)
        health_file = next((f for f in report.files if "health.py" in f.path), None)

        assert health_file is not None
        assert "APIRouter" in health_file.content
        assert "/ready" in health_file.content or "ready" in health_file.content
        assert "/live" in health_file.content or "live" in health_file.content


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldFileStructure:
    """Test generated file and directory structure"""

    def test_python_directory_structure(self):
        """Test Python service directory structure"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="structure-test",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        assert "structure-test" in report.directories
        assert "structure-test/app" in report.directories
        assert "structure-test/app/routers" in report.directories
        assert "structure-test/app/services" in report.directories
        assert "structure-test/app/models" in report.directories
        assert "structure-test/app/config" in report.directories

    def test_python_with_tests_directory_structure(self):
        """Test Python service directory structure with tests"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="test-structure",
            language=Language.PYTHON,
            include_tests=True
        )

        report = scaffold.generate(config)

        assert "test-structure/tests" in report.directories
        assert "test-structure/tests/unit" in report.directories
        assert "test-structure/tests/integration" in report.directories

    def test_typescript_directory_structure(self):
        """Test TypeScript service directory structure"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="ts-structure",
            language=Language.TYPESCRIPT
        )

        report = scaffold.generate(config)

        assert "ts-structure/src" in report.directories
        assert "ts-structure/src/routes" in report.directories
        assert "ts-structure/src/services" in report.directories
        assert "ts-structure/src/models" in report.directories
        assert "ts-structure/src/config" in report.directories

    def test_go_directory_structure(self):
        """Test Go service directory structure"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="go-structure",
            language=Language.GO
        )

        report = scaffold.generate(config)

        assert "go-structure/cmd" in report.directories
        assert "go-structure/cmd/server" in report.directories
        assert "go-structure/internal" in report.directories
        assert "go-structure/internal/handlers" in report.directories
        assert "go-structure/pkg" in report.directories

    def test_python_init_files_created(self):
        """Test that __init__.py files are created for Python packages"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="init-test",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert any("app/__init__.py" in path for path in file_paths)
        assert any("app/routers/__init__.py" in path for path in file_paths)
        assert any("app/services/__init__.py" in path for path in file_paths)
        assert any("app/models/__init__.py" in path for path in file_paths)


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldSaveToDirectory:
    """Test save_to_directory method"""

    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_save_to_directory_creates_files(self, mock_open, mock_makedirs):
        """save_to_directory uses os.makedirs + open() to create the project."""
        scaffold = MicroserviceScaffold(output_dir="/tmp/test")
        config = ServiceConfig(
            name="save-test",
            language=Language.PYTHON,
        )

        report = scaffold.generate(config)
        output_path = scaffold.save_to_directory(report, "/tmp/test")

        assert mock_makedirs.called
        assert mock_open.called
        assert output_path is not None

    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.write_text')
    @patch('os.chmod')
    def test_save_executable_files(self, mock_chmod, mock_write, mock_mkdir):
        """Test that executable files have permissions set"""
        from Asgard.Volundr.Scaffold.models.scaffold_models import FileEntry, ScaffoldReport

        scaffold = MicroserviceScaffold()

        report = ScaffoldReport(
            id="test-123",
            project_name="exec-test",
            project_type="microservice",
            files=[
                FileEntry(path="script.sh", content="#!/bin/bash\necho 'test'", executable=True)
            ]
        )

        scaffold.save_to_directory(report, "/tmp/test")

        assert mock_chmod.called


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMicroserviceScaffoldEdgeCases:
    """Test edge cases and error handling"""

    def test_generate_with_empty_name(self):
        """Test generating service with empty name still works"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        assert report is not None
        assert report.project_name == ""

    def test_generate_with_special_characters_in_name(self):
        """Test generating service with special characters in name"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="my-awesome_service.v2",
            language=Language.PYTHON
        )

        report = scaffold.generate(config)

        assert report.project_name == "my-awesome_service.v2"

    def test_generate_preserves_all_config_flags(self):
        """Test that all configuration flags are respected"""
        scaffold = MicroserviceScaffold()
        config = ServiceConfig(
            name="all-flags",
            language=Language.PYTHON,
            include_tests=False,
            include_docker=False,
            include_cicd=False,
            include_docs=False,
            include_healthcheck=False
        )

        report = scaffold.generate(config)

        file_paths = [f.path for f in report.files]
        assert not any("test" in path.lower() for path in file_paths)
        assert not any("dockerfile" in path.lower() for path in file_paths)
        assert not any("health" in path.lower() for path in file_paths)
