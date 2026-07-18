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

Supported languages today: python, java, javascript, typescript, go, csharp,
ruby, php, rust, cpp.  Others return ``None`` and callers fall back to the
regex engine.
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
# Type-switch cascade counting (OCP HIGH-confidence path — plan 02).
#
# Counts branches of a conditional cascade whose condition tests the runtime
# type of a value: Python ``if/elif`` chains using ``isinstance``/``type``,
# and switch/if-else-if chains in C-family languages using
# ``instanceof``/``typeof``/``.GetType()``/type-switch idioms.  This is a
# per-method total (not necessarily a single chain) — good enough for the
# evaluator, which only needs "count >= 3" plus a corroborating type-check
# identifier hit.
# ---------------------------------------------------------------------------

_TYPE_CHECK_TOKENS = ("isinstance", "instanceof", "typeof", "type(", "GetType", ".(type)")


def _count_python_type_switches(mnode, source_bytes: bytes) -> int:
    count = 0
    stack = [mnode]
    while stack:
        n = stack.pop()
        if n.type == "if_statement":
            cond = next((c for c in n.children if c.type not in ("if", ":", "block")), None)
            branches = [n] + [c for c in n.children if c.type == "elif_clause"]
            for b in branches:
                b_cond = next((c for c in b.children if c.type not in ("if", "elif", ":", "block")), None)
                text = _text(b_cond, source_bytes) if b_cond is not None else ""
                if "isinstance" in text or "type(" in text:
                    count += 1
        for c in n.children:
            stack.append(c)
    return count


def _count_switch_type_switches(mnode, source_bytes: bytes) -> int:
    """Java/JS/TS/C#: switch-case cascades and if/else-if chains gated on
    instanceof/typeof/GetType."""
    count = 0
    stack = [mnode]
    while stack:
        n = stack.pop()
        if n.type == "switch_statement":
            switch_text = _text(n, source_bytes)
            if any(tok in switch_text for tok in ("typeof", "instanceof", "GetType")):
                cases = [c for c in n.children if c.type in ("switch_case", "switch_section", "switch_label")]
                count += len(cases)
        if n.type == "if_statement":
            cond = next((c for c in n.children if c.type not in ("if", "else")), None)
            text = _text(cond, source_bytes) if cond is not None else ""
            if any(tok in text for tok in ("instanceof", "typeof", "GetType")):
                count += 1
        for c in n.children:
            stack.append(c)
    return count


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
        if child.type == type_name and getattr(child, "is_named", True):
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
                type_switches=_count_python_type_switches(mnode, source_bytes),
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
                type_switches=_count_switch_type_switches(mnode, source_bytes),
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
                type_switches=_count_switch_type_switches(mnode, source_bytes),
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


# ---------------------------------------------------------------------------
# Go — receiver-linked methods (methods declared outside the struct body;
# ``@method.receiver`` name-binding per DEEPTHINK_01 §4).
# ---------------------------------------------------------------------------

