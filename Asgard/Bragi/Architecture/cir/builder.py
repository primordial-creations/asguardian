"""Build the CIR (:mod:`.models`) from a tree-sitter parse tree.

Per ``_Docs/Planning/Heimdall/02_SOLID_Detection.md`` the target architecture
is a single ``extract.scm`` query per language whose captures are assembled
into the CIR by a shared byte-range-containment algorithm.  This
implementation reaches the same language-agnostic *output* (one
:class:`~Asgard.Bragi.Architecture.cir.models.FileInfo` per file, built from
tree-sitter captures only — no raw-text/regex fallback lives here) via a
thin per-language capture layer, because each grammar's node shapes for
"method belongs to this class" and "receiver-qualified field access" are not
uniform enough to share one generic walk without per-language field names.
Adding a language means adding one entry to ``_LANG_HANDLERS`` — the CIR
model and every downstream evaluator/metric are unchanged.

Supported languages today: python, java, javascript, typescript.  Others
return ``None`` and callers fall back to the regex engine.
"""
from typing import Callable, Dict, List, Optional, Set

from Asgard.Heimdall.treesitter._language_loader import get_language_object, is_available
from Asgard.Heimdall.treesitter._parser_pool import parse_source
from Asgard.Heimdall.treesitter._query_runner import _query_captures, node_text

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo, MethodInfo

_UNIMPLEMENTED_MARKERS = {
    "NotImplementedError", "NotImplemented", "NotSupportedException",
    "UnsupportedOperationException", "panic",
}


def build_file_cir(file_path: str, source: str, language: str) -> Optional[FileInfo]:
    """Return the :class:`FileInfo` CIR for *source*, or ``None`` on failure.

    Returns ``None`` when tree-sitter/the language binding is unavailable,
    the parse fails, or no handler exists yet for *language* — callers
    should fall back to the regex engine in that case.
    """
    handler = _LANG_HANDLERS.get(language)
    if handler is None or not is_available(language):
        return None

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    if root is None:
        return None

    lang_obj = get_language_object(language)
    if lang_obj is None:
        return None

    try:
        classes = handler(root, source_bytes, lang_obj, file_path)
    except Exception:
        return None

    return FileInfo(filepath=file_path, language=language, classes=classes)


def _query(lang_obj, query_str: str):
    try:
        from tree_sitter import Query  # noqa: PLC0415
        return Query(lang_obj, query_str)
    except Exception:
        return None


def _captures_dict(query, node) -> Dict[str, list]:
    """Normalize ``_query_captures`` output to ``{name: [Node, ...]}``."""
    if query is None or node is None:
        return {}
    raw = _query_captures(query, node)
    out: Dict[str, list] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[k] = v if isinstance(v, list) else [v]
    elif isinstance(raw, list):
        for n, name in raw:
            out.setdefault(name, []).append(n)
    return out


def _text(node, source_bytes: bytes) -> str:
    return node_text(node, source_bytes)


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

_PY_METHOD_Q = "(function_definition name: (identifier) @m.name) @m.def"
_PY_ATTR_Q = "(attribute object: (identifier) @a.obj attribute: (identifier) @a.field) @a.expr"
_PY_CALL_Q = "(call function: (identifier) @c.name) @c.expr"
_PY_METHOD_CALL_Q = "(call function: (attribute object: (identifier) @mc.obj attribute: (identifier) @mc.name)) @mc.expr"
_PY_CLASS_Q = "(class_definition name: (identifier) @cls.name) @cls.def"
_PY_RAISE_Q = "(raise_statement (call function: (identifier) @exc.name)) @raise"
_PY_RAISE_BARE_Q = "(raise_statement (identifier) @exc.name) @raise"


def _walk(node, type_name: str, out: list, stop_types: Optional[Set[str]] = None) -> None:
    """Collect all descendants of *type_name*, not descending past nested
    class/function bodies of the same kind (used to keep per-class method
    lists from bleeding into nested classes)."""
    for child in node.children:
        if child.type == type_name:
            out.append(child)
        if stop_types and child.type in stop_types and child.type != type_name:
            continue
        _walk(child, type_name, out, stop_types)


