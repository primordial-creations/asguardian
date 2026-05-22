# Additional Scan Handover — Exception Quality Detector Gap Patch

## File to Modify

`Asgard/Bragi/Quality/BugDetection/services/exception_quality_detector.py`

---

## Gap Description

**Check 3 (Overly Broad Catch Without Re-raise)** only fires when the caught type is a bare `ast.Name` node matching `"Exception"` or `"BaseException"`. Two patterns are missed:

| Pattern | AST node type | Example |
|---|---|---|
| Tuple catch containing a broad type | `ast.Tuple` | `except (Exception, ValueError):` |
| Attribute-qualified broad type | `ast.Attribute` | `except builtins.Exception:` |

---

## Fix — Replace the `is_broad` block (lines 178–201)

### Before

```python
# ── 3. Overly broad catch without re-raise ─────────────────────────────
is_broad = (
    isinstance(handler.type, ast.Name)
    and handler.type.id in ("Exception", "BaseException")
)
if is_broad and not _handler_has_bare_reraise(handler) and isinstance(handler.type, ast.Name):
    broad_name = handler.type.id
    findings.append(BugFinding(
        file_path=fp,
        line_number=handler.lineno,
        category=BugCategory.EXCEPTION_SWALLOWING,
        severity=BugSeverity.MEDIUM,
        title=f"Overly Broad `except {broad_name}` Without Re-raise",
        description=(
            f"Line {handler.lineno}: Catching `{broad_name}` is very broad and will "
            "mask unexpected programming errors (IndexError, AttributeError, etc.). "
            "Without a bare `raise` at the end, bugs can be silently absorbed."
        ),
        code_snippet=_snippet(lines, handler.lineno),
        fix_suggestion=(
            "Narrow the exception type to only what you expect, "
            "or add a bare `raise` after handling to re-propagate unexpected errors."
        ),
    ))
```

### After

```python
# ── 3. Overly broad catch without re-raise ─────────────────────────────
_BROAD_NAMES = frozenset(("Exception", "BaseException"))


def _extract_broad_names(node: ast.expr) -> list[str]:
    """Return any broad exception names found in a handler type node."""
    if isinstance(node, ast.Name) and node.id in _BROAD_NAMES:
        return [node.id]
    if isinstance(node, ast.Attribute) and node.attr in _BROAD_NAMES:
        return [node.attr]
    if isinstance(node, ast.Tuple):
        found = []
        for elt in node.elts:
            found.extend(_extract_broad_names(elt))
        return found
    return []


broad_names = _extract_broad_names(handler.type) if handler.type else []
if broad_names and not _handler_has_bare_reraise(handler):
    label = " | ".join(broad_names)
    findings.append(BugFinding(
        file_path=fp,
        line_number=handler.lineno,
        category=BugCategory.EXCEPTION_SWALLOWING,
        severity=BugSeverity.MEDIUM,
        title=f"Overly Broad `except {label}` Without Re-raise",
        description=(
            f"Line {handler.lineno}: Catching `{label}` is very broad and will "
            "mask unexpected programming errors (IndexError, AttributeError, etc.). "
            "Without a bare `raise` at the end, bugs can be silently absorbed."
        ),
        code_snippet=_snippet(lines, handler.lineno),
        fix_suggestion=(
            "Narrow the exception type to only what you expect, "
            "or add a bare `raise` after handling to re-propagate unexpected errors."
        ),
    ))
```

**Note:** `_extract_broad_names` and `_BROAD_NAMES` should be defined at module level (alongside the other module-level helpers like `_snippet`, `_ast_unparse`, `_is_effectively_empty`), not inside `_check_handler`.

---

## Tests to Add

File: `tests/` — wherever `ExceptionQualityDetector` tests currently live.

### New cases to cover

```python
# Should fire — tuple catch containing Exception
except (Exception, ValueError):
    logger.info("handled")

# Should fire — attribute-qualified
except builtins.Exception:
    logger.info("handled")

# Should NOT fire — tuple catch but has bare re-raise
except (Exception, ValueError):
    logger.info("handled")
    raise

# Should NOT fire — narrow types only in tuple
except (ValueError, TypeError):
    logger.info("handled")
```

---

## Notes

- The `_BROAD_NAMES` set is intentionally kept at module level so it can be reused if additional checks need it later.
- The `label` in the title will render as e.g. `except Exception | BaseException` for the edge case where someone writes `except (Exception, BaseException):` — ugly but accurate.
- No change to severities or categories; this is purely a coverage gap fix.
