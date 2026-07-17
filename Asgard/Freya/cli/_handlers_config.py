"""
Freya CLI Config Handlers

Real implementations of `config init/show/validate` (Plan 06 §3.1),
replacing the previous stub in cli/__init__.py.
"""

import argparse

from pydantic import ValidationError

from Asgard.Freya.Config.services.config_loader import (
    discover_config_path,
    load_config,
    write_default_config,
)


def run_config_init(args: argparse.Namespace, verbose: bool = False) -> int:
    """`config init` — write a commented default `.freyarc`."""
    target_path = getattr(args, "config", None)
    path = write_default_config(target_path)
    print(f"Configuration file created: {path}")
    return 0


def run_config_show(args: argparse.Namespace, verbose: bool = False) -> int:
    """`config show` — print the merged effective config, source-annotated."""
    explicit_path = getattr(args, "config", None)
    try:
        result = load_config(explicit_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    except (ValueError, ValidationError) as exc:
        print(f"Error: invalid configuration — {exc}")
        return 1

    config = result.config
    source_label = f"from {result.source_path.name}" if result.source_path else "default"

    print("Configuration:")
    print(f"  wcag_level: {config.wcag_level} ({'from ' + result.source_path.name if 'wcag_level' in result.sourced_fields else 'default'})")
    print(f"  output_format: {config.output_format} ({'from ' + result.source_path.name if 'output_format' in result.sourced_fields else 'default'})")
    print(f"  categories: {config.categories} ({'from ' + result.source_path.name if 'categories' in result.sourced_fields else 'default'})")

    if config.crawl is not None:
        crawl_source = "from " + result.source_path.name if any(
            k.startswith("crawl.") or k == "crawl" for k in result.sourced_fields
        ) else "default"
        print(f"  crawl.max_depth: {config.crawl.max_depth} ({crawl_source})")
        print(f"  crawl.max_pages: {config.crawl.max_pages} ({crawl_source})")
        print(f"  crawl.concurrency: {config.crawl.concurrency} ({crawl_source})")
        print(f"  crawl.concurrency_discovery: {config.crawl.concurrency_discovery} ({crawl_source})")
        print(f"  crawl.min_request_interval_ms: {config.crawl.min_request_interval_ms} ({crawl_source})")
    else:
        print("  crawl: (not configured)")

    gate_source = "from " + result.source_path.name if any(
        k.startswith("gate.") or k == "gate" for k in result.sourced_fields
    ) else "default"
    print(f"  gate.fail_on: {[s.value for s in config.gate.fail_on]} ({gate_source})")
    print(f"  gate.min_grade: {config.gate.min_grade} ({gate_source})")
    print(f"  gate.max_findings: {config.gate.max_findings} ({gate_source})")

    visual_source = "from " + result.source_path.name if any(
        k.startswith("visual.") or k == "visual" for k in result.sourced_fields
    ) else "default"
    print(f"  visual.allow_env_mismatch: {config.visual.allow_env_mismatch} ({visual_source})")

    print("")
    print(f"Config source: {source_label}")
    return 0


def run_config_validate(args: argparse.Namespace, verbose: bool = False) -> int:
    """`config validate` — load and report Pydantic errors with context."""
    explicit_path = getattr(args, "config", None)
    try:
        path = discover_config_path(explicit_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    if path is None:
        print("No config file found (.freyarc / freya.yaml) — defaults are valid.")
        return 0

    try:
        load_config(explicit_path)
    except ValueError as exc:
        print(f"Invalid configuration: {exc}")
        return 1
    except ValidationError as exc:
        print(f"Invalid configuration in {path}:")
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"])
            print(f"  - {loc}: {error['msg']}")
        return 1

    print(f"Configuration valid: {path}")
    return 0
