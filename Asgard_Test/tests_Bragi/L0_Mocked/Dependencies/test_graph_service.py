"""
Tests for DependencyGraphService (Plan 03 Phase B).

Covers: single-scan graph building, SCC condensation with reach-based
severity, weighted break suggestions, centrality percentiles, the
CentralityProvider feed into the debt Exposure Factor, and the
interface-hash cache property (body edit retains derived cache; export
change invalidates it).
"""

import time
from pathlib import Path

import pytest

from Asgard.Bragi.Dependencies.models.dependency_models import (
    DependencyConfig,
    DependencySeverity,
)
from Asgard.Bragi.Dependencies.services.cycle_detector import CycleDetector
from Asgard.Bragi.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Bragi.Dependencies.services.graph_service import (
    DependencyGraphService,
    interface_hash,
)


def write(root: Path, name: str, content: str) -> None:
    (root / name).write_text(content)


def make_cycle_repo(root: Path) -> None:
    """a -> b -> c -> a plus a leaf module d importing a."""
    write(root, "a.py", "import b\n\ndef fa():\n    return 1\n")
    write(root, "b.py", "import c\n\ndef fb():\n    return 2\n")
    write(root, "c.py", "import a\n\ndef fc():\n    return 3\n")
    write(root, "d.py", "import a\n\ndef fd():\n    return 4\n")


class TestBuildAndCache:
    def test_build_returns_graph_with_internal_edges(self, tmp_path):
        make_cycle_repo(tmp_path)
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        graph = service.build(tmp_path)
        assert graph.graph["a"] == {"b"}
        assert graph.graph["d"] == {"a"}
        assert "a" in graph.reverse and graph.reverse["a"] == {"c", "d"}

    def test_build_is_memoized_per_path(self, tmp_path):
        make_cycle_repo(tmp_path)
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        assert service.build(tmp_path) is service.build(tmp_path)

    def test_disk_cache_written_under_asgard_cache(self, tmp_path):
        make_cycle_repo(tmp_path)
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        service.build(tmp_path)
        assert (tmp_path / ".asgard_cache" / "bragi_dep_graph.json").exists()

    def test_body_edit_keeps_derived_cache(self, tmp_path):
        """RESEARCH_15 property: body-only edit does not invalidate dependents."""
        make_cycle_repo(tmp_path)
        DependencyGraphService(DependencyConfig(scan_path=tmp_path)).build(tmp_path)

        # Edit the BODY of a function in b.py (exports and imports unchanged).
        write(tmp_path, "b.py", "import c\n\ndef fb():\n    return 2 + 40\n")
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        service.build(tmp_path)
        assert service.derived_cache_hit is True
        # The other three files came straight from the content cache.
        assert service.last_file_cache_hits == 3

    def test_export_change_invalidates_derived_cache(self, tmp_path):
        make_cycle_repo(tmp_path)
        DependencyGraphService(DependencyConfig(scan_path=tmp_path)).build(tmp_path)

        # Add an export to b.py: interface hash changes -> derived invalidated.
        write(tmp_path, "b.py", "import c\n\ndef fb():\n    return 2\n\ndef fb2():\n    return 9\n")
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        service.build(tmp_path)
        assert service.derived_cache_hit is False

    def test_interface_hash_ignores_order(self):
        assert interface_hash(["a", "b"], ["x", "y"]) == interface_hash(
            ["b", "a"], ["y", "x"])
        assert interface_hash(["a"], ["x"]) != interface_hash(["a", "b"], ["x"])

    def test_deterministic_across_instances(self, tmp_path):
        make_cycle_repo(tmp_path)
        s1 = DependencyGraphService(DependencyConfig(scan_path=tmp_path),
                                    use_disk_cache=False)
        s2 = DependencyGraphService(DependencyConfig(scan_path=tmp_path),
                                    use_disk_cache=False)
        c1 = s1.centrality(tmp_path)
        c2 = s2.centrality(tmp_path)
        assert {k: v.__dict__ for k, v in c1.items()} == \
               {k: v.__dict__ for k, v in c2.items()}


