import argparse
import shutil
from pathlib import Path

from Asgard.Freya.Visual.services import (
    ScreenshotCapture,
    VisualRegressionTester,
    LayoutValidator,
    StyleValidator,
)
from Asgard.Freya.Responsive.services import (
    BreakpointTester,
    TouchTargetValidator,
    ViewportTester,
    MobileCompatibilityTester,
)
from Asgard.Freya.cli._formatters import (
    format_layout_text,
    format_style_text,
    format_breakpoint_text,
    format_touch_text,
    format_viewport_text,
    format_mobile_text,
)


async def run_visual_capture(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run screenshot capture."""
    output_dir = str(Path(args.output).parent) if args.output else "./screenshots"
    capture = ScreenshotCapture(output_directory=output_dir)

    print(f"\nCapturing screenshot: {args.url}")
    print("-" * 60)

    if args.device:
        results = await capture.capture_with_devices(
            args.url,
            devices=[args.device]
        )
        result = results[0] if results else None
        if result is None:
            print(f"Error: Device '{args.device}' not found")
            return 1
    else:
        if getattr(args, "full_page", False):
            result = await capture.capture_full_page(args.url)
        else:
            result = await capture.capture_viewport(args.url)

    if args.output:
        shutil.move(result.file_path, args.output)
        print(f"Screenshot saved to: {args.output}")
    else:
        print(f"Screenshot saved to: {result.file_path}")

    return 0


async def run_visual_compare(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run visual comparison."""
    threshold = 1.0 - args.threshold
    tester = VisualRegressionTester(threshold=threshold)

    print(f"\nComparing images:")
    print(f"  Baseline: {args.baseline}")
    print(f"  Current:  {args.current}")
    print("-" * 60)

    result = tester.compare(args.baseline, args.current)

    if args.format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print(f"\nMatch: {'Yes' if not result.has_difference else 'No'}")
        print(f"Difference: {result.difference_percentage:.2f}%")
        if result.diff_image_path:
            print(f"Diff image: {result.diff_image_path}")

    return 1 if result.has_difference else 0


async def run_layout_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run layout validation."""
    validator = LayoutValidator()

    print(f"\nValidating layout: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_layout_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_style_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run style validation."""
    theme_file = getattr(args, "theme", None)
    validator = StyleValidator(theme_file=theme_file)

    print(f"\nValidating styles: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_style_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_breakpoint_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run breakpoint testing."""
    tester = BreakpointTester()

    print(f"\nTesting breakpoints: {args.url}")
    print("-" * 60)

    result = await tester.test(
        args.url,
        capture_screenshots=getattr(args, "screenshots", False)
    )

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_breakpoint_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.total_issues > 0 else 0


async def run_touch_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run touch target validation."""
    min_size = getattr(args, "min_size", 44)
    validator = TouchTargetValidator(min_touch_size=min_size)

    print(f"\nValidating touch targets: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_touch_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_viewport_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run viewport testing."""
    tester = ViewportTester()

    print(f"\nTesting viewport: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_viewport_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_mobile_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run mobile compatibility test."""
    tester = MobileCompatibilityTester()

    devices = getattr(args, "devices", None)

    print(f"\nTesting mobile compatibility: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url, devices=devices)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_mobile_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0
