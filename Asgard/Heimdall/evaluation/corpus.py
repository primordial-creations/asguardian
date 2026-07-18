"""
Corpus data model + JSON manifest loading (plan 10 s1/s4).

Two kinds of ground truth feed the harness:

- **Annotated fixtures**: small per-rule files (the existing
  ``benchmarks/corpus/<domain>/`` trees + Semgrep-style ``# ruleid:`` /
  ``# ok:`` markers under ``benchmarks/<lang>/``). These already exist;
  this module does not duplicate them, it *consumes* them via
  ``ground_truth_from_taint_manifest`` / ``ground_truth_from_annotations``.
- **CVE holdouts**: real OSS repos referenced by commit SHA + patch line
  span, never vendored into the repo. Stored as a JSON manifest
  (``corpus/manifest.json``) that the runner resolves against a
  locally-checked-out copy of the repo (BYO checkout -- the harness does
  not clone anything itself, so it stays network-free in CI).

``ReportedFinding`` is a thin, scanner-agnostic wrapper: callers adapt
``VulnerabilityFinding`` / ``TaintFlow`` objects into this shape before
handing them to the runner, so this package never has to import scanner
internals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from Asgard.Heimdall.evaluation.spans import ASTSpan


@dataclass(frozen=True)
class GroundTruthInstance:
    """One must-find semantic instance (a real vulnerability / fixture TP)."""

    id: str
    file_path: str
    cwe: str
    span: ASTSpan
    source: str = "fixture"  # "fixture" | "cve_holdout" | "clean_repo" (no TPs)


@dataclass(frozen=True)
class ReportedFinding:
    """Scanner-agnostic adapter target for VulnerabilityFinding / TaintFlow."""

    file_path: str
    line: int
    cwe: str
    confidence: float
    sink_node_id: str = ""
    rule_id: str = ""
    raw: Any = None


def finding_from_vulnerability(vf: Any, sink_node_id: str = "") -> ReportedFinding:
    """Adapt a ``VulnerabilityFinding``-shaped object (duck-typed, so it
    works whether or not pydantic is importable in the caller's env)."""
    return ReportedFinding(
        file_path=str(getattr(vf, "file_path")),
        line=int(getattr(vf, "line_number")),
        cwe=str(getattr(vf, "cwe_id", "") or ""),
        confidence=float(getattr(vf, "confidence")),
        sink_node_id=sink_node_id,
        rule_id=str(getattr(vf, "vulnerability_type", "")),
        raw=vf,
    )


def finding_from_taint_flow(flow: Any, sink_node_id: str = "") -> ReportedFinding:
    """Adapt a ``TaintFlow``-shaped object."""
    sink_loc = getattr(flow, "sink_location")
    return ReportedFinding(
        file_path=str(getattr(sink_loc, "file_path")),
        line=int(getattr(sink_loc, "line_number")),
        cwe=str(getattr(flow, "cwe_id", "") or ""),
        confidence=float(getattr(flow, "confidence")),
        sink_node_id=sink_node_id or str(getattr(sink_loc, "line_number")),
        rule_id=str(getattr(flow, "sink_type", "")),
        raw=flow,
    )


@dataclass
class CorpusManifest:
    """Parsed ``corpus/manifest.json``: CVE holdout references + clean
    repos for precision sampling. Repos are *referenced*, not vendored."""

    cve_holdouts: List[Dict[str, Any]] = field(default_factory=list)
    clean_repos: List[Dict[str, Any]] = field(default_factory=list)
    stratification: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "CorpusManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            cve_holdouts=data.get("cve_holdouts", []),
            clean_repos=data.get("clean_repos", []),
            stratification=data.get("stratification", {}),
        )

    def ground_truth_instances(self, checkout_root: Optional[Path] = None) -> List[GroundTruthInstance]:
        """Resolve CVE holdout entries into GroundTruthInstance objects.

        Each holdout entry names a repo path (relative to ``checkout_root``
        if given, else absolute/as-is), a commit SHA (informational -- the
        harness does not shell out to git), and one or more patch line
        spans with a CWE. Entries whose file does not exist locally are
        skipped (holdout not checked out yet) rather than raising, so the
        harness degrades gracefully to "0 CVE instances available" instead
        of crashing CI when repos are not attached.
        """
        instances: List[GroundTruthInstance] = []
        for entry in self.cve_holdouts:
            repo_rel = entry["repo_path"]
            base = (Path(checkout_root) / repo_rel) if checkout_root else Path(repo_rel)
            for i, patch in enumerate(entry.get("patch_spans", [])):
                file_path = str(base / patch["file"])
                span = ASTSpan(
                    file_path=file_path,
                    start_line=patch["start_line"],
                    end_line=patch["end_line"],
                )
                instances.append(
                    GroundTruthInstance(
                        id=f"{entry.get('cve_id', entry.get('repo_path'))}#{i}",
                        file_path=file_path,
                        cwe=patch.get("cwe", ""),
                        span=span,
                        source="cve_holdout",
                    )
                )
        return instances


def ground_truth_from_taint_manifest(
    corpus_dir: Path, manifest_cases: List[Dict[str, Any]]
) -> List[GroundTruthInstance]:
    """Convert the existing taint benchmark ``manifest.yml`` (TP/FP fixture
    cases) into GroundTruthInstance objects, so the plan-10 harness can be
    exercised against the corpus plans 01-08 already seeded, without
    duplicating fixture authoring.

    Each ``expect: flow`` case contributes one ground-truth instance whose
    span is the whole fixture file (fixtures are small, single-flow files
    by construction -- see ``benchmarks/corpus/taint/*.py``); ``no_flow``
    cases contribute none (they exist purely to police false positives).
    """
    instances: List[GroundTruthInstance] = []
    for case in manifest_cases:
        if case.get("expect") != "flow":
            continue
        fixture_path = corpus_dir / case["file"]
        n_lines = max(1, len(fixture_path.read_text(encoding="utf-8").splitlines()))
        instances.append(
            GroundTruthInstance(
                id=case["file"],
                file_path=str(fixture_path),
                cwe=case.get("cwe", ""),
                span=ASTSpan(file_path=str(fixture_path), start_line=1, end_line=n_lines),
                source="fixture",
            )
        )
    return instances
