import argparse

from Asgard.Freya.Images.services.image_optimization_scanner import ImageOptimizationScanner
from Asgard.Freya.Images.models.image_models import ImageConfig
from Asgard.Freya.cli._formatters_images import (
    format_images_text,
    format_images_alt_text,
    format_images_performance_text,
)


async def run_images_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run full image optimization audit."""
    config = ImageConfig(
        include_all_images=getattr(args, "include_all", False),
    )
    scanner = ImageOptimizationScanner(config)

    print(f"\nScanning images: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_critical_issues else 0


async def run_images_alt_text(args: argparse.Namespace, verbose: bool = False) -> int:
    """Check image alt text only."""
    scanner = ImageOptimizationScanner()

    print(f"\nChecking image alt text: {args.url}")
    print("-" * 60)

    result = await scanner.check_alt_text(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_alt_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_accessibility_issues else 0


async def run_images_performance(args: argparse.Namespace, verbose: bool = False) -> int:
    """Check image performance issues only."""
    config = ImageConfig(
        oversized_threshold=getattr(args, "oversized_threshold", 1.5),
    )
    scanner = ImageOptimizationScanner(config)

    print(f"\nChecking image performance: {args.url}")
    print("-" * 60)

    result = await scanner.check_performance(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_performance_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.warning_count > 0 else 0
