"""Source, propagator, and sink regex catalogues per language.

Each catalogue entry is a dict with:
  sources: list[str]      — patterns that introduce taint; capture group 1 is the variable name
  propagators: list[str]  — patterns that carry taint from RHS to LHS
  sinks: list[str]        — patterns whose arguments must not be tainted
  sanitizers: list[str]   — function names that break the taint chain
"""

_COMMON_SANITIZERS = [
    "escape", "sanitize", "quote", "htmlspecialchars", "encode",
    "validate", "strip_tags", "clean", "purify", "filter",
]

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

_PYTHON_SOURCES = [
    r"(\w+)\s*=\s*request\.GET\.get\s*\(",
    r"(\w+)\s*=\s*request\.POST\.get\s*\(",
    r"(\w+)\s*=\s*request\.GET\s*\[",
    r"(\w+)\s*=\s*request\.POST\s*\[",
    r"(\w+)\s*=\s*request\.args\.get\s*\(",
    r"(\w+)\s*=\s*request\.args\s*\[",
    r"(\w+)\s*=\s*request\.form\.get\s*\(",
    r"(\w+)\s*=\s*request\.form\s*\[",
    r"(\w+)\s*=\s*request\.data",
    r"(\w+)\s*=\s*request\.json",
    r"(\w+)\s*=\s*input\s*\(",
    r"(\w+)\s*=\s*os\.environ\.get\s*\(",
    r"(\w+)\s*=\s*os\.getenv\s*\(",
    r"(\w+)\s*=\s*sys\.argv\s*\[",
    r"(\w+)\s*=\s*os\.args\s*\[",
    r"(\w+)\s*=\s*params\s*\[",
    r"(\w+)\s*=\s*kwargs\s*\[",
]

_PYTHON_PROPAGATORS = [
    r"(\w+)\s*=\s*.*(\w+)",
    r"(\w+)\s*=\s*f['\"].*\{(\w+)\}",
    r"(\w+)\s*=\s*['\"].*['\"\s]*\+\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\s*\+",
    r"(\w+)\s*=\s*(?:str|repr|format)\s*\(\s*(\w+)",
    r"(\w+)\s*=\s*\S+\.format\s*\(",
    r"(\w+)\s*\+=\s*(\w+)",
]

_PYTHON_SINKS = [
    r"cursor\.execute\s*\(\s*(\w+)",
    r"db\.execute\s*\(\s*(\w+)",
    r"conn\.execute\s*\(\s*(\w+)",
    r"execute\s*\(\s*(\w+)",
    r"raw\s*\(\s*(\w+)",
    r"eval\s*\(\s*(\w+)",
    r"exec\s*\(\s*(\w+)",
    r"os\.system\s*\(\s*(\w+)",
    r"subprocess\.\w+\s*\(\s*(\w+)",
    r"open\s*\(\s*(\w+)",
    r"render_template_string\s*\(\s*(\w+)",
    r"Markup\s*\(\s*(\w+)",
    r"pickle\.loads\s*\(\s*(\w+)",
    r"yaml\.load\s*\(\s*(\w+)",
    r"print\s*\(\s*(\w+)",
    r"(?:response\.write|HttpResponse)\s*\(\s*(\w+)",
]

# ---------------------------------------------------------------------------
# JavaScript / TypeScript (shared)
# ---------------------------------------------------------------------------

_JS_SOURCES = [
    r"(?:const|let|var)\s+(\w+)\s*=\s*req\.query\b",
    r"(?:const|let|var)\s+(\w+)\s*=\s*req\.body\b",
    r"(?:const|let|var)\s+(\w+)\s*=\s*req\.params\b",
    r"(?:const|let|var)\s+(\w+)\s*=\s*request\.query\b",
    r"(?:const|let|var)\s+(\w+)\s*=\s*request\.body\b",
    r"(?:const|let|var)\s+(\w+)\s*=\s*process\.argv\s*\[",
    r"(?:const|let|var)\s+(\w+)\s*=\s*process\.env\.",
    r"(\w+)\s*=\s*req\.query\b",
    r"(\w+)\s*=\s*req\.body\b",
    r"(\w+)\s*=\s*req\.params\b",
    r"(\w+)\s*=\s*event\.target\.value",
    r"(\w+)\s*=\s*document\.getElementById\s*\(",
    r"(\w+)\s*=\s*location\.search",
    r"(\w+)\s*=\s*location\.hash",
    r"(\w+)\s*=\s*URLSearchParams",
]

