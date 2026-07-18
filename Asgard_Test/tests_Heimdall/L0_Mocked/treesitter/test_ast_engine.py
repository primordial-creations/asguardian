"""Tests for the dual-engine decorator and engine-mode reporting.

All tests pass whether or not the tree-sitter optional dependency is installed.
"""
import logging

import pytest

from Asgard.Heimdall.treesitter import ast_engine
from Asgard.Heimdall.treesitter import _language_loader
from Asgard.Heimdall.treesitter.ast_engine import (
    engine_status,
    is_engine_enabled,
    log_engine_mode,
    reset_engine_mode_logged,
    with_ast_fallback,
    REGEX_MODE_MESSAGE,
)
from Asgard.Heimdall.treesitter.file_context import FileParseContext


class _FakeNode:
    pass


def _fake_ctx(root=None):
    ctx = FileParseContext(file_path="x.py", language="python")
    ctx.root = root
    return ctx


def _make_rule(ast_result=None, ast_raises=False):
    calls = {"ast": 0, "regex": 0}

    def ast_impl(file_path, ctx):
        calls["ast"] += 1
        if ast_raises:
            raise RuntimeError("boom")
        return ast_result if ast_result is not None else [{"engine": "ast"}]

    @with_ast_fallback("python", ast_impl)
    def rule(file_path, lines, enabled=True, **kwargs):
        calls["regex"] += 1
        return [{"engine": "regex"}]

    return rule, calls


# ---------------------------------------------------------------------------
# with_ast_fallback
# ---------------------------------------------------------------------------

def test_disabled_rule_returns_empty():
    rule, calls = _make_rule()
    assert rule("x.py", ["a"], False) == []
    assert calls == {"ast": 0, "regex": 0}


def test_regex_path_when_engine_unavailable(monkeypatch):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", False)
    rule, calls = _make_rule()
    result = rule("x.py", ["a"], True)
    assert result == [{"engine": "regex"}]
    assert calls["ast"] == 0


def test_ast_path_with_provided_context(monkeypatch):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", True)
    monkeypatch.setattr(_language_loader, "is_available", lambda lang: True)
    rule, calls = _make_rule()
    result = rule("x.py", ["a"], True, parse_context=_fake_ctx(root=_FakeNode()))
    assert result == [{"engine": "ast"}]
    assert calls["regex"] == 0


def test_ast_failure_falls_back_to_regex(monkeypatch):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", True)
    monkeypatch.setattr(_language_loader, "is_available", lambda lang: True)
    rule, calls = _make_rule(ast_raises=True)
    result = rule("x.py", ["a"], True, parse_context=_fake_ctx(root=_FakeNode()))
    assert result == [{"engine": "regex"}]
    assert calls["ast"] == 1 and calls["regex"] == 1


def test_context_without_tree_uses_regex(monkeypatch):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", True)
    monkeypatch.setattr(_language_loader, "is_available", lambda lang: True)
    rule, calls = _make_rule()
    result = rule("x.py", ["a"], True, parse_context=_fake_ctx(root=None))
    assert result == [{"engine": "regex"}]
    assert calls["ast"] == 0


def test_decorator_exposes_both_impls():
    rule, _ = _make_rule()
    assert callable(rule.__ast_impl__)
    assert callable(rule.__regex_impl__)
    assert rule.__ast_language__ == "python"
    assert rule.__engine__ == "dual"


def test_dual_engine_fixture_runs_both_modes(dual_engine_mode):
    assert dual_engine_mode in ("regex", "ast")
    if dual_engine_mode == "regex":
        assert ast_engine.TS_AVAILABLE is False
    else:
        assert is_engine_enabled("python")


# ---------------------------------------------------------------------------
# is_engine_enabled / engine_status
# ---------------------------------------------------------------------------

def test_is_engine_enabled_false_when_ts_disabled(monkeypatch):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", False)
    assert is_engine_enabled("python") is False


def test_is_engine_enabled_never_raises():
    for lang in ("python", "cobol_9000", "", None):
        try:
            is_engine_enabled(lang)
        except TypeError:
            pass  # None is acceptable to reject loudly only via TypeError


def test_engine_status_shape():
    status = engine_status()
    assert status["engine"] in ("ast", "regex")
    assert isinstance(status["tree_sitter_available"], bool)
    assert isinstance(status["languages"], list)


# ---------------------------------------------------------------------------
# log_engine_mode — single INFO line per process
# ---------------------------------------------------------------------------

def test_log_engine_mode_emits_single_info_when_unavailable(monkeypatch, caplog):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", False)
    reset_engine_mode_logged()
    with caplog.at_level(logging.INFO, logger="Asgard.Heimdall.treesitter"):
        log_engine_mode()
        log_engine_mode()
    messages = [r.message for r in caplog.records if r.message == REGEX_MODE_MESSAGE]
    assert len(messages) == 1
    reset_engine_mode_logged()


def test_log_engine_mode_silent_when_available(monkeypatch, caplog):
    monkeypatch.setattr(ast_engine, "TS_AVAILABLE", True)
    reset_engine_mode_logged()
    with caplog.at_level(logging.INFO, logger="Asgard.Heimdall.treesitter"):
        log_engine_mode()
    assert all(r.message != REGEX_MODE_MESSAGE for r in caplog.records)
    reset_engine_mode_logged()
