"""
Tests for Heimdall Plan 03 — import-graph layer inference CSP, drift-paradox
detection, module-level cycles, and incremental updates.
"""
import os
import random

import pytest

from Asgard.Bragi.Architecture.graph.drift import detect_drift
from Asgard.Bragi.Architecture.graph.module_cycles import detect_module_cycles, module_id
from Asgard.Bragi.Architecture.graph.nodes import LevelBounds
from Asgard.Bragi.Architecture.graph.propagation import infer_levels, infer_levels_incremental
from Asgard.Bragi.Architecture.graph.service import ArchGraphService
from Asgard.Bragi.Architecture.services._architecture_config import (
    LayerConfig,
    ArchitectureConfig as LayerArchitectureConfig,
    RulesConfig,
    default_architecture_config,
    load_architecture_config,
)
from Asgard.Bragi.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Bragi.Dependencies.services.graph_service import DependencyGraphService


@pytest.fixture(autouse=True)
def _no_disk_cache(monkeypatch):
    # Read-only-target safety + deterministic tests: never touch disk cache.
    monkeypatch.setenv("ASGARD_NO_CACHE", "1")


def _write_project(root, files: dict):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


CLEAN_PROJECT = {
    "domain/__init__.py": "",
    "domain/order.py": "class Order:\n    pass\n",
    "services/__init__.py": "",
    "services/order_service.py": "from domain.order import Order\n\nclass OrderService:\n    pass\n",
    "infrastructure/__init__.py": "",
    "infrastructure/order_repo.py": (
        "from services.order_service import OrderService\n"
        "from domain.order import Order\n\n"
        "class OrderRepository:\n    pass\n"
    ),
}

DRIFTED_PROJECT = {
    **CLEAN_PROJECT,
    "domain/drifted.py": "import sqlalchemy\n\nclass Drifted:\n    pass\n",
}


def _arch_service(scan_path):
    cfg = default_architecture_config()
    return ArchGraphService(config=cfg, dep_config=DependencyConfig(scan_path=scan_path))


class TestLayerInferenceCSP:
    def test_assigns_matched_layers_with_full_confidence(self, tmp_path):
        _write_project(tmp_path, CLEAN_PROJECT)
        service = _arch_service(tmp_path)
        bounds = service.infer(tmp_path)

        assert bounds["domain.order"].assigned_level == 0
        assert bounds["services.order_service"].assigned_level == 1
        assert bounds["infrastructure.order_repo"].assigned_level == 2
        assert bounds["domain.order"].confidence(2) == 1.0

    def test_no_level_inference_without_level_config(self, tmp_path):
        _write_project(tmp_path, CLEAN_PROJECT)
        no_level_cfg = LayerArchitectureConfig(
            language="python",
            layers=[LayerConfig(name="domain", path_patterns=["*/domain/*"],
                                 allowed_imports=[], forbidden_imports=[])],
        )
        assert no_level_cfg.has_level_inference is False
        service = ArchGraphService(config=no_level_cfg, dep_config=DependencyConfig(scan_path=tmp_path))
        assert service.infer(tmp_path) == {}

    def test_unmatched_file_gets_default_bounds(self, tmp_path):
        _write_project(tmp_path, CLEAN_PROJECT)
        _write_project(tmp_path, {"utils/helper.py": "def f(): pass\n", "utils/__init__.py": ""})
        service = _arch_service(tmp_path)
        bounds = service.infer(tmp_path)
        helper = bounds["utils.helper"]
        assert helper.matched is False
        assert helper.min_level == 0

    def test_ioc_zero_violations(self, tmp_path):
        """Interface in domain implemented in infrastructure (Impl level 2 ->
        interface level 0) must NOT be flagged: 2 >= 0 satisfies the
        universal invariant Level(A) >= Level(B)."""
        _write_project(tmp_path, CLEAN_PROJECT)
        service = _arch_service(tmp_path)
        bounds = service.infer(tmp_path)
        graph = service.graph_service.build(tmp_path)
        for src, deps in graph.graph.items():
            src_level = bounds[src].assigned_level
            for dst in deps:
                dst_level = bounds[dst].assigned_level
                assert src_level >= dst_level, f"{src}({src_level}) -> {dst}({dst_level})"

    def test_convergence_on_random_dags(self):
        """Propagation reaches fixpoint without oscillation on random DAGs."""
        from Asgard.Bragi.Dependencies.models.dependency_models import ModuleDependencies

        random.seed(42)
        for _ in range(5):
            n = 12
            names = [f"pkg.mod{i}" for i in range(n)]
            modules = []
            graph_edges = {name: set() for name in names}
            for i, name in enumerate(names):
                # Only edges to higher-indexed nodes -> guaranteed DAG.
                possible = names[i + 1:]
                targets = set(random.sample(possible, k=min(len(possible), random.randint(0, 2))))
                graph_edges[name] = targets

            class FakeGraph:
                pass

            fg = FakeGraph()
            fg.graph = graph_edges
            fg.modules = []
            fg.by_name = {n: True for n in names}
            fg.reverse = {n: set() for n in names}
            for src, deps in graph_edges.items():
                for dst in deps:
                    fg.reverse[dst].add(src)

            cfg = default_architecture_config()
            bounds = infer_levels(fg, cfg, {}, {})
            # Fixpoint reached: re-running propagation changes nothing.
            bounds2 = infer_levels(fg, cfg, {}, {})
            for name in names:
                assert bounds[name].min_level == bounds2[name].min_level
                assert bounds[name].max_level == bounds2[name].max_level


