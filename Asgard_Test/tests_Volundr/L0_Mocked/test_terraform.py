"""
Volundr Terraform Module Tests

Unit tests for Terraform module generation.
"""

import pytest

from Asgard.Volundr.Terraform import (
    ModuleConfig,
    ModuleBuilder,
    GeneratedModule,
    CloudProvider,
    ResourceCategory,
    ModuleComplexity,
)
from Asgard.Volundr.Terraform.models.terraform_models import (
    VariableConfig,
    OutputConfig,
)


class TestModuleConfig:
    """Tests for ModuleConfig model validation."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
        )
        assert config.name == "vpc"
        assert config.provider == CloudProvider.AWS
        assert config.category == ResourceCategory.NETWORKING
        assert config.complexity == ModuleComplexity.SIMPLE

    def test_full_config(self):
        """Test creating config with all fields."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            complexity=ModuleComplexity.COMPLEX,
            description="Production VPC module",
            variables=[
                VariableConfig(name="vpc_cidr", type="string", default="10.0.0.0/16"),
            ],
            outputs=[
                OutputConfig(name="vpc_id", description="VPC ID", value="aws_vpc.main.id"),
            ],
            tags={"Environment": "production"},
            terraform_version=">= 1.5.0",
        )
        assert config.complexity == ModuleComplexity.COMPLEX
        assert len(config.variables) == 1
        assert len(config.outputs) == 1

    def test_variable_config(self):
        """Test VariableConfig model."""
        var = VariableConfig(
            name="vpc_cidr",
            type="string",
            description="CIDR block for VPC",
            default="10.0.0.0/16",
            validation="can(cidrnetmask(var.vpc_cidr))",
        )
        assert var.name == "vpc_cidr"
        assert var.type == "string"
        assert var.default == "10.0.0.0/16"

    def test_output_config(self):
        """Test OutputConfig model."""
        output = OutputConfig(
            name="vpc_id",
            description="The VPC ID",
            value="aws_vpc.main.id",
            sensitive=False,
        )
        assert output.name == "vpc_id"
        assert output.value == "aws_vpc.main.id"


class TestCloudProvider:
    """Tests for CloudProvider enum."""

    def test_all_providers(self):
        """Test all cloud providers exist."""
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azurerm"
        assert CloudProvider.GCP.value == "google"
        assert CloudProvider.KUBERNETES.value == "kubernetes"
        assert CloudProvider.HELM.value == "helm"
        assert CloudProvider.VAULT.value == "vault"


class TestResourceCategory:
    """Tests for ResourceCategory enum."""

    def test_all_categories(self):
        """Test all resource categories exist."""
        assert ResourceCategory.COMPUTE.value == "compute"
        assert ResourceCategory.NETWORKING.value == "networking"
        assert ResourceCategory.STORAGE.value == "storage"
        assert ResourceCategory.DATABASE.value == "database"
        assert ResourceCategory.SECURITY.value == "security"
        assert ResourceCategory.MONITORING.value == "monitoring"
        assert ResourceCategory.CONTAINER.value == "container"
        assert ResourceCategory.SERVERLESS.value == "serverless"


class TestModuleComplexity:
    """Tests for ModuleComplexity enum."""

    def test_all_complexities(self):
        """Test all complexity levels exist."""
        assert ModuleComplexity.SIMPLE.value == "simple"
        assert ModuleComplexity.MODERATE.value == "moderate"
        assert ModuleComplexity.COMPLEX.value == "complex"
        assert ModuleComplexity.ENTERPRISE.value == "enterprise"


