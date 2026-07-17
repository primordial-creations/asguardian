"""Terraform resource and data source block generators + example generation."""

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
                'data "aws_subnets" "default" {', "  filter {",
                '    name   = "vpc-id"', "    values = [data.aws_vpc.default.id]",
                "  }", "}",
            ])
        elif "ami" in data_source.lower():
            lines.extend([
                'data "aws_ami" "latest" {', "  most_recent = true",
                '  owners      = ["amazon"]', "", "  filter {",
                '    name   = "name"',
                '    values = ["amzn2-ami-hvm-*-x86_64-gp2"]', "  }", "}",
            ])
    elif config.provider == CloudProvider.AZURE:
        if "resource_group" in data_source.lower():
            lines.extend([
                'data "azurerm_resource_group" "main" {',
                "  name = var.resource_group_name", "}",
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
                "  subnet_id     = data.aws_subnets.default.ids[0]", "",
                f"  tags = merge({tags_ref}, {{",
                "    Name = var.instance_name", "  })", "}",
            ])
        elif "s3" in resource.lower():
            lines.extend([
                'resource "aws_s3_bucket" "main" {',
                "  bucket = var.bucket_name", "",
                f"  tags = {tags_ref}", "}", "",
                # Security companions (plan 02 §2): public-access block is
                # "the most notorious cloud vulnerability" (RESEARCH_01).
                'resource "aws_s3_bucket_public_access_block" "main" {',
                "  bucket = aws_s3_bucket.main.id", "",
                "  block_public_acls       = true",
                "  block_public_policy     = true",
                "  ignore_public_acls      = true",
                "  restrict_public_buckets = true", "}", "",
                'resource "aws_s3_bucket_ownership_controls" "main" {',
                "  bucket = aws_s3_bucket.main.id", "",
                "  rule {", '    object_ownership = "BucketOwnerEnforced"', "  }", "}", "",
                'resource "aws_s3_bucket_versioning" "main" {',
                "  bucket = aws_s3_bucket.main.id",
                "  versioning_configuration {",
                '    status = "Enabled"', "  }", "}", "",
                'resource "aws_s3_bucket_server_side_encryption_configuration" "main" {',
                "  bucket = aws_s3_bucket.main.id", "", "  rule {",
                "    apply_server_side_encryption_by_default {",
                '      sse_algorithm = var.kms_encryption ? "aws:kms" : "AES256"',
                "      kms_master_key_id = var.kms_encryption ? var.kms_key_id : null",
                "    }",
                "    bucket_key_enabled = true",
                "  }", "}",
            ])
        elif "rds" in resource.lower() or "db_instance" in resource.lower():
            lines.extend([
                'resource "aws_db_instance" "main" {',
                "  identifier     = var.db_identifier",
                "  engine         = var.db_engine",
                "  instance_class = var.db_instance_class",
                "  allocated_storage = var.db_allocated_storage", "",
                # Security baseline (plan 02 §2): encrypted storage,
                # deletion protection, no hardcoded credentials.
                "  storage_encrypted  = true",
                "  deletion_protection = var.db_deletion_protection",
                "  username = var.db_username",
                "  password = var.db_password", "",
                f"  tags = {tags_ref}", "}",
            ])
        elif "security_group" in resource.lower() or resource.lower() == "sg":
            lines.extend([
                'resource "aws_security_group" "main" {',
                "  name        = var.security_group_name",
                "  description = var.security_group_description",
                "  vpc_id      = var.vpc_id", "",
                "  ingress {",
                "    description = \"restricted ingress (VOL-TF-0005: no 0.0.0.0/0 default)\"",
                "    from_port   = var.ingress_from_port",
                "    to_port     = var.ingress_to_port",
                "    protocol    = var.ingress_protocol",
                "    cidr_blocks = var.ingress_cidr_blocks", "  }", "",
                "  egress {",
                "    from_port   = 0",
                "    to_port     = 0",
                "    protocol    = \"-1\"",
                "    cidr_blocks = [\"0.0.0.0/0\"]", "  }", "",
                f"  tags = {tags_ref}", "}",
            ])
        elif "vpc" in resource.lower():
            lines.extend([
                'resource "aws_vpc" "main" {',
                "  cidr_block           = var.vpc_cidr",
                "  enable_dns_hostnames = true",
                "  enable_dns_support   = true", "",
                f"  tags = merge({tags_ref}, {{",
                '    Name = "${var.name_prefix}-vpc"', "  })", "}",
            ])
    elif config.provider == CloudProvider.AZURE:
        if "resource_group" in resource.lower():
            lines.extend([
                'resource "azurerm_resource_group" "main" {',
                "  name     = var.resource_group_name",
                "  location = var.location", "",
                "  tags = var.tags", "}",
            ])
        elif "virtual_network" in resource.lower():
            lines.extend([
                'resource "azurerm_virtual_network" "main" {',
                '  name                = "${var.name_prefix}-vnet"',
                "  address_space       = [var.vnet_cidr]",
                "  location            = azurerm_resource_group.main.location",
                "  resource_group_name = azurerm_resource_group.main.name", "",
                "  tags = var.tags", "}",
            ])
        elif "storage_account" in resource.lower() or "storage" in resource.lower():
            lines.extend([
                'resource "azurerm_storage_account" "main" {',
                "  name                     = var.storage_account_name",
                "  resource_group_name      = azurerm_resource_group.main.name",
                "  location                 = azurerm_resource_group.main.location",
                '  account_tier             = "Standard"',
                '  account_replication_type = "GRS"', "",
                # Security baseline (plan 02 §2 Azure parity).
                "  allow_nested_items_to_be_public = false",
                '  min_tls_version                 = "TLS1_2"', "",
                "  tags = var.tags", "}",
            ])
    elif config.provider == CloudProvider.GCP:
        if "compute_instance" in resource.lower():
            lines.extend([
                'resource "google_compute_instance" "main" {',
                "  name         = var.instance_name",
                "  machine_type = var.machine_type",
                "  zone         = var.zone", "",
                "  boot_disk {", "    initialize_params {",
                "      image = var.image", "    }", "}", "",
                "  network_interface {", '    network = "default"',
                "    access_config {}", "}", "",
                "  labels = var.labels", "}",
            ])
        elif "storage_bucket" in resource.lower() or "storage" in resource.lower() or "gcs" in resource.lower():
            lines.extend([
                'resource "google_storage_bucket" "main" {',
                "  name     = var.bucket_name",
                "  location = var.gcp_region", "",
                # Security baseline (plan 02 §2 GCP parity).
                "  uniform_bucket_level_access = true", "",
                "  versioning {", "    enabled = true", "  }", "",
                "  labels = var.labels", "}",
            ])
    return lines


def generate_examples(config: ModuleConfig) -> Dict[str, str]:
    examples: Dict[str, str] = {}
    basic_example: List[str] = [
        f'module "{config.name}_basic" {{', '  source = "../../"', "",
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
            f'module "{config.name}_advanced" {{', '  source = "../../"', "",
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
