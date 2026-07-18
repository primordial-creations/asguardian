"""
Heimdall CLI - Calibration and evaluation subparser setup.

Wires Bragi's Calibration services (local threshold calibration, empirical
rule validity) and Heimdall's own evaluation harness onto the CLI:

- calibrate run              (Bragi Calibration/services/local_calibrator.py)
- validate-rules              (Bragi Calibration/services/rule_validator.py)
- eval run                    (Heimdall evaluation/runner.py + gate.py)
"""

import argparse


def setup_calibrate_command(subparsers) -> None:
    """Set up the calibrate command group."""
    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Derive locally-calibrated metric thresholds from sampled data (Bragi)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall calibrate run samples.json\n"
            "  heimdall calibrate run samples.json --write --format json\n"
        ),
    )
    calibrate_subparsers = calibrate_parser.add_subparsers(
        dest="calibrate_command", help="Calibrate subcommand to run"
    )

    run_parser = calibrate_subparsers.add_parser(
        "run",
        help="Calibrate a local per-language profile from sampled metric distributions",
    )
    run_parser.add_argument(
        "input_file",
        help=(
            "JSON file: {language, metric_samples: {metric: [values...]}, "
            "anchor_profile: {...LanguageProfile...}, min_sample_size?}"
        ),
    )
    run_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    run_parser.add_argument(
        "--write", action="store_true",
        help="Write the derived profile to .asgard_cache/bragi_local_profile.yaml",
    )


def setup_validate_rules_command(subparsers) -> None:
    """Set up the top-level validate-rules command."""
    parser = subparsers.add_parser(
        "validate-rules",
        help="Score empirical rule validity from bugfix-vs-clean file observations (Bragi)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall validate-rules observations.json\n"
            "  heimdall validate-rules observations.json --format json\n"
        ),
    )
    parser.add_argument(
        "input_file",
        help=(
            "JSON file: {rule_id, observations: [{file_path, loc, "
            "violation_count, touched_by_bugfix}, ...], burn_in_threshold?}"
        ),
    )
    parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )


def setup_eval_command(subparsers) -> None:
    """Set up the eval command group (Heimdall's own evaluation harness)."""
    eval_parser = subparsers.add_parser(
        "eval",
        help="Run the Heimdall evaluation harness against findings + ground truth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall eval run corpus.json\n"
            "  heimdall eval run corpus.json --profile default --format json\n"
        ),
    )
    eval_subparsers = eval_parser.add_subparsers(
        dest="eval_command", help="Eval subcommand to run"
    )

    run_parser = eval_subparsers.add_parser(
        "run",
        help="Compute corpus precision/recall/F-scores, optionally gated by an acceptance profile",
    )
    run_parser.add_argument(
        "input_file",
        help=(
            "JSON file: {findings: [...ReportedFinding...], "
            "ground_truth: [...GroundTruthInstance...], total_loc: int, "
            "fallback: 3?}"
        ),
    )
    run_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    run_parser.add_argument(
        "--gate-profile", type=str, default=None,
        help="Acceptance-profile name to gate the run against (skips gating if omitted)",
    )
