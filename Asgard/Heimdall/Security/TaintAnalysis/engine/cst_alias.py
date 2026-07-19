"""
Per-file import/require alias resolution for the JS/TS/Java CST taint engine
(plan 04 gap: "Import/binding/alias resolution", mirrors the Python
``build_alias_map``/``resolve_chain`` pair in ``services/_taint_visitor.py``).

Without this, ``const cp = require('child_process'); cp.exec(x)`` is
invisible to the catalog (which only matches the literal
``child_process.exec`` chain) and ``import {exec as run} from
'child_process'; run(x)`` is invisible entirely. The alias map produced here
lets the visitor canonicalize a receiver/identifier back to its import
origin before matching sources/sinks/sanitizers, using the SAME
``resolve_chain`` dotted-string algorithm already used by the Python engine
(imported, not reimplemented) -- only the parsing of "what got imported as
what" differs per language/module system.

Cross-file resolution note: for local/relative specifiers (``./helpers``,
``../lib/db``) the alias target is normalized to the specifier's basename
(``helpers``, ``db``) -- NOT the full path -- so that
``Security/TaintAnalysis/summaries.SummaryIndex``-style module-stem lookups
(``Path(file).stem``) resolve cleanly across files without reinventing a
module resolver. Bare package specifiers (``child_process``, ``express``)
are kept as-is since there is no local file to resolve to.

Honest limitations:
- No re-export chasing (``export { q } from './other'`` is not followed).
- CommonJS ``module.exports = {...}`` object literals are not parsed as an
  export surface; only ``require(...)`` call sites (the binding side) are.
- Namespace imports/requires (`import * as ns` / `const ns = require(...)`)
  bind the *whole* module to `ns`; member accesses `ns.member` resolve via
  the shared dotted-chain algorithm at match time, not here.
- Java wildcard imports (``import java.util.*;``) are not expanded (no way
  to know which simple names they introduce without a classpath).
"""

import re
from pathlib import Path
from typing import Dict, NamedTuple, Optional

_JS_LANGS = frozenset({"javascript", "typescript", "tsx"})

_JS_KNOWN_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".tsx")

# Real, well-known sanitizer *packages* (JS) / *packages-or-classes* (Java).
# Sanitizer-verification (promoting a heuristic library sanitizer to a full
# clear) is ONLY permitted when an alias's resolved import origin matches one
# of these -- a relative-path import (``./...``) or any other bare package
# name must stay at the heuristic downgrade, never a full clear. This is the
# fix for the "sanitizer-verification full-clears a no-op imported from ANY
# module" bug: alias-map membership alone (any import/require binding) is not
# sufficient evidence that the callee is a *real* sanitizer.
JS_SANITIZER_ALLOWED_MODULES = frozenset({
    "escape-html", "dompurify", "he", "validator", "sanitize-html", "xss",
})
JAVA_SANITIZER_ALLOWED_MODULES = frozenset({
    "org.owasp.encoder",
    "org.owasp.esapi",
    "org.apache.commons.text",
    "org.apache.commons.lang3",
})


class _WildcardAliasMap(dict):
    """dict that additionally resolves bare, capitalized class-name heads
    through Java wildcard-import packages (``import pkg.*;``) when no
    explicit alias exists. Deterministic: when multiple wildcard packages
    are in scope, the lexicographically-first is used (over-approximation
    is acceptable per plan; never silently drops the possibility)."""

    def __init__(self, wildcard_packages=()):
        super().__init__()
        self._wildcard_packages = sorted(set(wildcard_packages))

    def get(self, key, default=None):
        if key in self:
            return dict.get(self, key)
        if self._wildcard_packages and key and key[0].isupper():
            return f"{self._wildcard_packages[0]}.{key}"
        return default


class _WildcardOriginMap(dict):
    """Origin-map counterpart to ``_WildcardAliasMap``: synthesizes an
    ``AliasOrigin`` for wildcard-resolved class names so sanitizer-origin
    verification also benefits from wildcard expansion."""

    def __init__(self, wildcard_packages=()):
        super().__init__()
        self._wildcard_packages = sorted(set(wildcard_packages))

    def get(self, key, default=None):
        if key in self:
            return dict.get(self, key)
        if self._wildcard_packages and key and key[0].isupper():
            pkg = self._wildcard_packages[0]
            return AliasOrigin(
                target=f"{pkg}.{key}", raw_specifier=f"{pkg}.{key}", is_relative=False
            )
        return default


