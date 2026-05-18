"""Pydantic models for security log analysis."""

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class LogEvent(BaseModel):
    file_path: str
    line_number: int
    timestamp: str = ""
    event_type: str
    severity: str
    description: str
    raw_line: str = ""
    source_ip: str = ""


class LogAnalysisReport(BaseModel):
    total_events: int = 0
    lines_analyzed: int = 0
    events: List[LogEvent] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    top_ips: List[Tuple[str, int]] = Field(default_factory=list)
