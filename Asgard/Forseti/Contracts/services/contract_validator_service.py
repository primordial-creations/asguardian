"""
Contract Validator Service.

Validates API implementations against contracts.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Contracts.models.contract_models import (
    ContractConfig,
    ContractValidationResult,
    ContractValidationError,
)
from Asgard.Forseti.Contracts.utilities.contract_utils import load_contract_file


class ContractValidatorService:
    """
    Service for validating API implementations against contracts.

    Usage:
        service = ContractValidatorService()
        result = service.validate("contract.yaml", "implementation.yaml")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    def __init__(self, config: Optional[ContractConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or ContractConfig()

    def validate(
        self,
        contract_path: str | Path,
        implementation_path: str | Path
    ) -> ContractValidationResult:
        """
        Validate an implementation against a contract.

        Args:
            contract_path: Path to the contract specification.
            implementation_path: Path to the implementation specification.

        Returns:
            ContractValidationResult with validation details.
        """
        start_time = time.time()

        errors: list[ContractValidationError] = []
        warnings: list[ContractValidationError] = []

        # Load contract
        try:
            contract = load_contract_file(Path(contract_path))
        except Exception as e:
            errors.append(ContractValidationError(
                path="/",
                message=f"Failed to load contract: {str(e)}",
                severity="error",
            ))
            return ContractValidationResult(
                is_valid=False,
                contract_path=str(contract_path),
                errors=errors,
            )

        # Load implementation
        try:
            implementation = load_contract_file(Path(implementation_path))
        except Exception as e:
            errors.append(ContractValidationError(
                path="/",
                message=f"Failed to load implementation: {str(e)}",
                severity="error",
            ))
            return ContractValidationResult(
                is_valid=False,
                contract_path=str(contract_path),
                implementation_path=str(implementation_path),
                errors=errors,
            )

        # Validate paths
        contract_paths = self._extract_paths(contract)
        impl_paths = self._extract_paths(implementation)

        # Check all contract paths exist in implementation
        for path in contract_paths:
            if path not in impl_paths:
                errors.append(ContractValidationError(
                    path=path,
                    message=f"Contract path not implemented: {path}",
                    severity="error",
                ))

        # Validate each endpoint
        for path in contract_paths:
            if path in impl_paths:
                path_errors = self._validate_path(
                    path,
                    contract.get("paths", {}).get(path, {}),
                    implementation.get("paths", {}).get(path, {})
                )
                errors.extend([e for e in path_errors if e.severity == "error"])
                warnings.extend([e for e in path_errors if e.severity == "warning"])

        return ContractValidationResult(
            is_valid=len(errors) == 0,
            contract_path=str(contract_path),
            implementation_path=str(implementation_path),
            errors=errors,
            warnings=warnings,
        )

    def _extract_paths(self, spec: dict[str, Any]) -> set[str]:
        """Extract all paths from a specification."""
        return set(spec.get("paths", {}).keys())

    def _validate_path(
        self,
        path: str,
        contract_item: dict[str, Any],
        impl_item: dict[str, Any]
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
                    op_errors = self._validate_operation(
                        f"{path}/{method}",
                        contract_item[method],
                        impl_item[method]
                    )
                    errors.extend(op_errors)

        return errors

    def _validate_operation(
        self,
        path: str,
        contract_op: dict[str, Any],
        impl_op: dict[str, Any]
    ) -> list[ContractValidationError]:
        """Validate a single operation."""
        errors: list[ContractValidationError] = []

        # Validate parameters
        if self.config.check_parameters:
            param_errors = self._validate_parameters(
                path,
                contract_op.get("parameters", []),
                impl_op.get("parameters", [])
            )
            errors.extend(param_errors)

        # Validate request body
        if self.config.check_request_body:
            if "requestBody" in contract_op:
                if "requestBody" not in impl_op:
                    errors.append(ContractValidationError(
                        path=f"{path}/requestBody",
                        message="Request body not implemented",
                        severity="error",
                    ))
                else:
                    body_errors = self._validate_request_body(
                        path,
                        contract_op["requestBody"],
                        impl_op["requestBody"]
                    )
                    errors.extend(body_errors)

        # Validate responses
        if self.config.check_response_body:
            resp_errors = self._validate_responses(
                path,
                contract_op.get("responses", {}),
                impl_op.get("responses", {})
            )
            errors.extend(resp_errors)

        return errors

    def _validate_parameters(
        self,
        path: str,
        contract_params: list[dict[str, Any]],
        impl_params: list[dict[str, Any]]
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
                # Check required matches
                if param.get("required", False) and not impl_param.get("required", False):
                    errors.append(ContractValidationError(
                        path=f"{path}/parameters/{name}",
                        message=f"Parameter '{name}' should be required",
                        expected="required=true",
                        actual="required=false",
                        severity="error",
                    ))

        return errors

    def _validate_request_body(
        self,
        path: str,
        contract_body: dict[str, Any],
        impl_body: dict[str, Any]
    ) -> list[ContractValidationError]:
        """Validate request body."""
        errors: list[ContractValidationError] = []

        # Check required
        if contract_body.get("required", False) and not impl_body.get("required", False):
            errors.append(ContractValidationError(
                path=f"{path}/requestBody",
                message="Request body should be required",
                severity="error",
            ))

        # Check content types
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

    def _validate_responses(
        self,
        path: str,
        contract_responses: dict[str, Any],
        impl_responses: dict[str, Any]
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

    def generate_report(
        self,
        result: ContractValidationResult,
        format: str = "text"
    ) -> str:
        """Generate a validation report."""
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: ContractValidationResult) -> str:
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

    def _generate_markdown_report(self, result: ContractValidationResult) -> str:
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
