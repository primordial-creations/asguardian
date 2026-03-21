"""
Heimdall Taint Analysis Patterns

Constants defining taint sources, sinks, sanitizers, and their metadata.
"""

from typing import Dict, List, Set, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintSinkType,
    TaintSourceType,
)


# --- Source pattern definitions ---

# Mapping: attribute access patterns -> TaintSourceType
SOURCE_PATTERNS: List[Tuple[str, TaintSourceType]] = [
    # HTTP parameters
    ("request.args", TaintSourceType.HTTP_PARAMETER),
    ("request.form", TaintSourceType.HTTP_PARAMETER),
    ("request.json", TaintSourceType.HTTP_PARAMETER),
    ("request.data", TaintSourceType.HTTP_PARAMETER),
    ("request.GET", TaintSourceType.HTTP_PARAMETER),
    ("request.POST", TaintSourceType.HTTP_PARAMETER),
    ("request.values", TaintSourceType.HTTP_PARAMETER),
    ("request.params", TaintSourceType.HTTP_PARAMETER),
    # Cookies
    ("request.cookies", TaintSourceType.COOKIE),
    # Headers
    ("request.headers", TaintSourceType.HEADER),
    # Environment variables
    ("os.environ", TaintSourceType.ENV_VAR),
    ("os.getenv", TaintSourceType.ENV_VAR),
    ("environ.get", TaintSourceType.ENV_VAR),
    # User input
    ("input", TaintSourceType.USER_INPUT),
    # Command line args
    ("sys.argv", TaintSourceType.COMMAND_LINE_ARG),
    ("args.parse_args", TaintSourceType.COMMAND_LINE_ARG),
    ("parser.parse_args", TaintSourceType.COMMAND_LINE_ARG),
    ("argparse.parse_args", TaintSourceType.COMMAND_LINE_ARG),
]

# Source function names (single-name calls, not attribute access)
SOURCE_CALL_NAMES: Dict[str, TaintSourceType] = {
    "input": TaintSourceType.USER_INPUT,
}

# --- Sink pattern definitions ---

# Mapping: function/method call patterns -> (TaintSinkType, severity)
SINK_PATTERNS: Dict[str, Tuple[TaintSinkType, str]] = {
    # SQL sinks - CRITICAL
    "cursor.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "cursor.executemany": (TaintSinkType.SQL_QUERY, "critical"),
    "session.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "db.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "connection.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "conn.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "engine.execute": (TaintSinkType.SQL_QUERY, "critical"),
    "db.query": (TaintSinkType.SQL_QUERY, "critical"),
    # Shell command sinks - CRITICAL
    "os.system": (TaintSinkType.SHELL_COMMAND, "critical"),
    "os.popen": (TaintSinkType.SHELL_COMMAND, "critical"),
    "subprocess.run": (TaintSinkType.SHELL_COMMAND, "critical"),
    "subprocess.call": (TaintSinkType.SHELL_COMMAND, "critical"),
    "subprocess.Popen": (TaintSinkType.SHELL_COMMAND, "critical"),
    "subprocess.check_output": (TaintSinkType.SHELL_COMMAND, "critical"),
    "subprocess.check_call": (TaintSinkType.SHELL_COMMAND, "critical"),
    # Eval/Exec sinks - CRITICAL
    "eval": (TaintSinkType.EVAL_EXEC, "critical"),
    "exec": (TaintSinkType.EVAL_EXEC, "critical"),
    # File path sinks - HIGH
    "open": (TaintSinkType.FILE_PATH, "high"),
    "pathlib.Path": (TaintSinkType.FILE_PATH, "high"),
    "Path": (TaintSinkType.FILE_PATH, "high"),
    # Template render sinks - HIGH
    "render_template": (TaintSinkType.TEMPLATE_RENDER, "high"),
    "template.render": (TaintSinkType.TEMPLATE_RENDER, "high"),
    "jinja2.Template": (TaintSinkType.TEMPLATE_RENDER, "high"),
    "Environment.get_template": (TaintSinkType.TEMPLATE_RENDER, "high"),
    # LDAP sinks - HIGH
    "ldap.search": (TaintSinkType.LDAP_QUERY, "high"),
    "ldap.search_s": (TaintSinkType.LDAP_QUERY, "high"),
    "connection.search": (TaintSinkType.LDAP_QUERY, "high"),
    # HTML output sinks - MEDIUM
    "render": (TaintSinkType.HTML_OUTPUT, "medium"),
    "make_response": (TaintSinkType.HTML_OUTPUT, "medium"),
    # File write sinks - MEDIUM
    "write": (TaintSinkType.FILE_WRITE, "medium"),
    "writelines": (TaintSinkType.FILE_WRITE, "medium"),
    # Redirect sinks - MEDIUM
    "redirect": (TaintSinkType.REDIRECT, "medium"),
    "HttpResponseRedirect": (TaintSinkType.REDIRECT, "medium"),
    # Log output sinks - MEDIUM
    "logger.info": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logger.debug": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logger.warning": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logger.error": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logging.info": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logging.debug": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logging.warning": (TaintSinkType.LOG_OUTPUT, "medium"),
    "logging.error": (TaintSinkType.LOG_OUTPUT, "medium"),
}

