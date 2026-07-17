"""
GraphQL Schema Diff Service - compatibility diffing over SDL (plan 01,
phase 3). GraphQL previously had no compatibility checking at all.

Removed fields/types/enum values are input-contravariance breaks per
DEEPTHINK_01 1: the server stops accepting a previously valid query.
"""

import re
from pathlib import Path
from typing import Any

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.utilities.compat_utils import dedup_changes
from Asgard.Forseti.GraphQL.utilities._graphql_parse_utils import parse_sdl
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

FMT = SchemaFormat.GRAPHQL

_TYPE_BODY = re.compile(r'(?:type|interface|input)\s+(\w+)(?:\s+implements\s+[^{]+)?\s*\{([^}]*)\}')
_FIELD_ARGS = re.compile(r'(\w+)\s*\(([^)]*)\)\s*:')
_ARG = re.compile(r'(\w+)\s*:\s*([\w\[\]!]+)(\s*=\s*[^,)]+)?')


def _parse_args(sdl: str) -> dict[str, dict[str, dict[str, tuple[str, bool]]]]:
    """type -> field -> arg -> (type, has_default)."""
    sdl_clean = re.sub(r'#[^\n]*', '', sdl)
    sdl_clean = re.sub(r'"""[\s\S]*?"""', '""', sdl_clean)
    out: dict[str, dict[str, dict[str, tuple[str, bool]]]] = {}
    for tmatch in _TYPE_BODY.finditer(sdl_clean):
        type_name, body = tmatch.group(1), tmatch.group(2)
        fields: dict[str, dict[str, tuple[str, bool]]] = {}
        for fmatch in _FIELD_ARGS.finditer(body):
            field_name, args_src = fmatch.group(1), fmatch.group(2)
            args: dict[str, tuple[str, bool]] = {}
            for amatch in _ARG.finditer(args_src):
                args[amatch.group(1)] = (
                    amatch.group(2).strip(),
                    amatch.group(3) is not None,
                )
            fields[field_name] = args
        out[type_name] = fields
    return out


