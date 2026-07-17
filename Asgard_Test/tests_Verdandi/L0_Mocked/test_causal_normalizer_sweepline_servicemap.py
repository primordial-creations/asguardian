"""
L0 regression tests for Verdandi Plan 08 (Tracing & APM):

- Causal trace normalization (orphan adoption, clock-skew correction, async
  truncation) — Asgard/Verdandi/Tracing/services/causal_normalizer.py
- Sweep-line "latest-finisher" critical path — additive strategy on
  Asgard/Verdandi/Tracing/services/critical_path_analyzer.py
- Service-map hardening (identity resolution, messaging virtual nodes,
  pruning/ghost edges, ego view, centrality) — Asgard/Verdandi/APM/

Each test encodes a worked example from
_Docs/Planning/Verdandi/08_Tracing_APM.md "Testing Notes".
"""

from typing import List, Optional

import pytest

from Asgard.Verdandi.Tracing.models.tracing_models import (
    AnalysisOutcome,
    ConfidenceFlag,
    DistributedTrace,
    TraceSpan,
)
from Asgard.Verdandi.Tracing.services.causal_normalizer import (
    adopt_orphans,
    correct_clock_skew,
    normalize_trace,
    truncate_async,
)
from Asgard.Verdandi.Tracing.services.critical_path_analyzer import CriticalPathAnalyzer

from Asgard.Verdandi.APM.models.apm_models import (
    Span,
    SpanKind,
    SpanStatus,
)
from Asgard.Verdandi.APM.services._identity_resolver import (
    AliasRegistry,
    canonicalize_lexical,
    resolve_identity,
)
from Asgard.Verdandi.APM.services.service_map_builder import ServiceMapBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tspan(
    span_id: str,
    start_ms: float,
    end_ms: float,
    parent_id: Optional[str] = None,
    service_name: str = "svc",
    kind: str = "INTERNAL",
    trace_id: str = "trace-1",
) -> TraceSpan:
    start_ns = int(start_ms * 1e6)
    end_ns = int(end_ms * 1e6)
    return TraceSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_id,
        operation_name=f"op-{span_id}",
        service_name=service_name,
        start_time_unix_nano=start_ns,
        end_time_unix_nano=end_ns,
        duration_ms=end_ms - start_ms,
        kind=kind,
    )


def _dtrace(spans: List[TraceSpan], trace_id: str = "trace-1") -> DistributedTrace:
    root = next((s for s in spans if s.parent_span_id is None), None)
    starts = [s.start_time_unix_nano for s in spans]
    ends = [s.end_time_unix_nano for s in spans]
    return DistributedTrace(
        trace_id=trace_id,
        spans=spans,
        root_span=root,
        total_duration_ms=(max(ends) - min(starts)) / 1e6 if spans else 0.0,
        span_count=len(spans),
    )


def _pspan(
    span_id: str,
    parent_id: Optional[str],
    service_name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict] = None,
    has_error: bool = False,
    duration_ms: float = 10.0,
) -> Span:
    from datetime import datetime, timedelta

    start = datetime(2026, 1, 1)
    return Span(
        trace_id="t1",
        span_id=span_id,
        parent_span_id=parent_id,
        operation_name="op",
        service_name=service_name,
        kind=kind,
        start_time=start,
        end_time=start + timedelta(milliseconds=duration_ms),
        duration_ms=duration_ms,
        status=SpanStatus.ERROR if has_error else SpanStatus.OK,
        attributes=attributes or {},
    )


# ---------------------------------------------------------------------------
# L0 skew
# ---------------------------------------------------------------------------


