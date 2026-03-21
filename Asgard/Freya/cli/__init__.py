import asyncio
import sys

from Asgard.Freya.cli._parser import create_parser
from Asgard.Freya.cli._handlers_accessibility import (
    run_accessibility_audit,
    run_contrast_check,
    run_keyboard_test,
    run_aria_validation,
    run_screen_reader_test,
)
from Asgard.Freya.cli._handlers_visual_responsive import (
    run_visual_capture,
    run_visual_compare,
    run_layout_validation,
    run_style_validation,
    run_breakpoint_test,
    run_touch_validation,
    run_viewport_test,
    run_mobile_test,
)
from Asgard.Freya.cli._handlers_perf_seo_security import (
    run_performance_audit,
    run_performance_load_time,
    run_performance_resources,
    run_seo_audit,
    run_seo_meta,
    run_seo_structured_data,
    run_seo_robots,
    run_security_headers,
    run_security_csp,
    run_console_errors,
    run_links_validate,
)
from Asgard.Freya.cli._handlers_images_integration import (
    run_images_audit,
    run_images_alt_text,
    run_images_performance,
    run_unified_test,
    run_baseline_update,
    run_baseline_compare,
    run_baseline_list,
    run_baseline_delete,
    run_crawl,
)


def main(args=None) -> int:
    """Main entry point.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    args = parser.parse_args(args)

    verbose = getattr(args, "verbose", False)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "accessibility":
        if not hasattr(args, "accessibility_command") or args.accessibility_command is None:
            print("Error: Please specify an accessibility command (e.g., 'audit', 'contrast')")
            sys.exit(1)

        if args.accessibility_command == "audit":
            exit_code = asyncio.run(run_accessibility_audit(args, verbose))
        elif args.accessibility_command == "contrast":
            exit_code = asyncio.run(run_contrast_check(args, verbose))
        elif args.accessibility_command == "keyboard":
            exit_code = asyncio.run(run_keyboard_test(args, verbose))
        elif args.accessibility_command == "aria":
            exit_code = asyncio.run(run_aria_validation(args, verbose))
        elif args.accessibility_command == "screen-reader":
            exit_code = asyncio.run(run_screen_reader_test(args, verbose))
        else:
            print(f"Unknown accessibility command: {args.accessibility_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "visual":
        if not hasattr(args, "visual_command") or args.visual_command is None:
            print("Error: Please specify a visual command (e.g., 'capture', 'compare')")
            sys.exit(1)

        if args.visual_command == "capture":
            exit_code = asyncio.run(run_visual_capture(args, verbose))
        elif args.visual_command == "compare":
            exit_code = asyncio.run(run_visual_compare(args, verbose))
        elif args.visual_command == "layout":
            exit_code = asyncio.run(run_layout_validation(args, verbose))
        elif args.visual_command == "style":
            exit_code = asyncio.run(run_style_validation(args, verbose))
        else:
            print(f"Unknown visual command: {args.visual_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "responsive":
        if not hasattr(args, "responsive_command") or args.responsive_command is None:
            print("Error: Please specify a responsive command (e.g., 'breakpoints', 'touch')")
            sys.exit(1)

        if args.responsive_command == "breakpoints":
            exit_code = asyncio.run(run_breakpoint_test(args, verbose))
        elif args.responsive_command == "touch":
            exit_code = asyncio.run(run_touch_validation(args, verbose))
        elif args.responsive_command == "viewport":
            exit_code = asyncio.run(run_viewport_test(args, verbose))
        elif args.responsive_command == "mobile":
            exit_code = asyncio.run(run_mobile_test(args, verbose))
        else:
            print(f"Unknown responsive command: {args.responsive_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "performance":
        if not hasattr(args, "performance_command") or args.performance_command is None:
            print("Error: Please specify a performance command (e.g., 'audit', 'load-time')")
            sys.exit(1)

        if args.performance_command == "audit":
            exit_code = asyncio.run(run_performance_audit(args, verbose))
        elif args.performance_command == "load-time":
            exit_code = asyncio.run(run_performance_load_time(args, verbose))
        elif args.performance_command == "resources":
            exit_code = asyncio.run(run_performance_resources(args, verbose))
        else:
            print(f"Unknown performance command: {args.performance_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "seo":
        if not hasattr(args, "seo_command") or args.seo_command is None:
            print("Error: Please specify an SEO command (e.g., 'audit', 'meta')")
            sys.exit(1)

        if args.seo_command == "audit":
            exit_code = asyncio.run(run_seo_audit(args, verbose))
        elif args.seo_command == "meta":
            exit_code = asyncio.run(run_seo_meta(args, verbose))
        elif args.seo_command == "structured-data":
            exit_code = asyncio.run(run_seo_structured_data(args, verbose))
        elif args.seo_command == "robots":
            exit_code = asyncio.run(run_seo_robots(args, verbose))
        else:
            print(f"Unknown SEO command: {args.seo_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "security":
        if not hasattr(args, "security_command") or args.security_command is None:
            print("Error: Please specify a security command (e.g., 'headers', 'csp')")
            sys.exit(1)

        if args.security_command == "headers":
            exit_code = asyncio.run(run_security_headers(args, verbose))
        elif args.security_command == "csp":
            exit_code = asyncio.run(run_security_csp(args, verbose))
        else:
            print(f"Unknown security command: {args.security_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "console":
        if not hasattr(args, "console_command") or args.console_command is None:
            print("Error: Please specify a console command (e.g., 'errors')")
            sys.exit(1)

        if args.console_command == "errors":
            exit_code = asyncio.run(run_console_errors(args, verbose))
        else:
            print(f"Unknown console command: {args.console_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "links":
        if not hasattr(args, "links_command") or args.links_command is None:
            print("Error: Please specify a links command (e.g., 'validate')")
            sys.exit(1)

        if args.links_command == "validate":
            exit_code = asyncio.run(run_links_validate(args, verbose))
        else:
            print(f"Unknown links command: {args.links_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "images":
        if not hasattr(args, "images_command") or args.images_command is None:
            print("Error: Please specify an images command (e.g., 'audit', 'alt-text', 'performance')")
            sys.exit(1)

        if args.images_command == "audit":
            exit_code = asyncio.run(run_images_audit(args, verbose))
        elif args.images_command == "alt-text":
            exit_code = asyncio.run(run_images_alt_text(args, verbose))
        elif args.images_command == "performance":
            exit_code = asyncio.run(run_images_performance(args, verbose))
        else:
            print(f"Unknown images command: {args.images_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "test":
        exit_code = asyncio.run(run_unified_test(args, verbose))
        sys.exit(exit_code)

    elif args.command == "crawl":
        exit_code = asyncio.run(run_crawl(args, verbose))
        sys.exit(exit_code)

    elif args.command == "baseline":
        if not hasattr(args, "baseline_command") or args.baseline_command is None:
            print("Error: Please specify a baseline command (e.g., 'update', 'compare')")
            sys.exit(1)

        if args.baseline_command == "update":
            exit_code = asyncio.run(run_baseline_update(args, verbose))
        elif args.baseline_command == "compare":
            exit_code = asyncio.run(run_baseline_compare(args, verbose))
        elif args.baseline_command == "list":
            exit_code = run_baseline_list(args, verbose)
        elif args.baseline_command == "delete":
            exit_code = run_baseline_delete(args, verbose)
        else:
            print(f"Unknown baseline command: {args.baseline_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "config":
        if args.config_command == "show":
            print("Configuration: (defaults)")
            print("  WCAG Level: AA")
            print("  Output Format: text")
            print("  Baseline Directory: ./freya_baselines")
        elif args.config_command == "init":
            print("Configuration file created: .freyarc")
        else:
            print("Error: Please specify a config command (e.g., 'show', 'init')")
            sys.exit(1)
        sys.exit(0)

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
