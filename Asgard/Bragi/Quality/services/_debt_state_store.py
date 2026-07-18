"""
Bragi Debt State Store (Plan 02 Phase E / RESEARCH_15)

Content-hash keyed per-file debt cache: on re-scan, only files whose
SHA-256 changed are re-analyzed; project totals are updated arithmetically
(`total += sum(new_file_debt) - sum(old_file_debt)`) instead of rescanning
the world. Persisted under `.asgard_cache/bragi_debt_state.json` (per scan
root) and is a prerequisite for Plan 06's PR-differential gating.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from Asgard.Bragi.Quality.models.debt_models import DebtItem

STATE_RELATIVE_PATH = Path(".asgard_cache") / "bragi_debt_state.json"
STATE_SCHEMA_VERSION = 1


class FileDebtState(BaseModel):
    """Cached per-file debt state: content hash + the items it produced."""
    content_hash: str = Field(..., description="SHA-256 of the file's bytes at last scan")
    debt_minutes: float = Field(0.0, ge=0.0, description="Total remediation minutes for this file")
    item_count: int = Field(0, ge=0, description="Number of debt items last recorded for this file")

    class Config:
        use_enum_values = True


class DebtState(BaseModel):
    """Persisted per-scan-root debt cache."""
    schema_version: int = Field(STATE_SCHEMA_VERSION)
    scan_root: str = Field("", description="Root path this state was computed for")
    files: Dict[str, FileDebtState] = Field(default_factory=dict)
    total_debt_minutes: float = Field(0.0, ge=0.0)

    class Config:
        use_enum_values = True


class DeltaResult(BaseModel):
    """Result of an incremental delta analysis."""
    changed_files: List[str] = Field(default_factory=list, description="Files re-analyzed this run")
    unchanged_files: int = Field(0, ge=0, description="Files skipped because content was unchanged")
    added_or_changed_minutes: float = Field(0.0, description="Debt minutes added by new/changed files")
    removed_minutes: float = Field(0.0, description="Debt minutes removed (deleted/fixed files)")
    total_debt_minutes: float = Field(0.0, ge=0.0, description="Updated project total after the delta")

    class Config:
        use_enum_values = True


def content_hash(file_path: Path) -> Optional[str]:
    """SHA-256 of a file's bytes; None when the file cannot be read."""
    try:
        data = Path(file_path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()


def load_state(scan_root: Path) -> DebtState:
    """Load `debt_state.json` for `scan_root`; returns an empty state when absent/corrupt."""
    path = Path(scan_root) / STATE_RELATIVE_PATH
    if not path.exists():
        return DebtState(scan_root=str(scan_root))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DebtState(scan_root=str(scan_root))
    if not isinstance(data, dict) or data.get("schema_version") != STATE_SCHEMA_VERSION:
        return DebtState(scan_root=str(scan_root))
    try:
        return DebtState(**data)
    except Exception:
        return DebtState(scan_root=str(scan_root))


def save_state(scan_root: Path, state: DebtState) -> None:
    """Persist `state` to `.asgard_cache/bragi_debt_state.json` under `scan_root`."""
    path = Path(scan_root) / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # Stable key order for deterministic bytes across identical runs.
    payload = json.loads(state.model_dump_json())
    payload["files"] = dict(sorted(payload.get("files", {}).items()))
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def changed_files(scan_root: Path, candidate_files: Iterable[Path], state: Optional[DebtState] = None) -> List[Path]:
    """
    Files among `candidate_files` whose content hash differs from (or is
    absent from) the persisted state - i.e. the set that needs re-analysis.
    """
    state = state or load_state(scan_root)
    result: List[Path] = []
    for file_path in candidate_files:
        rel = _relative_key(scan_root, file_path)
        cached = state.files.get(rel)
        current_hash = content_hash(file_path)
        if current_hash is None:
            continue
        if cached is None or cached.content_hash != current_hash:
            result.append(file_path)
    return result


def _relative_key(scan_root: Path, file_path: Path) -> str:
    try:
        return str(Path(file_path).resolve().relative_to(Path(scan_root).resolve()))
    except ValueError:
        return str(file_path)


def apply_delta(
    scan_root: Path,
    state: DebtState,
    file_items: Dict[str, List[DebtItem]],
    all_current_files: Iterable[str],
) -> DeltaResult:
    """
    Update `state` arithmetically from freshly-computed `file_items` (only
    for files that were actually re-analyzed) and return the delta.

    `all_current_files` is the full current file set (relative keys) used
    to detect deletions: any cached file absent from it has its debt
    removed from the total.
    """
    all_current = set(all_current_files)
    removed_minutes = 0.0
    for rel, cached in list(state.files.items()):
        if rel not in all_current:
            removed_minutes += cached.debt_minutes
            del state.files[rel]

    added_or_changed_minutes = 0.0
    for rel, items in file_items.items():
        old_minutes = state.files.get(rel).debt_minutes if rel in state.files else 0.0
        new_minutes = sum(_item_minutes(item) for item in items)
        full_path = Path(scan_root) / rel
        new_hash = content_hash(full_path) or ""
        state.files[rel] = FileDebtState(
            content_hash=new_hash, debt_minutes=new_minutes, item_count=len(items),
        )
        added_or_changed_minutes += new_minutes - old_minutes

    state.total_debt_minutes = max(
        state.total_debt_minutes + added_or_changed_minutes - removed_minutes, 0.0
    )
    state.scan_root = str(scan_root)

    return DeltaResult(
        changed_files=sorted(file_items.keys()),
        unchanged_files=len(all_current) - len(file_items),
        added_or_changed_minutes=added_or_changed_minutes,
        removed_minutes=removed_minutes,
        total_debt_minutes=state.total_debt_minutes,
    )


def _item_minutes(item: DebtItem) -> float:
    """Minutes for one debt item, preferring the effort interval midpoint."""
    if item.effort_interval is not None:
        return item.effort_interval.midpoint_minutes
    return item.effort_hours * 60.0