class TestDriftDetection:
    def test_drift_paradox_detected_with_pin_explanation(self, tmp_path):
        _write_project(tmp_path, DRIFTED_PROJECT)
        service = _arch_service(tmp_path)
        violations = service.drift_violations(tmp_path)
        assert any(v.module == "domain.drifted" for v in violations)
        v = next(v for v in violations if v.module == "domain.drifted")
        assert v.intrinsic_level == 0
        assert v.effective_level == 2
        assert any("sqlalchemy" in p for p in v.pinned_by)

    def test_clean_project_has_no_drift(self, tmp_path):
        _write_project(tmp_path, CLEAN_PROJECT)
        service = _arch_service(tmp_path)
        assert service.drift_violations(tmp_path) == []

    def test_explain_reports_drift(self, tmp_path):
        _write_project(tmp_path, DRIFTED_PROJECT)
        service = _arch_service(tmp_path)
        explanation = service.explain(str(tmp_path / "domain" / "drifted.py"), tmp_path)
        assert "ARCHITECTURE DRIFT" in explanation
        assert "sqlalchemy" in explanation


class TestModuleCycles:
    def test_file_level_cycle_absent_module_level_present(self, tmp_path):
        """Two files in the SAME directory importing each other is benign
        (no module cycle); two DIRECTORIES importing each other through
        different files IS a module-level cycle."""
        _write_project(tmp_path, {
            "pkg_a/__init__.py": "",
            "pkg_a/one.py": "from pkg_b.two import Two\n\nclass One:\n    pass\n",
            "pkg_b/__init__.py": "",
            "pkg_b/two.py": "from pkg_a.one import One\n\nclass Two:\n    pass\n",
        })
        dep_config = DependencyConfig(scan_path=tmp_path)
        gs = DependencyGraphService(dep_config)
        graph = gs.build(tmp_path)
        cycles = detect_module_cycles(graph)
        assert len(cycles) == 1
        assert set(cycles[0].members) == {"pkg_a", "pkg_b"}

    def test_same_directory_mutual_recursion_is_not_a_module_cycle(self, tmp_path):
        _write_project(tmp_path, {
            "pkg/__init__.py": "",
            "pkg/one.py": "from pkg.two import Two\n\nclass One:\n    pass\n",
            "pkg/two.py": "from pkg.one import One\n\nclass Two:\n    pass\n",
        })
        dep_config = DependencyConfig(scan_path=tmp_path)
        gs = DependencyGraphService(dep_config)
        graph = gs.build(tmp_path)
        cycles = detect_module_cycles(graph)
        assert cycles == []

    def test_module_id_collapses_to_directory(self):
        assert module_id("pkg_a.one") == "pkg_a"
        assert module_id("top_level") == ""


class TestIncrementalEquivalence:
    def test_incremental_matches_full_rebuild_after_edit(self, tmp_path):
        _write_project(tmp_path, CLEAN_PROJECT)
        cfg = default_architecture_config()
        dep_config = DependencyConfig(scan_path=tmp_path)

        gs1 = DependencyGraphService(dep_config)
        graph1 = gs1.build(tmp_path)
        class_names1 = {m.module_name: set() for m in graph1.modules}
        raw1 = {m.module_name: set() for m in graph1.modules}
        full_bounds = infer_levels(graph1, cfg, class_names1, raw1)

        # Edit one file (does not change its layer classification) and
        # recompute both ways.
        (tmp_path / "services" / "order_service.py").write_text(
            "from domain.order import Order\n\nclass OrderService:\n    # edited\n    pass\n"
        )

        gs2 = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        graph2 = gs2.build(tmp_path)
        class_names2 = {m.module_name: set() for m in graph2.modules}
        raw2 = {m.module_name: set() for m in graph2.modules}

        rebuilt = infer_levels(graph2, cfg, class_names2, raw2)
        incremental = infer_levels_incremental(
            graph2, cfg, {"services.order_service"}, full_bounds, class_names2, raw2,
        )

        assert set(rebuilt) == set(incremental)
        for module in rebuilt:
            assert rebuilt[module].min_level == incremental[module].min_level, module
            assert rebuilt[module].max_level == incremental[module].max_level, module

    def test_arch_graph_service_disk_cache_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)
        _write_project(tmp_path, CLEAN_PROJECT)
        cfg = default_architecture_config()
        service = ArchGraphService(config=cfg, dep_config=DependencyConfig(scan_path=tmp_path))
        first = service.infer(tmp_path)
        assert (tmp_path / ".asgard_cache" / "bragi_arch_bounds.json").exists()

        # Fresh service instance simulating a second run; cache should be
        # reused/updated without error and produce identical bounds.
        service2 = ArchGraphService(config=cfg, dep_config=DependencyConfig(scan_path=tmp_path))
        second = service2.infer(tmp_path)
        assert set(first) == set(second)
        for module in first:
            assert first[module].min_level == second[module].min_level
            assert first[module].max_level == second[module].max_level


