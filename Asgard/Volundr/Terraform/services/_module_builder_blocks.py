"""Terraform resource and data source block generators + validation/scoring."""

import json
from typing import Dict, List

from Asgard.Volundr.Terraform.models.terraform_models import (
    CloudProvider,
    ModuleComplexity,
    ModuleConfig,
)

PROVIDER_SOURCES = {
    CloudProvider.AWS: ("hashicorp/aws", ">= 5.0"),
    CloudProvider.AZURE: ("hashicorp/azurerm", ">= 3.0"),
    CloudProvider.GCP: ("hashicorp/google", ">= 4.0"),
    CloudProvider.KUBERNETES: ("hashicorp/kubernetes", ">= 2.0"),
    CloudProvider.HELM: ("hashicorp/helm", ">= 2.0"),
    CloudProvider.VAULT: ("hashicorp/vault", ">= 3.0"),
}


def generate_data_source_block(data_source: str, config: ModuleConfig) -> List[str]:
    lines: List[str] = []

    if config.provider == CloudProvider.AWS:
        if "vpc" in data_source.lower():
            lines.extend(['data "aws_vpc" "default" {', "  default = true", "}"])
        elif "subnet" in data_source.lower():
            lines.extend([
                'data "aws_subnets" "default" {',
                "  filter {",
                '    name   = "vpc-id"',
                "    values = [data.aws_vpc.default.id]",
                "  }",
                "}",
            ])
        elif "ami" in data_source.lower():
            lines.extend([
                'data "aws_ami" "latest" {',
                "  most_recent = true",
                '  owners      = ["amazon"]',
                "",
                "  filter {",
                '    name   = "name"',
                '    values = ["amzn2-ami-hvm-*-x86_64-gp2"]',
                "  }",
                "}",
            ])
    elif config.provider == CloudProvider.AZURE:
        if "resource_group" in data_source.lower():
            lines.extend([
                'data "azurerm_resource_group" "main" {',
                "  name = var.resource_group_name",
                "}",
            ])
    elif config.provider == CloudProvider.GCP:
        if "project" in data_source.lower():
            lines.extend(['data "google_project" "current" {', "}"])

    return lines


def generate_resource_block(resource: str, config: ModuleConfig) -> List[str]:
    lines: List[str] = []
    tags_ref = "local.common_tags" if config.tags else "var.tags"

    if config.provider == CloudProvider.AWS:
        if "instance" in resource.lower():
            lines.extend([
                'resource "aws_instance" "main" {',
                "  ami           = data.aws_ami.latest.id",
                "  instance_type = var.instance_type",
                "  subnet_id     = data.aws_subnets.default.ids[0]",
                "",
                f"  tags = merge({tags_ref}, {{",
                "    Name = var.instance_name",
                "  })",
                "}",
            ])
        elif "s3" in resource.lower():
            lines.extend([
                'resource "aws_s3_bucket" "main" {',
                "  bucket = var.bucket_name",
                "",
                f"  tags = {tags_ref}",
                "}",
                "",
                'resource "aws_s3_bucket_versioning" "main" {',
                "  bucket = aws_s3_bucket.main.id",
                "  versioning_configuration {",
                '    status = "Enabled"',
                "  }",
                "}",
                "",
                'resource "aws_s3_bucket_server_side_encryption_configuration" "main" {',
                "  bucket = aws_s3_bucket.main.id",
                "",
                "  rule {",
                "    apply_server_side_encryption_by_default {",
                '      sse_algorithm = "AES256"',
                "    }",
                "  }",
                "}",
            ])
        elif "vpc" in resource.lower():
            lines.extend([
                'resource "aws_vpc" "main" {',
                "  cidr_block           = var.vpc_cidr",
                "  enable_dns_hostnames = true",
                "  enable_dns_support   = true",
                "",
                f"  tags = merge({tags_ref}, {{",
                '    Name = "${var.name_prefix}-vpc"',
                "  })",
                "}",
            ])
    elif config.provider == CloudProvider.AZURE:
        if "resource_group" in resource.lower():
            lines.extend([
                'resource "azurerm_resource_group" "main" {',
                "  name     = var.resource_group_name",
                "  location = var.location",
                "",
                "  tags = var.tags",
                "}",
            ])
        elif "virtual_network" in resource.lower():
            lines.extend([
                'resource "azurerm_virtual_network" "main" {',
                '  name                = "${var.name_prefix}-vnet"',
                "  address_space       = [var.vnet_cidr]",
                "  location            = azurerm_resource_group.main.location",
                "  resource_group_name = azurerm_resource_group.main.name",
                "",
                "  tags = var.tags",
                "}",
            ])
    elif config.provider == CloudProvider.GCP:
        if "compute_instance" in resource.lower():
            lines.extend([
                'resource "google_compute_instance" "main" {',
                "  name         = var.instance_name",
                "  machine_type = var.machine_type",
                "  zone         = var.zone",
                "",
                "  boot_disk {",
                "    initialize_params {",
                "      image = var.image",
                "    }",
                "  }",
                "",
                "  network_interface {",
                '    network = "default"',
                "    access_config {}",
                "  }",
                "",
                "  labels = var.labels",
                "}",
            ])

    return lines