class TestClockSkewCorrection:
    def test_skew_offset_shifts_server_and_flags_when_negative_transit(self):
        # client: 0-100ms; server reports start=-20ms, end=70ms (duration 90ms)
        # transit = (100 - 90) / 2 = 5ms; offset = (0 + 5) - (-20) = 25ms
        client = _tspan("client", 0, 100, parent_id=None, service_name="a", kind="CLIENT")
        server = _tspan(
            "server", -20, 70, parent_id="client", service_name="b", kind="SERVER"
        )
        updated, flags = correct_clock_skew([client, server])
        by_id = {s.span_id: s for s in updated}

        offset_ms = (
            by_id["server"].start_time_unix_nano - server.start_time_unix_nano
        ) / 1e6
        assert offset_ms == pytest.approx(25.0, abs=0.01)
        # shifted start must be >= client start: no negative-edge causality violation
        assert by_id["server"].start_time_unix_nano >= client.start_time_unix_nano

    def test_negative_transit_flags_heavy_skew(self):
        # server slower than client's observed round trip -> transit < 0
        client = _tspan("client", 0, 50, parent_id=None, service_name="a", kind="CLIENT")
        server = _tspan(
            "server", 0, 200, parent_id="client", service_name="b", kind="SERVER"
        )
        _, flags = correct_clock_skew([client, server])
        assert ConfidenceFlag.HEAVY_CLOCK_SKEW_ADJUSTED in flags

    def test_descendants_shifted_with_server_span(self):
        client = _tspan("client", 0, 100, parent_id=None, service_name="a", kind="CLIENT")
        server = _tspan(
            "server", -20, 70, parent_id="client", service_name="b", kind="SERVER"
        )
        grandchild = _tspan("gc", -10, 40, parent_id="server", service_name="b")
        updated, _ = correct_clock_skew([client, server, grandchild])
        by_id = {s.span_id: s for s in updated}
        server_offset = by_id["server"].start_time_unix_nano - server.start_time_unix_nano
        gc_offset = by_id["gc"].start_time_unix_nano - grandchild.start_time_unix_nano
        assert server_offset == gc_offset != 0

    def test_same_service_pair_not_treated_as_cross_host(self):
        client = _tspan("client", 0, 100, parent_id=None, service_name="a", kind="CLIENT")
        server = _tspan(
            "server", -20, 70, parent_id="client", service_name="a", kind="SERVER"
        )
        updated, flags = correct_clock_skew([client, server])
        by_id = {s.span_id: s for s in updated}
        assert by_id["server"].start_time_unix_nano == server.start_time_unix_nano
        assert flags == []


# ---------------------------------------------------------------------------
# L0 truncation
# ---------------------------------------------------------------------------


class TestAsyncTruncation:
    def test_async_child_truncated_to_parent_effective_end(self):
        parent = _tspan("p", 0, 50, parent_id=None)
        async_child = _tspan("c", 10, 5000, parent_id="p")
        updated, flags = truncate_async([parent, async_child])
        by_id = {s.span_id: s for s in updated}
        assert by_id["c"].effective_end_ns == by_id["p"].effective_end_ns == 50 * 1_000_000
        assert ConfidenceFlag.SEVERE_ASYNC_TRUNCATION in flags

    def test_child_within_parent_window_untruncated(self):
        parent = _tspan("p", 0, 50, parent_id=None)
        child = _tspan("c", 5, 20, parent_id="p")
        updated, flags = truncate_async([parent, child])
        by_id = {s.span_id: s for s in updated}
        assert by_id["c"].effective_end_ns == 20 * 1_000_000
        assert ConfidenceFlag.SEVERE_ASYNC_TRUNCATION not in flags


# ---------------------------------------------------------------------------
# L0 orphan adoption
# ---------------------------------------------------------------------------


