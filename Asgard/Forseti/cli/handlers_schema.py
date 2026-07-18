import argparse
import json
import re
import sys
from pathlib import Path

from Asgard.Forseti.OpenAPI import (
    SpecValidatorService,
    OpenAPIConfig,
    SpecGeneratorService,
    SpecConverterService,
)
from Asgard.Forseti.OpenAPI.utilities import compare_specs, save_spec_file
from Asgard.Forseti.GraphQL import (
    SchemaValidatorService as GraphQLSchemaValidatorService,
    GraphQLConfig,
    SchemaGeneratorService as GraphQLSchemaGeneratorService,
    IntrospectionService,
)
from Asgard.Forseti.Database import SchemaAnalyzerService, SchemaDiffService, MigrationGeneratorService
from Asgard.Forseti.Contracts import (
    ContractValidatorService,
    CompatibilityCheckerService,
    BreakingChangeDetectorService,
)
from Asgard.Forseti.JSONSchema import (
    SchemaValidatorService as JSONSchemaValidatorService,
    JSONSchemaConfig,
    SchemaGeneratorService as JSONSchemaGeneratorService,
    SchemaInferenceService,
)


def _handle_openapi(args: argparse.Namespace) -> int:
    """Handle OpenAPI commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti openapi --help' for options.")
        return 1

    if args.command == "validate":
        from pathlib import Path as _Path

        from Asgard.Forseti.cli._handler_runner import EXIT_INPUT_ERROR, wants_unified_output
        from Asgard.Forseti.cli.handlers_rules_baseline import run_governed_validation

        if wants_unified_output(args):
            return run_governed_validation(args.spec_file, args)
        if not _Path(args.spec_file).is_file():
            print(f"Error: file not found: {args.spec_file}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        config = OpenAPIConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        validator = SpecValidatorService(config)
        result = validator.validate(args.spec_file)
        print(validator.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        generator = SpecGeneratorService()
        spec = generator.generate_from_fastapi(args.source_path)
        if args.output:
            save_spec_file(Path(args.output), generator.to_dict(spec))
            print(f"Specification saved to {args.output}")
        else:
            print(json.dumps(generator.to_dict(spec), indent=2))
        return 0

    elif args.command == "convert":
        converter = SpecConverterService()
        converted = converter.convert(args.spec_file, args.target_version)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(converted, f, indent=2)
            print(f"Converted specification saved to {args.output}")
        else:
            print(json.dumps(converted, indent=2))
        return 0

    elif args.command == "diff":
        diff = compare_specs(args.spec1, args.spec2)
        print(json.dumps(diff, indent=2))
        return 0

    elif args.command == "completeness":
        return _handle_openapi_completeness(args)

    elif args.command == "security":
        return _handle_openapi_security(args)

    return 1


def _handle_openapi_completeness(args: argparse.Namespace) -> int:
    """Handle `forseti openapi completeness`."""
    from Asgard.Forseti.cli._handler_runner import (
        EXIT_GATE_FAILURE,
        EXIT_INPUT_ERROR,
        EXIT_OK,
    )
    from Asgard.Forseti.OpenAPI.models.completeness_models import MaturityTier
    from Asgard.Forseti.OpenAPI.services.completeness_service import (
        CompletenessService,
    )

    if not Path(args.spec_file).is_file():
        print(f"Error: file not found: {args.spec_file}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    service = CompletenessService()
    try:
        report = service.assess(
            args.spec_file,
            profile=getattr(args, "completeness_profile", "dx") or "dx",
        )
    except Exception as exc:
        print(f"Error: failed to parse specification: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    print(service.generate_report(report, getattr(args, "format", "text")))
    min_tier = getattr(args, "min_tier", None)
    if min_tier and not service.meets_tier(report, MaturityTier(min_tier)):
        return EXIT_GATE_FAILURE
    return EXIT_OK


def _handle_openapi_security(args: argparse.Namespace) -> int:
    """Handle `forseti openapi security` — security-category rules only."""
    import yaml

    from Asgard.Forseti.cli._handler_runner import (
        EXIT_INPUT_ERROR,
        run_and_report,
    )
    from Asgard.Forseti.Rules.models._rule_base_models import (
        RuleCategory,
        SchemaFormat,
    )
    from Asgard.Forseti.Rules.services.rule_registry_service import (
        get_default_registry,
    )

    spec_path = Path(args.spec_file)
    if not spec_path.is_file():
        print(f"Error: file not found: {spec_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error: failed to parse specification: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if not isinstance(document, dict):
        print(f"Error: document root is not an object: {spec_path}",
              file=sys.stderr)
        return EXIT_INPUT_ERROR
    registry = get_default_registry()
    findings = []
    for rule in registry.query(fmt=SchemaFormat.OPENAPI,
                               category=RuleCategory.SECURITY):
        for finding in rule.check(document):
            finding.coordinates.file = str(spec_path)
            findings.append(finding)
    return run_and_report(
        findings,
        args,
        rule_metas=[r.meta for r in registry.all_rules()],
    )


def _handle_graphql(args: argparse.Namespace) -> int:
    """Handle GraphQL commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti graphql --help' for options.")
        return 1

    if args.command == "validate":
        config = GraphQLConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        service = GraphQLSchemaValidatorService(config)
        result = service.validate(args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = GraphQLSchemaGeneratorService()
        print("Note: Generation from source requires importable Python modules")
        return 0

    elif args.command == "introspect":
        service = IntrospectionService()
        headers = {}
        if args.header:
            for h in args.header:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()
        result = service.introspect(args.endpoint, headers=headers if headers else None)
        if args.output:
            Path(args.output).write_text(result.sdl, encoding="utf-8")
            print(f"Schema saved to {args.output}")
        else:
            print(result.sdl)
        return 0

    return 1


def _handle_database(args: argparse.Namespace) -> int:
    """Handle Database commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti database --help' for options.")
        return 1

    if args.command == "analyze":
        analyzer = SchemaAnalyzerService()
        schema = analyzer.analyze_file(args.source)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(schema.model_dump(), f, indent=2)
            print(f"Schema analysis saved to {args.output}")
        else:
            print(json.dumps(schema.model_dump(), indent=2, default=str))
        return 0

    elif args.command == "diff":
        differ = SchemaDiffService()
        result = differ.diff_schemas(args.schema1, args.schema2)
        print(differ.generate_report(result, args.format))
        return 0 if not result.has_changes else 1

    elif args.command == "migrate":
        service = MigrationGeneratorService()
        with open(args.diff_file) as f:
            diff_data = json.load(f)
        print("Migration generation from diff file not yet implemented")
        return 0

    return 1


def _spec_version(path: str) -> str:
    """Read info.version from a spec file (best-effort)."""
    import yaml

    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return str((data or {}).get("info", {}).get("version", ""))
    except Exception:
        return ""


def _apply_compat_waivers(result, args: argparse.Namespace):
    """
    Apply epoch waivers (.forseti-waivers.yaml) to a CompatibilityResult.

    Waived breaking changes move to warnings with the waiver reason noted;
    if every breaking change is waived, the gate opens for this epoch only.
    """
    from Asgard.Forseti.Rules.services.waiver_service import WAIVERS_FILENAME, WaiverService

    waivers_path = getattr(args, "waivers", None)
    if waivers_path is None and not Path(WAIVERS_FILENAME).is_file():
        return result
    service = WaiverService(waivers_path)
    waivers = service.load()
    if not waivers:
        return result
    from_version = _spec_version(args.old_spec)
    to_version = _spec_version(args.new_spec)
    remaining, waived = [], []
    for change in result.breaking_changes:
        change_rule = str(getattr(change, "change_type", "") or "")
        waiver = service.is_waived(
            change_rule, change.location, from_version, to_version, waivers=waivers
        )
        if waiver is None:
            remaining.append(change)
        else:
            change.severity = "warning"
            change.mitigation = (
                f"WAIVED until {waiver.expires or 'merge'}: {waiver.reason}"
            )
            waived.append(change)
    result.breaking_changes = remaining
    result.warnings = list(result.warnings) + waived
    if not remaining:
        result.is_compatible = True
    return result


def _handle_contract(args: argparse.Namespace) -> int:
    """Handle Contract commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti contract --help' for options.")
        return 1

    if args.command == "validate":
        service = ContractValidatorService()
        result = service.validate(args.contract_file, args.implementation)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "check-compat":
        service = CompatibilityCheckerService()
        result = service.check(args.old_spec, args.new_spec)
        result = _apply_compat_waivers(result, args)
        if getattr(args, "format", "text") == "json":
            from Asgard.Forseti.cli.handlers_compat import engine_score_extras

            payload = json.loads(service.generate_report(result, "json"))
            payload.update(engine_score_extras(args.old_spec, args.new_spec, "openapi"))
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(service.generate_report(result, args.format))
        return 0 if result.is_compatible else 1

    elif args.command == "breaking-changes":
        service = BreakingChangeDetectorService()
        changes = service.detect(args.old_spec, args.new_spec)
        version = getattr(args, 'version', 'unknown')
        current_version = getattr(args, "current_version", None)
        migration_out = getattr(args, "migration_guide", None)
        changelog_out = getattr(args, "changelog", None)
        recommendation = None
        if current_version or migration_out or changelog_out \
                or getattr(args, "format", "text") == "json":
            try:
                recommendation = service.recommend_version(
                    args.old_spec, args.new_spec, current_version
                )
            except Exception:
                recommendation = None
        target_version = (recommendation.recommended_version
                          if recommendation and recommendation.recommended_version
                          else (version if version and version != "unknown"
                                else "next"))
        if migration_out:
            Path(migration_out).write_text(
                service.generate_migration_guide(
                    args.old_spec, args.new_spec, target_version
                ),
                encoding="utf-8",
            )
            print(f"Migration guide written to {migration_out}")
        if changelog_out:
            Path(changelog_out).write_text(
                service.generate_structured_changelog(
                    args.old_spec, args.new_spec, target_version
                ),
                encoding="utf-8",
            )
            print(f"Changelog written to {changelog_out}")
        if getattr(args, "format", "text") == "json":
            payload: dict = {
                "version": version,
                "breaking_changes": [
                    {"type": str(c.change_type), "location": c.location,
                     "message": c.message, "severity": c.severity}
                    for c in changes
                ],
            }
            if recommendation is not None:
                payload["version_recommendation"] = recommendation.model_dump(
                    mode="json"
                )
            print(json.dumps(payload, indent=2, default=str))
        else:
            changelog = service.generate_changelog(changes, version)
            print(changelog)
            if recommendation is not None and current_version:
                print(f"Recommended bump: {recommendation.recommended_bump.value}"
                      f" ({current_version} -> "
                      f"{recommendation.recommended_version})")
                for reason in recommendation.reasons:
                    print(f"  - {reason}")
        return 0 if not changes else 1

    elif args.command == "audit-deps":
        return _handle_audit_deps(args)

    elif args.command == "test":
        return _handle_contract_test(args)

    return 1


def _handle_contract_test(args: argparse.Namespace) -> int:
    """Handle `forseti contract test <spec> --base-url ...` (Cost: NETWORK, explicit opt-in)."""
    import yaml

    from Asgard.Forseti.LiveContract import LiveValidatorService, ProbePlannerService
    from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeConfig

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"Error: spec not found: {spec_path}", file=sys.stderr)
        return 1
    document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    plan = ProbePlannerService().plan(document)
    config = ProbeConfig(
        base_url=args.base_url,
        auth_header=args.auth_header,
        max_requests=args.max_requests,
        negative=args.negative,
        timeout_s=args.timeout_s,
        verify_tls=args.verify_tls,
    )
    report = LiveValidatorService(config).run(plan)

    if getattr(args, "format", "text") == "json":
        print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
    else:
        print("=" * 60)
        print("Live Contract Drift Report")
        print("=" * 60)
        print(f"Base URL: {report.base_url}")
        print(f"Operations attempted: {report.operations_attempted}  "
              f"succeeded: {report.operations_succeeded}")
        if report.findings:
            print("-" * 60)
            for finding in report.findings:
                print(f"  [{finding.rule_id}] {finding.severity.value.upper()}: {finding.message}")
        else:
            print("No drift findings.")
        print("=" * 60)

    return 1 if report.has_errors else 0


