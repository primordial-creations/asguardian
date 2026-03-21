"""
Contract Validator Helpers.

Helper functions for ContractValidatorService.
"""

from typing import Any

from Asgard.Forseti.Contracts.models.contract_models import (
    ContractValidationError,
    ContractValidationResult,
)


def validate_parameters(
    path: str,
    contract_params: list[dict[str, Any]],
    impl_params: list[dict[str, Any]],
) -> list[ContractValidationError]:
    """Validate parameters."""
    errors: list[ContractValidationError] = []

    contract_param_map = {
        (p.get("name"), p.get("in")): p
        for p in contract_params
    }
    impl_param_map = {
        (p.get("name"), p.get("in")): p
        for p in impl_params
    }

    for (name, loc), param in contract_param_map.items():
        if (name, loc) not in impl_param_map:
            errors.append(ContractValidationError(
                path=f"{path}/parameters/{name}",
                message=f"Parameter '{name}' ({loc}) not implemented",
                severity="error",
            ))
        else:
            impl_param = impl_param_map[(name, loc)]
            if param.get("required", False) and not impl_param.get("required", False):
                errors.append(ContractValidationError(
                    path=f"{path}/parameters/{name}",
                    message=f"Parameter '{name}' should be required",
                    expected="required=true",
                    actual="required=false",
                    severity="error",
                ))

    return errors


def validate_request_body(
    path: str,
    contract_body: dict[str, Any],
    impl_body: dict[str, Any],
) -> list[ContractValidationError]:
    """Validate request body."""
    errors: list[ContractValidationError] = []

    if contract_body.get("required", False) and not impl_body.get("required", False):
        errors.append(ContractValidationError(
            path=f"{path}/requestBody",
            message="Request body should be required",
            severity="error",
        ))

    contract_content = contract_body.get("content", {})
    impl_content = impl_body.get("content", {})

    for content_type in contract_content:
        if content_type not in impl_content:
            errors.append(ContractValidationError(
                path=f"{path}/requestBody/content/{content_type}",
                message=f"Content type '{content_type}' not implemented",
                severity="error",
            ))

    return errors


def validate_responses(
    path: str,
    contract_responses: dict[str, Any],
    impl_responses: dict[str, Any],
) -> list[ContractValidationError]:
    """Validate responses."""
    errors: list[ContractValidationError] = []

    for status_code in contract_responses:
        if status_code not in impl_responses:
            errors.append(ContractValidationError(
                path=f"{path}/responses/{status_code}",
                message=f"Response {status_code} not implemented",
                severity="error",
            ))

    return errors


def validate_operation(
    path: str,
    contract_op: dict[str, Any],
    impl_op: dict[str, Any],
    check_parameters: bool,
    check_request_body: bool,
    check_response_body: bool,
) -> list[ContractValidationError]:
    """Validate a single operation."""
    errors: list[ContractValidationError] = []

    if check_parameters:
        errors.extend(validate_parameters(
            path,
            contract_op.get("parameters", []),
            impl_op.get("parameters", []),
        ))

    if check_request_body:
        if "requestBody" in contract_op:
            if "requestBody" not in impl_op:
                errors.append(ContractValidationError(
                    path=f"{path}/requestBody",
                    message="Request body not implemented",
                    severity="error",
                ))
            else:
                errors.extend(validate_request_body(
                    path,
                    contract_op["requestBody"],
                    impl_op["requestBody"],
                ))

    if check_response_body:
        errors.extend(validate_responses(
            path,
            contract_op.get("responses", {}),
            impl_op.get("responses", {}),
        ))

    return errors


def validate_path(
    path: str,
    contract_item: dict[str, Any],
    impl_item: dict[str, Any],
    check_parameters: bool,
    check_request_body: bool,
    check_response_body: bool,
) -> list[ContractValidationError]:
    """Validate a single path."""
    errors: list[ContractValidationError] = []
    methods = ["get", "post", "put", "delete", "patch", "options", "head"]

    for method in methods:
        if method in contract_item:
            if method not in impl_item:
                errors.append(ContractValidationError(
                    path=f"{path}/{method}",
                    message=f"Method {method.upper()} not implemented for {path}",
                    severity="error",
                ))
            else:
                errors.extend(validate_operation(
                    f"{path}/{method}",
                    contract_item[method],
                    impl_item[method],
                    check_parameters,
                    check_request_body,
                    check_response_body,
                ))

    return errors


def generate_text_report(result: ContractValidationResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Contract Validation Report")
    lines.append("=" * 60)
    lines.append(f"Contract: {result.contract_path or 'N/A'}")
    lines.append(f"Implementation: {result.implementation_path or 'N/A'}")
    lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"Errors: {result.error_count}")
    lines.append("-" * 60)

    if result.errors:
        lines.append("\nErrors:")
        for error in result.errors:
            lines.append(f"  [{error.path}] {error.message}")

    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            lines.append(f"  [{warning.path}] {warning.message}")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: ContractValidationResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# Contract Validation Report\n")
    lines.append(f"- **Contract**: {result.contract_path or 'N/A'}")
    lines.append(f"- **Implementation**: {result.implementation_path or 'N/A'}")
    lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"- **Errors**: {result.error_count}\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            lines.append(f"- `{error.path}`: {error.message}")

    if result.warnings:
        lines.append("\n## Warnings\n")
        for warning in result.warnings:
            lines.append(f"- `{warning.path}`: {warning.message}")

    return "\n".join(lines)