class TestOrphanAdoption:
    def test_orphan_adopted_by_tightest_bounding_ancestor(self):
        root = _tspan("root", 0, 1000, parent_id=None)
        mid = _tspan("mid", 100, 500, parent_id="root")
        # orphan's parent_span_id points at an unknown id, but its window
        # [start,end] is fully bounded by `mid`, not just `root`.
        orphan = _tspan("orphan", 150, 300, parent_id="does-not-exist")
        updated, flags = adopt_orphans([root, mid, orphan])
        by_id = {s.span_id: s for s in updated}
        assert by_id["orphan"].parent_span_id == "mid"
        assert ConfidenceFlag.ORPHANED_SUBTREE_RECOVERED in flags

    def test_orphan_falls_back_to_root_when_no_bounding_span(self):
        root = _tspan("root", 0, 1000, parent_id=None)
        orphan = _tspan("orphan", 2000, 2100, parent_id="missing")
        updated, flags = adopt_orphans([root, orphan])
        by_id = {s.span_id: s for s in updated}
        assert by_id["orphan"].parent_span_id == "root"
        assert ConfidenceFlag.ORPHANED_SUBTREE_RECOVERED in flags


# ---------------------------------------------------------------------------
# L0 sweep-line parallel + conservation invariant
# ---------------------------------------------------------------------------


class TestSweepLineCriticalPath:
    def test_three_overlapping_children_conservation_invariant(self):
        # parent 0-50; children 0-30 / 0-40 / 5-45 under parent 0-50
        parent = _tspan("p", 0, 50, parent_id=None)
        c1 = _tspan("c1", 0, 30, parent_id="p")
        c2 = _tspan("c2", 0, 40, parent_id="p")
        c3 = _tspan("c3", 5, 45, parent_id="p")
        trace = _dtrace([parent, c1, c2, c3])

        analyzer = CriticalPathAnalyzer(min_contribution_percent=0.0)
        result = analyzer.analyze_sweepline(trace, apply_causal_normalization=False)

        assert result.strategy == "sweepline"
        assert result.outcome == AnalysisOutcome.OK
        total_credited_ms = sum(seg.contribution_ms for seg in result.segments)
        # Conservation invariant: total credited == parent duration exactly.
        assert total_credited_ms == pytest.approx(50.0, abs=1e-6)

    def test_legacy_strategy_default_unchanged(self):
        """analyze() with no strategy arg must keep legacy behavior/signature."""
        parent = _tspan("p", 0, 50, parent_id=None)
        child = _tspan("c", 0, 30, parent_id="p")
        trace = _dtrace([parent, child])
        analyzer = CriticalPathAnalyzer()
        result = analyzer.analyze(trace)
        assert result.strategy == "legacy"
        assert result.total_duration_ms == pytest.approx(50.0)

    def test_sweepline_strategy_via_analyze_dispatch(self):
        parent = _tspan("p", 0, 50, parent_id=None)
        child = _tspan("c", 0, 30, parent_id="p")
        trace = _dtrace([parent, child])
        analyzer = CriticalPathAnalyzer()
        result = analyzer.analyze(trace, strategy="sweepline")
        assert result.strategy == "sweepline"


# ---------------------------------------------------------------------------
# L0 dark matter
# ---------------------------------------------------------------------------


