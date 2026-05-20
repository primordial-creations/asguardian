"""
Tests for Tree-sitter-based SOLID checks.

All tests that exercise tree-sitter queries are skipped when the python
binding is not installed, so the suite remains green in CI environments
without tree-sitter.
"""

import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.Architecture.services._treesitter_solid_checks import (
    check_srp_lcom4,
    check_isp_fat_interface,
    check_dip_concrete_dependency,
    check_ocp_type_dispatch,
)

_ALL_RULES = {
    "solid.srp-lcom4": True,
    "solid.isp-fat-interface": True,
    "solid.dip-concrete-dependency": True,
    "solid.ocp-type-dispatch": True,
}

_SKIP_NO_PYTHON = pytest.mark.skipif(
    not is_available("python"),
    reason="tree-sitter-python not installed",
)


# ---------------------------------------------------------------------------
# SRP — LCOM4
# ---------------------------------------------------------------------------

_COHESIVE_CLASS = """
class Calculator:
    def __init__(self):
        self.value = 0

    def add(self, x):
        self.value += x
        return self.value

    def subtract(self, x):
        self.value -= x
        return self.value
"""

_SPLIT_CLASS = """
class MixedClass:
    def __init__(self):
        self.db = None
        self.email = None

    def save_record(self):
        return self.db

    def send_notification(self):
        return self.email
"""


