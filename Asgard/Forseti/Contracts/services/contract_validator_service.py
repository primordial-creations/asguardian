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
from Asgard.Forseti.Contracts.services._contract_validator_helpers import (
    generate_markdown_report,
    generate_text_report,
    validate_path,
)


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

        contract_paths = self._extract_paths(contract)
        impl_paths = self._extract_paths(implementation)

        for path in contract_paths:
            if path not in impl_paths:
                errors.append(ContractValidationError(
                    path=path,
                    message=f"Contract path not implemented: {path}",
                    severity="error",
                ))

        for path in contract_paths:
            if path in impl_paths:
                path_errors = validate_path(
                    path,
                    contract.get("paths", {}).get(path, {}),
                    implementation.get("paths", {}).get(path, {}),
                    self.config.check_parameters,
                    self.config.check_request_body,
                    self.config.check_response_body,
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

    def generate_report(
        self,
        result: ContractValidationResult,
        format: str = "text"
    ) -> str:
        """Generate a validation report."""
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
