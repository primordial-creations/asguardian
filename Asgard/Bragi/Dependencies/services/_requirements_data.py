"""
Heimdall Requirements Checker - static data tables and AST visitor.

Contains:
- IMPORT_TO_PACKAGE_MAP: mapping of import name to pip package name
- STDLIB_MODULES: set of standard library module names
- ImportVisitor: AST node visitor that extracts import statements
"""

import ast
from typing import Dict, List


# Common import name to package name mappings
# When import name differs from pip package name
IMPORT_TO_PACKAGE_MAP: Dict[str, str] = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "jose": "python-jose",
    "jwt": "PyJWT",
    "dotenv": "python-dotenv",
    "multipart": "python-multipart",
    "magic": "python-magic",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "cx_Oracle": "cx-Oracle",
    "google": "google-api-python-client",
    "googleapiclient": "google-api-python-client",
    "msal": "msal",
    "azure": "azure-identity",
    "botocore": "botocore",
    "boto3": "boto3",
    "redis": "redis",
    "celery": "celery",
    "flask": "Flask",
    "django": "Django",
    "fastapi": "fastapi",
    "starlette": "starlette",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "alembic",
    "psycopg2": "psycopg2-binary",
    "pymysql": "PyMySQL",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "requests": "requests",
    "websockets": "websockets",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "pytest": "pytest",
    "coverage": "coverage",
    "mock": "mock",
    "freezegun": "freezegun",
    "faker": "Faker",
    "factory": "factory-boy",
    "hypothesis": "hypothesis",
    "locust": "locust",
    "playwright": "playwright",
    "anthropic": "anthropic",
    "openai": "openai",
    "tiktoken": "tiktoken",
    "transformers": "transformers",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "keras": "keras",
    "jinja2": "Jinja2",
    "markdown": "Markdown",
    "pygments": "Pygments",
    "passlib": "passlib",
    "cryptography": "cryptography",
    "fernet": "cryptography",
    "hvac": "hvac",
    "kubernetes": "kubernetes",
    "docker": "docker",
    "paramiko": "paramiko",
    "fabric": "fabric",
    "invoke": "invoke",
}

# Standard library modules to exclude from checks
STDLIB_MODULES = {
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
    "turtle", "turtledemo", "types", "typing", "typing_extensions",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
    "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
    "zlib", "_thread", "__future__",
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that extracts import statements."""

    def __init__(self) -> None:
        self.imports: List[Dict] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        for alias in node.names:
            self.imports.append({
                "package_name": alias.name.split(".")[0],
                "import_statement": f"import {alias.name}",
                "line_number": node.lineno,
                "import_type": "import",
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        if node.module:
            package_name = node.module.split(".")[0]
            names = ", ".join(a.name for a in node.names if a.name != "*")
            self.imports.append({
                "package_name": package_name,
                "import_statement": f"from {node.module} import {names}",
                "line_number": node.lineno,
                "import_type": "from_import",
            })
        self.generic_visit(node)
