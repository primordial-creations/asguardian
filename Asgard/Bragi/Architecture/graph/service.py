"""
ArchGraphService — the single entry point for import-graph-based
architecture enforcement (Heimdall Plan 03).

Reuses `Bragi.Dependencies.services.graph_service.DependencyGraphService`
for the cached import graph rather than rebuilding it; layers a level
CSP (layer inference + drift), module-granularity cycle detection, and
fan-out checking on top; persists inferred bounds for incremental reuse.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Architecture.graph.drift import ArchitectureDriftViolation, detect_drift
from Asgard.Bragi.Architecture.graph.module_cycles import ModuleCycle, detect_module_cycles
from Asgard.Bragi.Architecture.graph.nodes import LevelBounds
from Asgard.Bragi.Architecture.graph.propagation import infer_levels, infer_levels_incremental
from Asgard.Bragi.Architecture.services._architecture_config import (
    ArchitectureConfig,
    default_architecture_config,
    load_architecture_config,
)
from Asgard.Bragi.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Bragi.Dependencies.services.graph_service import (
    DependencyGraph,
    DependencyGraphService,
    no_cache_env,
)

BOUNDS_CACHE_RELATIVE_PATH = Path(".asgard_cache") / "bragi_arch_bounds.json"
BOUNDS_CACHE_VERSION = "1.0.0"


@dataclass
class FanOutViolation:
    module: str
    fan_out: int
    limit: int
    targets: List[str] = field(default_factory=list)


def _class_names(source: str) -> Set[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def _raw_imports(source: str) -> Set[str]:
    """All import targets (module or 'from' source), resolved or not —
    used to anchor external-package imports (e.g. sqlalchemy) that
    `DependencyGraph.dependency_list` drops because they never resolve to
    an internal graph node."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return set()
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class ArchGraphService:
    """Import-graph layer inference + drift + module cycles + fan-out.

    One `DependencyGraphService` per instance so the underlying import
    graph is parsed once and shared across every check in this module.
    """

    def __init__(
        self,
        config: Optional[ArchitectureConfig] = None,
        dep_config: Optional[DependencyConfig] = None,
        graph_service: Optional[DependencyGraphService] = None,
    ):
        self.config = config or default_architecture_config()
        self.dep_config = dep_config or DependencyConfig()
        self.graph_service = graph_service or DependencyGraphService(self.dep_config)
        self.use_disk_cache = self.graph_service.use_disk_cache and not no_cache_env()

    @classmethod
    def from_yaml(
        cls, config_path: str, scan_path: Optional[Path] = None
    ) -> "ArchGraphService":
        arch_config = load_architecture_config(config_path)
        dep_config = DependencyConfig(scan_path=scan_path) if scan_path else DependencyConfig()
        return cls(config=arch_config, dep_config=dep_config)

    # ------------------------------------------------------------------

    def _class_names_by_module(self, graph: DependencyGraph) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = {}
        for m in graph.modules:
            result[m.module_name] = _class_names(self._source(m))
        return result

    def _raw_imports_by_module(self, graph: DependencyGraph) -> Dict[str, Set[str]]:
        result: Dict[str, Set[str]] = {}
        for m in graph.modules:
            result[m.module_name] = _raw_imports(self._source(m))
        return result

    @staticmethod
    def _source(m) -> str:
        try:
            return Path(m.file_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def infer(self, scan_path: Optional[Path] = None) -> Dict[str, LevelBounds]:
        """Full or incremental level inference, whichever the disk cache
        allows. Returns {} if the active config has no `level:` layers."""
        path = Path(scan_path or self.dep_config.scan_path).resolve()
        graph = self.graph_service.build(path)
        if not self.config.has_level_inference:
            return {}

        class_names = self._class_names_by_module(graph)
        raw_imports = self._raw_imports_by_module(graph)
        cache = self._load_bounds_cache(path)
        current_modules = set(graph.graph)

        if cache is not None:
            prev_bounds_raw = cache.get("bounds", {})
            prev_modules = set(prev_bounds_raw)
            prev_bounds: Dict[str, LevelBounds] = {
                m: LevelBounds(
                    module=m,
                    min_level=b["min_level"],
                    max_level=b["max_level"],
                    base_level=b.get("base_level"),
                    matched=b.get("matched", False),
                    pinned_by=list(b.get("pinned_by", [])),
                )
                for m, b in prev_bounds_raw.items()
            }
            changed = self._changed_modules(path, graph, cache)
            changed |= (current_modules - prev_modules)  # new modules
            changed |= (prev_modules - current_modules)  # removed modules trigger neighbours too
            if changed or (current_modules != prev_modules):
                bounds = infer_levels_incremental(
                    graph, self.config, changed & current_modules, prev_bounds,
                    class_names, raw_imports,
                )
            else:
                bounds = {m: prev_bounds[m] for m in current_modules if m in prev_bounds}
        else:
            bounds = infer_levels(graph, self.config, class_names, raw_imports)

        self._save_bounds_cache(path, graph, bounds)
        return bounds

    def drift_violations(self, scan_path: Optional[Path] = None) -> List[ArchitectureDriftViolation]:
        return detect_drift(self.infer(scan_path))

    def module_cycles(self, scan_path: Optional[Path] = None) -> List[ModuleCycle]:
        path = Path(scan_path or self.dep_config.scan_path).resolve()
        if not self.config.rules.detect_module_cycles:
            return []
        graph = self.graph_service.build(path)
        return detect_module_cycles(graph)

    def fan_out_violations(self, scan_path: Optional[Path] = None) -> List[FanOutViolation]:
        limit = self.config.rules.max_module_fan_out
        if not limit:
            return []
        path = Path(scan_path or self.dep_config.scan_path).resolve()
        graph = self.graph_service.build(path)
        from Asgard.Bragi.Architecture.graph.module_cycles import module_id

        fan_out: Dict[str, Set[str]] = {}
        for src, deps in graph.graph.items():
            src_mod = module_id(src)
            for dst in deps:
                dst_mod = module_id(dst)
                if dst_mod != src_mod:
                    fan_out.setdefault(src_mod, set()).add(dst_mod)

        violations: List[FanOutViolation] = []
        for module, targets in sorted(fan_out.items()):
            if len(targets) > limit:
                violations.append(FanOutViolation(
                    module=module, fan_out=len(targets), limit=limit,
                    targets=sorted(targets),
                ))
        return violations

    def explain(self, file_path: str, scan_path: Optional[Path] = None) -> str:
        """Human-readable explanation of a file's inferred bounds and which
        imports pinned them (`heimdall arch layers <path> --explain <file>`)."""
        path = Path(scan_path or self.dep_config.scan_path).resolve()
        graph = self.graph_service.build(path)
        bounds = self.infer(path)

        module = self._resolve_module(file_path, graph)
        if module is None or module not in bounds:
            return f"'{file_path}' is not part of the scanned import graph."

        b = bounds[module]
        lines = [f"Module: {module}"]
        if b.is_drift:
            lines.append(
                f"ARCHITECTURE DRIFT: intrinsic level {b.base_level} but effective "
                f"max level is {b.max_level} (min={b.min_level} > max={b.max_level})."
            )
        elif b.is_bridge:
            lines.append(
                f"Bridge file: assigned level {b.min_level} "
                f"(bound spread {b.min_level}..{b.max_level}, "
                f"confidence {b.confidence(max(1, b.max_level)):.0%})"
            )
        else:
            lines.append(f"Assigned level: {b.min_level} (confidence 100%)")
        lines.append("Pinned by:")
        if b.pinned_by:
            for reason in b.pinned_by:
                lines.append(f"  - {reason}")
        else:
            lines.append("  - (unmatched by any heuristic; default bounds)")
        return "\n".join(lines)

    @staticmethod
    def _resolve_module(file_path: str, graph: DependencyGraph) -> Optional[str]:
        target = str(Path(file_path).resolve())
        for m in graph.modules:
            if str(Path(m.file_path).resolve()) == target:
                return m.module_name
        # Fall back to relative-path or dotted-module match.
        for m in graph.modules:
            if m.relative_path == file_path or m.module_name == file_path:
                return m.module_name
        return None

    # ------------------------------------------------------- bounds cache

    def _cache_path(self, scan_path: Path) -> Path:
        return scan_path / BOUNDS_CACHE_RELATIVE_PATH

    def _load_bounds_cache(self, scan_path: Path) -> Optional[dict]:
        if not self.use_disk_cache:
            return None
        cache_file = self._cache_path(scan_path)
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != BOUNDS_CACHE_VERSION:
                return None
            if data.get("config_hash") != self._config_hash():
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _save_bounds_cache(self, scan_path: Path, graph: DependencyGraph, bounds: Dict[str, LevelBounds]) -> None:
        if not self.use_disk_cache:
            return
        try:
            cache_file = self._cache_path(scan_path)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": BOUNDS_CACHE_VERSION,
                "config_hash": self._config_hash(),
                "file_hashes": self._current_file_hashes(graph),
                "bounds": {
                    m: {
                        "min_level": b.min_level, "max_level": b.max_level,
                        "base_level": b.base_level, "matched": b.matched,
                        "pinned_by": b.pinned_by,
                    }
                    for m, b in bounds.items()
                },
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1, sort_keys=True)
        except OSError:
            pass  # caching is best-effort, never fatal

    def _config_hash(self) -> str:
        payload = json.dumps(
            [
                {
                    "name": l.name, "level": l.level, "path_patterns": l.path_patterns,
                    "suffixes": l.suffixes, "external_imports": l.external_imports,
                }
                for l in self.config.layers
            ],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _current_file_hashes(graph: DependencyGraph) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        for m in graph.modules:
            try:
                source = Path(m.file_path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                source = ""
            hashes[m.module_name] = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return hashes

    def _changed_modules(self, scan_path: Path, graph: DependencyGraph, cache: dict) -> Set[str]:
        prev_hashes: Dict[str, str] = cache.get("file_hashes", {})
        current_hashes = self._current_file_hashes(graph)
        changed: Set[str] = set()
        for module, h in current_hashes.items():
            if prev_hashes.get(module) != h:
                changed.add(module)
        return changed