def _handle_audit_deps(args: argparse.Namespace) -> int:
    """
    Handle `forseti contract audit-deps` — 'npm-audit for APIs'
    (DEEPTHINK_07 §3). Config shape:

        dependencies:
          - spec: path/to/openapi.yaml
            operations: ["GET /users", "/orders/post"]
    """
    import yaml

    from datetime import date, timedelta

    from Asgard.Forseti.cli._handler_runner import (
        EXIT_GATE_FAILURE,
        EXIT_INPUT_ERROR,
        EXIT_OK,
    )

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"Error: config not found: {config_path}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Error: failed to parse config: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    horizon = max(0, int(getattr(args, "horizon", 30) or 30))
    deadline = date.today() + timedelta(days=horizon)
    service = BreakingChangeDetectorService()
    failures: list[str] = []
    warnings: list[str] = []
    checked = 0

    for dep in config.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        spec_ref = str(dep.get("spec", ""))
        if spec_ref.startswith(("http://", "https://")):
            print(f"SKIP {spec_ref}: remote specs are NETWORK-cost and not "
                  "fetched in this profile")
            continue
        spec_path = Path(spec_ref)
        if not spec_path.is_absolute():
            spec_path = config_path.parent / spec_path
        if not spec_path.is_file():
            print(f"Error: dependency spec not found: {spec_path}",
                  file=sys.stderr)
            return EXIT_INPUT_ERROR
        metas = service.extract_lifecycle(spec_path)
        for operation in dep.get("operations") or []:
            checked += 1
            key = _normalize_operation_key(str(operation))
            meta = metas.get(key)
            if meta is None or not meta.deprecated:
                continue
            label = f"{operation} ({spec_path.name})"
            if meta.sunset is None:
                warnings.append(f"{label} is deprecated (no sunset date declared)")
            elif meta.sunset <= deadline:
                failures.append(
                    f"{label} sunsets on {meta.sunset.isoformat()} "
                    f"(within {horizon}-day horizon)"
                )
            else:
                warnings.append(
                    f"{label} is deprecated, sunset {meta.sunset.isoformat()}"
                )

    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"Checked {checked} consumed operation(s): "
          f"{len(failures)} failing, {len(warnings)} warning(s)")
    return EXIT_GATE_FAILURE if failures else EXIT_OK


