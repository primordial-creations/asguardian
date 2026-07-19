"""
Heimdall Taint Analysis Models

Pydantic models for taint analysis operations and results.

Taint analysis tracks untrusted user input (sources) through code execution
paths to dangerous sinks (SQL queries, shell commands, etc.) to detect
injection vulnerabilities.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TaintSourceType(str, Enum):
    """Types of taint sources (untrusted user input entry points)."""
    HTTP_PARAMETER = "http_parameter"       # request.args, request.form, request.json, request.data, request.GET, request.POST
    PATH_PARAMETER = "path_parameter"       # path variables in FastAPI/Flask/Django routes
    COOKIE = "cookie"                       # request.cookies
    HEADER = "header"                       # request.headers
    ENV_VAR = "env_var"                     # os.environ, os.getenv
    FILE_READ = "file_read"                 # open().read(), file.read()
    DATABASE_READ = "database_read"         # query results that re-enter application
    USER_INPUT = "user_input"               # input() calls
    COMMAND_LINE_ARG = "command_line_arg"   # sys.argv, argparse results


class TaintSinkType(str, Enum):
    """Types of taint sinks (dangerous operations that must not receive untrusted data)."""
    SQL_QUERY = "sql_query"             # cursor.execute, session.execute, db.query
    SHELL_COMMAND = "shell_command"     # os.system, subprocess.run/call/Popen, os.popen
    HTML_OUTPUT = "html_output"         # render_template, return HTML strings
    FILE_WRITE = "file_write"           # open(path, 'w').write, with open as f: f.write
    FILE_PATH = "file_path"             # open(user_path), pathlib.Path(user_input)
    TEMPLATE_RENDER = "template_render" # template.render, jinja2 Environment
    EVAL_EXEC = "eval_exec"             # eval(), exec()
    LDAP_QUERY = "ldap_query"           # ldap search operations
    LOG_OUTPUT = "log_output"           # log.info/debug with user data (log injection)
    REDIRECT = "redirect"               # redirect(url) with user-controlled url
    SSRF = "ssrf"                       # outbound HTTP request (requests.get, fetch, HttpClient) with tainted URL/host
    BUFFER_OVERFLOW = "buffer_overflow" # C: sprintf/strcpy/strcat/gets into a fixed-size buffer with tainted data
    FORMAT_STRING = "format_string"     # C: printf/fprintf/syslog with a tainted (non-literal) format string
    DYNAMIC_CONSTRUCT = "dynamic_construct"  # eval/exec/reflection/dynamic require-import/computed dispatch with a
                                              # non-constant operand -- undecidable statically (WS5); ALWAYS surfaced
                                              # as an explicit needs-review finding rather than silently skipped, even
                                              # when the operand's taint provenance cannot be resolved by the normal
                                              # source/sink pipeline. Never emitted for a statically-constant operand
                                              # (e.g. eval("1+1")).


class TaintFlowStep(BaseModel):
    """A single step in a taint propagation flow."""
    file_path: str = Field(..., description="Path to the file where this step occurs")
    line_number: int = Field(..., description="Line number of this step")
    column: int = Field(0, description="Column offset of this step (0 when unknown)")
    function_name: str = Field(..., description="Name of the enclosing function")
    step_type: str = Field(..., description="Type of step: source, propagation, or sink")
    code_snippet: str = Field("", description="The code snippet at this step")
    variable_name: str = Field("", description="The tainted variable name at this step")

    class Config:
        use_enum_values = True


class SanitizerRecord(BaseModel):
    """A sanitizer encountered along a taint flow (taxonomy, not boolean)."""
    name: str = Field(..., description="Resolved call chain of the sanitizer")
    kind: str = Field(..., description="Sanitizer class: exact or heuristic")
    factor: float = Field(..., ge=0.0, le=1.0, description="Confidence multiplier applied (0.0 would have dropped the flow)")
    line_number: int = Field(0, description="Line where the sanitizer was applied")

    class Config:
        use_enum_values = True


class TaintFlow(BaseModel):
    """A complete taint flow from source to sink.

    ``severity`` encodes impact (blast radius) and ``confidence`` encodes
    detection certainty. They are orthogonal: severity is never diluted by
    uncertainty. ``confidence_bucket`` is the display form (certain /
    probable / possible / unlikely) -- raw probabilities are internal.
    """
    source_type: TaintSourceType = Field(..., description="Type of taint source")
    sink_type: TaintSinkType = Field(..., description="Type of taint sink")
    severity: str = Field(..., description="Severity: critical, high, or medium")
    confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Bayesian-style flow confidence: source x propagator decays x hop decays x sink x context"
    )
    confidence_bucket: str = Field(
        "certain",
        description="Qualitative confidence bucket: certain/probable/possible/unlikely"
    )
    hop_count: int = Field(
        0, ge=0,
        description="Number of inter-procedural hops between source and sink (0 = intra-function)"
    )
    sanitizers_applied: List[SanitizerRecord] = Field(
        default_factory=list,
        description="Sanitizers encountered along the flow, with class and confidence factor"
    )
    source_location: TaintFlowStep = Field(..., description="Location of the taint source")
    sink_location: TaintFlowStep = Field(..., description="Location of the taint sink")
    intermediate_steps: List[TaintFlowStep] = Field(
        default_factory=list,
        description="Intermediate propagation steps between source and sink"
    )
    title: str = Field(..., description="Short title describing the taint flow")
    description: str = Field(..., description="Detailed description of the vulnerability")
    cwe_id: str = Field("", description="CWE ID for this class of vulnerability")
    owasp_category: str = Field("", description="OWASP Top 10 category")
    sanitizers_present: bool = Field(
        False,
        description="Whether a sanitizer was detected in the flow (reduces confidence)"
    )
    origin: str = Field(
        "static",
        description=(
            "Provenance of this finding: 'static' (found by static taint "
            "analysis, the default) or 'runtime' (added from a runtime/IAST "
            "observation with no static counterpart, e.g. a dynamic-dispatch "
            "or reflection path static analysis could not resolve)."
        ),
    )
    confirmed_at_runtime: bool = Field(
        False,
        description=(
            "Whether a runtime observation (see Security/runtime/) matched "
            "this static finding, raising it out of the possible/needs-review "
            "bucket to a runtime-confirmed verdict. Never set False->True "
            "based on absence of an observation -- absence is not evidence "
            "of safety, only of non-observation."
        ),
    )
    runtime_trace_ids: List[str] = Field(
        default_factory=list,
        description="Trace ids of the runtime observation(s) that confirmed this flow, if any",
    )
    finding_class: str = Field(
        "taint_flow",
        description=(
            "'taint_flow' (default: a resolved source->sink flow) or "
            "'dynamic_construct' (WS5: an eval/reflection/dynamic-dispatch "
            "construct was reached; the operand's provenance could not be "
            "proven statically, so this is surfaced as an honest "
            "needs-review finding instead of being silently dropped -- "
            "never treat 'unresolved' as 'safe')."
        ),
    )

    class Config:
        use_enum_values = True


class TaintReport(BaseModel):
    """Report from a taint analysis scan."""
    total_flows: int = Field(0, description="Total taint flows found")
    critical_count: int = Field(0, description="Number of critical severity flows")
    high_count: int = Field(0, description="Number of high severity flows")
    medium_count: int = Field(0, description="Number of medium severity flows")
    flows: List[TaintFlow] = Field(default_factory=list, description="All taint flows found")
    files_analyzed: int = Field(0, description="Number of files analyzed")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_flow(self, flow: TaintFlow) -> None:
        """Add a taint flow to the report."""
        self.total_flows += 1
        self.flows.append(flow)
        if flow.severity == "critical":
            self.critical_count += 1
        elif flow.severity == "high":
            self.high_count += 1
        elif flow.severity == "medium":
            self.medium_count += 1

    @property
    def has_findings(self) -> bool:
        """Check if any taint flows were found."""
        return self.total_flows > 0

    @property
    def is_passing(self) -> bool:
        """Check if the scan passes (no critical or high flows)."""
        return self.critical_count == 0 and self.high_count == 0

    def get_flows_by_severity(self) -> Dict[str, List[TaintFlow]]:
        """Group flows by severity level."""
        result: Dict[str, List[TaintFlow]] = {
            "critical": [],
            "high": [],
            "medium": [],
        }
        for flow in self.flows:
            sev = flow.severity if isinstance(flow.severity, str) else flow.severity
            if sev in result:
                result[sev].append(flow)
        return result

    def get_flows_by_sink(self) -> Dict[str, List[TaintFlow]]:
        """Group flows by sink type."""
        result: Dict[str, List[TaintFlow]] = {}
        for flow in self.flows:
            sink = flow.sink_type if isinstance(flow.sink_type, str) else flow.sink_type
            if sink not in result:
                result[sink] = []
            result[sink].append(flow)
        return result


class TaintConfig(BaseModel):
    """Configuration for taint analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    track_cross_file: bool = Field(True, description="Track taint across file boundaries (best-effort)")
    track_cross_function: bool = Field(True, description="Track taint across function calls within a file")
    min_severity: str = Field("medium", description="Minimum severity to report: critical, high, or medium")
    min_confidence: float = Field(
        0.25, ge=0.0, le=1.0,
        description=(
            "Minimum flow confidence to report. Default 0.25 hides the "
            "'unlikely' bucket (audit-only) while keeping possible/probable/"
            "certain findings visible. Set to 0.0 for audit dashboards."
        ),
    )
    max_hops: int = Field(
        4, ge=0, le=8,
        description="Maximum inter-procedural hops to follow (paths are dropped beyond this depth)"
    )
    summary_cache_path: Optional[Path] = Field(
        None,
        description="Optional SQLite cache for function summaries (e.g. ~/.asgard/taintcache.db). None disables caching."
    )
    framework_stubs: List[str] = Field(
        default_factory=lambda: ["flask", "django", "fastapi", "sqlalchemy"],
        description="Framework stub models to load (YAML files under TaintAnalysis/stubs/)"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "test_*",
            "*_test.py",
            "tests",
        ],
        description="Patterns to exclude from scanning"
    )
    custom_sources: List[str] = Field(
        default_factory=list,
        description="Additional source function/attribute names to treat as taint sources"
    )
    custom_sinks: List[str] = Field(
        default_factory=list,
        description="Additional sink function/attribute names to treat as taint sinks"
    )
    custom_sanitizers: List[str] = Field(
        default_factory=list,
        description="Additional sanitizer function names that remove taint"
    )

    class Config:
        use_enum_values = True