_JS_PROPAGATORS = [
    r"(?:const|let|var)\s+(\w+)\s*=\s*.*(\w+)",
    r"(\w+)\s*=\s*`[^`]*\$\{(\w+)\}",
    r"(\w+)\s*=\s*(\w+)\s*\+",
    r"(\w+)\s*\+=\s*(\w+)",
    r"(\w+)\s*=\s*`.*\$\{(\w+)\}",
    r"(\w+)\s*=\s*String\s*\(\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\.toString\s*\(",
]

_JS_SINKS = [
    r"(?:res|response)\.send\s*\(\s*[^)]*(\w+)",
    r"(?:res|response)\.json\s*\(\s*[^)]*(\w+)",
    r"(?:res|response)\.write\s*\(\s*[^)]*(\w+)",
    r"document\.write\s*\(\s*[^)]*(\w+)",
    r"\.innerHTML\s*=\s*[^;]*(\w+)",
    r"\.outerHTML\s*=\s*[^;]*(\w+)",
    r"eval\s*\(\s*(\w+)",
    r"db\.query\s*\(\s*[^)]*(\w+)",
    r"pool\.query\s*\(\s*[^)]*(\w+)",
    r"connection\.query\s*\(\s*[^)]*(\w+)",
    r"exec(?:Sync)?\s*\(\s*[^)]*(\w+)",
    r"spawnSync?\s*\(\s*[^)]*(\w+)",
    r"fs\.\w+\s*\(\s*(\w+)",
    r"require\s*\(\s*(\w+)",
]

# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

_JAVA_SOURCES = [
    r"(\w+)\s*=\s*request\.getParameter\s*\(",
    r"(\w+)\s*=\s*request\.getHeader\s*\(",
    r"(\w+)\s*=\s*request\.getAttribute\s*\(",
    r"(\w+)\s*=\s*request\.getQueryString\s*\(",
    r"(\w+)\s*=\s*System\.getenv\s*\(",
    r"(\w+)\s*=\s*System\.getProperty\s*\(",
    r"(\w+)\s*=\s*args\s*\[",
]

_JAVA_PROPAGATORS = [
    r"(\w+)\s*=\s*.*\+\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\s*\+",
    r"(\w+)\s*=\s*String\.format\s*\(",
    r"(\w+)\s*=\s*new StringBuilder\s*\(",
    r"(\w+)\.append\s*\(\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\.toString\s*\(",
]

_JAVA_SINKS = [
    r"Statement\s*\.\s*execute(?:Query|Update)?\s*\(\s*(\w+)",
    r"prepareStatement\s*\(\s*(\w+)",
    r"createQuery\s*\(\s*(\w+)",
    r"Runtime\.getRuntime\(\)\.exec\s*\(\s*(\w+)",
    r"ProcessBuilder\s*\(\s*(\w+)",
    r"out\.print(?:ln)?\s*\(\s*(\w+)",
    r"response\.getWriter\(\)\.(?:print|write)\s*\(\s*(\w+)",
    r"ObjectInputStream",
    r"new\s+FileInputStream\s*\(\s*(\w+)",
    r"Files\.\w+\s*\(\s*(?:Paths\.get\s*\(\s*)?(\w+)",
]

# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

_GO_SOURCES = [
    r"(\w+)\s*:?=\s*r\.URL\.Query\(\)\.",
    r"(\w+)\s*:?=\s*r\.FormValue\s*\(",
    r"(\w+)\s*:?=\s*r\.PostFormValue\s*\(",
    r"(\w+)\s*:?=\s*r\.Header\.Get\s*\(",
    r"(\w+)\s*:?=\s*os\.Args\s*\[",
    r"(\w+)\s*:?=\s*os\.Getenv\s*\(",
    r"(\w+)\s*:?=\s*mux\.Vars\s*\(",
]

