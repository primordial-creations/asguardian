"""
Unit tests for _generic_hexagonal_checks — multi-language hexagonal violation detection.
"""

import pytest

from Asgard.Bragi.Architecture.services._generic_hexagonal_checks import (
    check_domain_imports_infrastructure,
    check_missing_port_reference,
)
from Asgard.Bragi.Architecture.models.architecture_models import HexagonalZone


# ---------------------------------------------------------------------------
# Domain imports infrastructure
# ---------------------------------------------------------------------------

_DOMAIN_INFRA_IMPORT = """
package com.example.domain;

import com.myapp.database.UserRepo;
import com.myapp.domain.User;

public class UserDomainService {
    private final UserRepo repo;
}
"""

_DOMAIN_CLEAN_IMPORT = """
package com.example.domain;

import com.myapp.domain.User;
import com.myapp.domain.events.UserCreated;

public class UserDomainService {
}
"""


class TestDomainImportsInfrastructure:
    def test_domain_java_file_importing_database_package_is_violation(self):
        lines = _DOMAIN_INFRA_IMPORT.splitlines()
        # Simulate a path inside a 'domain' directory
        violations = check_domain_imports_infrastructure(
            "com/myapp/domain/UserDomainService.java", lines, "java"
        )
        assert len(violations) >= 1
        v = violations[0]
        assert v.source_zone == HexagonalZone.DOMAIN
        assert v.target_zone == HexagonalZone.INFRASTRUCTURE
        assert "database" in v.message or "UserRepo" in v.message or "database" in v.message

    def test_domain_java_file_clean_imports_no_violation(self):
        lines = _DOMAIN_CLEAN_IMPORT.splitlines()
        violations = check_domain_imports_infrastructure(
            "com/myapp/domain/UserDomainService.java", lines, "java"
        )
        assert violations == []

    def test_non_domain_file_skipped(self):
        lines = _DOMAIN_INFRA_IMPORT.splitlines()
        # File is in 'application' layer, not domain
        violations = check_domain_imports_infrastructure(
            "com/myapp/application/UserAppService.java", lines, "java"
        )
        assert violations == []


# ---------------------------------------------------------------------------
# Adapter missing port reference
# ---------------------------------------------------------------------------

_ADAPTER_WITH_PORT = """
public class JpaOrderAdapter implements IOrderRepository {
    public Order findById(String id) {
        // ...
    }
}
"""

_ADAPTER_WITHOUT_PORT = """
public class JpaOrderAdapter {
    public Order findById(String id) {
        // ...
    }
}
"""


class TestMissingPortReference:
    def test_adapter_implementing_port_interface_no_violation(self):
        lines = _ADAPTER_WITH_PORT.splitlines()
        violations = check_missing_port_reference(
            "com/myapp/adapters/JpaOrderAdapter.java", lines, "java"
        )
        assert violations == []

    def test_adapter_without_port_reference_is_violation(self):
        lines = _ADAPTER_WITHOUT_PORT.splitlines()
        violations = check_missing_port_reference(
            "com/myapp/adapters/JpaOrderAdapter.java", lines, "java"
        )
        assert len(violations) == 1
        v = violations[0]
        assert v.source_zone == HexagonalZone.ADAPTER
        assert v.target_zone == HexagonalZone.PORT

    def test_non_adapter_file_skipped(self):
        lines = _ADAPTER_WITHOUT_PORT.splitlines()
        violations = check_missing_port_reference(
            "com/myapp/services/OrderService.java", lines, "java"
        )
        assert violations == []
