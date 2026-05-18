"""API security scanner — detects vulnerabilities in REST and GraphQL API code."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.API.models.api_models import (
    APIFinding,
    APIScanConfig,
    APIScanReport,
    APISecurityCategory,
    APISeverity,
)

_API_FILE_INDICATORS = {"route", "controller", "api", "endpoint", "handler", "resolver"}
_CODE_EXTENSIONS = {".js", ".ts", ".py", ".rb", ".java", ".go", ".php"}

_VULNERABILITY_PATTERNS: dict = {
    "authentication": [
        ("r'@(?:app\\.route|router\\.(?:get|post|put|delete)|Get|Post|Put|Delete)\\s*\\([^)]+\\)(?!.*(?:auth|login|jwt|token|bearer))'", "MEDIUM", "no_auth_check", "API endpoint may lack authentication", "Add authentication middleware"),
        (r"(?:api|endpoint|route).*(?:public|open|unauth)", "LOW", "public_endpoint", "Explicitly public endpoint", "Verify endpoint should be public"),
    ],
    "authorization": [
        (r"(?:user_id|userId|user\.id)\s*=\s*(?:req\.|request\.|params\.|body\.)", "HIGH", "idor", "Potential IDOR - user ID from request", "Use authenticated user ID from session/token"),
        (r"(?:findById|find_by_id|get)\s*\(\s*(?:req\.|request\.|params\.)", "MEDIUM", "direct_object_ref", "Direct object reference from user input", "Verify user has access to resource"),
        (r"(?:admin|role|permission)\s*(?:=|:)\s*(?:req\.|request\.|params\.)", "CRITICAL", "privilege_escalation", "Role/permission from user input", "Never trust client-supplied roles"),
    ],
    "mass_assignment": [
        (r"(?:create|update|save)\s*\(\s*(?:req\.body|request\.body|params)", "HIGH", "mass_assignment", "Mass assignment vulnerability", "Whitelist allowed fields explicitly"),
        (r"Object\.assign\s*\([^,]+,\s*(?:req\.body|request\.body)", "HIGH", "object_assign_body", "Direct object assignment from request body", "Pick specific allowed fields"),
        (r"\{\s*\.\.\.\s*(?:req\.body|request\.body|params)", "HIGH", "spread_body", "Spread operator with request body", "Destructure only allowed fields"),
    ],
    "rate_limiting": [
        (r"@(?:app\.route|router)\s*\([^)]*(?:login|auth|password|reset|signup|register)", "MEDIUM", "auth_no_ratelimit", "Auth endpoint may lack rate limiting", "Add rate limiting to prevent brute force"),
    ],
    "data_exposure": [
        (r"(?:res\.json|response\.json|send)\s*\(\s*(?:user|account|profile)(?!\s*\.\s*(?:toJSON|select|pick))", "MEDIUM", "excessive_data", "May expose excessive user data", "Select only necessary fields"),
        (r"(?:password|secret|token|ssn|credit).*(?:res\.json|response\.send)", "CRITICAL", "sensitive_response", "Sensitive data in API response", "Never return sensitive data in responses"),
        (r"\.select\s*\(\s*['\"]\\*['\"]", "MEDIUM", "select_all", "Selecting all fields from database", "Select only required fields"),
    ],
    "graphql": [
        (r"introspection\s*:\s*true", "MEDIUM", "graphql_introspection", "GraphQL introspection enabled", "Disable in production"),
        (r"(?:depthLimit|queryComplexity)\s*:\s*(?:null|undefined|false)", "HIGH", "graphql_no_limits", "GraphQL without query limits", "Set depth and complexity limits"),
        (r"@(?:Query|Mutation)\s*\([^)]*\)(?!.*@(?:Auth|Authorized|Guard))", "MEDIUM", "graphql_no_auth", "GraphQL resolver without auth", "Add authorization guards"),
    ],
    "input_validation": [
        (r"(?:req\.body|req\.query|req\.params)\s*\.\s*\w+(?!\s*\.\s*(?:validate|sanitize|trim|escape))", "LOW", "no_validation", "Input used without visible validation", "Validate and sanitize all input"),
    ],
    "error_handling": [
        (r"catch\s*\([^)]*\)\s*\{[^}]*(?:res\.json|send)\s*\(\s*(?:err|error)", "MEDIUM", "error_disclosure", "Raw error sent to client", "Return generic error messages"),
        (r"stack.*(?:res\.|response\.)", "HIGH", "stack_trace_exposure", "Stack trace exposed to client", "Never expose stack traces"),
    ],
    "cors": [
        (r"(?:cors|Access-Control-Allow-Origin).*(?:\*|true)", "MEDIUM", "cors_permissive", "Permissive CORS configuration", "Whitelist specific origins"),
        (r"Access-Control-Allow-Credentials.*true.*Access-Control-Allow-Origin.*(?:req\.|origin)", "HIGH", "cors_credentials_dynamic", "CORS credentials with dynamic origin", "Validate origin against whitelist"),
    ],
    "versioning": [
        (r"(?:app|router)\.(?:get|post|put|delete)\s*\(\s*['\"][^'\"]*(?<!/v\d)(?<!api/v)", "LOW", "no_api_versioning", "API endpoint without versioning", "Version APIs (e.g., /api/v1/)"),
    ],
    "file_upload": [
        (r"(?:multer|upload|formidable)(?!.*(?:fileFilter|limits|allowedTypes))", "HIGH", "unsafe_upload", "File upload without restrictions", "Validate file type, size, and name"),
        (r"(?:filename|originalname).*(?:path\.join|writeFile)", "HIGH", "path_traversal_upload", "Original filename in path (traversal risk)", "Generate safe filenames"),
    ],
}


def _is_api_file(file_path: Path) -> bool:
    stem = file_path.stem.lower()
    if any(ind in stem for ind in _API_FILE_INDICATORS):
        return True
    return file_path.suffix.lower() in _CODE_EXTENSIONS


class APISecurityScanner:
    """Scans source code for API security vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _VULNERABILITY_PATTERNS.items():
            self._compiled[category] = []
            for pattern, severity, ptype, desc, rec in patterns:
                try:
                    self._compiled[category].append(
                        (re.compile(pattern, re.IGNORECASE), severity, ptype, desc, rec)
                    )
                except re.error:
                    pass

    def scan(self, config: APIScanConfig) -> APIScanReport:
        findings: List[APIFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            file_findings = self._scan_file(target)
            findings.extend(file_findings)
            files_scanned = 1 if file_findings or _is_api_file(target) else 0
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    if not _is_api_file(fp):
                        continue
                    ff = self._scan_file(fp)
                    findings.extend(ff)
                    files_scanned += 1

        by_severity: dict = {}
        by_category: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category.value] = by_category.get(f.category.value, 0) + 1

        return APIScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[APIFinding]:
        findings: List[APIFinding] = []
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return findings

        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, severity, ptype, desc, rec in patterns:
                    if regex.search(line):
                        findings.append(
                            APIFinding(
                                file_path=str(file_path),
                                line_number=line_num,
                                severity=APISeverity(severity),
                                category=APISecurityCategory(category),
                                pattern_type=ptype,
                                code_snippet=line.strip()[:150],
                                description=desc,
                                recommendation=rec,
                            )
                        )
        return findings
