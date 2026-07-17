"""
Service Map Builder Service

Builds service dependency maps from distributed traces.
"""

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Verdandi.APM.models.apm_models import (
    ServiceDependency,
    ServiceIdentity,
    ServiceMap,
    Span,
    Trace,
    VirtualNode,
)
from Asgard.Verdandi.APM.services._graph_helpers import (
    calculate_service_depth,
    detect_cycles,
    get_downstream_services,
    get_upstream_services,
    percentile,
)
from Asgard.Verdandi.APM.services._identity_resolver import (
    AliasRegistry,
    resolve_identity,
)

# Generated/high-cardinality messaging destination names to collapse to a
# single placeholder so they don't blow up node cardinality (amq.gen-*
# broker-generated queue names, UUID-like segments).
_GENERATED_DESTINATION_RE = re.compile(
    r"^amq\.gen-.+$"
    r"|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _normalize_destination(destination: str) -> str:
    """Collapse generated/UUID-like messaging destination names."""
    if _GENERATED_DESTINATION_RE.match(destination):
        return "<generated>"
    return destination


class ServiceMapBuilder:
    """
    Builder for service dependency maps.

    Analyzes traces to identify service relationships and builds
    a dependency graph showing how services interact.

    Example:
        builder = ServiceMapBuilder()
        service_map = builder.build(traces)
        for dep in service_map.dependencies:
            print(f"{dep.source_service} -> {dep.target_service}")
    """

    def __init__(self):
        """Initialize the service map builder."""
        pass

    def build(
        self,
        traces: Sequence[Trace],
    ) -> ServiceMap:
        """
        Build a service dependency map from traces.

        Args:
            traces: List of traces to analyze

        Returns:
            ServiceMap with services and their dependencies
        """
        if not traces:
            return ServiceMap()

        all_spans: List[Span] = []
        for trace in traces:
            all_spans.extend(trace.spans)

        return self.build_from_spans(all_spans)

    def build_from_spans(
        self,
        spans: Sequence[Span],
    ) -> ServiceMap:
        """
        Build a service dependency map directly from spans.

        Args:
            spans: List of spans to analyze

        Returns:
            ServiceMap with services and their dependencies
        """
        if not spans:
            return ServiceMap()

        span_lookup: Dict[str, Span] = {}
        for span in spans:
            span_lookup[span.span_id] = span

        services: Set[str] = set()
        for span in spans:
            services.add(span.service_name)

        dependency_stats: Dict[Tuple[str, str], Dict] = {}

        for span in spans:
            if span.parent_span_id and span.parent_span_id in span_lookup:
                parent_span = span_lookup[span.parent_span_id]

                if parent_span.service_name != span.service_name:
                    key = (parent_span.service_name, span.service_name)

                    if key not in dependency_stats:
                        dependency_stats[key] = {
                            "call_count": 0,
                            "error_count": 0,
                            "latencies": [],
                        }

                    dependency_stats[key]["call_count"] += 1
                    if span.has_error:
                        dependency_stats[key]["error_count"] += 1
                    dependency_stats[key]["latencies"].append(span.duration_ms)

        dependencies = []
        for (source, target), stats in dependency_stats.items():
            latencies = stats["latencies"]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            p99_latency = percentile(sorted(latencies), 99) if latencies else 0.0

            dependencies.append(
                ServiceDependency(
                    source_service=source,
                    target_service=target,
                    call_count=stats["call_count"],
                    error_count=stats["error_count"],
                    avg_latency_ms=avg_latency,
                    p99_latency_ms=p99_latency,
                )
            )

        callers = set(d.source_service for d in dependencies)
        callees = set(d.target_service for d in dependencies)

        root_services = list(services - callees)
        leaf_services = list(services - callers)

        return ServiceMap(
            services=sorted(list(services)),
            dependencies=dependencies,
            root_services=sorted(root_services),
            leaf_services=sorted(leaf_services),
            edge_count=len(dependencies),
            service_count=len(services),
        )

    def find_critical_path(
        self,
        trace: Trace,
    ) -> List[Span]:
        """
        Find the critical path in a trace.

        The critical path is the sequence of spans that contribute most
        to the total trace duration.

        Args:
            trace: The trace to analyze

        Returns:
            List of spans forming the critical path
        """
        if not trace.spans:
            return []

        span_lookup: Dict[str, Span] = {}
        children: Dict[str, List[Span]] = {}

        for span in trace.spans:
            span_lookup[span.span_id] = span
            parent_id = span.parent_span_id or ""
            if parent_id not in children:
                children[parent_id] = []
            children[parent_id].append(span)

        root_span = trace.root_span
        if root_span is None:
            for span in trace.spans:
                if span.parent_span_id is None:
                    root_span = span
                    break

        if root_span is None:
            return []

        critical_path = [root_span]
        current_span = root_span

        while current_span.span_id in children:
            child_spans = children[current_span.span_id]
            if not child_spans:
                break

            longest_child = max(child_spans, key=lambda s: s.duration_ms)
            critical_path.append(longest_child)
            current_span = longest_child

        return critical_path

    def detect_cycles(
        self,
        service_map: ServiceMap,
    ) -> List[List[str]]:
        """
        Detect cycles in the service dependency graph.

        Args:
            service_map: The service map to analyze

        Returns:
            List of cycles (each cycle is a list of service names)
        """
        return detect_cycles(service_map)

    def get_downstream_services(
        self,
        service_map: ServiceMap,
        service_name: str,
    ) -> Set[str]:
        """
        Get all services that depend on the given service (downstream).

        Args:
            service_map: The service map to analyze
            service_name: The service to find dependents for

        Returns:
            Set of service names that are downstream
        """
        return get_downstream_services(service_map, service_name)

    def get_upstream_services(
        self,
        service_map: ServiceMap,
        service_name: str,
    ) -> Set[str]:
        """
        Get all services that the given service depends on (upstream).

        Args:
            service_map: The service map to analyze
            service_name: The service to find dependencies for

        Returns:
            Set of service names that are upstream
        """
        return get_upstream_services(service_map, service_name)

    def calculate_service_depth(
        self,
        service_map: ServiceMap,
    ) -> Dict[str, int]:
        """
        Calculate the depth of each service in the call hierarchy.

        Root services have depth 0, their direct callees have depth 1, etc.

        Args:
            service_map: The service map to analyze

        Returns:
            Dictionary mapping service name to depth
        """
        return calculate_service_depth(service_map)

    def build_with_identity(
        self,
        spans: Sequence[Span],
        alias_registry: Optional[AliasRegistry] = None,
    ) -> ServiceMap:
        """
        Build a service map with identity resolution applied to raw span
        service names before graph construction (DEEPTHINK_10).

        Composite key `env:namespace:canonical_name` is used when spans
        carry resource attrs (`k8s.namespace.name`, deployment env);
        otherwise lexical canonicalization only. No suffix stripping, no
        version merging. An optional `alias_registry` applies operator-
        approved merges on top of the resolved canonical names.

        Args:
            spans: Spans to analyze
            alias_registry: Optional operator-approved alias registry

        Returns:
            ServiceMap with `identities` populated (raw_name -> ServiceIdentity)
        """
        span_list = list(spans)
        if not span_list:
            return ServiceMap()

        identities: Dict[str, ServiceIdentity] = {}
        canonical_by_raw: Dict[str, str] = {}
        for span in span_list:
            if span.service_name in canonical_by_raw:
                continue
            identity = resolve_identity(span.service_name, span.attributes)
            canonical = identity.canonical_name
            if alias_registry is not None:
                canonical = alias_registry.resolve(canonical)
            canonical_by_raw[span.service_name] = canonical
            identities[span.service_name] = identity

        remapped_spans = [
            span.model_copy(update={"service_name": canonical_by_raw[span.service_name]})
            for span in span_list
        ]
        base_map = self.build_from_spans(remapped_spans)
        return base_map.model_copy(update={"identities": identities})

    def build_messaging_view(
        self,
        spans: Sequence[Span],
    ) -> Tuple[List[VirtualNode], List[ServiceDependency]]:
        """
        Derive messaging virtual nodes and async edges from PRODUCER/
        CONSUMER spans carrying `messaging.system` / `messaging.destination.name`
        attributes (DEEPTHINK_10). A producer span yields
        `service -> [system:destination]`; a consumer span yields
        `[system:destination] -> service`. Both edges are `is_async=True`
        (rendered dashed). Generated/UUID-like destination names are
        parameterized to `<generated>` to prevent cardinality explosion.

        Args:
            spans: Spans to analyze

        Returns:
            (virtual_nodes, async_edges) — VirtualNode list and
            ServiceDependency list (is_async=True) connecting services to
            virtual nodes.
        """
        nodes: Dict[str, VirtualNode] = {}
        edge_stats: Dict[Tuple[str, str], Dict[str, int]] = {}

        for span in spans:
            kind = getattr(span, "kind", None)
            kind_value = getattr(kind, "value", kind)
            kind_str = str(kind_value).lower() if kind_value is not None else ""
            if kind_str not in ("producer", "consumer"):
                continue

            system = span.attributes.get("messaging.system")
            destination = span.attributes.get(
                "messaging.destination.name", span.attributes.get("messaging.destination")
            )
            if not system or not destination:
                continue

            dest_norm = _normalize_destination(str(destination))
            node_key = f"{system}:{dest_norm}"
            if node_key not in nodes:
                nodes[node_key] = VirtualNode(
                    key=node_key, system=str(system), destination=dest_norm
                )

            if kind_str == "producer":
                edge_key = (span.service_name, node_key)
            else:
                edge_key = (node_key, span.service_name)

            stats = edge_stats.setdefault(edge_key, {"calls": 0, "errors": 0})
            stats["calls"] += 1
            if span.has_error:
                stats["errors"] += 1

        edges = [
            ServiceDependency(
                source_service=source,
                target_service=target,
                call_count=stats["calls"],
                error_count=stats["errors"],
                is_async=True,
            )
            for (source, target), stats in edge_stats.items()
        ]
        return list(nodes.values()), edges

    def prune(
        self,
        service_map: ServiceMap,
        min_traffic_share: float = 0.001,
        keep_if_errors: bool = True,
    ) -> ServiceMap:
        """
        Return a new ServiceMap with low-traffic edges removed
        (DEEPTHINK_10 threshold pruning). An edge is kept if its share of
        total call volume is >= `min_traffic_share`, OR (when
        `keep_if_errors`) it has any errors regardless of volume — a
        0.05%-traffic edge with 1 error stays visible even though the same
        edge with 0 errors would be hidden.

        Args:
            service_map: The service map to prune
            min_traffic_share: Minimum fraction of total calls to keep an edge
            keep_if_errors: Always keep edges with error_count > 0

        Returns:
            New ServiceMap with `traffic_share` set on kept dependencies
        """
        total_calls = sum(d.call_count for d in service_map.dependencies) or 1

        kept: List[ServiceDependency] = []
        for dep in service_map.dependencies:
            share = dep.call_count / total_calls
            if share >= min_traffic_share or (keep_if_errors and dep.error_count > 0):
                kept.append(dep.model_copy(update={"traffic_share": share}))

        callers = {d.source_service for d in kept}
        callees = {d.target_service for d in kept}
        connected = callers | callees
        original_callers = {d.source_service for d in service_map.dependencies}
        original_callees = {d.target_service for d in service_map.dependencies}
        isolated = [
            s
            for s in service_map.services
            if s not in original_callers and s not in original_callees
        ]
        services = sorted(connected | set(isolated))

        return ServiceMap(
            services=services,
            dependencies=kept,
            root_services=sorted(set(services) - callees),
            leaf_services=sorted(set(services) - callers),
            edge_count=len(kept),
            service_count=len(services),
            virtual_nodes=service_map.virtual_nodes,
            identities=service_map.identities,
        )

    def ghost_edges(
        self,
        current_window: ServiceMap,
        previous_window: ServiceMap,
    ) -> ServiceMap:
        """
        Return a new ServiceMap with "ghost" edges appended: dependencies
        present in `previous_window` but absent from `current_window`,
        marked `ghost=True` and `call_count=0` (DEEPTHINK_10 ghost-edge
        decay). Existing current-window edges are unaffected.

        Args:
            current_window: The current-period service map
            previous_window: The prior-period service map to diff against

        Returns:
            New ServiceMap = current_window.dependencies + ghost edges
        """
        current_keys = {
            (d.source_service, d.target_service) for d in current_window.dependencies
        }
        ghosts = [
            dep.model_copy(update={"ghost": True, "call_count": 0, "error_count": 0})
            for dep in previous_window.dependencies
            if (dep.source_service, dep.target_service) not in current_keys
        ]
        if not ghosts:
            return current_window

        all_deps = list(current_window.dependencies) + ghosts
        ghost_services = {d.source_service for d in ghosts} | {d.target_service for d in ghosts}
        services = sorted(set(current_window.services) | ghost_services)

        return current_window.model_copy(
            update={
                "dependencies": all_deps,
                "services": services,
                "edge_count": len(all_deps),
                "service_count": len(services),
            }
        )

    def ego_subgraph(
        self,
        service_map: ServiceMap,
        service: str,
        upstream_hops: int = 1,
        downstream_hops: int = 2,
    ) -> ServiceMap:
        """
        Return an ego-centric subgraph: `service` plus its upstream
        neighbors out to `upstream_hops` and downstream neighbors out to
        `downstream_hops` (DEEPTHINK_10 semantic zoom).

        Args:
            service_map: The full service map
            service: The center service
            upstream_hops: How many hops upstream (callers) to include
            downstream_hops: How many hops downstream (callees) to include

        Returns:
            New ServiceMap restricted to the ego subgraph
        """
        forward: Dict[str, List[str]] = {s: [] for s in service_map.services}
        reverse: Dict[str, List[str]] = {s: [] for s in service_map.services}
        for dep in service_map.dependencies:
            forward.setdefault(dep.source_service, []).append(dep.target_service)
            reverse.setdefault(dep.target_service, []).append(dep.source_service)

        def bfs(start: str, hops: int, adjacency: Dict[str, List[str]]) -> Set[str]:
            visited = {start}
            frontier = [start]
            for _ in range(hops):
                next_frontier = []
                for node in frontier:
                    for neighbor in adjacency.get(node, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            next_frontier.append(neighbor)
                frontier = next_frontier
            return visited

        downstream_set = bfs(service, downstream_hops, forward)
        upstream_set = bfs(service, upstream_hops, reverse)
        keep = downstream_set | upstream_set

        deps = [
            d
            for d in service_map.dependencies
            if d.source_service in keep and d.target_service in keep
        ]
        callers = {d.source_service for d in deps}
        callees = {d.target_service for d in deps}
        services = sorted(keep)

        return ServiceMap(
            services=services,
            dependencies=deps,
            root_services=sorted(set(services) - callees),
            leaf_services=sorted(set(services) - callers),
            edge_count=len(deps),
            service_count=len(services),
            virtual_nodes=service_map.virtual_nodes,
            identities={k: v for k, v in service_map.identities.items() if k in keep},
        )

    def centrality(
        self,
        service_map: ServiceMap,
        damping: float = 0.85,
        iterations: int = 20,
    ) -> Dict[str, float]:
        """
        Compute call-volume-weighted PageRank centrality over the service
        dependency graph (DEEPTHINK_11). Pure-stdlib power iteration,
        dangling (no-outbound-edge) nodes redistribute their mass uniformly
        each iteration.

        STABLE EXPORT — consumed by SLO/portfolio_scorer for portfolio SRI
        weighting. Method name (`centrality`), signature
        `(service_map: ServiceMap, damping: float = 0.85, iterations: int = 20) -> Dict[str, float]`,
        and return shape (`{service_name: float}`, scores summing to ~1.0)
        are a stable contract — do not rename or change the return type.

        Args:
            service_map: ServiceMap to analyze (from build/build_with_identity/prune/etc.)
            damping: PageRank damping factor (default 0.85)
            iterations: Power-iteration step count (default 20)

        Returns:
            Dict mapping service_name -> centrality score in [0, 1].
            Scores sum to ~1.0 across all services (floating-point exact).
            Empty dict if service_map has no services.
        """
        services = list(service_map.services)
        n = len(services)
        if n == 0:
            return {}

        index = {name: i for i, name in enumerate(services)}
        out_weights: List[Dict[int, float]] = [dict() for _ in range(n)]
        out_totals = [0.0] * n

        for dep in service_map.dependencies:
            if dep.source_service not in index or dep.target_service not in index:
                continue
            weight = max(float(dep.call_count), 1.0)
            src, dst = index[dep.source_service], index[dep.target_service]
            out_weights[src][dst] = out_weights[src].get(dst, 0.0) + weight
            out_totals[src] += weight

        scores = [1.0 / n] * n
        for _ in range(max(iterations, 0)):
            new_scores = [(1.0 - damping) / n] * n
            dangling_mass = sum(scores[i] for i in range(n) if out_totals[i] == 0.0)

            for i in range(n):
                if out_totals[i] == 0.0:
                    continue
                share = scores[i] / out_totals[i]
                for j, weight in out_weights[i].items():
                    new_scores[j] += damping * share * weight

            if dangling_mass > 0:
                redistributed = damping * dangling_mass / n
                new_scores = [s + redistributed for s in new_scores]

            scores = new_scores

        total = sum(scores) or 1.0
        return {services[i]: scores[i] / total for i in range(n)}
