"""
Heimdall AST Hotspot Checks

AST-based detection for the six hotspot families (plan 08 Part A) on
Python source. Each check flags only *syntactically flawless* code whose
safety depends on extrinsic context; anything provable stays with the
taint/finding pipeline (never rerouted here).

Removed cop-outs (rerouted per plan 08): REGEX_DOS -> ReDoS analyzer,
SSRF -> SSRF pipeline, PERMISSION_CHECK -> dropped, XXE -> AST kwarg
finding, generic CRYPTO_CODE import flag -> only weak-hash calls and
cryptography.hazmat remain, DYNAMIC_EXECUTION / COOKIE_CONFIG -> finding
pipelines.
"""

import ast
from typing import List, Optional

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    HotspotConfig,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)

_WEAK_HASH_CALLS = ("hashlib.md5", "hashlib.sha1")
_PRNG_SECURITY_ADJACENT = (
    "random.random", "random.randint", "random.randrange", "random.choice",
    "random.choices", "random.getrandbits", "random.sample", "random.uniform",
    "random.randbytes", "random.shuffle",
)
_UNVERIFIED_CONTEXT_CALLS = (
    "ssl._create_unverified_context",
)
_OPAQUE_DESER_CALLS = (
    "pickle.loads", "pickle.load", "cPickle.loads", "cPickle.load",
    "marshal.loads", "marshal.load",
    "shelve.open",
    "dill.loads", "dill.load",
)


def _kwarg(node: ast.Call, name: str) -> Optional[ast.expr]:
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_const(node: Optional[ast.expr], value) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _attr_str(node: Optional[ast.expr]) -> str:
    """Dotted-name string for a Name/Attribute expression ('' otherwise)."""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _hotspot(
    file_path: str,
    line: int,
    category: HotspotCategory,
    priority: ReviewPriority,
    title: str,
    description: str,
    snippet: str,
    guidance: str,
    owasp: str,
    cwe: str,
) -> SecurityHotspot:
    return SecurityHotspot(
        file_path=file_path,
        line_number=line,
        category=category,
        review_priority=priority,
        title=title,
        description=description,
        code_snippet=snippet,
        review_guidance=guidance,
        review_status=ReviewStatus.TO_REVIEW,
        owasp_category=owasp,
        cwe_id=cwe,
    )