@_SKIP_NO_PYTHON
def test_lcom4_cohesive_class_no_violation():
    results = check_srp_lcom4("<test>", _COHESIVE_CLASS, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.srp-lcom4" not in rule_ids


@_SKIP_NO_PYTHON
def test_lcom4_disconnected_class_flagged():
    results = check_srp_lcom4("<test>", _SPLIT_CLASS, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.srp-lcom4" in rule_ids


@_SKIP_NO_PYTHON
def test_lcom4_rule_disabled_skips_check():
    rules = dict(_ALL_RULES)
    rules["solid.srp-lcom4"] = False
    results = check_srp_lcom4("<test>", _SPLIT_CLASS, "python", rules)
    assert results == []


# ---------------------------------------------------------------------------
# ISP — Fat interface
# ---------------------------------------------------------------------------

_LEAN_ABC = """
from abc import ABC, abstractmethod

class SmallInterface(ABC):
    @abstractmethod
    def read(self): ...

    @abstractmethod
    def write(self): ...
"""

_FAT_ABC = """
from abc import ABC, abstractmethod

class FatInterface(ABC):
    @abstractmethod
    def method_a(self): ...
    @abstractmethod
    def method_b(self): ...
    @abstractmethod
    def method_c(self): ...
    @abstractmethod
    def method_d(self): ...
    @abstractmethod
    def method_e(self): ...
    @abstractmethod
    def method_f(self): ...
    @abstractmethod
    def method_g(self): ...
    @abstractmethod
    def method_h(self): ...
    @abstractmethod
    def method_i(self): ...
    @abstractmethod
    def method_j(self): ...
    @abstractmethod
    def method_k(self): ...
    @abstractmethod
    def method_l(self): ...
    @abstractmethod
    def method_m(self): ...
"""


@_SKIP_NO_PYTHON
def test_isp_lean_abstract_class_no_violation():
    results = check_isp_fat_interface("<test>", _LEAN_ABC, "python", _ALL_RULES)
    assert all(r["rule_id"] != "solid.isp-fat-interface" for r in results)


@_SKIP_NO_PYTHON
def test_isp_fat_abstract_class_flagged():
    results = check_isp_fat_interface("<test>", _FAT_ABC, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.isp-fat-interface" in rule_ids


@_SKIP_NO_PYTHON
def test_isp_rule_disabled_skips_check():
    rules = dict(_ALL_RULES)
    rules["solid.isp-fat-interface"] = False
    results = check_isp_fat_interface("<test>", _FAT_ABC, "python", rules)
    assert results == []


# ---------------------------------------------------------------------------
# DIP — Concrete instantiation
# ---------------------------------------------------------------------------

_NO_CONCRETE = """
class MyService:
    def __init__(self, repo):
        self.repo = repo

    def do_work(self):
        return self.repo.fetch()
"""

_CONCRETE_INSTANTIATION = """
class OrderController:
    def __init__(self):
        self.repo = OrderRepository()
        self.svc = PaymentService()
"""

_FACTORY_WITH_CONCRETE = """
class OrderFactory:
    def create(self):
        return OrderRepository()
"""


@_SKIP_NO_PYTHON
def test_dip_no_concrete_no_violation():
    results = check_dip_concrete_dependency("<test>", _NO_CONCRETE, "python", _ALL_RULES)
    assert all(r["rule_id"] != "solid.dip-concrete-dependency" for r in results)


@_SKIP_NO_PYTHON
def test_dip_concrete_instantiation_flagged():
    results = check_dip_concrete_dependency("<test>", _CONCRETE_INSTANTIATION, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.dip-concrete-dependency" in rule_ids


@_SKIP_NO_PYTHON
def test_dip_factory_class_suppressed():
    results = check_dip_concrete_dependency("<test>", _FACTORY_WITH_CONCRETE, "python", _ALL_RULES)
    assert all(r["rule_id"] != "solid.dip-concrete-dependency" for r in results)


@_SKIP_NO_PYTHON
def test_dip_rule_disabled_skips_check():
    rules = dict(_ALL_RULES)
    rules["solid.dip-concrete-dependency"] = False
    results = check_dip_concrete_dependency("<test>", _CONCRETE_INSTANTIATION, "python", rules)
    assert results == []


# ---------------------------------------------------------------------------
# OCP — Type dispatch
# ---------------------------------------------------------------------------

_POLYMORPHIC = """
class Renderer:
    def render(self, shape):
        return shape.draw()
"""

_TYPE_DISPATCH = """
class Renderer:
    def render(self, shape):
        if isinstance(shape, Circle):
            return shape.draw_circle()
        elif isinstance(shape, Square):
            return shape.draw_square()
"""

_TYPE_CHECK = """
def process(obj):
    if type(obj) == int:
        return obj + 1
    return obj
"""


@_SKIP_NO_PYTHON
def test_ocp_polymorphic_no_violation():
    results = check_ocp_type_dispatch("<test>", _POLYMORPHIC, "python", _ALL_RULES)
    assert all(r["rule_id"] != "solid.ocp-type-dispatch" for r in results)


@_SKIP_NO_PYTHON
def test_ocp_isinstance_flagged():
    results = check_ocp_type_dispatch("<test>", _TYPE_DISPATCH, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.ocp-type-dispatch" in rule_ids


@_SKIP_NO_PYTHON
def test_ocp_type_equality_check_flagged():
    results = check_ocp_type_dispatch("<test>", _TYPE_CHECK, "python", _ALL_RULES)
    rule_ids = [r["rule_id"] for r in results]
    assert "solid.ocp-type-dispatch" in rule_ids


@_SKIP_NO_PYTHON
def test_ocp_rule_disabled_skips_check():
    rules = dict(_ALL_RULES)
    rules["solid.ocp-type-dispatch"] = False
    results = check_ocp_type_dispatch("<test>", _TYPE_DISPATCH, "python", rules)
    assert results == []


# ---------------------------------------------------------------------------
# Fallback: unsupported language returns list (no exception)
# ---------------------------------------------------------------------------

def test_unsupported_language_returns_list():
    results = check_srp_lcom4("<test>", "fn main() {}", "rust", _ALL_RULES)
    assert isinstance(results, list)

    results = check_isp_fat_interface("<test>", "fn main() {}", "rust", _ALL_RULES)
    assert isinstance(results, list)

    results = check_dip_concrete_dependency("<test>", "fn main() {}", "rust", _ALL_RULES)
    assert isinstance(results, list)

    results = check_ocp_type_dispatch("<test>", "fn main() {}", "rust", _ALL_RULES)
    assert isinstance(results, list)
