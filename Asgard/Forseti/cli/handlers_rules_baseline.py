"""
CLI handlers: `forseti rules list`, `forseti baseline update|show`,
and the governed (profile/suppression/baseline-aware) validation pipeline.
"""

import argparse
import json
import sys
from pathlib import Path

from Asgard.Forseti.cli._handler_runner import (
    EXIT_INPUT_ERROR,
    EXIT_OK,
    run_and_report,
)
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Reporting.utilities.sourcemap_loader import (
    annotate_findings,
    build_sourcemap,
)
from Asgard.Forseti.Rules import RULESET_VERSION
from Asgard.Forseti.Rules.models._rule_base_models import (
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.services.baseline_service import (
    BASELINE_FILENAME,
    BaselineService,
)
from Asgard.Forseti.Rules.services.profile_service import (
    effective_severity,
    load_config,
    resolve_profile,
    select_rules,
)
from Asgard.Forseti.Rules.services.rule_registry_service import get_default_registry
from Asgard.Forseti.Rules.services._suppression_helpers import (
    apply_suppressions,
    collect_suppressions,
)


def _handle_rules(args: argparse.Namespace) -> int:
    """Handle rules commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti rules --help' for options.")
        return 1

    if args.command == "list":
        registry = get_default_registry()
        fmt_filter = getattr(args, "rule_format", None)
        fmt = SchemaFormat(fmt_filter) if fmt_filter else None
        rules = registry.query(fmt=fmt)
        if getattr(args, "format", "text") == "json":
            payload = {
                "ruleset_version": RULESET_VERSION,
                "rules": [rule.meta.model_dump(mode="json") for rule in rules],
            }
            print(json.dumps(payload, indent=2, default=list))
        else:
            print(f"Ruleset version: {RULESET_VERSION}")
            print(f"{'RULE ID':<45} {'SEV':<8} {'CONF':<14} {'CAT':<14} CORE")
            for rule in rules:
                meta = rule.meta
                print(
                    f"{meta.rule_id:<45} {meta.severity.value:<8} "
                    f"{meta.confidence.value:<14} {meta.category.value:<14} "
                    f"{'yes' if meta.core else 'no'}"
                )
        return EXIT_OK

    return 1


def _handle_baseline(args: argparse.Namespace) -> int:
    """Handle baseline commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti baseline --help' for options.")
        return 1

    service = BaselineService(getattr(args, "baseline", None) or BASELINE_FILENAME)

    if args.command == "show":
        entries = service.load()
        print(json.dumps([entry.model_dump() for entry in entries], indent=2))
        return EXIT_OK

    if args.command == "update":
        spec_path = Path(args.spec_file)
        if not spec_path.is_file():
            print(f"Error: file not found: {spec_path}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        findings, document, input_error = _collect_findings(spec_path, args)
        if input_error:
            return EXIT_INPUT_ERROR
        count = service.update(
            [f for f in findings if not f.suppressed], document
        )
        print(f"Baseline written: {service.baseline_path} ({count} finding(s) accepted)")
        return EXIT_OK

    return 1


def _detect_format(document, path: Path) -> SchemaFormat:
    """Best-effort format detection for a structured spec document."""
    if isinstance(document, dict):
        if "openapi" in document or "swagger" in document:
            return SchemaFormat.OPENAPI
        if "asyncapi" in document:
            return SchemaFormat.ASYNCAPI
        if "$schema" in document or path.suffix == ".avsc":
            return SchemaFormat.AVRO if path.suffix == ".avsc" else SchemaFormat.JSONSCHEMA
    return SchemaFormat.OPENAPI


def _collect_findings(
    spec_path: Path,
    args: argparse.Namespace,
) -> tuple[list[Finding], object, bool]:
    """
    Run the governed pipeline for a structured spec file:
    load -> registry rules -> profile severity filter -> suppressions.
    Returns (findings, document, input_error).
    """
    import yaml

    try:
        text = spec_path.read_text(encoding="utf-8")
        document = yaml.safe_load(text)
    except Exception as exc:
        return ([Finding(
            rule_id="forseti.input.unparseable",
            severity=Severity.ERROR,
            message=f"Failed to parse {spec_path}: {exc}",
            coordinates=Coordinates(file=str(spec_path)),
            category=RuleCategory.STRUCTURE,
        )], None, True)
    if not isinstance(document, dict):
        return ([Finding(
            rule_id="forseti.input.unparseable",
            severity=Severity.ERROR,
            message=f"Document root is not an object: {spec_path}",
            coordinates=Coordinates(file=str(spec_path)),
            category=RuleCategory.STRUCTURE,
        )], None, True)

    fmt = _detect_format(document, spec_path)
    config = load_config(getattr(args, "config", None))
    profile_name = getattr(args, "profile", None)
    if profile_name is None and getattr(args, "strict", False):
        profile_name = "ci"
    profile = resolve_profile(profile_name, config)
    registry = get_default_registry()

    findings: list[Finding] = []
    for rule in select_rules(registry, profile, fmt=fmt):
        if not rule.executable:
            continue
        severity = effective_severity(rule.meta, profile, str(spec_path))
        if severity is None:
            continue
        for finding in rule.check(document):
            finding.severity = severity
            finding.coordinates.file = str(spec_path)
            findings.append(finding)

    # Pair-programmer layer: lexical-inference HINTs are IDE fodder and are
    # never emitted in ci/pre-commit output (plan 03, DEEPTHINK_06). Severity
    # stays fixed; only display is filtered.
    if profile.name in ("ci", "pre-commit"):
        findings = [f for f in findings if f.severity != Severity.HINT]

    core_ids = {r.meta.rule_id for r in registry.all_rules() if r.meta.core}
    suppressions = collect_suppressions(document)
    findings = apply_suppressions(
        findings, suppressions, fmt=fmt, core_rule_ids=core_ids, file=str(spec_path)
    )

    if not getattr(args, "no_baseline", False):
        baseline_path = getattr(args, "baseline", None) or BASELINE_FILENAME
        if Path(baseline_path).is_file():
            BaselineService(baseline_path).apply(findings, document)

    annotate_findings(findings, build_sourcemap(text))
    return findings, document, False


def run_governed_validation(spec_path: str, args: argparse.Namespace) -> int:
    """Full governed validate for the unified output path (sarif/github/etc.)."""
    path = Path(spec_path)
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    findings, _document, input_error = _collect_findings(path, args)
    profile_name = getattr(args, "profile", None) or (
        "ci" if getattr(args, "strict", False) else "ci"
    )
    from Asgard.Forseti.Rules.services.profile_service import BUILTIN_PROFILES

    blocking = BUILTIN_PROFILES.get(profile_name, BUILTIN_PROFILES["ci"]).blocking
    registry = get_default_registry()
    rule_metas = [rule.meta for rule in registry.all_rules()]
    return run_and_report(
        findings,
        args,
        rule_metas=rule_metas,
        input_error=input_error,
        blocking=blocking,
    )
