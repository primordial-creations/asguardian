import ast
from typing import List, Optional, Union, cast

from Asgard.Bragi.Quality.models.env_fallback_models import (
    EnvFallbackSeverity,
    EnvFallbackType,
    EnvFallbackViolation,
)
from Asgard.Bragi.Quality.services._env_fallback_helpers import (
    is_credential_key_name,
    is_credential_like_value,
)


class EnvFallbackVisitor(ast.NodeVisitor):
    """AST visitor that detects environment variable fallback patterns."""

    CONFIG_VAR_NAMES = {
        "secrets", "secret", "credentials", "creds",
        "vault_data", "vault_secrets", "vault_config",
        "db_config", "database_config",
        "rabbitmq_config", "redis_config", "storage_config",
        "env_config", "env_vars",
    }

    def __init__(self, file_path: str, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: List[EnvFallbackViolation] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

    def _get_code_snippet(self, node: ast.expr) -> str:
        if node.lineno <= len(self.source_lines):
            return self.source_lines[node.lineno - 1].strip()
        return ""

    def _get_string_value(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return str(node.value)
        elif isinstance(node, ast.Str):
            return cast(str, node.s)
        return None

    def _is_os_getenv(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "getenv":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    return True
        elif isinstance(node.func, ast.Name):
            if node.func.id == "getenv":
                return True
        return False

    def _is_os_environ_get(self, node: ast.Call) -> bool:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "get":
                if isinstance(node.func.value, ast.Attribute):
                    if node.func.value.attr == "environ":
                        if isinstance(node.func.value.value, ast.Name):
                            if node.func.value.value.id == "os":
                                return True
                elif isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "environ":
                        return True
        return False

    def _get_env_var_name(self, call_node: ast.Call) -> Optional[str]:
        if call_node.args:
            return self._get_string_value(call_node.args[0])
        return None

    def _get_default_value_repr(self, node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Str):
            return repr(node.s)
        elif isinstance(node, ast.Num):
            return repr(node.n)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.NameConstant):
            return repr(node.value)
        elif isinstance(node, ast.List):
            return "[...]"
        elif isinstance(node, ast.Dict):
            return "{...}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}(...)"
            elif isinstance(node.func, ast.Attribute):
                return f"...{node.func.attr}(...)"
        return "<expression>"

    def _record_violation(
        self, node: ast.expr, fallback_type: EnvFallbackType,
        variable_name: Optional[str], default_value: Optional[str],
    ) -> None:
        severity = self._determine_severity(fallback_type)
        code_snippet = self._get_code_snippet(node)
        context_parts = []
        if self.current_class:
            context_parts.append(f"class {self.current_class}")
        if self.current_function:
            context_parts.append(f"function {self.current_function}")
        context = f"in {', '.join(context_parts)}" if context_parts else "at module level"
        config_types = {
            EnvFallbackType.CONFIG_GET_DEFAULT,
            EnvFallbackType.SECRETS_GET_DEFAULT,
            EnvFallbackType.VAULT_OR_FALLBACK,
        }
        context_desc = f"Config/secrets fallback {context}" if fallback_type in config_types else f"Environment variable fallback {context}"
        self.violations.append(EnvFallbackViolation(
            file_path=self.file_path, line_number=node.lineno,
            column=getattr(node, 'col_offset', 0), code_snippet=code_snippet,
            variable_name=variable_name, default_value=default_value,
            fallback_type=fallback_type, severity=severity,
            containing_function=self.current_function,
            containing_class=self.current_class, context_description=context_desc,
        ))

    def _determine_severity(self, fallback_type: EnvFallbackType) -> EnvFallbackSeverity:
        high_severity = {
            EnvFallbackType.GETENV_DEFAULT, EnvFallbackType.ENVIRON_GET_DEFAULT,
            EnvFallbackType.CONFIG_GET_DEFAULT, EnvFallbackType.SECRETS_GET_DEFAULT,
            EnvFallbackType.CREDENTIAL_KEY_GETENV_DEFAULT,
            EnvFallbackType.CREDENTIAL_VALUE_ENVIRON_DEFAULT,
        }
        medium_severity = {
            EnvFallbackType.GETENV_OR_FALLBACK,
            EnvFallbackType.ENVIRON_GET_OR_FALLBACK,
            EnvFallbackType.VAULT_OR_FALLBACK,
        }
        if fallback_type in high_severity:
            return EnvFallbackSeverity.HIGH
        elif fallback_type in medium_severity:
            return EnvFallbackSeverity.MEDIUM
        return EnvFallbackSeverity.LOW

    def _is_config_dict_get(self, node: ast.Call) -> tuple[bool, Optional[str]]:
        """Check if call is a .get() on a config/secrets dictionary variable."""
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
            return False, None
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id.lower() in self.CONFIG_VAR_NAMES:
                return True, node.func.value.id
        return False, None

    def _extract_default(self, node: ast.Call) -> tuple[bool, Optional[str]]:
        """Extract default value from args or keywords of a call."""
        if len(node.args) >= 2:
            return True, self._get_default_value_repr(node.args[1])
        for kw in node.keywords:
            if kw.arg == "default":
                return True, self._get_default_value_repr(kw.value)
        return False, None

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to detect getenv/environ.get with defaults."""
        if self._is_os_getenv(node):
            has_default, default_value = self._extract_default(node)
            if has_default:
                var_name = self._get_env_var_name(node)
                if is_credential_key_name(var_name) and is_credential_like_value(default_value):
                    fallback_type = EnvFallbackType.CREDENTIAL_KEY_GETENV_DEFAULT
                else:
                    fallback_type = EnvFallbackType.GETENV_DEFAULT
                self._record_violation(node, fallback_type, var_name, default_value)
        elif self._is_os_environ_get(node):
            has_default, default_value = self._extract_default(node)
            if has_default:
                var_name = self._get_env_var_name(node)
                if is_credential_like_value(default_value):
                    fallback_type = EnvFallbackType.CREDENTIAL_VALUE_ENVIRON_DEFAULT
                else:
                    fallback_type = EnvFallbackType.ENVIRON_GET_DEFAULT
                self._record_violation(node, fallback_type, var_name, default_value)
        else:
            is_config_get, config_var = self._is_config_dict_get(node)
            if is_config_get:
                key_name = self._get_string_value(node.args[0]) if node.args else None
                has_default = False
                default_value = None
                if len(node.args) >= 2:
                    has_default = True
                    default_value = self._get_default_value_repr(node.args[1])
                else:
                    for kw in node.keywords:
                        if kw.arg == "default" or kw.arg is None:
                            has_default = True
                            default_value = self._get_default_value_repr(kw.value)
                            break
                if has_default:
                    var_lower = config_var.lower() if config_var else ""
                    if "secret" in var_lower or "cred" in var_lower:
                        fallback_type = EnvFallbackType.SECRETS_GET_DEFAULT
                    else:
                        fallback_type = EnvFallbackType.CONFIG_GET_DEFAULT
                    self._record_violation(node, fallback_type, key_name, default_value)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Visit boolean operations to detect 'getenv(...) or default' patterns."""
        if isinstance(node.op, ast.Or) and len(node.values) >= 2:
            left = node.values[0]
            if isinstance(left, ast.Call):
                if self._is_os_getenv(left):
                    var_name = self._get_env_var_name(left)
                    default_value = self._get_default_value_repr(node.values[1])
                    self._record_violation(node, EnvFallbackType.GETENV_OR_FALLBACK, var_name, default_value)
                elif self._is_os_environ_get(left):
                    var_name = self._get_env_var_name(left)
                    default_value = self._get_default_value_repr(node.values[1])
                    self._record_violation(node, EnvFallbackType.ENVIRON_GET_OR_FALLBACK, var_name, default_value)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> None:
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
