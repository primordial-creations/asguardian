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
    # SSRF sinks - HIGH severity: tainted URL/host reaching an outbound
    # HTTP request. First-argument-only (the URL), see _FIRST_ARG_SINKS in
    # the CST visitor / equivalent Python-side handling in _taint_visitor.py.
    SinkSpec("requests.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("requests.post", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("requests.put", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("requests.delete", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("requests.request", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("requests.Session.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("session.get", TaintSinkType.SSRF, "high", 0.4),
    SinkSpec("urllib.request.urlopen", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("urlopen", TaintSinkType.SSRF, "high", 0.6, match_suffix=False),
    SinkSpec("urllib2.urlopen", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("httpx.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("httpx.post", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("httpx.Client.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("aiohttp.ClientSession.get", TaintSinkType.SSRF, "high", 0.8),
)


# --------------------------------------------------------------------------
# JavaScript / TypeScript (Express/Node) -- DEEPTHINK_04 top-level catalogue.
# --------------------------------------------------------------------------
JS_SINK_SPECS: Tuple[SinkSpec, ...] = (
    # SQL sinks
    SinkSpec("connection.query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("pool.query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("knex.raw", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("sequelize.query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("query", TaintSinkType.SQL_QUERY, "critical", 0.4),
    # Command injection
    SinkSpec("child_process.exec", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("child_process.execSync", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("child_process.spawn", TaintSinkType.SHELL_COMMAND, "critical", 0.8),
    SinkSpec("exec", TaintSinkType.SHELL_COMMAND, "critical", 0.6, match_suffix=False),
    SinkSpec("execSync", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    # Eval / dynamic code
    SinkSpec("eval", TaintSinkType.EVAL_EXEC, "critical", 1.0, match_suffix=False),
    SinkSpec("Function", TaintSinkType.EVAL_EXEC, "critical", 0.8, match_suffix=False),
    SinkSpec("setTimeout", TaintSinkType.EVAL_EXEC, "medium", 0.4, match_suffix=False),
    SinkSpec("setInterval", TaintSinkType.EVAL_EXEC, "medium", 0.4, match_suffix=False),
    SinkSpec("vm.runInNewContext", TaintSinkType.EVAL_EXEC, "critical", 1.0),
    # XSS / DOM
    SinkSpec("innerHTML", TaintSinkType.HTML_OUTPUT, "high", 0.8, match_suffix=False),
    SinkSpec("outerHTML", TaintSinkType.HTML_OUTPUT, "high", 0.8, match_suffix=False),
    SinkSpec("document.write", TaintSinkType.HTML_OUTPUT, "high", 0.8),
    SinkSpec("insertAdjacentHTML", TaintSinkType.HTML_OUTPUT, "high", 0.8),
    SinkSpec("res.send", TaintSinkType.HTML_OUTPUT, "medium", 0.6),
    SinkSpec("res.write", TaintSinkType.HTML_OUTPUT, "medium", 0.6),
    SinkSpec("dangerouslySetInnerHTML", TaintSinkType.HTML_OUTPUT, "high", 0.8),
    # File path
    SinkSpec("fs.readFile", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("fs.readFileSync", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("fs.writeFile", TaintSinkType.FILE_WRITE, "medium", 0.8),
    SinkSpec("fs.writeFileSync", TaintSinkType.FILE_WRITE, "medium", 0.8),
    # Redirect
    SinkSpec("res.redirect", TaintSinkType.REDIRECT, "medium", 0.8),
    # Log
    SinkSpec("console.log", TaintSinkType.LOG_OUTPUT, "medium", 0.4),
    SinkSpec("logger.info", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.warn", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.error", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    # SSRF sinks
    SinkSpec("fetch", TaintSinkType.SSRF, "high", 0.8, match_suffix=False),
    SinkSpec("axios.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("axios.post", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("axios.request", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("axios", TaintSinkType.SSRF, "high", 0.6, match_suffix=False),
    SinkSpec("http.request", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("https.request", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("http.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("https.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("got", TaintSinkType.SSRF, "high", 0.6, match_suffix=False),
    SinkSpec("request", TaintSinkType.SSRF, "high", 0.4, match_suffix=False),
)

# --------------------------------------------------------------------------
# Java (Servlet/Spring) -- DEEPTHINK_04 top-level catalogue.
# --------------------------------------------------------------------------
JAVA_SINK_SPECS: Tuple[SinkSpec, ...] = (
    SinkSpec("Statement.execute", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("statement.execute", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("statement.executeQuery", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("statement.executeUpdate", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("stmt.executeQuery", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("stmt.executeUpdate", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("stmt.execute", TaintSinkType.SQL_QUERY, "critical", 1.0),
    SinkSpec("createQuery", TaintSinkType.SQL_QUERY, "critical", 0.6, match_suffix=False),
    SinkSpec("createNativeQuery", TaintSinkType.SQL_QUERY, "critical", 0.8, match_suffix=False),
    SinkSpec("executeQuery", TaintSinkType.SQL_QUERY, "critical", 0.4),
    SinkSpec("executeUpdate", TaintSinkType.SQL_QUERY, "critical", 0.4),
    SinkSpec("Runtime.exec", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("runtime.exec", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    # Covers the common Runtime.getRuntime().exec(...) chained-call idiom,
    # which resolves to "Runtime.getRuntime.exec" (not a suffix of the
    # exact "Runtime.exec" pattern above) -- generic name, lower confidence.
    SinkSpec("exec", TaintSinkType.SHELL_COMMAND, "critical", 0.6),
    SinkSpec("ProcessBuilder", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("response.getWriter", TaintSinkType.HTML_OUTPUT, "medium", 0.4, match_suffix=False),
    SinkSpec("out.println", TaintSinkType.HTML_OUTPUT, "medium", 0.4),
    SinkSpec("FileWriter", TaintSinkType.FILE_WRITE, "medium", 0.6, match_suffix=False),
    SinkSpec("FileOutputStream", TaintSinkType.FILE_WRITE, "medium", 0.6, match_suffix=False),
    SinkSpec("Files.newInputStream", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("File", TaintSinkType.FILE_PATH, "high", 0.4, match_suffix=False),
    SinkSpec("response.sendRedirect", TaintSinkType.REDIRECT, "medium", 0.8),
    SinkSpec("logger.info", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.debug", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.warn", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("logger.error", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("log.info", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    SinkSpec("log.error", TaintSinkType.LOG_OUTPUT, "medium", 0.8),
    # SSRF sinks
    SinkSpec("HttpClient.send", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("client.send", TaintSinkType.SSRF, "high", 0.4),
    SinkSpec("URL.openConnection", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("url.openConnection", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("URL.openStream", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("RestTemplate.getForObject", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("restTemplate.getForObject", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("RestTemplate.postForObject", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("restTemplate.postForObject", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("WebClient.get", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("HttpGet", TaintSinkType.SSRF, "high", 0.6, match_suffix=False),
    SinkSpec("HttpPost", TaintSinkType.SSRF, "high", 0.6, match_suffix=False),
)


# --------------------------------------------------------------------------
# Go (net/http, os/exec, database/sql) -- plan 04 multi-language extension.
# --------------------------------------------------------------------------
GO_SINK_SPECS: Tuple[SinkSpec, ...] = (
    # SQL sinks
    SinkSpec("db.Query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.QueryContext", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.QueryRow", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.QueryRowContext", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.Exec", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("db.ExecContext", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("tx.Query", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("tx.Exec", TaintSinkType.SQL_QUERY, "critical", 0.8),
    SinkSpec("Query", TaintSinkType.SQL_QUERY, "critical", 0.4, match_suffix=False),
    SinkSpec("Exec", TaintSinkType.SQL_QUERY, "critical", 0.4, match_suffix=False),
    # Command injection
    SinkSpec("exec.Command", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    SinkSpec("exec.CommandContext", TaintSinkType.SHELL_COMMAND, "critical", 1.0),
    # Path traversal / file access
    SinkSpec("os.Open", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("os.OpenFile", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("os.Create", TaintSinkType.FILE_PATH, "high", 0.6),
    SinkSpec("ioutil.ReadFile", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("os.ReadFile", TaintSinkType.FILE_PATH, "high", 0.8),
    SinkSpec("ioutil.WriteFile", TaintSinkType.FILE_WRITE, "medium", 0.6),
    SinkSpec("os.WriteFile", TaintSinkType.FILE_WRITE, "medium", 0.6),
    # XSS / HTML output
    SinkSpec("template.HTML", TaintSinkType.HTML_OUTPUT, "high", 0.8, match_suffix=False),
    SinkSpec("w.Write", TaintSinkType.HTML_OUTPUT, "medium", 0.4),
    SinkSpec("Fprintf", TaintSinkType.HTML_OUTPUT, "medium", 0.4, match_suffix=False),
    # Redirect
    SinkSpec("http.Redirect", TaintSinkType.REDIRECT, "medium", 0.8),
    # Log
    SinkSpec("log.Printf", TaintSinkType.LOG_OUTPUT, "medium", 0.4),
    SinkSpec("log.Println", TaintSinkType.LOG_OUTPUT, "medium", 0.4),
    # SSRF -- tainted URL reaching an outbound HTTP client call
    SinkSpec("http.Get", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("http.Post", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("http.PostForm", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("http.Head", TaintSinkType.SSRF, "high", 1.0),
    SinkSpec("http.NewRequest", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("http.NewRequestWithContext", TaintSinkType.SSRF, "high", 0.8),
    SinkSpec("client.Get", TaintSinkType.SSRF, "high", 0.4),
    SinkSpec("client.Do", TaintSinkType.SSRF, "high", 0.4),
)


# --------------------------------------------------------------------------
# C (libc) -- bounded first pass, intra-procedural only.  No pointer-aliasing
# or memory-layout modeling: a buffer passed through several pointer hops
# before reaching sprintf/strcpy will not be tracked (false-negative,
# documented).  All patterns are bare identifiers (C has no method-call
# receiver syntax), hence ``match_suffix=False`` throughout.
# --------------------------------------------------------------------------
C_SINK_SPECS: Tuple[SinkSpec, ...] = (
    # Shell / process sinks - CRITICAL severity
    SinkSpec("system", TaintSinkType.SHELL_COMMAND, "critical", 1.0, match_suffix=False),
    SinkSpec("popen", TaintSinkType.SHELL_COMMAND, "critical", 1.0, match_suffix=False),
    SinkSpec("execl", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("execlp", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("execle", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("execv", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("execvp", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    SinkSpec("execve", TaintSinkType.SHELL_COMMAND, "critical", 0.8, match_suffix=False),
    # Buffer overflow sinks - CRITICAL severity: tainted data copied into a
    # fixed-size buffer with no bounds check.
    SinkSpec("strcpy", TaintSinkType.BUFFER_OVERFLOW, "critical", 1.0, match_suffix=False),
    SinkSpec("strcat", TaintSinkType.BUFFER_OVERFLOW, "critical", 1.0, match_suffix=False),
    SinkSpec("sprintf", TaintSinkType.BUFFER_OVERFLOW, "critical", 1.0, match_suffix=False),
    SinkSpec("vsprintf", TaintSinkType.BUFFER_OVERFLOW, "critical", 0.8, match_suffix=False),
    SinkSpec("gets", TaintSinkType.BUFFER_OVERFLOW, "critical", 1.0, match_suffix=False),
    # Format string sinks - HIGH severity: tainted value used AS the format
    # string itself (not merely as an argument to a fixed format string).
    SinkSpec("printf", TaintSinkType.FORMAT_STRING, "high", 0.6, match_suffix=False),
    SinkSpec("fprintf", TaintSinkType.FORMAT_STRING, "high", 0.6, match_suffix=False),
    SinkSpec("snprintf", TaintSinkType.FORMAT_STRING, "high", 0.4, match_suffix=False),
    SinkSpec("syslog", TaintSinkType.FORMAT_STRING, "high", 0.6, match_suffix=False),
    # Path traversal / file access - HIGH severity
    SinkSpec("fopen", TaintSinkType.FILE_PATH, "high", 0.8, match_suffix=False),
    SinkSpec("open", TaintSinkType.FILE_PATH, "high", 0.6, match_suffix=False),
    SinkSpec("freopen", TaintSinkType.FILE_PATH, "high", 0.6, match_suffix=False),
    SinkSpec("unlink", TaintSinkType.FILE_PATH, "high", 0.6, match_suffix=False),
    SinkSpec("remove", TaintSinkType.FILE_PATH, "high", 0.6, match_suffix=False),
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