_GO_PROPAGATORS = [
    r"(\w+)\s*:?=\s*.*\+\s*(\w+)",
    r"(\w+)\s*:?=\s*(\w+)\s*\+",
    r"(\w+)\s*:?=\s*fmt\.Sprintf\s*\(",
    r"(\w+)\s*:?=\s*strings\.Join\s*\(",
    r"(\w+)\s*\+=\s*(\w+)",
]

_GO_SINKS = [
    r"db\.(?:Query|Exec)\s*\(\s*(\w+)",
    r"sql\.(?:Query|Exec)\s*\(\s*(\w+)",
    r"fmt\.Fprintf\s*\(\s*\w+\s*,\s*(\w+)",
    r"fmt\.Fprint(?:ln)?\s*\(\s*\w+\s*,\s*(\w+)",
    r"exec\.Command\s*\(\s*(\w+)",
    r"os\.Open\s*\(\s*(\w+)",
    r"ioutil\.ReadFile\s*\(\s*(\w+)",
    r"os\.ReadFile\s*\(\s*(\w+)",
    r"template\.HTML\s*\(\s*(\w+)",
]

# ---------------------------------------------------------------------------
# Ruby
# ---------------------------------------------------------------------------

_RUBY_SOURCES = [
    r"(\w+)\s*=\s*params\s*\[",
    r"(\w+)\s*=\s*request\.params\s*\[",
    r"(\w+)\s*=\s*request\.GET\s*\[",
    r"(\w+)\s*=\s*request\.POST\s*\[",
    r"(\w+)\s*=\s*ENV\s*\[",
    r"(\w+)\s*=\s*ARGV\s*\[",
]

_RUBY_PROPAGATORS = [
    r"(\w+)\s*=\s*.*\+\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\s*\+",
    r"(\w+)\s*=\s*\"[^\"]*#\{(\w+)\}",
    r"(\w+)\s*=\s*'[^']*'\s*\+\s*(\w+)",
    r"(\w+)\s*\+=\s*(\w+)",
    r"(\w+)\s*=\s*\".*%s.*\"\s*%\s*(\w+)",
]

_RUBY_SINKS = [
    r"ActiveRecord::Base\.(?:find_by_sql|connection\.execute)\s*\(\s*(\w+)",
    r"\.where\s*\(\s*(\w+)",
    r"\.find_by_sql\s*\(\s*(\w+)",
    r"system\s*\(\s*(\w+)",
    r"%x\s*\{\s*(\w+)",
    r"eval\s*\(\s*(\w+)",
    r"render\s+(?:inline|html):\s*(\w+)",
    r"File\.(?:open|read)\s*\(\s*(\w+)",
    r"send\s*\(\s*(\w+)",
]

# ---------------------------------------------------------------------------
# PHP
# ---------------------------------------------------------------------------

_PHP_SOURCES = [
    r"(\$\w+)\s*=\s*\$_GET\s*\[",
    r"(\$\w+)\s*=\s*\$_POST\s*\[",
    r"(\$\w+)\s*=\s*\$_REQUEST\s*\[",
    r"(\$\w+)\s*=\s*\$_COOKIE\s*\[",
    r"(\$\w+)\s*=\s*\$_SERVER\s*\[",
    r"(\$\w+)\s*=\s*\$_FILES\s*\[",
    r"(\$\w+)\s*=\s*\$_ENV\s*\[",
    r"(\$\w+)\s*=\s*getenv\s*\(",
]

_PHP_PROPAGATORS = [
    r"(\$\w+)\s*=\s*.*\.\s*(\$\w+)",
    r"(\$\w+)\s*=\s*(\$\w+)\s*\.",
    r"(\$\w+)\s*\.=\s*(\$\w+)",
    r"(\$\w+)\s*=\s*(\$\w+)\s*\+",
    r"(\$\w+)\s*=\s*sprintf\s*\(",
    r"(\$\w+)\s*=\s*\"[^\"]*\$(\w+)",
    r"(\$\w+)\s*=\s*'[^']*'\s*\.\s*(\$\w+)",
]

