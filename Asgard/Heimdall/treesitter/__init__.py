"""Tree-sitter infrastructure for Heimdall — optional dependency."""
from Asgard.Heimdall.treesitter._language_loader import is_available, get_supported_languages
from Asgard.Heimdall.treesitter._parser_pool import get_parser, parse_source, parse_file
from Asgard.Heimdall.treesitter._query_runner import run_query, run_query_all

__all__ = [
    "is_available", "get_supported_languages",
    "get_parser", "parse_source", "parse_file",
    "run_query", "run_query_all",
]
