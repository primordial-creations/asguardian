"""
Forseti Contracts Module - API Contract Testing

This module provides comprehensive API contract testing including:
- Contract validation against implementations
- Backward compatibility checking
- Breaking change detection

Usage:
    from Asgard.Forseti.Contracts import CompatibilityCheckerService, ContractConfig

    # Check backward compatibility
    service = CompatibilityCheckerService()
    result = service.check("v1.yaml", "v2.yaml")
    print(f"Compatible: {result.is_compatible}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

# Import models
from Asgard.Forseti.Contracts.models import (
    ContractConfig,
    CompatibilityResult,
    BreakingChange,
    BreakingChangeType,
    CompatibilityLevel,
)

# Import services
from Asgard.Forseti.Contracts.services import (
    ContractValidatorService,
    CompatibilityCheckerService,
    BreakingChangeDetectorService,
)

# Import utilities
from Asgard.Forseti.Contracts.utilities import (
    load_contract_file,
    compare_schemas,
    is_breaking_change,
)

# Live spec-vs-implementation contract testing (plan 06-A). Re-exported here
# so the documented Contracts import surface also covers drift detection;
# the LiveContract package itself never runs probes implicitly.
from Asgard.Forseti.LiveContract import LiveValidatorService, ProbePlannerService

__all__ = [
    # Models
    "ContractConfig",
    "CompatibilityResult",
    "BreakingChange",
    "BreakingChangeType",
    "CompatibilityLevel",
    # Services
    "ContractValidatorService",
    "CompatibilityCheckerService",
    "BreakingChangeDetectorService",
    "LiveValidatorService",
    "ProbePlannerService",
    # Utilities
    "load_contract_file",
    "compare_schemas",
    "is_breaking_change",
]
