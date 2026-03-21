"""
Heimdall Graph Builder Service

Builds NetworkX dependency graphs from analyzed imports.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import networkx as nx

from Asgard.Heimdall.Dependencies.models.dependency_models import (
    DependencyConfig,
    ModuleDependencies,
)
from Asgard.Heimdall.Dependencies.services.import_analyzer import ImportAnalyzer


class GraphBuilder:
    """
    Builds dependency graphs from analyzed imports.

    Uses NetworkX for graph operations and matplotlib for visualization.
    Both packages are required dependencies.
    """

    def __init__(self, config: Optional[DependencyConfig] = None):
        """Initialize the graph builder."""
        self.config = config or DependencyConfig()
        self.import_analyzer = ImportAnalyzer(self.config)

    def build_graph(
        self, scan_path: Optional[Path] = None
    ) -> "nx.DiGraph":
        """
        Build a NetworkX directed graph of dependencies.

        Args:
            scan_path: Root path to scan

        Returns:
            NetworkX DiGraph

        Returns:
            NetworkX DiGraph
        """
        path = scan_path or self.config.scan_path
        modules = self.import_analyzer.analyze(path)

        graph = nx.DiGraph()

        # Add all modules as nodes
        for module in modules:
            graph.add_node(
                module.module_name,
                file_path=module.file_path,
                relative_path=module.relative_path,
            )

        # Add edges for dependencies
        for module in modules:
            for dep in module.all_dependencies:
                graph.add_edge(module.module_name, dep)

        return graph

    def build_dict_graph(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, Set[str]]:
        """
        Build a dictionary-based dependency graph.

        This works without NetworkX.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict mapping module names to their dependencies
        """
        path = scan_path or self.config.scan_path
        modules = self.import_analyzer.analyze(path)

        graph = {}
        for module in modules:
            graph[module.module_name] = module.all_dependencies

        return graph

    def get_reverse_graph(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, Set[str]]:
        """
        Build a reverse dependency graph (who depends on whom).

        Args:
            scan_path: Root path to scan

        Returns:
            Dict mapping module names to modules that depend on them
        """
        forward_graph = self.build_dict_graph(scan_path)

        reverse: Dict[str, Set[str]] = {module: set() for module in forward_graph}

        for module, deps in forward_graph.items():
            for dep in deps:
                if dep in reverse:
                    reverse[dep].add(module)

        return reverse

    def export_dot(
        self,
        scan_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Export the dependency graph in DOT format.

        Args:
            scan_path: Root path to scan
            output_path: Optional path to write DOT file

        Returns:
            DOT format string
        """
        graph = self.build_dict_graph(scan_path)

        lines = ["digraph dependencies {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        lines.append("")

        # Add edges
        for module, deps in sorted(graph.items()):
            for dep in sorted(deps):
                # Escape dots in node names
                src = module.replace(".", "_")
                tgt = dep.replace(".", "_")
                lines.append(f'  "{src}" -> "{tgt}";')

        lines.append("}")

        dot_content = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(dot_content)

        return dot_content

    def export_mermaid(
        self,
        scan_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        direction: str = "LR",
    ) -> str:
        """
        Export the dependency graph in Mermaid flowchart format.

        Args:
            scan_path: Root path to scan
            output_path: Optional path to write Mermaid file
            direction: Graph direction (LR, TB, RL, BT)

        Returns:
            Mermaid format string
        """
        graph = self.build_dict_graph(scan_path)

        lines = [f"flowchart {direction}"]

        # Collect all node names for ID mapping
        node_ids: Dict[str, str] = {}
        for idx, module in enumerate(sorted(graph.keys())):
            node_id = f"n{idx}"
            node_ids[module] = node_id
            lines.append(f"  {node_id}[\"{module}\"]")

        lines.append("")

        # Add edges
        for module, deps in sorted(graph.items()):
            src_id = node_ids[module]
            for dep in sorted(deps):
                if dep in node_ids:
                    tgt_id = node_ids[dep]
                    lines.append(f"  {src_id} --> {tgt_id}")

        mermaid_content = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(mermaid_content)

        return mermaid_content

    def export_json(
        self, scan_path: Optional[Path] = None
    ) -> Dict:
        """
        Export the dependency graph as JSON-serializable dict.

        Args:
            scan_path: Root path to scan

        Returns:
            Dictionary suitable for JSON serialization
        """
        graph = self.build_dict_graph(scan_path)

        return {
            "nodes": list(graph.keys()),
            "edges": [
                {"source": src, "target": tgt}
                for src, deps in graph.items()
                for tgt in deps
            ],
        }

    def visualize(
        self,
        scan_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> None:
        """
        Visualize the dependency graph using matplotlib.

        Args:
            scan_path: Root path to scan
            output_path: Path to save the image
            figsize: Figure size (width, height)

        """
        graph = self.build_graph(scan_path)

        fig, ax = plt.subplots(figsize=figsize)

        # Use spring layout for positioning
        pos = nx.spring_layout(graph, k=2, iterations=50)

        # Draw the graph
        nx.draw(
            graph,
            pos,
            ax=ax,
            with_labels=True,
            node_color="lightblue",
            node_size=2000,
            font_size=8,
            font_weight="bold",
            arrows=True,
            arrowsize=15,
            edge_color="gray",
            alpha=0.7,
        )

        ax.set_title("Module Dependencies")

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close()
        else:
            plt.show()

    def get_metrics(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, Dict]:
        """
        Get graph metrics for each node.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict mapping module names to their metrics
        """
        graph = self.build_graph(scan_path)

        metrics = {}
        for node in graph.nodes():
            metrics[node] = {
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
            }

        return metrics
