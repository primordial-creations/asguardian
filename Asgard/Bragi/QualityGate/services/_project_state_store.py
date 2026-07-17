"""
Project State Store (Plan Bragi-06 Phase B).

Persists the main-branch aggregate the differential gate diffs against:
violation fingerprints, per-file scores, the debt aggregate, and the
dependency-graph interface hashes — `.asgard_cache/bragi_project_state.json`.

Cache discipline (RESEARCH_15 / SonarQube): only reference-branch (main)
scans write this state; PR evaluations load it READ-ONLY and never write
back. The store enforces that with a `writable` policy flag — a store opened
for a PR evaluation raises on any save attempt instead of silently polluting
the baseline.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectState(BaseModel):
    """Persisted main-branch aggregate for differential evaluation."""
    branch: str = Field("main", description="Branch this state was captured on")
    commit: str = Field("", description="Commit sha at capture time")
    captured_at: datetime = Field(default_factory=datetime.now)
    violation_fingerprints: List[str] = Field(
        default_factory=list,
        description="Fingerprints of all findings on the reference branch",
    )
    file_scores: Dict[str, float] = Field(
        default_factory=dict, description="Per-file composite scores"
    )
    debt_minutes: float = Field(
        0.0, description="Aggregate technical-debt minutes on the branch"
    )
    interface_hashes: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-file dependency-graph interface hashes",
    )

    class Config:
        use_enum_values = True

    @property
    def fingerprint_set(self) -> set:
        return set(self.violation_fingerprints)


class ReadOnlyStateError(RuntimeError):
    """Raised when a PR-scoped (read-only) store is asked to write."""


class ProjectStateStore:
    """
    Load/save ProjectState with write-only-on-main discipline.

    Args:
        project_path: project root (state lives under `.asgard_cache/`).
        writable: pass True ONLY for reference-branch scans. PR evaluations
            must keep the default False; save() then raises.
    """

    DEFAULT_RELATIVE_PATH = Path(".asgard_cache") / "bragi_project_state.json"

    def __init__(self, project_path: Path, *, writable: bool = False,
                 store_path: Optional[Path] = None):
        self.project_path = Path(project_path)
        self.writable = writable
        self.store_path = store_path or (
            self.project_path / self.DEFAULT_RELATIVE_PATH)

    def load(self) -> Optional[ProjectState]:
        """Load the persisted state (None when absent or unreadable)."""
        if not self.store_path.exists():
            return None
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ProjectState(**data)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None

    def save(self, state: ProjectState) -> None:
        """Persist the state. Raises ReadOnlyStateError on a read-only store."""
        if not self.writable:
            raise ReadOnlyStateError(
                "This ProjectStateStore is read-only (PR evaluation scope). "
                "Only reference-branch scans may persist project state "
                "(RESEARCH_15 cache discipline)."
            )
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(state.model_dump_json())
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def merge_delta(
        self,
        *,
        commit: str,
        resolved_fingerprints: Optional[List[str]] = None,
        new_fingerprints: Optional[List[str]] = None,
        file_scores: Optional[Dict[str, float]] = None,
        debt_minutes: Optional[float] = None,
        interface_hashes: Optional[Dict[str, str]] = None,
    ) -> ProjectState:
        """
        Apply a delta to the persisted aggregate (main-branch scans only):
        remove resolved fingerprints, add new ones, overwrite touched file
        scores/hashes, update the debt aggregate.
        """
        state = self.load() or ProjectState()
        fingerprints = set(state.violation_fingerprints)
        fingerprints -= set(resolved_fingerprints or ())
        fingerprints |= set(new_fingerprints or ())
        state.violation_fingerprints = sorted(fingerprints)
        state.commit = commit
        state.captured_at = datetime.now()
        if file_scores:
            state.file_scores.update(file_scores)
        if debt_minutes is not None:
            state.debt_minutes = debt_minutes
        if interface_hashes:
            state.interface_hashes.update(interface_hashes)
        self.save(state)
        return state
