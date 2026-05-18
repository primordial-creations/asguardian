"""File integrity checker — baseline creation and verification via cryptographic hashes."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Security.FileIntegrity.models.file_integrity_models import (
    FileIntegrityReport,
    FileModification,
    FileRecord,
    PermissionChange,
)

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
_SKIP_EXTS = {".pyc", ".pyo", ".so", ".dylib", ".o"}


class FileIntegrityChecker:
    """Creates and verifies file integrity baselines using MD5 and SHA-256 hashes."""

    def __init__(self, baseline_file: str = ".file_integrity_baseline.json") -> None:
        self.baseline_file = Path(baseline_file)
        self._baseline: Dict[str, FileRecord] = {}

    # ── public API ─────────────────────────────────────────────────────────────

    def create_baseline(self, directory: Path, patterns: Optional[List[str]] = None) -> int:
        self._baseline = self._scan_directory(directory, patterns)
        self._save_baseline()
        return len(self._baseline)

    def verify_integrity(self, directory: Path, patterns: Optional[List[str]] = None) -> FileIntegrityReport:
        if not self._load_baseline():
            raise FileNotFoundError(f"No baseline found at {self.baseline_file}. Run create_baseline() first.")

        current = self._scan_directory(directory, patterns)
        now = datetime.now().isoformat()
        report = FileIntegrityReport(
            verified_at=now,
            total_baseline_files=len(self._baseline),
            total_current_files=len(current),
        )

        for path, baseline_rec in self._baseline.items():
            if path in current:
                cur = current[path]
                if cur.sha256 != baseline_rec.sha256:
                    report.modified.append(FileModification(
                        path=path,
                        old_hash=baseline_rec.sha256[:16] + "...",
                        new_hash=cur.sha256[:16] + "...",
                        old_size=baseline_rec.size,
                        new_size=cur.size,
                    ))
                elif cur.permissions != baseline_rec.permissions:
                    report.permission_changes.append(PermissionChange(
                        path=path,
                        old_perms=baseline_rec.permissions,
                        new_perms=cur.permissions,
                    ))
                else:
                    report.ok_count += 1
            else:
                report.deleted.append({"path": path, "size": baseline_rec.size})

        for path, rec in current.items():
            if path not in self._baseline:
                report.added.append({"path": path, "size": rec.size})

        return report

    def hash_file(self, file_path: Path) -> Optional[FileRecord]:
        return self._get_record(file_path)

    # ── private helpers ────────────────────────────────────────────────────────

    def _scan_directory(self, directory: Path, patterns: Optional[List[str]] = None) -> Dict[str, FileRecord]:
        records: Dict[str, FileRecord] = {}
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for name in files:
                fp = Path(root) / name
                if fp.suffix in _SKIP_EXTS:
                    continue
                if patterns and not any(fp.match(p) for p in patterns):
                    continue
                rec = self._get_record(fp)
                if rec:
                    records[rec.path] = rec
        return records

    def _get_record(self, file_path: Path) -> Optional[FileRecord]:
        try:
            stat = file_path.stat()
            md5_h = hashlib.md5()
            sha256_h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5_h.update(chunk)
                    sha256_h.update(chunk)
            return FileRecord(
                path=str(file_path.absolute()),
                size=stat.st_size,
                md5=md5_h.hexdigest(),
                sha256=sha256_h.hexdigest(),
                modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                permissions=oct(stat.st_mode)[-3:],
            )
        except OSError:
            return None

    def _save_baseline(self) -> None:
        data = {
            "created": datetime.now().isoformat(),
            "files": {path: rec.model_dump() for path, rec in self._baseline.items()},
        }
        self.baseline_file.write_text(json.dumps(data, indent=2))

    def _load_baseline(self) -> bool:
        if not self.baseline_file.exists():
            return False
        try:
            data = json.loads(self.baseline_file.read_text())
            self._baseline = {path: FileRecord(**rec) for path, rec in data["files"].items()}
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False
