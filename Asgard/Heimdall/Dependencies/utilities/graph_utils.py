"""
Heimdall Dependencies Graph Utilities

Utility functions for working with dependency graphs.
"""

from typing import Dict, List, Optional, Set, Tuple

import networkx as nx


def create_dependency_graph(
    dependencies: List[Tuple[str, str]]
) -> "nx.DiGraph":
    """
    Create a directed graph from dependency pairs.

    Args:
        dependencies: List of (source, target) tuples

    Returns:
        NetworkX DiGraph

    Raises:
        ImportError: If NetworkX is not installed
    """
    graph = nx.DiGraph()

    for source, target in dependencies:
        graph.add_edge(source, target)

    return graph


def find_strongly_connected_components(
    graph: "nx.DiGraph"
) -> List[Set[str]]:
    """
    Find strongly connected components (cycles) in the graph.

    Args:
        graph: NetworkX DiGraph

    Returns:
        List of sets, each set is a strongly connected component
    """
    # Find SCCs with more than one node (actual cycles)
    sccs = list(nx.strongly_connected_components(graph))
    return [scc for scc in sccs if len(scc) > 1]


def find_simple_cycles(graph: "nx.DiGraph") -> List[List[str]]:
    """
    Find all simple cycles in the graph.

    Args:
        graph: NetworkX DiGraph

    Returns:
        List of cycles, each cycle is a list of nodes
    """
    return list(nx.simple_cycles(graph))


def calculate_modularity(
    graph: "nx.DiGraph",
    communities: List[Set[str]]
) -> float:
    """
    Calculate modularity score for a graph partitioning.

    Args:
        graph: NetworkX DiGraph
        communities: List of node sets representing communities

    Returns:
        Modularity score (0-1, higher is better)
    """
    # Convert to undirected for modularity calculation
    undirected = graph.to_undirected()

    try:
        return nx.algorithms.community.modularity(undirected, communities)
    except Exception:
        return 0.0


def detect_communities(graph: "nx.DiGraph") -> List[Set[str]]:
    """
    Detect communities/clusters in the dependency graph.

    Args:
        graph: NetworkX DiGraph

    Returns:
        List of node sets representing communities
    """
    # Convert to undirected for community detection
    undirected = graph.to_undirected()

    try:
        # Use greedy modularity communities
        communities = nx.algorithms.community.greedy_modularity_communities(undirected)
        return [set(c) for c in communities]
    except Exception:
        # Fallback: each node is its own community
        return [set([node]) for node in graph.nodes()]


def get_node_degrees(graph: "nx.DiGraph") -> Dict[str, Dict[str, int]]:
    """
    Get in-degree and out-degree for each node.

    Args:
        graph: NetworkX DiGraph

    Returns:
        Dict mapping node to {in_degree, out_degree}
    """
    result = {}
    for node in graph.nodes():
        result[node] = {
            "in_degree": graph.in_degree(node),
            "out_degree": graph.out_degree(node),
        }
    return result


def topological_sort(graph: "nx.DiGraph") -> Optional[List[str]]:
    """
    Get topological ordering of nodes (if graph is acyclic).

    Args:
        graph: NetworkX DiGraph

    Returns:
        List of nodes in topological order, or None if cycles exist
    """
    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        return None


def get_transitive_closure(graph: "nx.DiGraph") -> "nx.DiGraph":
    """
    Get transitive closure of the graph.

    The transitive closure includes an edge (u, v) if there's
    any path from u to v in the original graph.

    Args:
        graph: NetworkX DiGraph

    Returns:
        Transitive closure graph
    """
    return nx.transitive_closure(graph)


def find_shortest_path(
    graph: "nx.DiGraph",
    source: str,
    target: str
) -> Optional[List[str]]:
    """
    Find shortest path between two nodes.

    Args:
        graph: NetworkX DiGraph
        source: Source node
        target: Target node

    Returns:
        List of nodes in the path, or None if no path exists
    """
    try:
        return nx.shortest_path(graph, source, target)
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None


# Fallback implementations for when NetworkX is not available

def find_cycles_fallback(
    dependencies: Dict[str, Set[str]]
) -> List[List[str]]:
    """
    Find cycles without NetworkX using DFS.

    Args:
        dependencies: Dict mapping module to its dependencies

    Returns:
        List of cycles found
    """
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: List[str]) -> None:
        if node in rec_stack:
            # Found a cycle
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:])
            return

        if node in visited:
            return

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in dependencies.get(node, set()):
            dfs(neighbor, path.copy())

        rec_stack.remove(node)

    for node in dependencies:
        if node not in visited:
            dfs(node, [])

    return cycles
