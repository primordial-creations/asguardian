"""
Alignment Checker Service - compares IRRecords for one logical entity.

Implements plan 07's algorithm in order: type contradiction (CRITICAL),
nullability contract breach on a declared direction edge (CRITICAL), enum
divergence (CRITICAL narrowing / INFO widening), precision risk (WARNING),
idiomatic coercion (INFO), subset divergence (INFO), lexical-casing
divergence (INFO). `ignore_fields` suppresses subset findings only -
never type contradictions, per plan 07's testing notes.
"""

from typing import Optional

from Asgard.Forseti.Alignment.models.ir_models import IRField, IRRecord, TypeClass
from Asgard.Forseti.Alignment.services._type_matrix_helpers import MatrixVerdict, classify
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity


def _finding(rule_id: str, severity: Severity, message: str, source_label: str, field_name: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        coordinates=Coordinates(file=source_label, json_path=f"/{field_name}"),
        category=RuleCategory.SEMANTICS,
        format=SchemaFormat.CONTRACT,
    )


def _check_field_pair(
    entity: str,
    left_label: str,
    left_field: IRField,
    right_label: str,
    right_field: IRField,
    *,
    left_is_producer: Optional[bool],
    ignore: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    name = left_field.raw_name
    verdict = classify(left_field.type.type_class, right_field.type.type_class)

    if verdict == MatrixVerdict.INCOMPATIBLE:
        findings.append(
            _finding(
                "align.type-contradiction",
                Severity.ERROR,
                f"{entity}.{name}: {left_label} has type {left_field.type.type_class.value}, "
                f"{right_label} has incompatible type {right_field.type.type_class.value}",
                left_label,
                name,
            )
        )
        # Type contradiction overrides other checks for this field pair.
        return findings

    if left_is_producer is True and left_field.nullable and not right_field.nullable:
        findings.append(
            _finding(
                "align.nullability-breach",
                Severity.ERROR,
                f"{entity}.{name}: {left_label} (producer) is nullable but {right_label} "
                "(consumer) requires a non-null value",
                right_label,
                name,
            )
        )
    elif left_is_producer is False and right_field.nullable and not left_field.nullable:
        findings.append(
            _finding(
                "align.nullability-breach",
                Severity.ERROR,
                f"{entity}.{name}: {right_label} (producer) is nullable but {left_label} "
                "(consumer) requires a non-null value",
                left_label,
                name,
            )
        )

    if left_field.type.type_class == TypeClass.ENUM and right_field.type.type_class == TypeClass.ENUM:
        left_symbols = set(left_field.type.enum_symbols)
        right_symbols = set(right_field.type.enum_symbols)
        if left_is_producer is True and not left_symbols.issubset(right_symbols):
            findings.append(
                _finding(
                    "align.enum-divergence",
                    Severity.ERROR,
                    f"{entity}.{name}: {left_label} enum symbols are not a subset of {right_label}'s",
                    right_label,
                    name,
                )
            )
        elif left_is_producer is None and left_symbols != right_symbols:
            wider = left_symbols.issuperset(right_symbols) or right_symbols.issuperset(left_symbols)
            findings.append(
                _finding(
                    "align.enum-divergence",
                    Severity.INFO if wider else Severity.ERROR,
                    f"{entity}.{name}: enum symbols differ between {left_label} and {right_label}",
                    left_label,
                    name,
                )
            )

    if verdict == MatrixVerdict.COERCIBLE_LOSSY:
        findings.append(
            _finding(
                "align.precision-risk",
                Severity.WARNING,
                f"{entity}.{name}: {left_label} type {left_field.type.type_class.value} may lose "
                f"precision when mapped to {right_label} type {right_field.type.type_class.value}",
                left_label,
                name,
            )
        )
    elif verdict == MatrixVerdict.COERCIBLE_IDIOMATIC and left_field.type.type_class != right_field.type.type_class:
        findings.append(
            _finding(
                "align.idiomatic-coercion",
                Severity.INFO,
                f"{entity}.{name}: {left_label} type {left_field.type.type_class.value} maps idiomatically "
                f"to {right_label} type {right_field.type.type_class.value}",
                left_label,
                name,
            )
        )

    if left_field.lexical_tokens == right_field.lexical_tokens and left_field.raw_name != right_field.raw_name:
        findings.append(
            _finding(
                "align.lexical-divergence",
                Severity.INFO,
                f"{entity}.{name}: field is named '{left_field.raw_name}' in {left_label} but "
                f"'{right_field.raw_name}' in {right_label}",
                left_label,
                name,
            )
        )

    return findings


def check_entity_alignment(
    entity: str,
    sources: dict[str, IRRecord],
    direction_edges: Optional[list[tuple[str, str]]] = None,
    ignore_fields: Optional[set[str]] = None,
) -> list[Finding]:
    """Compare every declared pair of sources for one logical entity.

    `direction_edges` is a list of (producer_label, consumer_label) pairs;
    when a pair is (or reverses) a declared edge, nullability/enum checks
    use producer-vs-consumer severity. Undeclared pairs still run type
    contradiction, precision, idiomatic and lexical checks, and use the
    symmetric (order-agnostic) branch for enum divergence.
    """
    direction_edges = direction_edges or []
    ignore_fields = ignore_fields or set()
    edge_set = {(a, b) for a, b in direction_edges}

    findings: list[Finding] = []
    labels = list(sources.keys())
    for i, left_label in enumerate(labels):
        for right_label in labels[i + 1 :]:
            left_record = sources[left_label]
            right_record = sources[right_label]
            if (left_label, right_label) in edge_set:
                left_is_producer: Optional[bool] = True
            elif (right_label, left_label) in edge_set:
                left_is_producer = False
            else:
                left_is_producer = None

            left_by_tokens = {f.lexical_tokens: f for f in left_record.fields}
            right_by_tokens = {f.lexical_tokens: f for f in right_record.fields}
            all_tokens = set(left_by_tokens) | set(right_by_tokens)

            for tokens in all_tokens:
                left_field = left_by_tokens.get(tokens)
                right_field = right_by_tokens.get(tokens)
                field_name = (left_field or right_field).raw_name
                ignore = field_name in ignore_fields

                if left_field is None or right_field is None:
                    if ignore:
                        continue
                    present_in = left_label if left_field else right_label
                    findings.append(
                        _finding(
                            "align.subset-divergence",
                            Severity.INFO,
                            f"{entity}.{field_name}: present in {present_in} only "
                            f"(add to ignore_fields if intentional)",
                            present_in,
                            field_name,
                        )
                    )
                    continue

                findings.extend(
                    _check_field_pair(
                        entity,
                        left_label,
                        left_field,
                        right_label,
                        right_field,
                        left_is_producer=left_is_producer,
                        ignore=ignore,
                    )
                )

    return findings
