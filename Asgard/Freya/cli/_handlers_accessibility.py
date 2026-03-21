import argparse

from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityConfig, WCAGLevel
from Asgard.Freya.Accessibility.services.wcag_validator import WCAGValidator
from Asgard.Freya.Accessibility.services.color_contrast import ColorContrastChecker
from Asgard.Freya.Accessibility.services.keyboard_nav import KeyboardNavigationTester
from Asgard.Freya.Accessibility.services.screen_reader import ScreenReaderValidator
from Asgard.Freya.Accessibility.services.aria_validator import ARIAValidator
from Asgard.Freya.cli._formatters import (
    format_accessibility_text,
    format_accessibility_markdown,
    format_accessibility_html,
    format_contrast_text,
    format_keyboard_text,
    format_aria_text,
    format_screen_reader_text,
)


async def run_accessibility_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run accessibility audit."""
    wcag_level = WCAGLevel(args.level)
    config = AccessibilityConfig(
        wcag_level=wcag_level,
        output_format=args.format,
    )

    validator = WCAGValidator(config)

    print(f"\nRunning accessibility audit on: {args.url}")
    print(f"WCAG Level: {wcag_level.value}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    elif args.format == "markdown":
        output = format_accessibility_markdown(result)
    elif args.format == "html":
        output = format_accessibility_html(result)
    else:
        output = format_accessibility_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_contrast_check(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run color contrast check."""
    wcag_level = WCAGLevel(args.level)
    config = AccessibilityConfig(wcag_level=wcag_level)

    checker = ColorContrastChecker(config)

    print(f"\nChecking color contrast on: {args.url}")
    print(f"WCAG Level: {wcag_level.value}")
    print("-" * 60)

    result = await checker.check(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_contrast_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_keyboard_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run keyboard navigation test."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    tester = KeyboardNavigationTester(config)

    print(f"\nTesting keyboard navigation on: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_keyboard_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_aria_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run ARIA validation."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    validator = ARIAValidator(config)

    print(f"\nValidating ARIA implementation on: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_aria_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_screen_reader_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run screen reader compatibility test."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    validator = ScreenReaderValidator(config)

    print(f"\nTesting screen reader compatibility on: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_screen_reader_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0
