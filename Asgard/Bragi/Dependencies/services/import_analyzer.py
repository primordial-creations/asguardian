"""
Heimdall Import Analyzer Service

Extracts import statements and dependencies from Python files.
"""

import ast
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Bragi.Dependencies.models.dependency_models import (
    DependencyConfig,
    DependencyInfo,
    DependencyType,
    ModuleDependencies,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that extracts import statements."""

    def __init__(self, include_external: bool = False):
        self.include_external = include_external
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, Set[str]] = {}
        self.dependencies: List[DependencyInfo] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        for alias in node.names:
            module = alias.name
            self.imports.add(module)
            self.dependencies.append(DependencyInfo(
                source="",  # Will be set by caller
                target=module,
                dependency_type=DependencyType.IMPORT,
                line_number=node.lineno,
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        module = node.module or ""

        if module not in self.from_imports:
            self.from_imports[module] = set()

        for alias in node.names:
            if alias.name != "*":
                self.from_imports[module].add(alias.name)
                self.dependencies.append(DependencyInfo(
                    source="",  # Will be set by caller
                    target=module,
                    dependency_type=DependencyType.FROM_IMPORT,
                    line_number=node.lineno,
                    import_name=alias.name,
                ))


class ImportAnalyzer:
    """
    Analyzes Python files for import statements and dependencies.

    Extracts:
    - Regular imports (import X)
    - From imports (from X import Y)
    - Relative imports
    - Package structure
    """

    def __init__(self, config: Optional[DependencyConfig] = None):
        """Initialize the import analyzer."""
        self.config = config or DependencyConfig()

        # Standard library modules to exclude
        self._stdlib_modules = {
            "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
            "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
            "binhex", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
            "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
            "colorsys", "compileall", "concurrent", "configparser", "contextlib",
            "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
            "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
            "difflib", "dis", "distutils", "doctest", "email", "encodings",
            "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
            "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
            "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
            "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imghdr",
            "imp", "importlib", "inspect", "io", "ipaddress", "itertools",
            "json", "keyword", "lib2to3", "linecache", "locale", "logging",
            "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes",
            "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
            "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev",
            "parser", "pathlib", "pdb", "pickle", "pickletools", "pipes",
            "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
            "pprint", "profile", "pstats", "pty", "pwd", "py_compile",
            "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
            "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets",
            "select", "selectors", "shelve", "shlex", "shutil", "signal",
            "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
            "spwd", "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
            "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
            "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
            "test", "textwrap", "threading", "time", "timeit", "tkinter",
            "token", "tokenize", "trace", "traceback", "tracemalloc", "tty",
            "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest",
            "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
            "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
            "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
        }

    def analyze(self, scan_path: Optional[Path] = None) -> List[ModuleDependencies]:
        """
        Analyze imports for all Python files in the path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            List of ModuleDependencies for each file
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        results: List[ModuleDependencies] = []

        # Build exclude patterns
        exclude_patterns = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        # First, build a map of internal modules
        internal_modules = self._build_module_map(path, exclude_patterns)

        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                module_deps = self._analyze_file(file_path, path, internal_modules)
                if module_deps:
                    results.append(module_deps)
            except (SyntaxError, Exception):
                continue

        return results

    def _build_module_map(
        self, root_path: Path, exclude_patterns: List[str]
    ) -> Set[str]:
        """Build a set of internal module names."""
        modules = set()

        for file_path in scan_directory(
            root_path,
            exclude_patterns=exclude_patterns,
            include_extensions=[".py"],
        ):
            module_name = self._path_to_module(file_path, root_path)
            if module_name:
                modules.add(module_name)
                # Also add parent packages
                parts = module_name.split(".")
                for i in range(1, len(parts)):
                    modules.add(".".join(parts[:i]))

        return modules

    def _path_to_module(self, file_path: Path, root_path: Path) -> Optional[str]:
        """Convert a file path to a module name."""
        try:
            relative = file_path.relative_to(root_path)
            parts = list(relative.parts)

            # Remove .py extension
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]

            # Remove __init__
            if parts[-1] == "__init__":
                parts = parts[:-1]

            if not parts:
                return None

            return ".".join(parts)
        except ValueError:
            return None

    def _analyze_file(
        self,
        file_path: Path,
        root_path: Path,
        internal_modules: Set[str]
    ) -> Optional[ModuleDependencies]:
        """Analyze a single file for imports."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, Exception):
            return None

        module_name = self._path_to_module(file_path, root_path)
        if not module_name:
            return None

        visitor = ImportVisitor(include_external=self.config.include_external)
        visitor.visit(tree)

        # Filter dependencies
        filtered_deps = []
        all_deps = set()

        for dep in visitor.dependencies:
            dep.source = module_name

            # Check if it's an internal module
            target_root = dep.target.split(".")[0]
            is_internal = (
                dep.target in internal_modules or
                target_root in internal_modules
            )

            # Check if it's stdlib
            is_stdlib = target_root in self._stdlib_modules

            if self.config.include_external or is_internal:
                if not is_stdlib or self.config.include_external:
                    filtered_deps.append(dep)
                    all_deps.add(dep.target)

        try:
            relative_path = str(file_path.relative_to(root_path))
        except ValueError:
            relative_path = file_path.name

        return ModuleDependencies(
            module_name=module_name,
            file_path=str(file_path),
            relative_path=relative_path,
            imports=visitor.imports,
            from_imports=visitor.from_imports,
            all_dependencies=all_deps,
            efferent_coupling=len(all_deps),
            dependency_list=filtered_deps,
        )

    def analyze_file(self, file_path: Path) -> Optional[ModuleDependencies]:
        """
        Analyze a single file for imports.

        Args:
            file_path: Path to the Python file

        Returns:
            ModuleDependencies for the file
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        return self._analyze_file(path, path.parent, set())

    def get_import_graph(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, Set[str]]:
        """
        Get a dictionary representation of the import graph.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict mapping module name to set of dependencies
        """
        modules = self.analyze(scan_path)

        graph = {}
        for module in modules:
            graph[module.module_name] = module.all_dependencies

        return graph
