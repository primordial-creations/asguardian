"""
Graph traversal helpers for ServiceMapBuilder.

Contains graph traversal functions extracted from the service map builder.
"""

from typing import Dict, List, Set, Tuple

from Asgard.Verdandi.APM.models.apm_models import ServiceMap


def percentile(sorted_values: List[float], pct: float) -> float:
    """Calculate percentile from sorted values."""
    if not sorted_values:
        return 0.0

    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    rank = (pct / 100) * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    fraction = rank - lower_idx

    return sorted_values[lower_idx] + fraction * (
        sorted_values[upper_idx] - sorted_values[lower_idx]
    )


def detect_cycles(service_map: ServiceMap) -> List[List[str]]:
    """
    Detect cycles in the service dependency graph.

    Args:
        service_map: The service map to analyze

    Returns:
        List of cycles (each cycle is a list of service names)
    """
    graph: Dict[str, List[str]] = {s: [] for s in service_map.services}
    for dep in service_map.dependencies:
        graph[dep.source_service].append(dep.target_service)

    cycles = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def dfs(node: str, path: List[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.remove(node)

    for service in service_map.services:
        if service not in visited:
            dfs(service, [])

    return cycles


def get_downstream_services(
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
    reverse_graph: Dict[str, List[str]] = {s: [] for s in service_map.services}
    for dep in service_map.dependencies:
        reverse_graph[dep.target_service].append(dep.source_service)

    downstream: Set[str] = set()
    queue = [service_name]

    while queue:
        current = queue.pop(0)
        for dependent in reverse_graph.get(current, []):
            if dependent not in downstream:
                downstream.add(dependent)
                queue.append(dependent)

    return downstream


def get_upstream_services(
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
    graph: Dict[str, List[str]] = {s: [] for s in service_map.services}
    for dep in service_map.dependencies:
        graph[dep.source_service].append(dep.target_service)

    upstream: Set[str] = set()
    queue = [service_name]

    while queue:
        current = queue.pop(0)
        for dependency in graph.get(current, []):
            if dependency not in upstream:
                upstream.add(dependency)
                queue.append(dependency)

    return upstream


def calculate_service_depth(service_map: ServiceMap) -> Dict[str, int]:
    """
    Calculate the depth of each service in the call hierarchy.

    Root services have depth 0, their direct callees have depth 1, etc.

    Args:
        service_map: The service map to analyze

    Returns:
        Dictionary mapping service name to depth
    """
    graph: Dict[str, List[str]] = {s: [] for s in service_map.services}
    for dep in service_map.dependencies:
        graph[dep.source_service].append(dep.target_service)

    depths: Dict[str, int] = {}

    queue: List[Tuple[str, int]] = [(s, 0) for s in service_map.root_services]

    while queue:
        service, depth = queue.pop(0)

        if service in depths:
            depths[service] = min(depths[service], depth)
        else:
            depths[service] = depth
            for callee in graph.get(service, []):
                queue.append((callee, depth + 1))

    for service in service_map.services:
        if service not in depths:
            depths[service] = -1

    return depths