def detect_ast_hotspots(
    tree: ast.AST,
    file_path: str,
    lines: List[str],
    config: HotspotConfig,
    get_line_fn,
    get_call_name_fn,
) -> List[SecurityHotspot]:
    """Detect the six hotspot families via Python AST analysis."""
    hotspots: List[SecurityHotspot] = []
    enabled = set(config.enabled_categories)

    for node in ast.walk(tree):
        # --- Family 1: weak hashing (business-domain question) ------------
        if HotspotCategory.WEAK_HASHING in enabled and isinstance(node, ast.Call):
            func_name = get_call_name_fn(node)
            if func_name in _WEAK_HASH_CALLS:
                # usedforsecurity=False is an explicit non-security
                # declaration: the extrinsic question is answered.
                if not _is_const(_kwarg(node, "usedforsecurity"), False):
                    algo = func_name.split(".")[-1].upper()
                    hotspots.append(_hotspot(
                        file_path, node.lineno,
                        HotspotCategory.WEAK_HASHING, ReviewPriority.MEDIUM,
                        f"Weak hash algorithm: {func_name}()",
                        (
                            f"{algo} is broken for security purposes but fine for "
                            "checksums/dedup. Whether this usage is security-"
                            "sensitive is a business-domain question."
                        ),
                        get_line_fn(lines, node.lineno),
                        (
                            "If used for passwords, signatures, or integrity of "
                            "untrusted data, replace with SHA-256+ (or bcrypt/argon2 "
                            "for passwords). If non-security, annotate with "
                            "usedforsecurity=False."
                        ),
                        "A02:Cryptographic Failures", "CWE-328",
                    ))

        # --- Family 2: standard PRNG (intent question) ---------------------
        if HotspotCategory.STANDARD_PRNG in enabled and isinstance(node, ast.Call):
            func_name = get_call_name_fn(node)
            if func_name in _PRNG_SECURITY_ADJACENT:
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.STANDARD_PRNG, ReviewPriority.LOW,
                    f"Standard PRNG usage: {func_name}()",
                    (
                        "The 'random' module is not cryptographically secure. "
                        "Whether that matters depends on intent (simulation vs "
                        "token generation) — taint analysis upgrades proven "
                        "security-sink flows to findings."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "If the value feeds tokens, passwords, session IDs, or "
                        "any security decision, use the 'secrets' module."
                    ),
                    "A02:Cryptographic Failures", "CWE-338",
                ))

        # --- Family 3: disabled transport security (topology question) -----
        if HotspotCategory.DISABLED_TLS in enabled and isinstance(node, ast.Call):
            func_name = get_call_name_fn(node)
            if func_name in _UNVERIFIED_CONTEXT_CALLS or _is_const(_kwarg(node, "verify"), False):
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.DISABLED_TLS, ReviewPriority.HIGH,
                    "TLS certificate verification disabled",
                    (
                        "Certificate verification is disabled. Whether this is "
                        "acceptable depends on network topology (e.g. a pinned "
                        "internal endpoint vs the open internet)."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "Enable verification or pin a CA bundle "
                        "(verify='/path/to/ca.crt'). Never disable verification "
                        "for internet-facing endpoints."
                    ),
                    "A02:Cryptographic Failures", "CWE-295",
                ))

        # --- Family 4: permissive bindings / CORS (deployment question) ----
        if HotspotCategory.PERMISSIVE_BINDING in enabled and isinstance(node, ast.Call):
            host = _kwarg(node, "host")
            if _is_const(host, "0.0.0.0") or (
                node.args and _is_const(node.args[0], "0.0.0.0")
            ):
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.PERMISSIVE_BINDING, ReviewPriority.MEDIUM,
                    "Service bound to all interfaces (0.0.0.0)",
                    (
                        "Binding to 0.0.0.0 exposes the service on every "
                        "interface. Safety depends on the deployment topology "
                        "(container-internal vs edge host)."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "Bind to 127.0.0.1 unless external exposure is intended "
                        "and fronted by appropriate network controls."
                    ),
                    "A05:Security Misconfiguration", "CWE-1327",
                ))
            allow_origins = _kwarg(node, "allow_origins")
            wildcard = False
            if isinstance(allow_origins, (ast.List, ast.Tuple)):
                wildcard = any(_is_const(el, "*") for el in allow_origins.elts)
            elif _is_const(allow_origins, "*"):
                wildcard = True
            if wildcard:
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.PERMISSIVE_BINDING, ReviewPriority.MEDIUM,
                    "CORS configured with wildcard origin",
                    (
                        "allow_origins=['*'] permits any site to call this API. "
                        "Acceptability depends on whether the API is public and "
                        "credential-free (deployment question)."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "Restrict origins to an explicit allow-list unless the "
                        "API is intentionally public and unauthenticated."
                    ),
                    "A05:Security Misconfiguration", "CWE-942",
                ))

        # --- Family 5: opaque deserialization (provenance question) --------
        if HotspotCategory.OPAQUE_DESERIALIZATION in enabled and isinstance(node, ast.Call):
            func_name = get_call_name_fn(node)
            if func_name in _OPAQUE_DESER_CALLS:
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.OPAQUE_DESERIALIZATION, ReviewPriority.HIGH,
                    f"Opaque deserialization: {func_name}()",
                    (
                        f"'{func_name}()' executes arbitrary code when fed "
                        "attacker-controlled bytes. Static analysis cannot prove "
                        "the data's provenance; only a human can."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "Confirm the data source is fully trusted and tamper-"
                        "proof; prefer JSON or another data-only format for "
                        "anything crossing a trust boundary."
                    ),
                    "A08:Software and Data Integrity Failures", "CWE-502",
                ))
            elif func_name == "yaml.load":
                loader = _kwarg(node, "Loader")
                if "Safe" not in _attr_str(loader):
                    hotspots.append(_hotspot(
                        file_path, node.lineno,
                        HotspotCategory.OPAQUE_DESERIALIZATION, ReviewPriority.HIGH,
                        "yaml.load() without SafeLoader",
                        (
                            "yaml.load without SafeLoader can instantiate "
                            "arbitrary Python objects. Safety depends entirely on "
                            "the provenance of the YAML input."
                        ),
                        get_line_fn(lines, node.lineno),
                        (
                            "Use yaml.safe_load() or Loader=yaml.SafeLoader "
                            "unless object construction from trusted input is "
                            "explicitly required."
                        ),
                        "A08:Software and Data Integrity Failures", "CWE-502",
                    ))

        # --- Family 6: cryptography.hazmat (soundness review) --------------
        if HotspotCategory.HAZMAT_CRYPTO in enabled:
            module_name = ""
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("cryptography.hazmat"):
                        module_name = alias.name
                        break
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("cryptography.hazmat"):
                    module_name = node.module
            if module_name:
                hotspots.append(_hotspot(
                    file_path, node.lineno,
                    HotspotCategory.HAZMAT_CRYPTO, ReviewPriority.MEDIUM,
                    f"Low-level crypto primitive usage: {module_name}",
                    (
                        "cryptography.hazmat primitives are correct only when "
                        "composed correctly (modes, IVs, padding, key handling). "
                        "Mathematical soundness requires expert review."
                    ),
                    get_line_fn(lines, node.lineno),
                    (
                        "Prefer the high-level recipes layer (Fernet) where "
                        "possible; otherwise have the construction reviewed "
                        "against current cryptographic guidance."
                    ),
                    "A02:Cryptographic Failures", "CWE-327",
                ))

    return hotspots
