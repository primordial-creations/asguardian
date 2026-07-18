"""Tree-sitter infrastructure for Heimdall — optional dependency."""
from Asgard.Heimdall.treesitter._language_loader import is_available, get_supported_languages
from Asgard.Heimdall.treesitter._parser_pool import get_parser, parse_source, parse_file
from Asgard.Heimdall.treesitter._query_runner import run_query, run_query_all
from Asgard.Heimdall.treesitter.file_context import FileParseContext, language_for_path
from Asgard.Heimdall.treesitter.ast_engine import (
    is_engine_enabled,
    log_engine_mode,
    engine_status,
    with_ast_fallback,
)

__all__ = [
    "is_available", "get_supported_languages",
    "get_parser", "parse_source", "parse_file",
    "run_query", "run_query_all",
    "FileParseContext", "language_for_path",
    "is_engine_enabled", "log_engine_mode", "engine_status", "with_ast_fallback",
]
