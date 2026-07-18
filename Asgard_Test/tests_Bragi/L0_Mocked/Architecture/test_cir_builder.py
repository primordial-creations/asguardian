"""Tests for the CIR (Common Intermediate Representation) pipeline.

Covers ``Asgard/Bragi/Architecture/cir/builder.py`` and
``Asgard/Bragi/Architecture/evaluators/*`` per
``_Docs/Planning/Heimdall/02_SOLID_Detection.md``.
"""
import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.Architecture.cir.builder import build_file_cir
from Asgard.Bragi.Architecture.evaluators import evaluate_file
from Asgard.Bragi.Architecture.evaluators._lcom4 import lcom4, lcom4_components
from Asgard.Bragi.Architecture.models.architecture_models import Confidence, SOLIDPrinciple

pytestmark = pytest.mark.skipif(not is_available("python"), reason="tree-sitter python grammar unavailable")


class TestCIRBuilderPython:
    def test_extracts_class_and_methods(self):
        src = "class Foo:\n    def bar(self):\n        pass\n    def baz(self):\n        pass\n"
        fi = build_file_cir("foo.py", src, "python")
        assert fi is not None
        assert len(fi.classes) == 1
        cls = fi.classes[0]
        assert cls.name == "Foo"
        assert cls.method_count == 2
        assert cls.method_names() == {"bar", "baz"}

    def test_unsupported_language_returns_none(self):
        assert build_file_cir("f.kt", "class Foo", "kotlin") is None

    def test_field_and_method_call_edges_tracked(self):
        src = (
            "class Cohesive:\n"
            "    def a(self):\n"
            "        self.x = 1\n"
            "    def b(self):\n"
            "        return self.x\n"
        )
        fi = build_file_cir("cohesive.py", src, "python")
        cls = fi.classes[0]
        methods = {m.name: m for m in cls.methods}
        assert "x" in methods["a"].field_accesses
        assert "x" in methods["b"].field_accesses


class TestLCOM4Component:
    def test_cohesive_class_lcom4_is_1(self):
        src = (
            "class Cohesive:\n"
            "    def a(self):\n"
            "        self.x = 1\n"
            "    def b(self):\n"
            "        return self.x\n"
        )
        fi = build_file_cir("cohesive.py", src, "python")
        assert lcom4(fi.classes[0]) == 1

    def test_two_island_class_lcom4_is_2(self):
        src = (
            "class TwoIslands:\n"
            "    def a(self):\n"
            "        self.x = 1\n"
            "    def b(self):\n"
            "        return self.x\n"
            "    def c(self):\n"
            "        self.y = 1\n"
            "    def d(self):\n"
            "        return self.y\n"
        )
        fi = build_file_cir("two_islands.py", src, "python")
        assert lcom4(fi.classes[0]) == 2

    def test_delegation_via_method_call_stays_cohesive(self):
        # LCOM3-vs-LCOM4 regression: a helper method only connected via a
        # sibling call (not shared field access) must still count as one
        # component under true LCOM4 (method-call edges included).
        src = (
            "class Delegator:\n"
            "    def a(self):\n"
            "        self.x = 1\n"
            "        self._helper()\n"
            "    def _helper(self):\n"
            "        return 42\n"
        )
        fi = build_file_cir("delegator.py", src, "python")
        assert lcom4(fi.classes[0]) == 1

    def test_adding_disconnected_method_increments_by_one(self):
        base_src = (
            "class Grower:\n"
            "    def a(self):\n"
            "        self.x = 1\n"
            "    def b(self):\n"
            "        return self.x\n"
        )
        grown_src = base_src + "    def isolated(self):\n        self.z = 1\n        return self.z\n"
        fi_base = build_file_cir("grower.py", base_src, "python")
        fi_grown = build_file_cir("grower.py", grown_src, "python")
        assert lcom4(fi_grown.classes[0]) == lcom4(fi_base.classes[0]) + 1


