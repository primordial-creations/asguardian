"""
Heimdall Language Registry

Single source of truth for language ↔ file extension mapping.
All scanners import from here instead of hard-coding extension lists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set

LANGUAGE_EXTENSIONS: Dict[str, Set[str]] = {
    "python":     {".py", ".pyw"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
    "java":       {".java"},
    "go":         {".go"},
    "ruby":       {".rb", ".rake", ".gemspec"},
    "php":        {".php", ".php3", ".php4", ".php5", ".phtml"},
    "csharp":     {".cs"},
    "rust":       {".rs"},
    "kotlin":     {".kt", ".kts"},
    "swift":      {".swift"},
    "scala":      {".scala"},
    "cpp":        {".cpp", ".cxx", ".cc", ".c++", ".hpp", ".hxx"},
    "c":          {".c", ".h"},
    "shell":      {".sh", ".bash", ".zsh", ".fish"},
    "sql":        {".sql"},
    "terraform":  {".tf", ".hcl"},
    "yaml":       {".yaml", ".yml"},
    "json":       {".json"},
    "toml":       {".toml"},
    "html":       {".html", ".htm", ".jinja", ".jinja2", ".j2"},
    "css":        {".css", ".scss", ".sass", ".less"},
}

EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ext: lang
    for lang, exts in LANGUAGE_EXTENSIONS.items()
    for ext in exts
}

ALL_CODE_EXTENSIONS: Set[str] = {
    ext for exts in LANGUAGE_EXTENSIONS.values() for ext in exts
}

WEB_LANGUAGES: Set[str] = {
    "python", "javascript", "typescript", "php", "ruby", "java", "csharp", "go",
}

AST_SUPPORTED_LANGUAGES: Set[str] = {"python"}

SECURITY_SCAN_EXTENSIONS: List[str] = sorted(
    ext
    for lang in WEB_LANGUAGES
    for ext in LANGUAGE_EXTENSIONS[lang]
)

QUALITY_SCAN_EXTENSIONS: List[str] = sorted(ALL_CODE_EXTENSIONS)

# Lang-extension map used by multi-language regex scanners
LANG_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rake": "ruby",
    ".php": "php",
    ".php3": "php",
    ".php4": "php",
    ".php5": "php",
    ".phtml": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
}


def get_language(file_path: Path) -> Optional[str]:
    """Return canonical language name for a file, or None if unrecognised."""
    return EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())


def get_extensions_for_languages(*languages: str) -> Set[str]:
    """Return the union of extensions for the given language names."""
    result: Set[str] = set()
    for lang in languages:
        result.update(LANGUAGE_EXTENSIONS.get(lang, set()))
    return result


def is_scannable(file_path: Path, include_extensions: Optional[Set[str]] = None) -> bool:
    """Return True if the file extension is in scope."""
    ext = file_path.suffix.lower()
    return ext in (include_extensions if include_extensions is not None else ALL_CODE_EXTENSIONS)