class AliasOrigin(NamedTuple):
    """Provenance of one alias binding: the normalized target string (used
    for dotted-chain matching) plus enough of the raw specifier to tell a
    genuine external package apart from a relative/local file import -- the
    normalized target alone collapses both shapes (``./evil_local_utils`` and
    a real bare package ``evil_local_utils`` would normalize identically)."""

    target: str
    raw_specifier: str
    is_relative: bool


def module_target(specifier: str) -> str:
    """Normalize an import/require specifier to its alias-map target.

    Relative/local specifiers collapse to their basename (cross-file
    module-stem matching); bare package specifiers are returned unchanged.
    """
    if specifier.startswith(".") or "/" in specifier:
        stem = Path(specifier).stem or specifier
        return stem
    return specifier


# Backwards-compatible private alias (kept in case anything still imports the
# old private name).
_module_target = module_target


def is_verified_sanitizer_origin(raw_specifier: str, is_relative: bool, lang: str) -> bool:
    """True when an alias's raw import specifier is a genuine, allow-listed
    sanitizer package (never true for relative/local specifiers)."""
    if is_relative:
        return False
    allowed = JS_SANITIZER_ALLOWED_MODULES if lang in _JS_LANGS else JAVA_SANITIZER_ALLOWED_MODULES
    if lang in _JS_LANGS:
        return raw_specifier in allowed
    # Java: allow either an exact match or a fully-qualified name rooted at
    # an allow-listed package/class prefix (e.g. "org.owasp.encoder.Encode").
    return any(raw_specifier == pkg or raw_specifier.startswith(pkg + ".") for pkg in allowed)


_JS_NAMESPACE_IMPORT_RE = re.compile(
    r"import\s+\*\s+as\s+([\w$]+)\s+from\s+['\"]([^'\"]+)['\"]"
)
_JS_NAMED_IMPORT_RE = re.compile(
    r"import\s+(?:([\w$]+)\s*,\s*)?\{([^}]*)\}\s*from\s+['\"]([^'\"]+)['\"]"
)
_JS_DEFAULT_IMPORT_RE = re.compile(
    r"import\s+([\w$]+)\s+from\s+['\"]([^'\"]+)['\"]"
)
_JS_SIDE_EFFECT_IMPORT_RE = re.compile(r"import\s+['\"]([^'\"]+)['\"]")