class TestSRPEvaluator:
    def test_god_class_flagged(self):
        methods = "\n".join(
            f"    def method_{i}(self):\n        self.f{i % 3} = {i}\n" for i in range(25)
        )
        src = f"class GodClass:\n{methods}"
        fi = build_file_cir("god.py", src, "python")
        violations = evaluate_file(fi)
        srp = [v for v in violations if v.principle == SOLIDPrinciple.SRP]
        assert len(srp) == 1
        assert srp[0].confidence == Confidence.MEDIUM

    def test_small_class_not_flagged(self):
        src = "class Small:\n    def a(self): pass\n    def b(self): pass\n"
        fi = build_file_cir("small.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.SRP]


class TestOCPEvaluator:
    def test_isinstance_chain_flagged(self):
        src = (
            "class Renderer:\n"
            "    def render(self, shape):\n"
            "        if isinstance(shape, Circle):\n"
            "            pass\n"
            "        elif isinstance(shape, Square):\n"
            "            pass\n"
        )
        fi = build_file_cir("ocp.py", src, "python")
        assert [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.OCP]

    def test_polymorphic_dispatch_not_flagged(self):
        src = "class Renderer:\n    def render(self, shape):\n        shape.draw()\n"
        fi = build_file_cir("ocp_clean.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.OCP]


class TestLSPEvaluator:
    def test_refused_bequest_flagged(self):
        src = (
            "class Base:\n"
            "    def process(self):\n"
            "        pass\n"
            "class Impl(Base):\n"
            "    def process(self):\n"
            "        raise NotImplementedError()\n"
        )
        fi = build_file_cir("lsp.py", src, "python")
        lsp = [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.LSP]
        assert len(lsp) == 1
        assert lsp[0].confidence == Confidence.HIGH

    def test_full_override_not_flagged(self):
        src = (
            "class Base:\n"
            "    def process(self):\n"
            "        pass\n"
            "class Impl(Base):\n"
            "    def process(self):\n"
            "        return 42\n"
        )
        fi = build_file_cir("lsp_clean.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.LSP]


class TestISPEvaluator:
    def test_fat_abstract_class_flagged(self):
        methods = "\n".join(f"    @abstractmethod\n    def method_{i}(self): ..." for i in range(13))
        src = f"from abc import ABC, abstractmethod\nclass Fat(ABC):\n{methods}\n"
        fi = build_file_cir("isp.py", src, "python")
        assert [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.ISP]

    def test_lean_interface_not_flagged(self):
        src = (
            "from abc import ABC, abstractmethod\n"
            "class Lean(ABC):\n"
            "    @abstractmethod\n    def read(self): ...\n"
            "    @abstractmethod\n    def close(self): ...\n"
        )
        fi = build_file_cir("isp_clean.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.ISP]

    def test_stubbed_implementer_flagged(self):
        src = (
            "class Base:\n"
            "    def a(self): pass\n"
            "    def b(self): pass\n"
            "class Impl(Base):\n"
            "    def a(self):\n"
            "        raise NotImplementedError()\n"
            "    def b(self):\n"
            "        raise NotImplementedError()\n"
        )
        fi = build_file_cir("stub.py", src, "python")
        isp = [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.ISP]
        assert isp
        assert isp[0].confidence == Confidence.HIGH


class TestDIPEvaluator:
    def test_concrete_instantiation_flagged(self):
        src = (
            "class UserService:\n"
            "    def __init__(self):\n"
            "        self.repo = UserRepository()\n"
            "    def get(self, id):\n"
            "        return self.repo.find(id)\n"
        )
        fi = build_file_cir("dip.py", src, "python")
        dip = [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.DIP]
        assert dip
        assert dip[0].confidence == Confidence.HIGH

    def test_injected_dependency_not_flagged(self):
        src = (
            "class UserService:\n"
            "    def __init__(self, repo):\n"
            "        self.repo = repo\n"
            "    def get(self, id):\n"
            "        return self.repo.find(id)\n"
        )
        fi = build_file_cir("dip_clean.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.DIP]

    def test_factory_class_suppressed(self):
        src = (
            "class UserServiceFactory:\n"
            "    def create(self):\n"
            "        return UserRepository()\n"
        )
        fi = build_file_cir("factory.py", src, "python")
        assert not [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.DIP]


class TestCrossLanguageConsistency:
    def test_java_and_python_god_class_both_flagged(self):
        if not is_available("java"):
            pytest.skip("tree-sitter java grammar unavailable")

        py_methods = "\n".join(f"    def method_{i}(self):\n        self.f{i % 3} = {i}\n" for i in range(25))
        py_src = f"class GodClass:\n{py_methods}"
        py_fi = build_file_cir("god.py", py_src, "python")

        java_methods = "\n".join(
            f"    public void method{i}() {{ this.f{i % 3} = {i}; }}" for i in range(25)
        )
        java_src = f"class GodClass {{\n    int f0, f1, f2;\n{java_methods}\n}}\n"
        java_fi = build_file_cir("GodClass.java", java_src, "java")

        py_srp = [v for v in evaluate_file(py_fi) if v.principle == SOLIDPrinciple.SRP]
        java_srp = [v for v in evaluate_file(java_fi) if v.principle == SOLIDPrinciple.SRP]
        assert py_srp and java_srp


class TestExtendedLanguageHandlers:
    """Plan 02 gap: extend ``_LANG_HANDLERS`` beyond python/java/js/ts to
    go, csharp, ruby, php, rust, cpp."""

    def test_go_struct_and_receiver_methods(self):
        if not is_available("go"):
            pytest.skip("tree-sitter go grammar unavailable")
        src = (
            "package main\n"
            "type Dog struct { Name string }\n"
            "func (d *Dog) Speak() string { return d.Name }\n"
            "func (d *Dog) Empty() {}\n"
        )
        fi = build_file_cir("dog.go", src, "go")
        assert fi is not None
        cls = next(c for c in fi.classes if c.name == "Dog")
        assert cls.fields == {"Name"}
        assert cls.method_names() == {"Speak", "Empty"}
        speak = next(m for m in cls.methods if m.name == "Speak")
        assert speak.field_accesses == {"Name"}
        empty = next(m for m in cls.methods if m.name == "Empty")
        assert empty.is_empty

    def test_csharp_class_with_base_list(self):
        if not is_available("csharp"):
            pytest.skip("tree-sitter csharp grammar unavailable")
        src = (
            "public class Dog : Animal {\n"
            "    private string name;\n"
            "    public string Speak() { return this.name; }\n"
            "    public void Empty() {}\n"
            "}\n"
        )
        fi = build_file_cir("Dog.cs", src, "csharp")
        assert fi is not None
        cls = fi.classes[0]
        assert cls.name == "Dog"
        assert cls.implements == {"Animal"}
        assert cls.method_names() == {"Speak", "Empty"}

    def test_ruby_class_with_instance_variables(self):
        if not is_available("ruby"):
            pytest.skip("tree-sitter ruby grammar unavailable")
        src = "class Dog < Animal\n  def speak\n    @name\n  end\n  def empty_method\n  end\nend\n"
        fi = build_file_cir("dog.rb", src, "ruby")
        assert fi is not None
        cls = next(c for c in fi.classes if c.name == "Dog")
        assert cls.fields == {"name"}
        assert cls.implements == {"Animal"}

    def test_php_class_with_implements(self):
        if not is_available("php"):
            pytest.skip("tree-sitter php grammar unavailable")
        src = (
            "<?php\n"
            "class Dog extends Animal implements Speakable {\n"
            "    private $name;\n"
            "    public function speak() { return $this->name; }\n"
            "    public function emptyMethod() {}\n"
            "}\n"
        )
        fi = build_file_cir("Dog.php", src, "php")
        assert fi is not None
        cls = fi.classes[0]
        assert cls.name == "Dog"
        assert cls.implements == {"Animal", "Speakable"}
        assert cls.fields == {"name"}

    def test_rust_struct_with_impl_block(self):
        if not is_available("rust"):
            pytest.skip("tree-sitter rust grammar unavailable")
        src = (
            "struct Dog { name: String }\n"
            "impl Dog {\n"
            "    fn speak(&self) -> String { self.name.clone() }\n"
            "    fn empty_method(&self) {}\n"
            "}\n"
        )
        fi = build_file_cir("dog.rs", src, "rust")
        assert fi is not None
        cls = next(c for c in fi.classes if c.name == "Dog")
        assert cls.fields == {"name"}
        assert cls.method_names() == {"speak", "empty_method"}

    def test_cpp_class_with_base_clause(self):
        if not is_available("cpp"):
            pytest.skip("tree-sitter cpp grammar unavailable")
        src = (
            "class Dog : public Animal {\n"
            "public:\n"
            "    std::string name;\n"
            "    std::string speak() { return this->name; }\n"
            "    void empty_method() {}\n"
            "};\n"
        )
        fi = build_file_cir("dog.cpp", src, "cpp")
        assert fi is not None
        cls = fi.classes[0]
        assert cls.name == "Dog"
        assert cls.implements == {"Animal"}
        assert cls.method_names() == {"speak", "empty_method"}

    def test_all_six_new_languages_are_registered(self):
        from Asgard.Bragi.Architecture.cir.builder import _LANG_HANDLERS
        for lang in ("go", "csharp", "ruby", "php", "rust", "cpp"):
            assert lang in _LANG_HANDLERS


class TestTypeSwitchCounting:
    """Plan 02 gap: OCP HIGH-confidence path requires ``type_switches`` to
    be populated by the builder, not left at the zero default."""

    def test_python_elif_isinstance_chain_counted(self):
        src = (
            "class Renderer:\n"
            "    def render(self, shape):\n"
            "        if isinstance(shape, Circle):\n"
            "            pass\n"
            "        elif isinstance(shape, Square):\n"
            "            pass\n"
            "        elif isinstance(shape, Triangle):\n"
            "            pass\n"
        )
        fi = build_file_cir("shapes.py", src, "python")
        method = fi.classes[0].methods[0]
        assert method.type_switches == 3

    def test_java_switch_on_typeof_style_counted(self):
        if not is_available("java"):
            pytest.skip("tree-sitter java grammar unavailable")
        src = (
            "class Renderer {\n"
            "    void render(Object shape) {\n"
            "        if (shape instanceof Circle) {}\n"
            "        else if (shape instanceof Square) {}\n"
            "        else if (shape instanceof Triangle) {}\n"
            "    }\n"
            "}\n"
        )
        fi = build_file_cir("Renderer.java", src, "java")
        method = fi.classes[0].methods[0]
        assert method.type_switches == 3

    def test_ocp_high_confidence_on_3plus_branches(self):
        src = (
            "class Renderer:\n"
            "    def render(self, shape):\n"
            "        if isinstance(shape, Circle):\n"
            "            pass\n"
            "        elif isinstance(shape, Square):\n"
            "            pass\n"
            "        elif isinstance(shape, Triangle):\n"
            "            pass\n"
        )
        fi = build_file_cir("shapes.py", src, "python")
        violations = [v for v in evaluate_file(fi) if v.principle == SOLIDPrinciple.OCP]
        assert violations and violations[0].confidence == Confidence.HIGH