class TestFanOutAndBackwardCompatibility:
    def test_fan_out_violation_reported(self, tmp_path):
        # Fan-out is counted per distinct TARGET MODULE (directory), so each
        # imported package must live in its own directory.
        files = {"hub/__init__.py": ""}
        hub_imports = []
        for i in range(15):
            files[f"domain{i}/__init__.py"] = ""
            files[f"domain{i}/mod.py"] = f"class M{i}:\n    pass\n"
            hub_imports.append(f"from domain{i}.mod import M{i}")
        files["hub/hub.py"] = "\n".join(hub_imports) + "\n\nclass Hub:\n    pass\n"
        _write_project(tmp_path, files)

        cfg = LayerArchitectureConfig(
            language="python",
            layers=[
                LayerConfig(name="domain", path_patterns=["*/domain/*"],
                            allowed_imports=[], forbidden_imports=[], level=0),
                LayerConfig(name="hub", path_patterns=["*/hub/*"],
                            allowed_imports=["domain"], forbidden_imports=[], level=1),
            ],
            rules=RulesConfig(max_module_fan_out=3, detect_module_cycles=True),
        )
        service = ArchGraphService(config=cfg, dep_config=DependencyConfig(scan_path=tmp_path))
        violations = service.fan_out_violations(tmp_path)
        assert any(v.module == "hub" for v in violations)

    def test_old_schema_yaml_still_loads_without_level(self, tmp_path):
        yaml_content = (
            "language: python\n"
            "layers:\n"
            "  - name: core\n"
            "    path_patterns: [\"*/core/*\"]\n"
            "    allowed_imports: []\n"
            "    forbidden_imports: [infra]\n"
            "  - name: infra\n"
            "    path_patterns: [\"*/infra/*\"]\n"
            "    allowed_imports: [core]\n"
            "    forbidden_imports: []\n"
        )
        config_file = tmp_path / "architecture.yml"
        config_file.write_text(yaml_content)
        cfg = load_architecture_config(str(config_file))
        assert cfg.has_level_inference is False
        assert cfg.layers[0].path_patterns == ["*/core/*"]

    def test_new_schema_with_rules_and_heuristics_parses(self, tmp_path):
        yaml_content = (
            "language: python\n"
            "layers:\n"
            "  - name: domain\n"
            "    level: 0\n"
            "    heuristics:\n"
            "      paths: [\"*/domain/*\"]\n"
            "      suffixes: [\"Entity\"]\n"
            "    allowed_imports: []\n"
            "    forbidden_imports: [infra]\n"
            "  - name: infra\n"
            "    level: 1\n"
            "    heuristics:\n"
            "      paths: [\"*/infra/*\"]\n"
            "      external_imports: [\"sqlalchemy\"]\n"
            "    allowed_imports: [domain]\n"
            "    forbidden_imports: []\n"
            "rules:\n"
            "  max_module_fan_out: 5\n"
            "  detect_module_cycles: false\n"
        )
        config_file = tmp_path / "architecture.yml"
        config_file.write_text(yaml_content)
        cfg = load_architecture_config(str(config_file))
        assert cfg.has_level_inference is True
        domain = next(l for l in cfg.layers if l.name == "domain")
        assert domain.level == 0
        assert domain.path_patterns == ["*/domain/*"]
        assert domain.suffixes == ["Entity"]
        infra = next(l for l in cfg.layers if l.name == "infra")
        assert infra.external_imports == ["sqlalchemy"]
        assert cfg.rules.max_module_fan_out == 5
        assert cfg.rules.detect_module_cycles is False


class TestHexagonalAnalyzerIntegration:
    def test_analyze_reports_layer_and_drift_violations_from_inferred_levels(self, tmp_path):
        from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
        from Asgard.Bragi.Architecture.models.architecture_models import ArchitectureConfig

        _write_project(tmp_path, DRIFTED_PROJECT)
        layer_cfg = default_architecture_config()
        analyzer = HexagonalAnalyzer(
            ArchitectureConfig(scan_path=tmp_path), layer_config=layer_cfg,
        )
        report = analyzer.analyze(tmp_path)
        messages = [v.message for v in report.violations]
        assert any("Architecture drift" in m for m in messages)

    def test_explain_file_returns_bounds_explanation(self, tmp_path):
        from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
        from Asgard.Bragi.Architecture.models.architecture_models import ArchitectureConfig

        _write_project(tmp_path, CLEAN_PROJECT)
        layer_cfg = default_architecture_config()
        analyzer = HexagonalAnalyzer(
            ArchitectureConfig(scan_path=tmp_path), layer_config=layer_cfg,
        )
        explanation = analyzer.explain_file(str(tmp_path / "domain" / "order.py"), tmp_path)
        assert "Module: domain.order" in explanation
        assert "Assigned level: 0" in explanation