# Sanitizer function names that remove taint
SANITIZER_NAMES: Set[str] = {
    # SQL sanitizers
    "sql.escape",
    "escape_string",
    "quote_plus",
    "escape",
    "sanitize",
    "sanitize_sql",
    "parameterize",
    # HTML sanitizers
    "html.escape",
    "escape_html",
    "bleach.clean",
    "clean",
    "markupsafe.escape",
    "Markup.escape",
    # Shell sanitizers
    "shlex.quote",
    "quote",
    "escape_shell",
    # General sanitizers
    "validate",
    "validate_input",
    "sanitize_input",
    "clean_input",
}

# Severity mapping
SINK_SEVERITY: Dict[TaintSinkType, str] = {
    TaintSinkType.SQL_QUERY: "critical",
    TaintSinkType.SHELL_COMMAND: "critical",
    TaintSinkType.EVAL_EXEC: "critical",
    TaintSinkType.FILE_PATH: "high",
    TaintSinkType.TEMPLATE_RENDER: "high",
    TaintSinkType.LDAP_QUERY: "high",
    TaintSinkType.HTML_OUTPUT: "medium",
    TaintSinkType.FILE_WRITE: "medium",
    TaintSinkType.LOG_OUTPUT: "medium",
    TaintSinkType.REDIRECT: "medium",
}

# CWE and OWASP mappings for each sink type
SINK_CWE: Dict[TaintSinkType, str] = {
    TaintSinkType.SQL_QUERY: "CWE-89",
    TaintSinkType.SHELL_COMMAND: "CWE-78",
    TaintSinkType.HTML_OUTPUT: "CWE-79",
    TaintSinkType.FILE_WRITE: "CWE-73",
    TaintSinkType.FILE_PATH: "CWE-22",
    TaintSinkType.TEMPLATE_RENDER: "CWE-94",
    TaintSinkType.EVAL_EXEC: "CWE-95",
    TaintSinkType.LDAP_QUERY: "CWE-90",
    TaintSinkType.LOG_OUTPUT: "CWE-117",
    TaintSinkType.REDIRECT: "CWE-601",
}

SINK_OWASP: Dict[TaintSinkType, str] = {
    TaintSinkType.SQL_QUERY: "A03:2021",
    TaintSinkType.SHELL_COMMAND: "A03:2021",
    TaintSinkType.HTML_OUTPUT: "A03:2021",
    TaintSinkType.FILE_WRITE: "A01:2021",
    TaintSinkType.FILE_PATH: "A01:2021",
    TaintSinkType.TEMPLATE_RENDER: "A03:2021",
    TaintSinkType.EVAL_EXEC: "A03:2021",
    TaintSinkType.LDAP_QUERY: "A03:2021",
    TaintSinkType.LOG_OUTPUT: "A09:2021",
    TaintSinkType.REDIRECT: "A01:2021",
}

SINK_TITLES: Dict[TaintSinkType, str] = {
    TaintSinkType.SQL_QUERY: "SQL Injection",
    TaintSinkType.SHELL_COMMAND: "Command Injection",
    TaintSinkType.HTML_OUTPUT: "Cross-Site Scripting (XSS)",
    TaintSinkType.FILE_WRITE: "Tainted File Write",
    TaintSinkType.FILE_PATH: "Path Traversal",
    TaintSinkType.TEMPLATE_RENDER: "Server-Side Template Injection",
    TaintSinkType.EVAL_EXEC: "Code Injection via eval/exec",
    TaintSinkType.LDAP_QUERY: "LDAP Injection",
    TaintSinkType.LOG_OUTPUT: "Log Injection",
    TaintSinkType.REDIRECT: "Open Redirect",
}
