"""
Service Map Builder Service

Builds service dependency maps from distributed traces.
"""

from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Verdandi.APM.models.apm_models import (
    ServiceDependency,
    ServiceMap,
    Span,
    Trace,
)
from Asgard.Verdandi.APM.services._graph_helpers import (
    calculate_service_depth,
    detect_cycles,
    get_downstream_services,
    get_upstream_services,
    percentile,
)


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