def generate_examples(config: ModuleConfig) -> Dict[str, str]:
    examples: Dict[str, str] = {}

    basic_example: List[str] = [
        f'module "{config.name}_basic" {{',
        '  source = "../../"',
        "",
    ]

    for var in config.variables:
        if var.default is None:
            if "name" in var.name.lower():
                basic_example.append(f'  {var.name} = "example-{config.name}"')
            elif var.type == "string":
                basic_example.append(f'  {var.name} = "example-value"')
            elif var.type == "number":
                basic_example.append(f"  {var.name} = 1")
            elif var.type == "bool":
                basic_example.append(f"  {var.name} = true")

    basic_example.append("}")
    examples["basic"] = "\n".join(basic_example)

    if config.complexity in [ModuleComplexity.COMPLEX, ModuleComplexity.ENTERPRISE]:
        advanced_example: List[str] = [
            f'module "{config.name}_advanced" {{',
            '  source = "../../"',
            "",
        ]

        for var in config.variables:
            if var.default is not None:
                if isinstance(var.default, str):
                    advanced_example.append(f'  {var.name} = "advanced-{var.default}"')
                else:
                    advanced_example.append(f"  {var.name} = {json.dumps(var.default)}")
            else:
                advanced_example.append(f'  {var.name} = "advanced-example"')

        advanced_example.append("}")
        examples["advanced"] = "\n".join(advanced_example)

    return examples


def generate_tests(config: ModuleConfig) -> Dict[str, str]:
    tests: Dict[str, str] = {}

    output_name = config.outputs[0].name if config.outputs else "id"
    terratest_content = f'''package test

import (
    "testing"
    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
)

func Test{config.name.replace("_", "").title()}Basic(t *testing.T) {{
    terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{{
        TerraformDir: "../examples/basic",
    }})

    defer terraform.Destroy(t, terraformOptions)
    terraform.InitAndApply(t, terraformOptions)

    output := terraform.Output(t, terraformOptions, "{output_name}")
    assert.NotEmpty(t, output)
}}
'''
    tests["terratest"] = terratest_content

    kitchen_yml = f'''---
driver:
  name: terraform
  variable_files:
    - testing.tfvars

provisioner:
  name: terraform

verifier:
  name: terraform
  format: junit

platforms:
  - name: {config.provider.value}

suites:
  - name: {config.name}
    driver:
      root_module_directory: test/fixtures/{config.name}
    verifier:
      color: false
      fail_fast: false
      systems:
        - name: {config.name}
          backend: local
'''
    tests["kitchen"] = kitchen_yml

    return tests


def validate_module(module_files: Dict[str, str], config: ModuleConfig) -> List[str]:
    issues: List[str] = []

    required_files = ["main.tf", "variables.tf", "outputs.tf", "versions.tf"]
    for file in required_files:
        if file not in module_files:
            issues.append(f"Missing required file: {file}")

    if "variables.tf" in module_files:
        variables_content = module_files["variables.tf"]
        for var in config.variables:
            if f'variable "{var.name}"' not in variables_content:
                issues.append(f"Variable {var.name} not found in variables.tf")

    if "outputs.tf" in module_files:
        outputs_content = module_files["outputs.tf"]
        for output in config.outputs:
            if f'output "{output.name}"' not in outputs_content:
                issues.append(f"Output {output.name} not found in outputs.tf")

    if "main.tf" in module_files:
        main_content = module_files["main.tf"]
        if config.provider == CloudProvider.AWS:
            if "aws_s3_bucket" in main_content and "server_side_encryption" not in main_content:
                issues.append("S3 bucket missing encryption configuration")
            if "aws_security_group" in main_content and "0.0.0.0/0" in main_content:
                issues.append("Security group allows access from 0.0.0.0/0")

    return issues


def calculate_best_practice_score(module_files: Dict[str, str], config: ModuleConfig) -> float:
    score = 0.0
    max_score = 0.0

    max_score += 25
    required_files = ["main.tf", "variables.tf", "outputs.tf", "versions.tf", "README.md"]
    present_files = sum(1 for file in required_files if file in module_files)
    score += (present_files / len(required_files)) * 25

    max_score += 20
    if config.variables:
        documented_vars = sum(1 for var in config.variables if var.description)
        score += (documented_vars / len(config.variables)) * 20
    else:
        score += 20

    max_score += 15
    if config.outputs:
        documented_outputs = sum(1 for output in config.outputs if output.description)
        score += (documented_outputs / len(config.outputs)) * 15
    else:
        score += 15

    max_score += 15
    if "versions.tf" in module_files:
        versions_content = module_files["versions.tf"]
        if "required_version" in versions_content:
            score += 8
        if "required_providers" in versions_content:
            score += 7

    max_score += 15
    if "main.tf" in module_files:
        main_content = module_files["main.tf"]
        if config.provider == CloudProvider.AWS:
            if "encryption" in main_content or "kms" in main_content:
                score += 8
            if "0.0.0.0/0" not in main_content:
                score += 7
        else:
            score += 15

    max_score += 10
    if "README.md" in module_files:
        readme_content = module_files["README.md"]
        if len(readme_content) > 1000:
            score += 10
        elif len(readme_content) > 500:
            score += 5

    return (score / max_score) * 100 if max_score > 0 else 0.0