class TestSCCs:
    def test_finds_three_node_cycle(self, tmp_path):
        make_cycle_repo(tmp_path)
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        sccs = service.sccs(tmp_path)
        assert len(sccs) == 1
        assert sccs[0].members == ["a", "b", "c"]
        assert sccs[0].external_afferent == 1  # d -> a

    def test_severity_follows_reach_not_length(self, tmp_path):
        """A 2-cycle with many dependents outranks a long leaf cycle."""
        # 2-cycle between heavily-imported modules.
        write(tmp_path, "core.py", "import util\n\ndef c():\n    pass\n")
        write(tmp_path, "util.py", "import core\n\ndef u():\n    pass\n")
        for i in range(10):
            write(tmp_path, f"user{i}.py", "import core\n")
        # 3-cycle between leaf helpers nobody imports.
        write(tmp_path, "x.py", "import y\n")
        write(tmp_path, "y.py", "import z\n")
        write(tmp_path, "z.py", "import x\n")
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        sccs = {tuple(s.members): s for s in service.sccs(tmp_path)}
        two_cycle = sccs[("core", "util")]
        leaf_cycle = sccs[("x", "y", "z")]
        assert two_cycle.severity == DependencySeverity.CRITICAL
        assert leaf_cycle.severity == DependencySeverity.MODERATE

    def test_dense_scc_bounded_time(self, tmp_path):
        """50-node dense SCC: SCC path returns quickly (no simple_cycles blowup)."""
        n = 50
        for i in range(n):
            # Each node imports the next 3 (mod n): densely cyclic.
            imports = "\n".join(f"import m{(i + k) % n}" for k in (1, 2, 3))
            write(tmp_path, f"m{i}.py", imports + "\n")
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        start = time.monotonic()
        sccs = service.sccs(tmp_path)
        detector = CycleDetector(DependencyConfig(scan_path=tmp_path),
                                 graph_service=service)
        cycles = detector.detect(tmp_path)
        elapsed = time.monotonic() - start
        assert elapsed < 10.0  # generous CI bound; simple_cycles would explode
        assert len(sccs) == 1 and sccs[0].size == n
        # Large SCC reported as one component, not enumerated.
        assert len(cycles) == 1 and len(cycles[0].cycle) == n


class TestBreakSuggestions:
    def test_targets_min_weight_edge_not_min_out_degree(self, tmp_path):
        """
        Cycle a <-> b. Edge a->b imports 3 symbols; edge b->a imports 1.
        The old heuristic (source with fewest dependencies) is indifferent;
        the weighted engine must suggest breaking the 1-symbol edge b->a.
        """
        write(tmp_path, "a.py",
              "from b import f1, f2, f3\n\ndef ga():\n    pass\n")
        write(tmp_path, "b.py",
              "from a import ga\n\ndef f1():\n    pass\ndef f2():\n    pass\ndef f3():\n    pass\n")
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        scc = service.sccs(tmp_path)[0]
        breaks = service.break_suggestions(scc, tmp_path)
        assert breaks, "expected at least one break suggestion"
        assert (breaks[0].source, breaks[0].target) == ("b", "a")
        assert breaks[0].symbol_count == 1

    def test_cycle_detector_suggest_breaks_api_preserved(self, tmp_path):
        make_cycle_repo(tmp_path)
        detector = CycleDetector(DependencyConfig(scan_path=tmp_path))
        suggestions = detector.suggest_breaks(tmp_path)
        assert suggestions
        assert {"source", "target", "reason", "cycle"} <= set(suggestions[0])


class TestCentrality:
    def test_afferent_percentile_ranks_by_ca(self, tmp_path):
        make_cycle_repo(tmp_path)  # Ca: a=2, b=1, c=1, d=0
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        centrality = service.centrality(tmp_path)
        assert centrality["a"].afferent == 2
        assert centrality["d"].afferent == 0
        assert centrality["a"].afferent_percentile == 0.75  # 3 of 4 below
        assert centrality["d"].afferent_percentile == 0.0
        assert 0.0 <= centrality["a"].pagerank <= 1.0

    def test_centrality_provider_maps_module_and_paths(self, tmp_path):
        make_cycle_repo(tmp_path)
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        provider = service.centrality_provider(tmp_path)
        assert provider("a") == 0.75
        assert provider(str(tmp_path / "a.py")) == 0.75
        assert provider("a.py") == 0.75
        assert provider("no/such/module.py") is None

    def test_provider_wires_into_debt_analyzer(self, tmp_path):
        from Asgard.Bragi.Quality.services.technical_debt_analyzer import (
            TechnicalDebtAnalyzer,
        )
        make_cycle_repo(tmp_path)
        analyzer = TechnicalDebtAnalyzer()
        analyzer.use_dependency_graph(tmp_path)
        assert analyzer.centrality_provider is not None
        assert analyzer.aggregator.centrality_provider is analyzer.centrality_provider
        assert analyzer.centrality_provider("a") == 0.75


class TestSingleScanIntegration:
    def test_dependency_analyzer_uses_one_shared_graph(self, tmp_path):
        make_cycle_repo(tmp_path)
        analyzer = DependencyAnalyzer(DependencyConfig(scan_path=tmp_path))
        report = analyzer.analyze(tmp_path)
        # cycles + modularity + centrality all present from one scan
        assert report.has_cycles
        assert report.modularity.total_modules == 4
        assert report.centrality["a"].afferent_percentile == 0.75
        # the memoized graph is shared by all consumers
        assert analyzer.cycle_detector.graph_service is analyzer.graph_service
        assert analyzer.modularity_analyzer.graph_service is analyzer.graph_service


class TestImportFrequencies:
    def test_counts_import_sites_per_target(self, tmp_path):
        make_cycle_repo(tmp_path)  # a imported by c and d; b by a; c by b
        service = DependencyGraphService(DependencyConfig(scan_path=tmp_path))
        freq = service.import_frequencies(tmp_path)
        assert freq["a"] == 2
        assert freq["b"] == 1
        assert list(freq) == sorted(freq)  # deterministic ordering
