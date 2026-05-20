"""
Unit tests for _generic_solid_checks — multi-language regex SOLID detection.
"""

import pytest

from Asgard.Bragi.Architecture.services._generic_solid_checks import (
    check_srp_method_count,
    check_isp_interface_size,
    check_dip_concrete_instantiation,
    check_ocp_type_checking,
)
from Asgard.Bragi.Architecture.models.architecture_models import SOLIDPrinciple


# ---------------------------------------------------------------------------
# SRP
# ---------------------------------------------------------------------------

_JAVA_12_METHODS = """
public class OrderService {
    public void createOrder() {}
    public void updateOrder() {}
    public void deleteOrder() {}
    public void fetchOrder() {}
    public void listOrders() {}
    public void cancelOrder() {}
    public void shipOrder() {}
    public void trackOrder() {}
    public void refundOrder() {}
    public void archiveOrder() {}
    public void validateOrder() {}
    public void notifyCustomer() {}
}
"""

_JAVA_3_METHODS = """
public class Greeter {
    public String greet(String name) { return "Hello " + name; }
    public String farewell(String name) { return "Goodbye " + name; }
    public String info() { return "Greeter v1"; }
}
"""


class TestSRPMethodCount:
    def test_java_12_methods_exceeds_threshold(self):
        lines = _JAVA_12_METHODS.splitlines()
        violations = check_srp_method_count("OrderService.java", lines, "java", threshold=10)
        assert len(violations) == 1
        v = violations[0]
        assert v.principle == SOLIDPrinciple.SRP
        assert "12" in v.message

    def test_java_3_methods_no_violation(self):
        lines = _JAVA_3_METHODS.splitlines()
        violations = check_srp_method_count("Greeter.java", lines, "java", threshold=10)
        assert violations == []

    def test_unknown_language_returns_empty(self):
        violations = check_srp_method_count("file.cobol", ["public void foo(){}"], "cobol")
        assert violations == []


# ---------------------------------------------------------------------------
# ISP
# ---------------------------------------------------------------------------

_TS_INTERFACE_8_METHODS = """
interface IOrderRepository {
    findById(id: string): Order;
    findAll(): Order[];
    save(order: Order): void;
    update(order: Order): void;
    delete(id: string): void;
    findByCustomer(customerId: string): Order[];
    findByStatus(status: string): Order[];
    countAll(): number;
}
"""

_TS_INTERFACE_3_METHODS = """
interface IGreeter {
    greet(name: string): string;
    farewell(name: string): string;
    info(): string;
}
"""


class TestISPInterfaceSize:
    def test_ts_8_method_interface_violation(self):
        lines = _TS_INTERFACE_8_METHODS.splitlines()
        violations = check_isp_interface_size("IOrderRepository.ts", lines, "typescript", threshold=7)
        assert len(violations) == 1
        assert violations[0].principle == SOLIDPrinciple.ISP

    def test_ts_3_method_interface_no_violation(self):
        lines = _TS_INTERFACE_3_METHODS.splitlines()
        violations = check_isp_interface_size("IGreeter.ts", lines, "typescript", threshold=7)
        assert violations == []


# ---------------------------------------------------------------------------
# DIP
# ---------------------------------------------------------------------------

_JAVA_WITH_DIP_VIOLATION = """
public class OrderUseCase {
    private final OrderRepository repo = new UserRepository(dataSource);

    public void execute(String id) {
        repo.findById(id);
    }
}
"""

_JAVA_NO_DIP_VIOLATION = """
public class OrderUseCase {
    private final IOrderRepository repo;

    public OrderUseCase(IOrderRepository repo) {
        this.repo = repo;
    }
}
"""


class TestDIPConcreteInstantiation:
    def test_java_new_concrete_repository_violation(self):
        lines = _JAVA_WITH_DIP_VIOLATION.splitlines()
        violations = check_dip_concrete_instantiation("OrderUseCase.java", lines, "java")
        assert len(violations) >= 1
        assert violations[0].principle == SOLIDPrinciple.DIP

    def test_java_constructor_injection_no_violation(self):
        lines = _JAVA_NO_DIP_VIOLATION.splitlines()
        violations = check_dip_concrete_instantiation("OrderUseCase.java", lines, "java")
        assert violations == []


# ---------------------------------------------------------------------------
# OCP
# ---------------------------------------------------------------------------

_JAVA_WITH_INSTANCEOF = """
public class ShapeRenderer {
    public void render(Shape shape) {
        if (shape instanceof Circle) {
            renderCircle((Circle) shape);
        } else if (shape instanceof Square) {
            renderSquare((Square) shape);
        }
    }
}
"""

_JAVA_NO_INSTANCEOF = """
public class ShapeRenderer {
    public void render(Shape shape) {
        shape.draw();
    }
}
"""


class TestOCPTypeChecking:
    def test_java_instanceof_violation(self):
        lines = _JAVA_WITH_INSTANCEOF.splitlines()
        violations = check_ocp_type_checking("ShapeRenderer.java", lines, "java")
        assert len(violations) >= 1
        assert violations[0].principle == SOLIDPrinciple.OCP

    def test_java_polymorphism_no_violation(self):
        lines = _JAVA_NO_INSTANCEOF.splitlines()
        violations = check_ocp_type_checking("ShapeRenderer.java", lines, "java")
        assert violations == []