# Matched against a single ``variable_declarator``'s own text (the "const"/
# "let"/"var" keyword belongs to the enclosing ``lexical_declaration`` node,
# not the declarator, and is NOT part of ``ctx.node_text(declarator_node)``)
# -- node-type identification (caller only invokes these on a declarator
# whose RHS is a ``require(...)`` call) already scopes this, so no keyword
# prefix is required here.
_JS_REQUIRE_SIMPLE_RE = re.compile(
    r"^\s*([\w$]+)\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
_JS_REQUIRE_DESTRUCTURE_RE = re.compile(
    r"^\s*\{([^}]*)\}\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)"
)


def _record(aliases: Dict[str, str], origins: Dict[str, "AliasOrigin"],
            alias: str, target: str, raw_specifier: str) -> None:
    aliases[alias] = target
    is_relative = raw_specifier.startswith(".") or "/" in raw_specifier
    origins[alias] = AliasOrigin(target=target, raw_specifier=raw_specifier, is_relative=is_relative)


def _parse_js_import(text: str, aliases: Dict[str, str], origins: Dict[str, "AliasOrigin"]) -> None:
    m = _JS_NAMESPACE_IMPORT_RE.search(text)
    if m:
        _record(aliases, origins, m.group(1), _module_target(m.group(2)), m.group(2))
        return
    m = _JS_NAMED_IMPORT_RE.search(text)
    if m:
        default_name, named, module = m.groups()
        target = _module_target(module)
        if default_name:
            _record(aliases, origins, default_name, target, module)
        for part in named.split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                orig, alias = (p.strip() for p in part.split(" as ", 1))
            else:
                orig = alias = part
            _record(aliases, origins, alias, f"{target}.{orig}", module)
        return
    m = _JS_DEFAULT_IMPORT_RE.search(text)
    if m:
        _record(aliases, origins, m.group(1), _module_target(m.group(2)), m.group(2))
        return
    # Side-effect-only import (`import './foo'`) introduces no binding.


def _parse_js_require(text: str, aliases: Dict[str, str], origins: Dict[str, "AliasOrigin"]) -> None:
    m = _JS_REQUIRE_DESTRUCTURE_RE.search(text)
    if m:
        named, module = m.groups()
        target = _module_target(module)
        for part in named.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                orig, alias = (p.strip() for p in part.split(":", 1))
            else:
                orig = alias = part
            _record(aliases, origins, alias, f"{target}.{orig}", module)
        return
    m = _JS_REQUIRE_SIMPLE_RE.search(text)
    if m:
        _record(aliases, origins, m.group(1), _module_target(m.group(2)), m.group(2))


_JAVA_STATIC_IMPORT_RE = re.compile(r"import\s+static\s+([\w.]+)\.([\w]+)\s*;")
_JAVA_IMPORT_RE = re.compile(r"import\s+([\w.]+)\s*;")


def _parse_java_import(
    text: str, aliases: Dict[str, str], origins: Dict[str, "AliasOrigin"],
    wildcard_packages: Optional[set] = None,
) -> None:
    m = _JAVA_STATIC_IMPORT_RE.search(text)
    if m:
        owner, member = m.groups()
        cls = owner.rsplit(".", 1)[-1]
        _record(aliases, origins, member, f"{cls}.{member}", owner)
        return
    m = _JAVA_IMPORT_RE.search(text)
    if m:
        full = m.group(1)
        simple = full.rsplit(".", 1)[-1]
        if simple != "*":
            _record(aliases, origins, simple, full, full)
        elif wildcard_packages is not None:
            # `import pkg.*;` -- record the package prefix so bare class
            # names used elsewhere in the file resolve to `pkg.ClassName`
            # (see _WildcardAliasMap / _WildcardOriginMap above).
            pkg = full.rsplit(".", 1)[0]
            if pkg:
                wildcard_packages.add(pkg)


def build_cst_alias_map(ctx, lang: str) -> Dict[str, str]:
    """Build the import/require alias table for one parsed CST file.

    Returned map feeds ``Security.TaintAnalysis.services._taint_visitor
    .resolve_chain`` (language-agnostic dotted-chain canonicalization,
    reused as-is rather than reimplemented).
    """
    aliases, _origins = build_cst_alias_map_with_origins(ctx, lang)
    return aliases


def build_cst_alias_map_with_origins(ctx, lang: str):
    """Like ``build_cst_alias_map`` but also returns a parallel
    ``Dict[str, AliasOrigin]`` carrying each binding's raw (unnormalized)
    import specifier and whether it was a relative/local path -- needed to
    tell a genuine external package apart from a relative import that merely
    normalizes to the same-looking bare name (sanitizer-verification
    allow-listing)."""
    wildcard_packages: set = set()
    is_java = lang == "java"
    aliases: Dict[str, str] = _WildcardAliasMap(wildcard_packages) if is_java else {}
    origins: Dict[str, AliasOrigin] = _WildcardOriginMap(wildcard_packages) if is_java else {}
    if ctx is None or ctx.root is None:
        return aliases, origins

    def walk(node) -> None:
        t = node.type
        if lang in _JS_LANGS:
            if t == "import_statement":
                _parse_js_import(ctx.node_text(node), aliases, origins)
                return
            if t == "variable_declarator":
                value = node.child_by_field_name("value")
                if value is not None and value.type == "call_expression":
                    fn = value.child_by_field_name("function")
                    if (
                        fn is not None
                        and fn.type == "identifier"
                        and ctx.node_text(fn) == "require"
                    ):
                        _parse_js_require(ctx.node_text(node), aliases, origins)
                        return
        elif lang == "java":
            if t == "import_declaration":
                _parse_java_import(ctx.node_text(node), aliases, origins, wildcard_packages)
                return
        for child in node.children:
            walk(child)

    walk(ctx.root)
    # wildcard_packages is populated during the walk above; since the
    # _Wildcard*Map instances hold a *reference* to the same set object,
    # re-sort their cached view now that parsing is complete.
    if is_java:
        aliases._wildcard_packages = sorted(wildcard_packages)
        origins._wildcard_packages = sorted(wildcard_packages)
    return aliases, origins