def _normalize_operation_key(operation: str) -> str:
    """Map 'GET /users' or '/users/get' onto the lifecycle location key."""
    text = operation.strip()
    match = re.match(
        r"^(GET|PUT|POST|DELETE|OPTIONS|HEAD|PATCH|TRACE)\s+(/\S*)$",
        text, re.IGNORECASE,
    )
    if match:
        return f"{match.group(2)}/{match.group(1).lower()}"
    return text


def _handle_jsonschema(args: argparse.Namespace) -> int:
    """Handle JSONSchema commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti jsonschema --help' for options.")
        return 1

    if args.command == "validate":
        config = JSONSchemaConfig(strict_mode=args.strict if hasattr(args, 'strict') else True)
        service = JSONSchemaValidatorService(config)
        result = service.validate_file(args.data_file, args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = JSONSchemaGeneratorService()
        print("Note: Generation requires importable Python modules")
        print("Use Python API: SchemaGeneratorService().from_pydantic(YourModel)")
        return 0

    elif args.command == "infer":
        service = SchemaInferenceService()
        result = service.infer_from_file(args.samples_file, title=args.title)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result.schema, f, indent=2)
            print(f"Inferred schema saved to {args.output}")
            print(f"Confidence: {result.confidence:.1%}")
        else:
            print(service.generate_report(result, args.format))
        return 0

    return 1
