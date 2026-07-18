"""
Taint sinks with per-entry confidence and keyword-argument semantics.

Sink confidence (DEEPTHINK_03):
    1.0  unambiguous global sink (os.system, eval, cursor.execute)
    0.8  framework pattern (session.execute, render_template, logger.*)
    0.4  generic method name (.execute, .write on an unknown object)

Kwarg rules (evaluated against the actual call node):
    subprocess_shell : shell=True -> confidence 1.0; shell=False -> flow
        dropped (0.0). When ``shell`` is absent, subprocess executes an argv
        array without a shell -- classic shell injection is impossible, but
        argv-level injection (attacker-controlled arguments/binary) remains,
        so the flow is kept at x0.3 (lands in the "possible" bucket) rather
        than either dropped or reported as certain.
    yaml_safe_loader : Loader=SafeLoader/CSafeLoader (or yaml.safe_load) ->
        flow dropped.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintSinkType

SUBPROCESS_NO_SHELL_FACTOR = 0.3


@dataclass(frozen=True)
class SinkSpec:
    """A taint sink pattern with severity (impact) and detection confidence."""
    pattern: str
    sink_type: TaintSinkType
    severity: str
    confidence: float
    kwarg_rule: str = ""            # "", "subprocess_shell", "yaml_safe_loader"
    match_suffix: bool = True       # allow "x.y.<pattern>" suffix matches


SINK_SPECS: Tuple[SinkSpec, ...] = (
    # SQL sinks - CRITICAL severity
    SinkSpec("cursor.execute", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("cursor.executemany", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("session.execute", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.execute", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("connection.execute", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("conn.execute", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("engine.execute", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    # Generic ".execute" on an unknown receiver - generic name, 0.4
    SinkSpec("execute", TaintSinkType.SQL_QUERY, "critical", 0.4),
    # Shell command sinks - CRITICAL severity
    SinkSpec("os.system", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("os.popen", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("subprocess.run", TaintSinkType.SHELL_COMMAND, "critical", 1.0,
             kwarg_rule="subprocess_shell"),
    SinkSpec("subprocess.call", TaintSinkType.SHELL_COMMAND, "critical", 1.0,
             kwarg_rule="subprocess_shell"),
    SinkSpec("subprocess.Popen", TaintSinkType.SHELL_COMMAND, "critical", 1.0,
             kwarg_rule="subprocess_shell"),
    SinkSpec("subprocess.check_output", TaintSinkType.SHELL_COMMAND, "critical", 1.0,
             kwarg_rule="subprocess_shell"),
    SinkSpec("subprocess.check_call", TaintSinkType.SHELL_COMMAND, "critical", 1.0,
             kwarg_rule="subprocess_shell"),
    # Eval/exec/deserialization sinks - CRITICAL severity
    SinkSpec("eval", TaintSinkType.EVAL_EXEC, "critical", 1.0, match_suffix=False),
    SinkSpec("exec", TaintSinkType.EVAL_EXEC, "critical", 1.0, match_suffix=False),
    SinkSpec("yaml.load", TaintSinkType.EVAL_EXEC, "critical", 1.0,
             kwarg_rule="yaml_safe_loader"),
    SinkSpec("pickle.loads", TaintSinkType.EVAL_EXEC, "critical", 1.0),
    SinkSpec("pickle.load", TaintSinkType.EVAL_EXEC, "critical", 1.0),
    # File path sinks - HIGH severity
    SinkSpec("open", TaintSinkType.FILE_PATH, "high", 0.8, match_suffix=False),
    SinkSpec("pathlib.Path", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("Path", TaintSinkType.FILE_PATH, "high", 0.6, match_suffix=False),
    # Template render sinks - HIGH severity
    SinkSpec("render_template", TaintSinkType.TEMPLATE_RENDER, "high", 0.8),
    SinkSpec("template.render", TaintSinkType.TEMPLATE_RENDER, "high", 0.8),
    SinkSpec("jinja2.Template", TaintSinkType.TEMPLATE_RENDER, "high", 0.8),
    SinkSpec("Environment.get_template", TaintSinkType.TEMPLATE_RENDER, "high", 0.8),
    # LDAP sinks - HIGH severity
    SinkSpec("ldap.search", TaintSinkType.LDAP_QUERY, "high", 0.8),
    SinkSpec("ldap.search_s", TaintSinkType.LDAP_QUERY, "high", 0.8),
    SinkSpec("connection.search", TaintSinkType.LDAP_QUERY, "high", 0.4),
    # HTML output sinks - MEDIUM severity
    SinkSpec("render", TaintSinkType.HTML_OUTPUT, "medium", 0.4, match_suffix=False),
    SinkSpec("make_response", TaintSinkType.HTML_OUTPUT, "medium", 0.8),
    # File write sinks - MEDIUM severity (generic method names)
    SinkSpec("write", TaintSinkType.FILE_WRITE, "medium", 0.4),
    SinkSpec("writelines", TaintSinkType.FILE_WRITE, "medium", 0.4),
    # Redirect sinks - MEDIUM severity
    SinkSpec("redirect", TaintSinkType.REDIRECT, "medium", 0.8, match_suffix=False),
    SinkSpec("HttpResponseRedirect", TaintSinkType.REDIRECT, "medium", 0.8),
    # Log output sinks - MEDIUM severity
    SinkSpec("logger.info", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.debug", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.warning", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.error", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logging.info", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logging.debug", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logging.warning", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logging.error", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
)


def lookup_sink(
    chain: str, extra_specs: Sequence[SinkSpec] = ()
) -> Optional[SinkSpec]:
    """
    Match a (alias-resolved) dotted call chain against the sink catalog.

    Longest/most-specific patterns are declared first; suffix matching
    (``mydb.cursor.execute`` -> ``cursor.execute``) applies unless the spec
    opts out (bare builtins like ``eval``).
    """
    for spec in tuple(SINK_SPECS) + tuple(extra_specs):
        if chain == spec.pattern:
            return spec
        if spec.match_suffix and chain.endswith("." + spec.pattern):
            return spec
    return None
