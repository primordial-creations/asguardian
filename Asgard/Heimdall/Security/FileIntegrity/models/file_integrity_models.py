"""Pydantic models for file integrity checking."""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FileRecord(BaseModel):
    path: str
    size: int
    md5: str
    sha256: str
    modified_time: str
    permissions: str


class FileModification(BaseModel):
    path: str
    old_hash: str
    new_hash: str
    old_size: int
    new_size: int


class PermissionChange(BaseModel):
    path: str
    old_perms: str
    new_perms: str


class FileIntegrityReport(BaseModel):
    verified_at: str
    total_baseline_files: int = 0
    total_current_files: int = 0
    modified: List[FileModification] = Field(default_factory=list)
    added: List[Dict] = Field(default_factory=list)
    deleted: List[Dict] = Field(default_factory=list)
    permission_changes: List[PermissionChange] = Field(default_factory=list)
    ok_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.modified or self.deleted)