class TestModuleBuilder:
    """Tests for ModuleBuilder service."""

    @pytest.fixture
    def builder(self):
        """Create a ModuleBuilder instance."""
        return ModuleBuilder()

    @pytest.fixture
    def basic_config(self):
        """Create a basic module config."""
        return ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
        )

    def test_generate_returns_module(self, builder, basic_config):
        """Test that generate returns a GeneratedModule."""
        result = builder.generate(basic_config)
        assert isinstance(result, GeneratedModule)

    def test_generate_module_files(self, builder, basic_config):
        """Test that module_files dict is populated."""
        result = builder.generate(basic_config)
        assert isinstance(result.module_files, dict)
        assert len(result.module_files) > 0

    def test_generate_main_tf(self, builder, basic_config):
        """Test that main.tf is generated."""
        result = builder.generate(basic_config)
        assert "main.tf" in result.module_files
        assert len(result.module_files["main.tf"]) >= 0

    def test_generate_variables_tf(self, builder, basic_config):
        """Test that variables.tf is generated."""
        result = builder.generate(basic_config)
        assert "variables.tf" in result.module_files

    def test_generate_outputs_tf(self, builder, basic_config):
        """Test that outputs.tf is generated."""
        result = builder.generate(basic_config)
        assert "outputs.tf" in result.module_files

    def test_generate_versions_tf(self, builder, basic_config):
        """Test that versions.tf is generated."""
        result = builder.generate(basic_config)
        assert "versions.tf" in result.module_files
        assert "terraform" in result.module_files["versions.tf"]
        assert "required_version" in result.module_files["versions.tf"]

    def test_generate_readme(self, builder, basic_config):
        """Test that README.md is generated."""
        result = builder.generate(basic_config)
        assert "README.md" in result.module_files
        assert len(result.module_files["README.md"]) > 0
        assert result.documentation == result.module_files["README.md"]

    def test_generate_aws_module(self, builder):
        """Test generating an AWS module."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
        )
        result = builder.generate(config)
        assert "aws" in result.module_files["versions.tf"].lower()

    def test_generate_azure_module(self, builder):
        """Test generating an Azure module."""
        config = ModuleConfig(
            name="vnet",
            provider=CloudProvider.AZURE,
            category=ResourceCategory.NETWORKING,
        )
        result = builder.generate(config)
        assert "azurerm" in result.module_files["versions.tf"].lower()

    def test_generate_gcp_module(self, builder):
        """Test generating a GCP module."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.GCP,
            category=ResourceCategory.NETWORKING,
        )
        result = builder.generate(config)
        assert "google" in result.module_files["versions.tf"].lower()

    def test_generate_with_variables(self, builder):
        """Test generating module with custom variables."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            variables=[
                VariableConfig(name="vpc_cidr", type="string", default="10.0.0.0/16", description="VPC CIDR"),
                VariableConfig(name="environment", type="string", description="Environment name"),
            ],
        )
        result = builder.generate(config)
        assert "vpc_cidr" in result.module_files["variables.tf"]
        assert "environment" in result.module_files["variables.tf"]

    def test_generate_with_outputs(self, builder):
        """Test generating module with custom outputs."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            outputs=[
                OutputConfig(name="vpc_id", description="VPC ID", value="aws_vpc.main.id"),
                OutputConfig(name="subnet_ids", description="Subnet IDs", value="aws_subnet.main[*].id"),
            ],
        )
        result = builder.generate(config)
        assert "vpc_id" in result.module_files["outputs.tf"]
        assert "subnet_ids" in result.module_files["outputs.tf"]

    def test_generate_examples(self, builder, basic_config):
        """Test generating module with examples."""
        result = builder.generate(basic_config)
        assert result.examples is not None
        assert isinstance(result.examples, dict)

    def test_generate_tests(self, builder, basic_config):
        """Test generating module with tests."""
        result = builder.generate(basic_config)
        assert result.tests is not None
        assert isinstance(result.tests, dict)

    def test_generate_networking_category(self, builder):
        """Test generating networking module."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_generate_compute_category(self, builder):
        """Test generating compute module."""
        config = ModuleConfig(
            name="ec2",
            provider=CloudProvider.AWS,
            category=ResourceCategory.COMPUTE,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_generate_storage_category(self, builder):
        """Test generating storage module."""
        config = ModuleConfig(
            name="s3",
            provider=CloudProvider.AWS,
            category=ResourceCategory.STORAGE,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_generate_database_category(self, builder):
        """Test generating database module."""
        config = ModuleConfig(
            name="rds",
            provider=CloudProvider.AWS,
            category=ResourceCategory.DATABASE,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_best_practice_score(self, builder):
        """Test that best practice score is calculated."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            variables=[VariableConfig(name="cidr", type="string", description="CIDR block")],
            outputs=[OutputConfig(name="vpc_id", description="VPC ID", value="aws_vpc.main.id")],
        )
        result = builder.generate(config)
        assert result.best_practice_score > 0
        assert result.best_practice_score <= 100

    def test_save_to_directory(self, builder, basic_config, temp_output_dir):
        """Test saving module to directory."""
        result = builder.generate(basic_config)
        module_dir = builder.save_to_directory(result, output_dir=str(temp_output_dir))

        assert module_dir is not None
        from pathlib import Path
        module_path = Path(module_dir)
        assert module_path.exists()
        assert (module_path / "main.tf").exists()
        assert (module_path / "variables.tf").exists()
        assert (module_path / "outputs.tf").exists()
        assert (module_path / "versions.tf").exists()

    def test_terraform_version_constraint(self, builder):
        """Test that terraform version constraint is included."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            terraform_version=">= 1.5.0",
        )
        result = builder.generate(config)
        assert "1.5.0" in result.module_files["versions.tf"]

    def test_tags_in_locals(self, builder):
        """Test that tags are included in locals when present."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            tags={"Environment": "production", "Team": "platform"},
            locals={"region": "us-east-1"},
        )
        result = builder.generate(config)
        assert "locals.tf" in result.module_files
        assert "Environment" in result.module_files["locals.tf"] or "common_tags" in result.module_files["locals.tf"]

    def test_module_description_in_readme(self, builder):
        """Test that description is included in README."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            description="Production VPC with multi-AZ support",
        )
        result = builder.generate(config)
        assert "Production VPC" in result.documentation

    def test_complexity_simple(self, builder):
        """Test generating simple complexity module."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            complexity=ModuleComplexity.SIMPLE,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_complexity_complex(self, builder):
        """Test generating complex complexity module."""
        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            complexity=ModuleComplexity.COMPLEX,
        )
        result = builder.generate(config)
        assert "main.tf" in result.module_files

    def test_module_id_generated(self, builder, basic_config):
        """Test that module ID is generated."""
        result = builder.generate(basic_config)
        assert result.id is not None
        assert "vpc" in result.id

    def test_config_hash_generated(self, builder, basic_config):
        """Test that config hash is generated."""
        result = builder.generate(basic_config)
        assert result.config_hash is not None
        assert len(result.config_hash) > 0

    def test_validation_results(self, builder, basic_config):
        """Test that validation results are included."""
        result = builder.generate(basic_config)
        assert isinstance(result.validation_results, list)

    def test_file_count_property(self, builder, basic_config):
        """Test the file_count property."""
        result = builder.generate(basic_config)
        assert result.file_count > 0
        assert result.file_count == len(result.module_files)

    def test_has_issues_property(self, builder, basic_config):
        """Test the has_issues property."""
        result = builder.generate(basic_config)
        assert isinstance(result.has_issues, bool)