class GraphQLSchemaDiffService:
    """
    Service for diffing two GraphQL SDL schemas for breaking changes.

    Usage:
        service = GraphQLSchemaDiffService()
        changes = service.diff("old.graphql", "new.graphql")
    """

    def diff(self, old_path: str | Path, new_path: str | Path) -> list[UnifiedChange]:
        """Diff two SDL files."""
        old_sdl = Path(old_path).read_text(encoding="utf-8")
        new_sdl = Path(new_path).read_text(encoding="utf-8")
        return self.diff_sdl(old_sdl, new_sdl)

    def diff_sdl(self, old_sdl: str, new_sdl: str) -> list[UnifiedChange]:
        """Diff two SDL strings."""
        old = parse_sdl(old_sdl)
        new = parse_sdl(new_sdl)
        changes: list[UnifiedChange] = []

        for kind, rule_removed in (("types", "GQL-TYPE-REMOVED"),
                                   ("interfaces", "GQL-TYPE-REMOVED")):
            changes.extend(self._diff_field_containers(
                old.get(kind, {}), new.get(kind, {}), rule_removed,
                field_removed_rule="GQL-FIELD-REMOVED",
            ))
        changes.extend(self._diff_field_containers(
            old.get("inputs", {}), new.get("inputs", {}), "GQL-TYPE-REMOVED",
            field_removed_rule="GQL-INPUT-FIELD-REMOVED",
        ))
        changes.extend(self._diff_input_required(old.get("inputs", {}),
                                                 new.get("inputs", {})))
        changes.extend(self._diff_enums(old.get("enums", {}), new.get("enums", {})))
        changes.extend(self._diff_unions(old.get("unions", {}), new.get("unions", {})))
        changes.extend(self._diff_arguments(old_sdl, new_sdl))
        return dedup_changes(changes)

    def _diff_field_containers(
        self,
        old_types: dict[str, Any],
        new_types: dict[str, Any],
        type_removed_rule: str,
        *,
        field_removed_rule: str,
    ) -> list[UnifiedChange]:
        changes: list[UnifiedChange] = []
        for name in sorted(set(old_types) - set(new_types)):
            changes.append(make_change(
                type_removed_rule, FMT, Direction.INPUT, name,
                f"Type '{name}' was removed", old_value=name,
                mitigation="Deprecate the type before removing it",
            ))
        for name in sorted(set(old_types) & set(new_types)):
            old_fields = old_types[name].get("fields", {})
            new_fields = new_types[name].get("fields", {})
            for field in sorted(set(old_fields) - set(new_fields)):
                changes.append(make_change(
                    field_removed_rule, FMT, Direction.INPUT,
                    f"{name}.{field}",
                    f"Field '{field}' was removed from '{name}': previously "
                    "valid queries are now rejected",
                    old_value=field,
                    mitigation="Use @deprecated before removing fields",
                ))
            for field in sorted(set(old_fields) & set(new_fields)):
                old_type = str(old_fields[field].get("type", "")).strip()
                new_type = str(new_fields[field].get("type", "")).strip()
                if old_type != new_type:
                    changes.append(make_change(
                        "GQL-FIELD-TYPE-CHANGED", FMT, Direction.INPUT,
                        f"{name}.{field}",
                        f"Field '{name}.{field}' type changed from "
                        f"'{old_type}' to '{new_type}'",
                        old_value=old_type, new_value=new_type,
                    ))
        return changes

    def _diff_input_required(self, old_inputs: dict[str, Any],
                             new_inputs: dict[str, Any]) -> list[UnifiedChange]:
        changes: list[UnifiedChange] = []
        for name in sorted(set(old_inputs) & set(new_inputs)):
            old_fields = old_inputs[name].get("fields", {})
            new_fields = new_inputs[name].get("fields", {})
            for field in sorted(set(new_fields) - set(old_fields)):
                ftype = str(new_fields[field].get("type", "")).strip()
                if ftype.endswith("!"):
                    changes.append(make_change(
                        "GQL-INPUT-FIELD-REQUIRED-ADDED", FMT, Direction.INPUT,
                        f"{name}.{field}",
                        f"Required input field '{field}' added to '{name}'",
                        new_value=ftype,
                        mitigation="Make the field nullable or give it a default",
                    ))
        return changes

    def _diff_enums(self, old_enums: dict[str, list[str]],
                    new_enums: dict[str, list[str]]) -> list[UnifiedChange]:
        changes: list[UnifiedChange] = []
        for name in sorted(set(old_enums) - set(new_enums)):
            changes.append(make_change(
                "GQL-TYPE-REMOVED", FMT, Direction.INPUT, name,
                f"Enum '{name}' was removed", old_value=name,
            ))
        for name in sorted(set(old_enums) & set(new_enums)):
            old_values, new_values = set(old_enums[name]), set(new_enums[name])
            for value in sorted(old_values - new_values):
                changes.append(make_change(
                    "GQL-ENUM-VALUE-REMOVED", FMT, Direction.INPUT,
                    f"{name}.{value}",
                    f"Enum value '{value}' removed from '{name}'",
                    old_value=value,
                ))
            for value in sorted(new_values - old_values):
                changes.append(make_change(
                    "GQL-ENUM-VALUE-ADDED", FMT, Direction.OUTPUT,
                    f"{name}.{value}",
                    f"Enum value '{value}' added to '{name}': old consumers "
                    "never saw it",
                    new_value=value,
                    mitigation="Ensure clients tolerate unknown enum values",
                ))
        return changes

    def _diff_unions(self, old_unions: dict[str, list[str]],
                     new_unions: dict[str, list[str]]) -> list[UnifiedChange]:
        changes: list[UnifiedChange] = []
        for name in sorted(set(old_unions) & set(new_unions)):
            for member in sorted(set(old_unions[name]) - set(new_unions[name])):
                changes.append(make_change(
                    "GQL-UNION-MEMBER-REMOVED", FMT, Direction.OUTPUT,
                    f"{name}.{member}",
                    f"Member '{member}' removed from union '{name}'",
                    old_value=member,
                ))
        return changes

    def _diff_arguments(self, old_sdl: str, new_sdl: str) -> list[UnifiedChange]:
        changes: list[UnifiedChange] = []
        old_args = _parse_args(old_sdl)
        new_args = _parse_args(new_sdl)
        for type_name in sorted(set(old_args) & set(new_args)):
            old_fields = old_args[type_name]
            new_fields = new_args[type_name]
            for field in sorted(set(old_fields) & set(new_fields)):
                old_field_args = old_fields[field]
                new_field_args = new_fields[field]
                for arg in sorted(set(old_field_args) - set(new_field_args)):
                    changes.append(make_change(
                        "GQL-ARG-REMOVED", FMT, Direction.INPUT,
                        f"{type_name}.{field}({arg})",
                        f"Argument '{arg}' removed from '{type_name}.{field}'",
                        old_value=arg,
                    ))
                for arg in sorted(set(new_field_args) - set(old_field_args)):
                    arg_type, has_default = new_field_args[arg]
                    if arg_type.endswith("!") and not has_default:
                        changes.append(make_change(
                            "GQL-ARG-REQUIRED-ADDED", FMT, Direction.INPUT,
                            f"{type_name}.{field}({arg})",
                            f"Required argument '{arg}' added to "
                            f"'{type_name}.{field}'",
                            new_value=arg_type,
                            mitigation="Make the argument nullable or default it",
                        ))
        return changes
