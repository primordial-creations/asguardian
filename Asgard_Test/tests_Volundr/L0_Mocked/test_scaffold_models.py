"""
L0 Unit Tests for Volundr Scaffold Models

Tests Pydantic models for project scaffolding configuration.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    ProjectType,
    Language,
    Framework,
    DatabaseType,
    MessageBroker,
    CICDPlatform,
    ContainerOrchestration,
    DependencyConfig,
    DatabaseConfig,
    MessagingConfig,
    ServiceConfig,
    ProjectConfig,
    FileEntry,
    ScaffoldReport,
)


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestProjectType:
    """Test ProjectType enum"""

    def test_project_type_values(self):
        """Test all project type values are accessible"""
        assert ProjectType.MICROSERVICE == "microservice"
        assert ProjectType.LIBRARY == "library"
        assert ProjectType.CLI == "cli"
        assert ProjectType.WEB_APP == "web-app"
        assert ProjectType.API == "api"
        assert ProjectType.WORKER == "worker"

    def test_project_type_from_string(self):
        """Test creating ProjectType from string"""
        assert ProjectType("microservice") == ProjectType.MICROSERVICE
        assert ProjectType("library") == ProjectType.LIBRARY


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestLanguage:
    """Test Language enum"""

    def test_language_values(self):
        """Test all language values are accessible"""
        assert Language.PYTHON == "python"
        assert Language.TYPESCRIPT == "typescript"
        assert Language.GO == "go"
        assert Language.RUST == "rust"
        assert Language.JAVA == "java"

    def test_language_from_string(self):
        """Test creating Language from string"""
        assert Language("python") == Language.PYTHON
        assert Language("go") == Language.GO


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestFramework:
    """Test Framework enum"""

    def test_framework_values(self):
        """Test all framework values are accessible"""
        assert Framework.FASTAPI == "fastapi"
        assert Framework.FLASK == "flask"
        assert Framework.DJANGO == "django"
        assert Framework.EXPRESS == "express"
        assert Framework.NESTJS == "nestjs"
        assert Framework.GIN == "gin"
        assert Framework.ECHO == "echo"
        assert Framework.ACTIX == "actix"
        assert Framework.SPRING == "spring"
        assert Framework.NONE == "none"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDatabaseType:
    """Test DatabaseType enum"""

    def test_database_type_values(self):
        """Test all database type values are accessible"""
        assert DatabaseType.POSTGRESQL == "postgresql"
        assert DatabaseType.MYSQL == "mysql"
        assert DatabaseType.MONGODB == "mongodb"
        assert DatabaseType.REDIS == "redis"
        assert DatabaseType.SQLITE == "sqlite"
        assert DatabaseType.NONE == "none"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMessageBroker:
    """Test MessageBroker enum"""

    def test_message_broker_values(self):
        """Test all message broker values are accessible"""
        assert MessageBroker.RABBITMQ == "rabbitmq"
        assert MessageBroker.KAFKA == "kafka"
        assert MessageBroker.REDIS == "redis"
        assert MessageBroker.NATS == "nats"
        assert MessageBroker.NONE == "none"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCICDPlatform:
    """Test CICDPlatform enum"""

    def test_cicd_platform_values(self):
        """Test all CICD platform values are accessible"""
        assert CICDPlatform.GITHUB_ACTIONS == "github-actions"
        assert CICDPlatform.GITLAB_CI == "gitlab-ci"
        assert CICDPlatform.AZURE_DEVOPS == "azure-devops"
        assert CICDPlatform.JENKINS == "jenkins"
        assert CICDPlatform.NONE == "none"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestContainerOrchestration:
    """Test ContainerOrchestration enum"""

    def test_container_orchestration_values(self):
        """Test all container orchestration values are accessible"""
        assert ContainerOrchestration.KUBERNETES == "kubernetes"
        assert ContainerOrchestration.DOCKER_COMPOSE == "docker-compose"
        assert ContainerOrchestration.DOCKER_SWARM == "docker-swarm"
        assert ContainerOrchestration.NONE == "none"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDependencyConfig:
    """Test DependencyConfig model"""

    def test_dependency_config_minimal(self):
        """Test DependencyConfig with minimal required fields"""
        dep = DependencyConfig(name="fastapi")

        assert dep.name == "fastapi"
        assert dep.version is None
        assert dep.dev is False

    def test_dependency_config_full(self):
        """Test DependencyConfig with all fields"""
        dep = DependencyConfig(
            name="pytest",
            version=">=7.0.0",
            dev=True
        )

        assert dep.name == "pytest"
        assert dep.version == ">=7.0.0"
        assert dep.dev is True

    def test_dependency_config_validation_missing_name(self):
        """Test DependencyConfig fails without name"""
        with pytest.raises(ValidationError):
            DependencyConfig()


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDatabaseConfig:
    """Test DatabaseConfig model"""

    def test_database_config_minimal(self):
        """Test DatabaseConfig with minimal required fields"""
        db = DatabaseConfig(type=DatabaseType.POSTGRESQL)

        assert db.type == DatabaseType.POSTGRESQL
        assert db.orm is None
        assert db.migrations is True

    def test_database_config_full(self):
        """Test DatabaseConfig with all fields"""
        db = DatabaseConfig(
            type=DatabaseType.POSTGRESQL,
            orm="sqlalchemy",
            migrations=False
        )

        assert db.type == DatabaseType.POSTGRESQL
        assert db.orm == "sqlalchemy"
        assert db.migrations is False

    def test_database_config_with_enum_string(self):
        """Test DatabaseConfig accepts string for type"""
        db = DatabaseConfig(type="mysql")

        assert db.type == DatabaseType.MYSQL


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestMessagingConfig:
    """Test MessagingConfig model"""

    def test_messaging_config_minimal(self):
        """Test MessagingConfig with minimal required fields"""
        msg = MessagingConfig(broker=MessageBroker.RABBITMQ)

        assert msg.broker == MessageBroker.RABBITMQ
        assert msg.publish == []
        assert msg.subscribe == []

    def test_messaging_config_with_topics(self):
        """Test MessagingConfig with publish and subscribe topics"""
        msg = MessagingConfig(
            broker=MessageBroker.KAFKA,
            publish=["events.created", "events.updated"],
            subscribe=["commands.process"]
        )

        assert msg.broker == MessageBroker.KAFKA
        assert len(msg.publish) == 2
        assert "events.created" in msg.publish
        assert len(msg.subscribe) == 1
        assert "commands.process" in msg.subscribe


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestServiceConfig:
    """Test ServiceConfig model"""

    def test_service_config_minimal(self):
        """Test ServiceConfig with minimal required fields"""
        svc = ServiceConfig(
            name="test-service",
            language=Language.PYTHON
        )

        assert svc.name == "test-service"
        assert svc.language == Language.PYTHON
        assert svc.description == ""
        assert svc.project_type == ProjectType.MICROSERVICE
        assert svc.framework == Framework.NONE
        assert svc.port == 8080
        assert svc.database is None
        assert svc.messaging is None
        assert svc.dependencies == []
        assert svc.env_vars == {}
        assert svc.include_tests is True
        assert svc.include_docker is True
        assert svc.include_cicd is True
        assert svc.include_docs is True
        assert svc.include_healthcheck is True
        assert svc.include_logging is True
        assert svc.include_metrics is False
        assert svc.include_tracing is False

    def test_service_config_full(self):
        """Test ServiceConfig with all fields populated"""
        db_config = DatabaseConfig(type=DatabaseType.POSTGRESQL, orm="sqlalchemy")
        msg_config = MessagingConfig(broker=MessageBroker.RABBITMQ, publish=["events"])

        svc = ServiceConfig(
            name="api-service",
            description="REST API service",
            project_type=ProjectType.API,
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            port=9000,
            database=db_config,
            messaging=msg_config,
            dependencies=[
                DependencyConfig(name="pydantic", version=">=2.0"),
                DependencyConfig(name="pytest", dev=True)
            ],
            env_vars={"LOG_LEVEL": "DEBUG"},
            include_tests=True,
            include_docker=True,
            include_cicd=True,
            include_docs=True,
            include_healthcheck=True,
            include_logging=True,
            include_metrics=True,
            include_tracing=True
        )

        assert svc.name == "api-service"
        assert svc.description == "REST API service"
        assert svc.project_type == ProjectType.API
        assert svc.language == Language.PYTHON
        assert svc.framework == Framework.FASTAPI
        assert svc.port == 9000
        assert svc.database.type == DatabaseType.POSTGRESQL
        assert svc.messaging.broker == MessageBroker.RABBITMQ
        assert len(svc.dependencies) == 2
        assert "LOG_LEVEL" in svc.env_vars
        assert svc.include_metrics is True
        assert svc.include_tracing is True

    def test_service_config_validation_missing_name(self):
        """Test ServiceConfig fails without name"""
        with pytest.raises(ValidationError):
            ServiceConfig(language=Language.PYTHON)

    def test_service_config_validation_missing_language(self):
        """Test ServiceConfig fails without language"""
        with pytest.raises(ValidationError):
            ServiceConfig(name="test")


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestProjectConfig:
    """Test ProjectConfig model"""

    def test_project_config_minimal(self):
        """Test ProjectConfig with minimal required fields"""
        proj = ProjectConfig(name="my-project")

        assert proj.name == "my-project"
        assert proj.description == ""
        assert proj.version == "0.1.0"
        assert proj.author == ""
        assert proj.license == "MIT"
        assert proj.services == []
        assert proj.monorepo is False
        assert proj.cicd_platform == CICDPlatform.GITHUB_ACTIONS
        assert proj.orchestration == ContainerOrchestration.KUBERNETES
        assert proj.include_makefile is True
        assert proj.include_pre_commit is True
        assert proj.include_devcontainer is False
        assert proj.git_init is True
        assert proj.custom_templates == {}

    def test_project_config_full(self):
        """Test ProjectConfig with all fields populated"""
        svc1 = ServiceConfig(name="api", language=Language.PYTHON)
        svc2 = ServiceConfig(name="worker", language=Language.GO)

        proj = ProjectConfig(
            name="enterprise-app",
            description="Enterprise application suite",
            version="1.0.0",
            author="Development Team",
            license="Apache-2.0",
            services=[svc1, svc2],
            monorepo=True,
            cicd_platform=CICDPlatform.GITLAB_CI,
            orchestration=ContainerOrchestration.KUBERNETES,
            include_makefile=True,
            include_pre_commit=True,
            include_devcontainer=True,
            git_init=False,
            custom_templates={"README": "custom_readme.md"}
        )

        assert proj.name == "enterprise-app"
        assert proj.description == "Enterprise application suite"
        assert proj.version == "1.0.0"
        assert proj.author == "Development Team"
        assert proj.license == "Apache-2.0"
        assert len(proj.services) == 2
        assert proj.monorepo is True
        assert proj.cicd_platform == CICDPlatform.GITLAB_CI
        assert proj.include_devcontainer is True
        assert proj.git_init is False
        assert "README" in proj.custom_templates


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestFileEntry:
    """Test FileEntry model"""

    def test_file_entry_minimal(self):
        """Test FileEntry with minimal required fields"""
        file = FileEntry(path="src/main.py", content="print('hello')")

        assert file.path == "src/main.py"
        assert file.content == "print('hello')"
        assert file.executable is False

    def test_file_entry_executable(self):
        """Test FileEntry with executable flag"""
        file = FileEntry(
            path="scripts/deploy.sh",
            content="#!/bin/bash\necho 'deploying'",
            executable=True
        )

        assert file.path == "scripts/deploy.sh"
        assert file.executable is True

    def test_file_entry_empty_content(self):
        """Test FileEntry with empty content"""
        file = FileEntry(path="__init__.py", content="")

        assert file.path == "__init__.py"
        assert file.content == ""


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestScaffoldReport:
    """Test ScaffoldReport model"""

    def test_scaffold_report_minimal(self):
        """Test ScaffoldReport with minimal required fields"""
        report = ScaffoldReport(
            id="scaffold-123",
            project_name="test-project",
            project_type="microservice"
        )

        assert report.id == "scaffold-123"
        assert report.project_name == "test-project"
        assert report.project_type == "microservice"
        assert report.files == []
        assert report.directories == []
        assert report.total_files == 0
        assert report.total_directories == 0
        assert isinstance(report.created_at, datetime)
        assert report.output_path is None
        assert report.messages == []
        assert report.next_steps == []

    def test_scaffold_report_full(self):
        """Test ScaffoldReport with all fields populated"""
        files = [
            FileEntry(path="main.py", content="# main"),
            FileEntry(path="test.py", content="# test")
        ]

        report = ScaffoldReport(
            id="scaffold-456",
            project_name="api-service",
            project_type="api",
            files=files,
            directories=["src", "tests", "config"],
            total_files=2,
            total_directories=3,
            output_path="/projects/api-service",
            messages=["Generated successfully"],
            next_steps=["Run: cd api-service", "Run: pip install -r requirements.txt"]
        )

        assert report.id == "scaffold-456"
        assert len(report.files) == 2
        assert len(report.directories) == 3
        assert report.total_files == 2
        assert report.total_directories == 3
        assert report.output_path == "/projects/api-service"
        assert len(report.messages) == 1
        assert len(report.next_steps) == 2

    def test_scaffold_report_file_count_property(self):
        """Test ScaffoldReport file_count property"""
        files = [
            FileEntry(path="file1.py", content=""),
            FileEntry(path="file2.py", content=""),
            FileEntry(path="file3.py", content="")
        ]

        report = ScaffoldReport(
            id="scaffold-789",
            project_name="lib",
            project_type="library",
            files=files
        )

        assert report.file_count == 3
        assert report.file_count == len(report.files)

    def test_scaffold_report_created_at_default(self):
        """Test ScaffoldReport created_at defaults to current time"""
        before = datetime.now()
        report = ScaffoldReport(
            id="scaffold-000",
            project_name="test",
            project_type="microservice"
        )
        after = datetime.now()

        assert before <= report.created_at <= after