def _build_go(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    type_specs: list = []
    _walk(root, "type_spec", type_specs)

    structs: Dict[str, ClassInfo] = {}
    interfaces: Dict[str, ClassInfo] = {}
    for spec in type_specs:
        name_node = next((c for c in spec.children if c.type == "type_identifier"), None)
        if name_node is None:
            continue
        name = _text(name_node, source_bytes)
        body = next((c for c in spec.children if c.type in ("struct_type", "interface_type")), None)
        if body is None:
            continue
        if body.type == "struct_type":
            fields: Set[str] = set()
            field_list = next((c for c in body.children if c.type == "field_declaration_list"), None)
            if field_list is not None:
                for fd in field_list.children:
                    if fd.type == "field_declaration":
                        fid = next((c for c in fd.children if c.type == "field_identifier"), None)
                        if fid is not None:
                            fields.add(_text(fid, source_bytes))
            structs[name] = ClassInfo(
                name=name, filepath=file_path, start_line=spec.start_point[0] + 1,
                end_line=spec.end_point[0] + 1, language="go", fields=fields,
            )
        else:
            methods: List[MethodInfo] = []
            for elem in body.children:
                if elem.type == "method_elem":
                    fid = next((c for c in elem.children if c.type == "field_identifier"), None)
                    if fid is not None:
                        methods.append(MethodInfo(
                            name=_text(fid, source_bytes), start_line=elem.start_point[0] + 1,
                            end_line=elem.end_point[0] + 1, is_abstract=True, is_empty=True,
                        ))
            interfaces[name] = ClassInfo(
                name=name, filepath=file_path, start_line=spec.start_point[0] + 1,
                end_line=spec.end_point[0] + 1, language="go", is_interface=True,
                is_abstract=True, methods=methods,
            )

    method_decls: list = []
    _walk(root, "method_declaration", method_decls)
    for mnode in method_decls:
        params = [c for c in mnode.children if c.type == "parameter_list"]
        recv_list = params[0] if params else None
        recv_type = None
        recv_name = None
        if recv_list is not None:
            decl = next((c for c in recv_list.children if c.type == "parameter_declaration"), None)
            if decl is not None:
                recv_name_node = next((c for c in decl.children if c.type == "identifier"), None)
                recv_name = _text(recv_name_node, source_bytes) if recv_name_node else None
                type_node = next((c for c in decl.children if c.type in ("type_identifier", "pointer_type")), None)
                if type_node is not None:
                    recv_type = _text(type_node, source_bytes).lstrip("*")
        target = structs.get(recv_type)
        if target is None:
            continue

        fid = next((c for c in mnode.children if c.type == "field_identifier"), None)
        mname = _text(fid, source_bytes) if fid is not None else "<method>"
        body_node = next((c for c in mnode.children if c.type == "block"), None)
        is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

        field_accesses: Set[str] = set()
        method_calls: Set[str] = set()
        instantiations: Set[str] = set()
        if body_node is not None and recv_name:
            sel_caps = _captures_dict(
                _query(lang_obj, "(selector_expression operand: (identifier) @o field: (field_identifier) @f)"),
                body_node,
            )
            for o, f in zip(sel_caps.get("o", []), sel_caps.get("f", [])):
                if _text(o, source_bytes) == recv_name:
                    fname = _text(f, source_bytes)
                    if fname in target.fields:
                        field_accesses.add(fname)
                    else:
                        method_calls.add(fname)

        target.methods.append(MethodInfo(
            name=mname, start_line=mnode.start_point[0] + 1, end_line=mnode.end_point[0] + 1,
            is_empty=is_empty, is_public=mname[:1].isupper(),
            all_identifiers=field_accesses | method_calls,
            field_accesses=field_accesses, method_calls=method_calls,
            instantiations=instantiations,
            type_switches=_count_switch_type_switches(mnode, source_bytes),
        ))

    return list(structs.values()) + list(interfaces.values())


# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------

def _build_csharp(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class_declaration", class_nodes)
    iface_nodes: list = []
    _walk(root, "interface_declaration", iface_nodes)

    classes: List[ClassInfo] = []
    for cnode, is_iface in [(n, False) for n in class_nodes] + [(n, True) for n in iface_nodes]:
        name_node = next((c for c in cnode.children if c.type == "identifier"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        base_list = next((c for c in cnode.children if c.type == "base_list"), None)
        if base_list is not None:
            implements = {_text(c, source_bytes) for c in base_list.children if c.type == "identifier"}

        body = next((c for c in cnode.children if c.type in ("declaration_list",)), cnode)
        method_nodes = [c for c in body.children if c.type == "method_declaration"]
        field_nodes = [c for c in body.children if c.type == "field_declaration"]

        fields: Set[str] = set()
        for fnode in field_nodes:
            decl_caps = _captures_dict(_query(lang_obj, "(variable_declarator name: (identifier) @f)"), fnode)
            fields |= {_text(n, source_bytes) for n in decl_caps.get("f", [])}

        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            mname_node = next((c for c in mnode.children if c.type == "identifier"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"
            mods_node = next((c for c in mnode.children if c.type == "modifier"), None)
            mods_text = _text(mods_node, source_bytes) if mods_node else ""
            is_override = "override" in mods_text
            is_public = "public" in mods_text or is_iface

            body_node = next((c for c in mnode.children if c.type == "block"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            instantiations: Set[str] = set()
            if body_node is not None:
                new_caps = _captures_dict(_query(lang_obj, "(object_creation_expression type: (identifier) @t)"), body_node)
                instantiations = {_text(n, source_bytes) for n in new_caps.get("t", [])}

            methods.append(MethodInfo(
                name=mname, start_line=mnode.start_point[0] + 1, end_line=mnode.end_point[0] + 1,
                is_override=is_override, is_empty=is_empty, is_public=is_public,
                all_identifiers=field_accesses | method_calls | instantiations,
                field_accesses=field_accesses, method_calls=method_calls, instantiations=instantiations,
                type_switches=_count_switch_type_switches(mnode, source_bytes),
            ))

        classes.append(ClassInfo(
            name=cls_name, filepath=file_path, start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1, language="csharp", is_interface=is_iface,
            is_abstract=is_iface, fields=fields, methods=methods, implements=implements,
        ))
    return classes


# ---------------------------------------------------------------------------
# Ruby
# ---------------------------------------------------------------------------

def _build_ruby(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class", class_nodes)

    classes: List[ClassInfo] = []
    for cnode in class_nodes:
        name_node = next((c for c in cnode.children if c.type == "constant"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        super_node = next((c for c in cnode.children if c.type == "superclass"), None)
        if super_node is not None:
            const = next((c for c in super_node.children if c.type == "constant"), None)
            if const is not None:
                implements.add(_text(const, source_bytes))

        body = next((c for c in cnode.children if c.type == "body_statement"), cnode)
        method_nodes = [c for c in body.children if c.type == "method"]

        fields: Set[str] = set()
        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            mname_node = next((c for c in mnode.children if c.type == "identifier"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"
            mbody = next((c for c in mnode.children if c.type == "body_statement"), None)
            is_empty = mbody is None

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            if mbody is not None:
                ivar_caps = _captures_dict(_query(lang_obj, "(instance_variable) @iv"), mbody)
                for n in ivar_caps.get("iv", []):
                    fname = _text(n, source_bytes).lstrip("@")
                    field_accesses.add(fname)
                    fields.add(fname)

            methods.append(MethodInfo(
                name=mname, start_line=mnode.start_point[0] + 1, end_line=mnode.end_point[0] + 1,
                is_empty=is_empty, is_public=not mname.startswith("_"),
                all_identifiers=field_accesses | method_calls,
                field_accesses=field_accesses, method_calls=method_calls,
                type_switches=_count_python_type_switches(mnode, source_bytes),
            ))

        classes.append(ClassInfo(
            name=cls_name, filepath=file_path, start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1, language="ruby", fields=fields,
            methods=methods, implements=implements,
        ))
    return classes


# ---------------------------------------------------------------------------
# PHP
# ---------------------------------------------------------------------------

def _build_php(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class_declaration", class_nodes)
    iface_nodes: list = []
    _walk(root, "interface_declaration", iface_nodes)

    classes: List[ClassInfo] = []
    for cnode, is_iface in [(n, False) for n in class_nodes] + [(n, True) for n in iface_nodes]:
        name_node = next((c for c in cnode.children if c.type == "name"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        for clause_type in ("base_clause", "class_interface_clause"):
            clause = next((c for c in cnode.children if c.type == clause_type), None)
            if clause is not None:
                implements |= {_text(c, source_bytes) for c in clause.children if c.type == "name"}

        body = next((c for c in cnode.children if c.type == "declaration_list"), cnode)
        method_nodes = [c for c in body.children if c.type == "method_declaration"]
        prop_nodes = [c for c in body.children if c.type == "property_declaration"]

        fields: Set[str] = set()
        for pnode in prop_nodes:
            var_caps = _captures_dict(_query(lang_obj, "(variable_name (name) @f)"), pnode)
            fields |= {_text(n, source_bytes) for n in var_caps.get("f", [])}

        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            mname_node = next((c for c in mnode.children if c.type == "name"), None)
            mname = _text(mname_node, source_bytes) if mname_node else "<method>"
            mods_text = " ".join(
                _text(c, source_bytes) for c in mnode.children if c.type == "visibility_modifier"
            )
            body_node = next((c for c in mnode.children if c.type == "compound_statement"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            instantiations: Set[str] = set()
            if body_node is not None:
                prop_caps = _captures_dict(
                    _query(lang_obj, "(member_access_expression object: (variable_name (name) @o) name: (name) @f)"),
                    body_node,
                )
                for o, f in zip(prop_caps.get("o", []), prop_caps.get("f", [])):
                    if _text(o, source_bytes) == "this":
                        field_accesses.add(_text(f, source_bytes))
                new_caps = _captures_dict(_query(lang_obj, "(object_creation_expression (name) @t)"), body_node)
                instantiations = {_text(n, source_bytes) for n in new_caps.get("t", [])}

            methods.append(MethodInfo(
                name=mname, start_line=mnode.start_point[0] + 1, end_line=mnode.end_point[0] + 1,
                is_empty=is_empty, is_public=("private" not in mods_text and "protected" not in mods_text),
                all_identifiers=field_accesses | method_calls | instantiations,
                field_accesses=field_accesses, method_calls=method_calls, instantiations=instantiations,
                type_switches=_count_switch_type_switches(mnode, source_bytes),
            ))

        classes.append(ClassInfo(
            name=cls_name, filepath=file_path, start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1, language="php", is_interface=is_iface,
            is_abstract=is_iface, fields=fields, methods=methods, implements=implements,
        ))
    return classes


# ---------------------------------------------------------------------------
# Rust — struct + impl block (methods declared outside the struct; receiver
# is the ``self_parameter``).
# ---------------------------------------------------------------------------

def _build_rust(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    struct_nodes: list = []
    _walk(root, "struct_item", struct_nodes)
    trait_nodes: list = []
    _walk(root, "trait_item", trait_nodes)
    impl_nodes: list = []
    _walk(root, "impl_item", impl_nodes)

    structs: Dict[str, ClassInfo] = {}
    for snode in struct_nodes:
        name_node = next((c for c in snode.children if c.type == "type_identifier"), None)
        name = _text(name_node, source_bytes) if name_node else "<struct>"
        fields: Set[str] = set()
        flist = next((c for c in snode.children if c.type == "field_declaration_list"), None)
        if flist is not None:
            for fd in flist.children:
                if fd.type == "field_declaration":
                    fid = next((c for c in fd.children if c.type == "field_identifier"), None)
                    if fid is not None:
                        fields.add(_text(fid, source_bytes))
        structs[name] = ClassInfo(
            name=name, filepath=file_path, start_line=snode.start_point[0] + 1,
            end_line=snode.end_point[0] + 1, language="rust", fields=fields,
        )

    classes: List[ClassInfo] = []
    for tnode in trait_nodes:
        name_node = next((c for c in tnode.children if c.type == "type_identifier"), None)
        name = _text(name_node, source_bytes) if name_node else "<trait>"
        dlist = next((c for c in tnode.children if c.type == "declaration_list"), None)
        methods: List[MethodInfo] = []
        if dlist is not None:
            for c in dlist.children:
                if c.type == "function_signature_item":
                    fid = next((g for g in c.children if g.type == "identifier"), None)
                    if fid is not None:
                        methods.append(MethodInfo(
                            name=_text(fid, source_bytes), start_line=c.start_point[0] + 1,
                            end_line=c.end_point[0] + 1, is_abstract=True, is_empty=True,
                        ))
        classes.append(ClassInfo(
            name=name, filepath=file_path, start_line=tnode.start_point[0] + 1,
            end_line=tnode.end_point[0] + 1, language="rust", is_interface=True,
            is_abstract=True, methods=methods,
        ))

    for inode in impl_nodes:
        type_ids = [c for c in inode.children if c.type == "type_identifier"]
        target_name = _text(type_ids[-1], source_bytes) if type_ids else None
        target = structs.get(target_name)
        if target is None:
            continue
        dlist = next((c for c in inode.children if c.type == "declaration_list"), None)
        if dlist is None:
            continue
        for fn in dlist.children:
            if fn.type != "function_item":
                continue
            fid = next((c for c in fn.children if c.type == "identifier"), None)
            mname = _text(fid, source_bytes) if fid is not None else "<method>"
            body_node = next((c for c in fn.children if c.type == "block"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            if body_node is not None:
                fa_caps = _captures_dict(
                    _query(lang_obj, "(field_expression value: (self) field: (field_identifier) @f)"), body_node,
                )
                for n in fa_caps.get("f", []):
                    fname = _text(n, source_bytes)
                    if fname in target.fields:
                        field_accesses.add(fname)
                    else:
                        method_calls.add(fname)

            target.methods.append(MethodInfo(
                name=mname, start_line=fn.start_point[0] + 1, end_line=fn.end_point[0] + 1,
                is_empty=is_empty, is_public=True,
                all_identifiers=field_accesses | method_calls,
                field_accesses=field_accesses, method_calls=method_calls,
                type_switches=_count_switch_type_switches(fn, source_bytes),
            ))

    return list(structs.values()) + classes


# ---------------------------------------------------------------------------
# C++
# ---------------------------------------------------------------------------

def _build_cpp(root, source_bytes, lang_obj, file_path: str) -> List[ClassInfo]:
    class_nodes: list = []
    _walk(root, "class_specifier", class_nodes)
    _walk(root, "struct_specifier", class_nodes)

    classes: List[ClassInfo] = []
    for cnode in class_nodes:
        name_node = next((c for c in cnode.children if c.type == "type_identifier"), None)
        cls_name = _text(name_node, source_bytes) if name_node else "<class>"

        implements: Set[str] = set()
        base_clause = next((c for c in cnode.children if c.type == "base_class_clause"), None)
        if base_clause is not None:
            implements = {_text(c, source_bytes) for c in base_clause.children if c.type == "type_identifier"}

        flist = next((c for c in cnode.children if c.type == "field_declaration_list"), None)
        if flist is None:
            continue

        fields: Set[str] = set()
        method_nodes = []
        for c in flist.children:
            if c.type == "field_declaration":
                fid = next((g for g in c.children if g.type == "field_identifier"), None)
                if fid is not None:
                    fields.add(_text(fid, source_bytes))
            elif c.type == "function_definition":
                method_nodes.append(c)

        methods: List[MethodInfo] = []
        for mnode in method_nodes:
            declarator = next((c for c in mnode.children if c.type == "function_declarator"), None)
            fid = next((c for c in declarator.children if c.type == "field_identifier"), None) if declarator else None
            mname = _text(fid, source_bytes) if fid is not None else "<method>"
            body_node = next((c for c in mnode.children if c.type == "compound_statement"), None)
            is_empty = body_node is None or len([c for c in body_node.children if c.type not in ("{", "}")]) == 0

            field_accesses: Set[str] = set()
            method_calls: Set[str] = set()
            if body_node is not None:
                fa_caps = _captures_dict(
                    _query(lang_obj, "(field_expression argument: (this) field: (field_identifier) @f)"), body_node,
                )
                for n in fa_caps.get("f", []):
                    fname = _text(n, source_bytes)
                    if fname in fields:
                        field_accesses.add(fname)
                    else:
                        method_calls.add(fname)

            methods.append(MethodInfo(
                name=mname, start_line=mnode.start_point[0] + 1, end_line=mnode.end_point[0] + 1,
                is_empty=is_empty, is_public=True,
                all_identifiers=field_accesses | method_calls,
                field_accesses=field_accesses, method_calls=method_calls,
                type_switches=_count_switch_type_switches(mnode, source_bytes),
            ))

        classes.append(ClassInfo(
            name=cls_name, filepath=file_path, start_line=cnode.start_point[0] + 1,
            end_line=cnode.end_point[0] + 1, language="cpp", fields=fields,
            methods=methods, implements=implements,
        ))
    return classes


_LANG_HANDLERS: Dict[str, Callable] = {
    "python": _build_python,
    "java": _build_java,
    "javascript": lambda root, sb, lo, fp: _build_ts_js(root, sb, lo, fp, "javascript"),
    "typescript": lambda root, sb, lo, fp: _build_ts_js(root, sb, lo, fp, "typescript"),
    "go": _build_go,
    "csharp": _build_csharp,
    "ruby": _build_ruby,
    "php": _build_php,
    "rust": _build_rust,
    "cpp": _build_cpp,
}