def _build_python(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_q = _query(lang_obj, _PY_CLASS_Q)
    class_nodes: list = []
    _walk(root, "class_definition", class_nodes)

    classes: List[ClassInfo] = []
    for cnode in class_nodes:
        name_node = next((c for c in cnode.children if c.type == "identifier"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        bases_text = ""
        for c in cnode.children:
            if c.type == "argument_list":
                bases_text = _text(c, source_bytes)
        is_abc = "ABC" in bases_text or "Protocol" in bases_text
        implements = {b.strip() for b in bases_text.strip("()").split(",") if b.strip()}

        # Direct child methods only (skip methods of nested classes).
        body = next((c for c in cnode.children if c.type == "block"), cnode)
        method_nodes: list = []
        for c in body.children:
            if c.type == "function_definition":
                method_nodes.append(c)
            elif c.type == "decorated_definition":
                inner = next((g for g in c.children if g.type == "function_definition"), None)
                if inner is not None:
                    method_nodes.append((c, inner))

        methods: List[MethodInfo] = []
        fields: Set[str] = set()

        for entry in method_nodes:
            decorated_node = None
            if isinstance(entry, tuple):
                decorated_node, mnode = entry
            else:
                mnode = entry
            mname_node = next((c for c in mnode.children if c.type == "identifier"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"

            decorators_text = _text(decorated_node, source_bytes) if decorated_node else ""
            is_abstract = "abstractmethod" in decorators_text
            is_override = "override" in decorators_text

            body_node = next((c for c in mnode.children if c.type == "block"), None)
            statements = [c for c in body_node.children if c.type not in ("comment",)] if body_node else []
            is_empty = body_node is None or all(
                s.type in ("pass_statement", "comment", "ellipsis", "expression_statement")
                and _text(s, source_bytes).strip() in ("pass", "...", '"""..."""')
                for s in statements
            ) or (len(statements) == 0)

            throws_unimpl = False
            raise_q = _query(lang_obj, _PY_RAISE_Q)
            raise_bare_q = _query(lang_obj, _PY_RAISE_BARE_Q)
            for q in (raise_q, raise_bare_q):
                caps = _captures_dict(q, mnode)
                for n in caps.get("exc.name", []):
                    if _text(n, source_bytes) in _UNIMPLEMENTED_MARKERS:
                        throws_unimpl = True

            attr_caps = _captures_dict(_query(lang_obj, _PY_ATTR_Q), mnode)
            field_accesses: Set[str] = set()
            for obj_n, field_n in zip(attr_caps.get("a.obj", []), attr_caps.get("a.field", [])):
                if _text(obj_n, source_bytes) == "self":
                    field_accesses.add(_text(field_n, source_bytes))
                    fields.add(_text(field_n, source_bytes))

            call_caps = _captures_dict(_query(lang_obj, _PY_CALL_Q), mnode)
            calls = {_text(n, source_bytes) for n in call_caps.get("c.name", [])}
            instantiations = {c for c in calls if c and c[0].isupper()}

            mcall_caps = _captures_dict(_query(lang_obj, _PY_METHOD_CALL_Q), mnode)
            method_calls: Set[str] = set()
            for obj_n, mc_n in zip(mcall_caps.get("mc.obj", []), mcall_caps.get("mc.name", [])):
                if _text(obj_n, source_bytes) == "self":
                    method_calls.add(_text(mc_n, source_bytes))

            params_node = next((c for c in mnode.children if c.type == "parameters"), None)
            param_count = max(0, len(params_node.children) - 3) if params_node else 0  # rough: minus ( self ,

            methods.append(MethodInfo(
                name=mname,
                start_line=mnode.start_point[0] + 1,
                end_line=mnode.end_point[0] + 1,
                is_override=is_override,
                is_empty=is_empty,
                throws_unimplemented=throws_unimpl,
                is_abstract=is_abstract,
                is_public=not mname.startswith("_"),
                all_identifiers=field_accesses | calls | method_calls,
                field_accesses=field_accesses,
                method_calls=method_calls,
                instantiations=instantiations,
                param_count=param_count,
            ))

        classes.append(ClassInfo(
            name=cls_name,
            filepath=file_path,
            start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1,
            language="python",
            is_interface=is_abc,
            is_abstract=is_abc,
            fields=fields,
            methods=methods,
            implements=implements,
        ))

    # Second pass: infer is_override when a method name is also declared on
    # a locally-defined base class (no @override decorator in Python, so
    # this is the only same-file signal available; cross-file bases are
    # intentionally left unresolved -- precision over recall).
    by_name = {c.name: c for c in classes}
    for cls in classes:
        base_method_names: Set[str] = set()
        for base in cls.implements:
            base_cls = by_name.get(base)
            if base_cls is not None:
                base_method_names |= base_cls.method_names()
        if base_method_names:
            for m in cls.methods:
                if m.name in base_method_names:
                    m.is_override = True

    return classes


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

def _build_java(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class_declaration", class_nodes)
    iface_nodes: list = []
    _walk(root, "interface_declaration", iface_nodes)

    classes: List[ClassInfo] = []
    for cnode, is_iface in [(n, False) for n in class_nodes] + [(n, True) for n in iface_nodes]:
        name_node = next((c for c in cnode.children if c.type == "identifier"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        for c in cnode.children:
            if c.type in ("super_interfaces", "extends_interfaces"):
                iface_list_caps = _captures_dict(_query(lang_obj, "(type_identifier) @t"), c)
                implements |= {_text(n, source_bytes) for n in iface_list_caps.get("t", [])}

        body = next((c for c in cnode.children if c.type in ("class_body", "interface_body")), cnode)
        method_nodes = [c for c in body.children if c.type == "method_declaration"]
        field_nodes = [c for c in body.children if c.type == "field_declaration"]

        fields: Set[str] = set()
        for fnode in field_nodes:
            decl_caps = _captures_dict(_query(lang_obj, "(variable_declarator name: (identifier) @f)"), fnode)
            fields |= {_text(n, source_bytes) for n in decl_caps.get("f", [])}

        method_names_all = set()
        for m in method_nodes:
            mn = next((c for c in m.children if c.type == "identifier"), None)
            if mn is not None:
                method_names_all.add(_text(mn, source_bytes))

        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            mname_node = next((c for c in mnode.children if c.type == "identifier"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"

            mods_node = next((c for c in mnode.children if c.type == "modifiers"), None)
            mods_text = _text(mods_node, source_bytes) if mods_node else ""
            is_override = "@Override" in mods_text
            is_abstract = "abstract" in mods_text or is_iface
            is_public = "public" in mods_text or is_iface

            body_node = next((c for c in mnode.children if c.type == "block"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            throws_unimpl = False
            if body_node is not None:
                throw_caps = _captures_dict(
                    _query(lang_obj, "(throw_statement (object_creation_expression type: (type_identifier) @exc))"),
                    body_node,
                )
                for n in throw_caps.get("exc", []):
                    if _text(n, source_bytes) in _UNIMPLEMENTED_MARKERS:
                        throws_unimpl = True

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            instantiations: Set[str] = set()
            if body_node is not None:
                fa_caps = _captures_dict(
                    _query(lang_obj, "(field_access object: (this) field: (identifier) @f)"), body_node
                )
                field_accesses = {_text(n, source_bytes) for n in fa_caps.get("f", [])}

                mc_caps = _captures_dict(
                    _query(lang_obj, "(method_invocation object: (this) name: (identifier) @m)"), body_node
                )
                for n in mc_caps.get("m", []):
                    called = _text(n, source_bytes)
                    if called in method_names_all:
                        method_calls.add(called)

                new_caps = _captures_dict(
                    _query(lang_obj, "(object_creation_expression type: (type_identifier) @t)"), body_node
                )
                instantiations = {_text(n, source_bytes) for n in new_caps.get("t", [])}

            params_node = next((c for c in mnode.children if c.type == "formal_parameters"), None)
            param_count = len([c for c in params_node.children if c.type == "formal_parameter"]) if params_node else 0

            methods.append(MethodInfo(
                name=mname,
                start_line=mnode.start_point[0] + 1,
                end_line=mnode.end_point[0] + 1,
                is_override=is_override,
                is_empty=is_empty,
                throws_unimplemented=throws_unimpl,
                is_abstract=is_abstract,
                is_public=is_public,
                all_identifiers=field_accesses | method_calls | instantiations,
                field_accesses=field_accesses,
                method_calls=method_calls,
                instantiations=instantiations,
                param_count=param_count,
            ))

        classes.append(ClassInfo(
            name=cls_name,
            filepath=file_path,
            start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1,
            language="java",
            is_interface=is_iface,
            is_abstract=is_iface,
            fields=fields,
            methods=methods,
            implements=implements,
        ))

    return classes


# ---------------------------------------------------------------------------
# JavaScript / TypeScript (share grammar shape for classes)
# ---------------------------------------------------------------------------

def _build_ts_js(root, source_bytes, lang_obj, file_path: str, language: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class_declaration", class_nodes)
    iface_nodes: list = []
    if language == "typescript":
        _walk(root, "interface_declaration", iface_nodes)

    classes: List[ClassInfo] = []

    for cnode in class_nodes:
        name_node = next((c for c in cnode.children if c.type in ("identifier", "type_identifier")), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        heritage_caps = _captures_dict(_query(lang_obj, "(class_heritage) @h"), cnode)
        for h in heritage_caps.get("h", []):
            id_caps = _captures_dict(_query(lang_obj, "(identifier) @i"), h)
            implements |= {_text(n, source_bytes) for n in id_caps.get("i", [])}
            ti_caps = _captures_dict(_query(lang_obj, "(type_identifier) @i"), h)
            implements |= {_text(n, source_bytes) for n in ti_caps.get("i", [])}

        body = next((c for c in cnode.children if c.type == "class_body"), cnode)
        method_nodes = [c for c in body.children if c.type == "method_definition"]
        field_nodes = [c for c in body.children if c.type in ("field_definition", "public_field_definition")]

        fields: Set[str] = set()
        for fnode in field_nodes:
            fn_caps = _captures_dict(_query(lang_obj, "(property_identifier) @f"), fnode)
            fields |= {_text(n, source_bytes) for n in fn_caps.get("f", [])}

        method_names_all = set()
        for m in method_nodes:
            mn = next((c for c in m.children if c.type == "property_identifier"), None)
            if mn is not None:
                method_names_all.add(_text(mn, source_bytes))

        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            mname_node = next((c for c in mnode.children if c.type == "property_identifier"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"

            body_node = next((c for c in mnode.children if c.type == "statement_block"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            throws_unimpl = False
            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            instantiations: Set[str] = set()
            if body_node is not None:
                throw_caps = _captures_dict(
                    _query(lang_obj, "(throw_statement (new_expression constructor: (identifier) @exc))"),
                    body_node,
                )
                for n in throw_caps.get("exc", []):
                    if _text(n, source_bytes) in _UNIMPLEMENTED_MARKERS:
                        throws_unimpl = True

                fa_caps = _captures_dict(
                    _query(lang_obj, "(member_expression object: (this) property: (property_identifier) @f)"),
                    body_node,
                )
                field_accesses = {_text(n, source_bytes) for n in fa_caps.get("f", [])}

                mc_caps = _captures_dict(
                    _query(
                        lang_obj,
                        "(call_expression function: (member_expression object: (this) property: (property_identifier) @m))",
                    ),
                    body_node,
                )
                for n in mc_caps.get("m", []):
                    called = _text(n, source_bytes)
                    if called in method_names_all:
                        method_calls.add(called)

                new_caps = _captures_dict(_query(lang_obj, "(new_expression constructor: (identifier) @t)"), body_node)
                instantiations = {_text(n, source_bytes) for n in new_caps.get("t", [])}

            params_node = next((c for c in mnode.children if c.type == "formal_parameters"), None)
            param_count = max(0, len([c for c in params_node.children if c.type not in ("(", ")", ",")])) if params_node else 0

            methods.append(MethodInfo(
                name=mname,
                start_line=mnode.start_point[0] + 1,
                end_line=mnode.end_point[0] + 1,
                is_empty=is_empty,
                throws_unimplemented=throws_unimpl,
                is_public=not mname.startswith("_") and not mname.startswith("#"),
                all_identifiers=field_accesses | method_calls | instantiations,
                field_accesses=field_accesses,
                method_calls=method_calls,
                instantiations=instantiations,
                param_count=param_count,
            ))

        classes.append(ClassInfo(
            name=cls_name,
            filepath=file_path,
            start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1,
            language=language,
            is_interface=False,
            fields=fields,
            methods=methods,
            implements=implements,
        ))

    for inode in iface_nodes:
        name_node = next((c for c in inode.children if c.type == "type_identifier"), None)
        iface_name = _text(name_node, source_bytes) if name_node else "<interface>"
        sig_caps = _captures_dict(_query(lang_obj, "(method_signature name: (property_identifier) @m)"), inode)
        methods = [
            MethodInfo(name=_text(n, source_bytes), start_line=n.start_point[0] + 1, end_line=n.start_point[0] + 1,
                       is_abstract=True, is_empty=True)
            for n in sig_caps.get("m", [])
        ]
        classes.append(ClassInfo(
            name=iface_name,
            filepath=file_path,
            start_line=inode.start_point[0] + 1,
            end_line=inode.end_point[0] + 1,
            language=language,
            is_interface=True,
            is_abstract=True,
            methods=methods,
        ))

    return classes


_LANG_HANDLERS: Dict[str, Callable] = {
    "python": _build_python,
    "java": _build_java,
    "javascript": lambda root, sb, lo, fp: _build_ts_js(root, sb, lo, fp, "javascript"),
    "typescript": lambda root, sb, lo, fp: _build_ts_js(root, sb, lo, fp, "typescript"),
}