class TestDarkMatterUnattributedTime:
    def test_parent_500ms_children_sum_100ms_flags_high_unattributed(self):
        parent = _tspan("p", 0, 500, parent_id=None)
        c1 = _tspan("c1", 0, 60, parent_id="p")
        c2 = _tspan("c2", 100, 140, parent_id="p")
        trace = _dtrace([parent, c1, c2])

        analyzer = CriticalPathAnalyzer(min_contribution_percent=0.0)
        result = analyzer.analyze_sweepline(trace, apply_causal_normalization=False)

        assert ConfidenceFlag.HIGH_UNATTRIBUTED_TIME in result.flags
        parent_segment = next(s for s in result.segments if s.span.span_id == "p")
        assert parent_segment.contribution_ms == pytest.approx(400.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Full pipeline / INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


class TestNormalizeTracePipeline:
    def test_empty_trace_is_insufficient_data(self):
        trace = DistributedTrace(trace_id="empty")
        analyzer = CriticalPathAnalyzer()
        result = analyzer.analyze_sweepline(trace)
        assert result.outcome == AnalysisOutcome.INSUFFICIENT_DATA

    def test_full_pipeline_runs_all_three_passes(self):
        client = _tspan("client", 0, 100, parent_id=None, service_name="a", kind="CLIENT")
        server = _tspan(
            "server", -20, 70, parent_id="client", service_name="b", kind="SERVER"
        )
        orphan = _tspan("orphan", 1, 2, parent_id="missing", service_name="b")
        trace = _dtrace([client, server, orphan])
        normalized, flags, assumptions = normalize_trace(trace)
        assert len(assumptions) == 3
        by_id = {s.span_id: s for s in normalized.spans}
        assert by_id["orphan"].parent_span_id in ("client", "server")
        assert ConfidenceFlag.ORPHANED_SUBTREE_RECOVERED in flags


# ---------------------------------------------------------------------------
# L0 identity
# ---------------------------------------------------------------------------


class TestIdentityResolution:
    def test_payment_service_and_payment_service_camel_canonicalize_same(self):
        assert canonicalize_lexical("Payment_Service") == "payment-service"
        assert canonicalize_lexical("paymentService") == "payment-service"

    def test_payment_api_and_payment_worker_not_merged(self):
        assert canonicalize_lexical("payment-api") != canonicalize_lexical("payment-worker")

    def test_no_version_merging(self):
        assert canonicalize_lexical("payment-service-v2") != canonicalize_lexical(
            "payment-service"
        )

    def test_composite_key_uses_namespace_and_env_when_present(self):
        identity = resolve_identity(
            "paymentService",
            {"k8s.namespace.name": "prod", "deployment.environment.name": "prod-us"},
        )
        assert identity.composite_key == "prod-us:prod:payment-service"

    def test_lexical_only_when_no_resource_attrs(self):
        identity = resolve_identity("paymentService", {})
        assert identity.composite_key == "payment-service"

    def test_alias_registry_suggest_merges_does_not_auto_merge(self):
        builder = ServiceMapBuilder()
        spans = [
            _pspan("s1", None, "payment-api"),
            _pspan("s2", "s1", "inventory"),
            _pspan("s3", None, "payment-worker"),
        ]
        smap = builder.build_from_spans(spans)
        registry = AliasRegistry()
        suggestions = registry.suggest_merges(smap)
        suggested_names = {name for pair in suggestions for name in pair}
        assert "payment-api" not in suggested_names or "payment-worker" not in suggested_names
        # Registry never applies anything on its own.
        assert registry.resolve("payment-api") == "payment-api"

    def test_alias_registry_dict_in_dict_out(self):
        registry = AliasRegistry({"paymentsvc": "payment-service"})
        assert registry.resolve("paymentsvc") == "payment-service"
        registry.register("pay-svc", "payment-service")
        assert registry.to_dict()["pay-svc"] == "payment-service"


# ---------------------------------------------------------------------------
# L0 map
# ---------------------------------------------------------------------------


class TestServiceMapHardening:
    def test_producer_consumer_yields_virtual_node_and_async_edges(self):
        builder = ServiceMapBuilder()
        spans = [
            _pspan(
                "p1",
                None,
                "order-service",
                kind=SpanKind.PRODUCER,
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination.name": "orders",
                },
            ),
            _pspan(
                "c1",
                None,
                "billing-service",
                kind=SpanKind.CONSUMER,
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination.name": "orders",
                },
            ),
        ]
        nodes, edges = builder.build_messaging_view(spans)
        assert len(nodes) == 1
        assert nodes[0].key == "kafka:orders"
        edge_pairs = {(e.source_service, e.target_service) for e in edges}
        assert ("order-service", "kafka:orders") in edge_pairs
        assert ("kafka:orders", "billing-service") in edge_pairs
        assert all(e.is_async for e in edges)

    def test_generated_destination_names_are_parameterized(self):
        builder = ServiceMapBuilder()
        spans = [
            _pspan(
                "p1",
                None,
                "svc",
                kind=SpanKind.PRODUCER,
                attributes={
                    "messaging.system": "rabbitmq",
                    "messaging.destination.name": "amq.gen-abc123XYZ",
                },
            ),
        ]
        nodes, _ = builder.build_messaging_view(spans)
        assert nodes[0].destination == "<generated>"

    def test_low_traffic_edge_hidden_but_same_edge_with_error_visible(self):
        builder = ServiceMapBuilder()
        # 2000 clean calls a->b, plus 1 low-traffic call a->c (0.05% share)
        spans = [_pspan("root", None, "a")]
        for i in range(2000):
            spans.append(_pspan(f"ab{i}", "root", "b"))
        spans.append(_pspan("ac0", "root", "c"))

        smap = builder.build_from_spans(spans)
        pruned = builder.prune(smap, min_traffic_share=0.001, keep_if_errors=True)
        pruned_pairs = {(d.source_service, d.target_service) for d in pruned.dependencies}
        assert ("a", "c") not in pruned_pairs  # ~0.05% share, no errors -> hidden

        # Same edge but with 1 error -> stays visible even at tiny traffic share.
        spans_with_error = list(spans)
        spans_with_error.append(_pspan("ac_err", "root", "c", has_error=True))
        smap_err = builder.build_from_spans(spans_with_error)
        pruned_err = builder.prune(smap_err, min_traffic_share=0.001, keep_if_errors=True)
        pruned_err_pairs = {
            (d.source_service, d.target_service) for d in pruned_err.dependencies
        }
        assert ("a", "c") in pruned_err_pairs

    def test_ghost_edges_marks_present_before_absent_now(self):
        builder = ServiceMapBuilder()
        previous_spans = [_pspan("root", None, "a"), _pspan("s1", "root", "b")]
        current_spans = [_pspan("root2", None, "a")]  # a->b no longer occurs
        previous_map = builder.build_from_spans(previous_spans)
        current_map = builder.build_from_spans(current_spans)
        result = builder.ghost_edges(current_map, previous_map)
        ghost = next(d for d in result.dependencies if d.source_service == "a")
        assert ghost.ghost is True
        assert ghost.call_count == 0

    def test_ego_subgraph_respects_hop_limits(self):
        builder = ServiceMapBuilder()
        spans = [
            _pspan("s1", None, "a"),
            _pspan("s2", "s1", "b"),
            _pspan("s3", "s2", "c"),
            _pspan("s4", "s3", "d"),
        ]
        smap = builder.build_from_spans(spans)
        ego = builder.ego_subgraph(smap, "b", upstream_hops=1, downstream_hops=2)
        assert set(ego.services) == {"a", "b", "c", "d"}
        # 3 hops downstream from b would be too far given downstream_hops=2
        ego_tight = builder.ego_subgraph(smap, "a", upstream_hops=0, downstream_hops=1)
        assert "c" not in ego_tight.services

    def test_centrality_returns_normalized_scores_for_all_services(self):
        builder = ServiceMapBuilder()
        spans = [
            _pspan("s1", None, "a"),
            _pspan("s2", "s1", "b"),
            _pspan("s3", "s1", "c"),
            _pspan("s4", "s2", "c"),
        ]
        smap = builder.build_from_spans(spans)
        scores = builder.centrality(smap)
        assert set(scores.keys()) == set(smap.services)
        assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)
        # "c" receives inbound weight from both a and b -> should rank highest
        assert scores["c"] == max(scores.values())

    def test_centrality_empty_map_returns_empty_dict(self):
        builder = ServiceMapBuilder()
        from Asgard.Verdandi.APM.models.apm_models import ServiceMap

        assert builder.centrality(ServiceMap()) == {}
