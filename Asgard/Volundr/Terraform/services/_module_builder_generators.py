"""Terraform module file generators - main.tf, variables.tf, outputs.tf, versions.tf, locals.tf, docs."""

import json
from typing import Dict, List

from Asgard.Volundr.Terraform.models.terraform_models import (
    ModuleConfig,
)
from Asgard.Volundr.Terraform.services._module_builder_blocks import (
    PROVIDER_SOURCES,
    generate_data_source_block,
    generate_resource_block,
)


def generate_main_tf(config: ModuleConfig) -> str:
    content: List[str] = []

    if config.locals:
        content.append("locals {")
        for key, value in config.locals.items():
            if isinstance(value, str):
                content.append(f'  {key} = "{value}"')
            else:
                content.append(f"  {key} = {json.dumps(value)}")
        content.append("}")
        content.append("")

    for data_source in config.data_sources:
        content.extend(generate_data_source_block(data_source, config))
        content.append("")

    for resource in config.resources:
        content.extend(generate_resource_block(resource, config))
        content.append("")

    return "\n".join(content)


def generate_variables_tf(config: ModuleConfig) -> str:
    content: List[str] = []

    for var in config.variables:
        content.append(f'variable "{var.name}" {{')
        content.append(f'  description = "{var.description}"')
        content.append(f"  type        = {var.type}")

        if var.default is not None:
            if isinstance(var.default, str):
                content.append(f'  default     = "{var.default}"')
            elif isinstance(var.default, bool):
                content.append(f"  default     = {str(var.default).lower()}")
            else:
                content.append(f"  default     = {json.dumps(var.default)}")

        if var.validation:
            content.append("  validation {")
            content.append(f"    condition     = {var.validation}")
            content.append(f'    error_message = "Invalid value for {var.name}."')
            content.append("  }")

        if var.sensitive:
            content.append("  sensitive   = true")

        content.append("}")
        content.append("")

    return "\n".join(content)


def generate_outputs_tf(config: ModuleConfig) -> str:
    content: List[str] = []

    for output in config.outputs:
        content.append(f'output "{output.name}" {{')
        content.append(f'  description = "{output.description}"')
        content.append(f"  value       = {output.value}")

        if output.sensitive:
            content.append("  sensitive   = true")

        content.append("}")
        content.append("")

    return "\n".join(content)


def generate_versions_tf(config: ModuleConfig) -> str:
    content: List[str] = []

    content.append("terraform {")
    content.append(f'  required_version = "{config.terraform_version}"')
    content.append("")
    content.append("  required_providers {")

    source, version = PROVIDER_SOURCES.get(config.provider, ("hashicorp/null", ">= 3.0"))
    content.append(f"    {config.provider.value} = {{")
    content.append(f'      source  = "{source}"')
    content.append(f'      version = "{version}"')
    content.append("    }")

    for provider, version in config.required_providers.items():
        content.append(f"    {provider} = {{")
        content.append(f'      source  = "hashicorp/{provider}"')
        content.append(f'      version = "{version}"')
        content.append("    }")

    content.append("  }")
    content.append("}")

    return "\n".join(content)


def generate_locals_tf(config: ModuleConfig) -> str:
    content: List[str] = []

    content.append("locals {")

    if config.tags:
        content.append("  common_tags = {")
        for key, value in config.tags.items():
            content.append(f'    "{key}" = "{value}"')
        content.append("  }")
        content.append("")

    for key, value in config.locals.items():
        if key != "common_tags":
            if isinstance(value, str):
                content.append(f'  {key} = "{value}"')
            else:
                content.append(f"  {key} = {json.dumps(value, indent=2)}")

    content.append("}")

    return "\n".join(content)


def generate_documentation(config: ModuleConfig) -> str:
    content: List[str] = []

    content.extend([
        f"# {config.name.replace('_', ' ').title()}",
        "",
        config.description or f"Terraform module for {config.category.value} resources on {config.provider.value.upper()}.",
        "",
        "## Overview",
        "",
        f"This Terraform module creates {config.category.value} resources on {config.provider.value.upper()}.",
        f"It follows best practices for {config.complexity.value} deployments.",
        "",
        "## Usage",
        "",
        "```hcl",
        f'module "{config.name}" {{',
        f'  source = "./{config.name}"',
        "",
    ])

    for var in config.variables[:5]:
        if var.default is not None:
            if isinstance(var.default, str):
                content.append(f'  {var.name} = "{var.default}"')
            else:
                content.append(f"  {var.name} = {json.dumps(var.default)}")
        else:
            content.append(f'  {var.name} = "your-value-here"')

    content.extend([
        "}",
        "```",
        "",
        "## Requirements",
        "",
        "| Name | Version |",
        "|------|---------|",
        f"| terraform | {config.terraform_version} |",
    ])

    source, version = PROVIDER_SOURCES.get(config.provider, ("hashicorp/null", ">= 3.0"))
    content.append(f"| {config.provider.value} | {version} |")

    for provider, version in config.required_providers.items():
        content.append(f"| {provider} | {version} |")

    content.extend([
        "",
        "## Inputs",
        "",
        "| Name | Description | Type | Default | Required |",
        "|------|-------------|------|---------|----------|",
    ])

    for var in config.variables:
        default_val = "n/a" if var.default is None else str(var.default)
        required = "yes" if var.default is None else "no"
        content.append(f"| {var.name} | {var.description} | `{var.type}` | `{default_val}` | {required} |")

    content.extend([
        "",
        "## Outputs",
        "",
        "| Name | Description |",
        "|------|-------------|",
    ])

    for output in config.outputs:
        content.append(f"| {output.name} | {output.description} |")

    content.extend([
        "",
        "## Examples",
        "",
        "See the `examples/` directory for complete usage examples.",
        "",
        "## Security Considerations",
        "",
        "- All resources are created with security best practices",
        "- Sensitive values are marked appropriately",
        "- Network security groups follow least privilege principle",
        "",
        f"## Version: {config.version}",
    ])

    return "\n".join(content)
