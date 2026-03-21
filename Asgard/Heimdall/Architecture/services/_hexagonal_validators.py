"""
Heimdall Hexagonal Architecture Validation Helpers

Re-export shim: all public symbols are now split across
_hexagonal_detectors and _hexagonal_rule_checks.
"""

from Asgard.Heimdall.Architecture.services._hexagonal_detectors import (
    detect_adapters,
    detect_ports,
    infer_port_direction,
)
from Asgard.Heimdall.Architecture.services._hexagonal_rule_checks import (
    detect_cross_adapter_imports,
    validate_dependency_direction,
    validate_domain_isolation,
)

__all__ = [
    "infer_port_direction",
    "detect_ports",
    "detect_adapters",
    "validate_domain_isolation",
    "validate_dependency_direction",
    "detect_cross_adapter_imports",
]
