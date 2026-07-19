"""On-disk cache for triage verdicts, keyed by finding fingerprint + code hash.

Opt-in path only -- never touched by the default (non-assist) scan path. Honors
``ASGARD_NO_CACHE`` (any truthy value disables reads and writes, forcing every
call to re-invoke the adapter).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from Asgard.Heimdall.Security.triage.models.triage_models import TriageVerdict

_CACHE_DIRNAME = ".asgard_cache"
_CACHE_SUBDIR = "triage"


def _no_cache() -> bool:
    return bool(os.environ.get("ASGARD_NO_CACHE"))


def fingerprint(finding: Any, code_context: str) -> str:
    """Stable content-hash key for a (finding, code_context) pair."""
    parts = [
        str(getattr(finding, "file_path", "")),
        str(getattr(finding, "line_number", "")),
        str(getattr(finding, "vulnerability_type", "")),
        str(getattr(finding, "title", "")),
        str(getattr(finding, "description", "")),
        code_context or "",
    ]
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8", errors="replace")).hexdigest()
    return digest


class TriageCache:
    """Simple on-disk JSON cache, one file per fingerprint.

    Instantiated with a root directory (defaults to ``./.asgard_cache/triage``);
    reads/writes are skipped entirely when ``ASGARD_NO_CACHE`` is set, or when
    disk I/O fails for any reason (cache is best-effort, never fatal).
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else Path.cwd() / _CACHE_DIRNAME / _CACHE_SUBDIR

    def _path_for(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> Optional[TriageVerdict]:
        if _no_cache():
            return None
        try:
            path = self._path_for(key)
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            verdict = TriageVerdict(**data)
            verdict.from_cache = True
            return verdict
        except Exception:
            # Cache is best-effort; any corruption/IO error just means a miss.
            return None

    def set(self, key: str, verdict: TriageVerdict) -> None:
        if _no_cache():
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self._path_for(key)
            payload = verdict.model_dump() if hasattr(verdict, "model_dump") else verdict.dict()
            path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            # Best-effort: a failed cache write must never fail the triage call.
            pass