_PHP_SINKS = [
    r"mysql_query\s*\(\s*(\$\w+)",
    r"mysqli_query\s*\(\s*\w+\s*,\s*(\$\w+)",
    r"\$\w+->query\s*\(\s*(\$\w+)",
    r"\$\w+->execute\s*\(\s*(\$\w+)",
    r"pg_query\s*\(\s*(?:\w+\s*,\s*)?(\$\w+)",
    r"echo\s+(\$\w+)",
    r"print\s+(\$\w+)",
    r"print_r\s*\(\s*(\$\w+)",
    r"eval\s*\(\s*(\$\w+)",
    r"system\s*\(\s*(\$\w+)",
    r"exec\s*\(\s*(\$\w+)",
    r"passthru\s*\(\s*(\$\w+)",
    r"shell_exec\s*\(\s*(\$\w+)",
    r"include\s*\(\s*(\$\w+)",
    r"require\s*\(\s*(\$\w+)",
    r"file_get_contents\s*\(\s*(\$\w+)",
    r"unserialize\s*\(\s*(\$\w+)",
    r"header\s*\(\s*(\$\w+)",
]

# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------

_CSHARP_SOURCES = [
    r"(\w+)\s*=\s*Request\s*\[",
    r"(\w+)\s*=\s*Request\.QueryString\s*\[",
    r"(\w+)\s*=\s*Request\.Form\s*\[",
    r"(\w+)\s*=\s*Request\.Params\s*\[",
    r"(\w+)\s*=\s*Request\.Headers\s*\[",
    r"(\w+)\s*=\s*Environment\.GetEnvironmentVariable\s*\(",
    r"(\w+)\s*=\s*args\s*\[",
    r"(\w+)\s*=\s*Console\.ReadLine\s*\(",
]

_CSHARP_PROPAGATORS = [
    r"(\w+)\s*=\s*.*\+\s*(\w+)",
    r"(\w+)\s*=\s*(\w+)\s*\+",
    r"(\w+)\s*=\s*string\.Format\s*\(",
    r"(\w+)\s*=\s*\$\"[^\"]*\{(\w+)\}",
    r"(\w+)\s*=\s*(\w+)\.ToString\s*\(",
    r"(\w+)\s*\+=\s*(\w+)",
]

_CSHARP_SINKS = [
    r"SqlCommand\s*\(\s*(\w+)",
    r"ExecuteNonQuery\s*\(",
    r"ExecuteReader\s*\(",
    r"new\s+SqlCommand\s*\(\s*(\w+)",
    r"Process\.Start\s*\(\s*(\w+)",
    r"Response\.Write\s*\(\s*(\w+)",
    r"Response\.Output\.Write\s*\(\s*(\w+)",
    r"File\.\w+\s*\(\s*(\w+)",
    r"BinaryFormatter\s*\(",
    r"JsonConvert\.DeserializeObject\s*\(\s*(\w+)",
    r"XmlSerializer",
    r"eval\s*\(\s*(\w+)",
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CATALOGUES: dict[str, dict] = {
    "python": {
        "sources": _PYTHON_SOURCES,
        "propagators": _PYTHON_PROPAGATORS,
        "sinks": _PYTHON_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "javascript": {
        "sources": _JS_SOURCES,
        "propagators": _JS_PROPAGATORS,
        "sinks": _JS_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "typescript": {
        "sources": _JS_SOURCES,
        "propagators": _JS_PROPAGATORS,
        "sinks": _JS_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "java": {
        "sources": _JAVA_SOURCES,
        "propagators": _JAVA_PROPAGATORS,
        "sinks": _JAVA_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "go": {
        "sources": _GO_SOURCES,
        "propagators": _GO_PROPAGATORS,
        "sinks": _GO_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "ruby": {
        "sources": _RUBY_SOURCES,
        "propagators": _RUBY_PROPAGATORS,
        "sinks": _RUBY_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "php": {
        "sources": _PHP_SOURCES,
        "propagators": _PHP_PROPAGATORS,
        "sinks": _PHP_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
    "csharp": {
        "sources": _CSHARP_SOURCES,
        "propagators": _CSHARP_PROPAGATORS,
        "sinks": _CSHARP_SINKS,
        "sanitizers": _COMMON_SANITIZERS,
    },
}
