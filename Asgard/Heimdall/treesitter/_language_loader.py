"""Try-import each tree-sitter language binding at startup. Never raises to callers."""
from typing import Dict, Optional, Set

_AVAILABLE: Dict[str, object] = {}  # language_name -> Language object


def _try_load_all() -> None:
    """Attempt to import each language module at startup.

    Uses ``from tree_sitter import Language`` then wraps each per-language
    ``language()`` / ``language_*()`` callable.  Failures are silently
    swallowed so the rest of the application continues without tree-sitter.
    """
    try:
        from tree_sitter import Language  # noqa: PLC0415
    except ImportError:
        return

    _candidates = [
        ("python", "tree_sitter_python", "language"),
        ("javascript", "tree_sitter_javascript", "language"),
        ("java", "tree_sitter_java", "language"),
        ("go", "tree_sitter_go", "language"),
        ("ruby", "tree_sitter_ruby", "language"),
        ("csharp", "tree_sitter_c_sharp", "language"),
        ("cpp", "tree_sitter_cpp", "language"),
        ("rust", "tree_sitter_rust", "language"),
    ]

    for lang_name, module_name, fn_name in _candidates:
        try:
            import importlib  # noqa: PLC0415
            mod = importlib.import_module(module_name)
            fn = getattr(mod, fn_name)
            _AVAILABLE[lang_name] = Language(fn())
        except Exception:  # ImportError, AttributeError, etc.
            pass

    # TypeScript/TSX use differently-named functions in one package
    try:
        import importlib  # noqa: PLC0415
        mod = importlib.import_module("tree_sitter_typescript")
        _AVAILABLE["typescript"] = Language(mod.language_typescript())
        try:
            _AVAILABLE["tsx"] = Language(mod.language_tsx())
        except Exception:
            pass
    except Exception:
        pass

    # PHP uses a differently-named function
    try:
        import importlib  # noqa: PLC0415
        mod = importlib.import_module("tree_sitter_php")
        _AVAILABLE["php"] = Language(mod.language_php())
    except Exception:
        pass


_try_load_all()


def is_available(language: str) -> bool:
    """Return True if the tree-sitter binding for *language* loaded successfully."""
    return language in _AVAILABLE


def get_language_object(language: str):
    """Return the ``Language`` object for *language*, or ``None`` if unavailable."""
    return _AVAILABLE.get(language)


def get_supported_languages() -> Set[str]:
    """Return the set of language names whose bindings loaded successfully."""
    return set(_AVAILABLE.keys())
