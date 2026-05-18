"""Pydantic models for DNS security checking."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DNSCheckStatus(str):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class DNSIssue(BaseModel):
    severity: str
    issue_type: str
    description: str


class DNSCheck(BaseModel):
    name: str
    status: str
    description: str
    value: Optional[str] = None
    note: Optional[str] = None


class DNSScanReport(BaseModel):
    domain: str
    timestamp: str
    records: Dict[str, List[str]] = Field(default_factory=dict)
    security_checks: List[DNSCheck] = Field(default_factory=list)
    issues: List[DNSIssue] = Field(default_factory=list)
    score: int = 100

    @property
    def rating(self) -> str:
        if self.score >= 90:
            return "A"
        if self.score >= 75:
            return "B"
        if self.score >= 60:
            return "C"
        if self.score >= 40:
            return "D"
        return "F"
