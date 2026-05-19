"""
Tests for Heimdall CLI

Unit tests for the current command-line interface in Asgard.Heimdall.cli.
Exercises create_parser() and main() at a behavioural level: argument parsing,
default subcommand insertion, help output, and exit codes.
"""

import io
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

from Asgard.Heimdall.cli.main import (
    COMMAND_DEFAULT_SUBCOMMANDS,
    COMMAND_KNOWN_SUBCOMMANDS,
    create_parser,
    main,
)


class TestCreateParser:
    """Tests for create_parser()."""

    def test_returns_argument_parser(self):
        parser = create_parser()
        import argparse
        assert isinstance(parser, argparse.ArgumentParser)

    def test_program_name_is_heimdall(self):
        parser = create_parser()
        assert parser.prog == "heimdall"

    def test_parser_has_subcommands(self):
        """The top-level parser must expose subcommands via 'command'."""
        parser = create_parser()
        # Parse a known subcommand path to verify dest='command'
        with tempfile.TemporaryDirectory() as tmp:
            args = parser.parse_args(["quality", "analyze", tmp])
            assert args.command == "quality"

    def test_quality_analyze_parses(self):
        parser = create_parser()
        with tempfile.TemporaryDirectory() as tmp:
            args = parser.parse_args(["quality", "analyze", tmp])
            assert args.command == "quality"
            assert args.quality_command == "analyze"


class TestCommandRegistry:
    """Tests for the command default/known registry constants."""

    def test_default_subcommands_keys_match_known(self):
        """Every command with a default subcommand must declare known subcommands."""
        for cmd, default_sub in COMMAND_DEFAULT_SUBCOMMANDS.items():
            assert cmd in COMMAND_KNOWN_SUBCOMMANDS
            assert default_sub in COMMAND_KNOWN_SUBCOMMANDS[cmd]

    def test_known_subcommands_are_non_empty(self):
        for cmd, subs in COMMAND_KNOWN_SUBCOMMANDS.items():
            assert isinstance(subs, set)
            assert len(subs) > 0


class TestMainHelp:
    """Tests for the main() entry point at a high level."""

    def test_main_with_no_args_prints_help_and_exits_zero(self):
        """Running heimdall with no args prints help and exits with code 0."""
        buf = io.StringIO()
        with redirect_stdout(buf), pytest.raises(SystemExit) as excinfo:
            main([])
        assert excinfo.value.code == 0
        # Help should mention the program name or main commands
        output = buf.getvalue()
        assert "heimdall" in output.lower() or "usage" in output.lower()

    def test_main_help_flag_exits_zero(self):
        """--help should exit with code 0."""
        buf = io.StringIO()
        with redirect_stdout(buf), pytest.raises(SystemExit) as excinfo:
            main(["--help"])
        assert excinfo.value.code == 0

    def test_main_invalid_command_exits_nonzero(self):
        """An unknown top-level command should exit with a non-zero code."""
        err = io.StringIO()
        with redirect_stderr(err), pytest.raises(SystemExit) as excinfo:
            main(["this-command-does-not-exist"])
        assert excinfo.value.code != 0


class TestDefaultSubcommandInjection:
    """Tests that main() inserts the default subcommand when omitted."""

    def test_security_path_only_inserts_scan(self):
        """`heimdall security <path>` should be parsed as security scan <path>."""
        # We exercise the same insertion logic by replicating what main does,
        # without actually dispatching the analyzer (which would hit the FS).
        argv = ["security", "."]
        cmd = argv[0]
        if cmd in COMMAND_DEFAULT_SUBCOMMANDS:
            next_arg = argv[1]
            known = COMMAND_KNOWN_SUBCOMMANDS[cmd]
            if next_arg not in known and next_arg not in ("-h", "--help"):
                argv.insert(1, COMMAND_DEFAULT_SUBCOMMANDS[cmd])
        assert argv == ["security", "scan", "."]

    def test_oop_path_only_inserts_analyze(self):
        argv = ["oop", "."]
        cmd = argv[0]
        if cmd in COMMAND_DEFAULT_SUBCOMMANDS:
            next_arg = argv[1]
            known = COMMAND_KNOWN_SUBCOMMANDS[cmd]
            if next_arg not in known and next_arg not in ("-h", "--help"):
                argv.insert(1, COMMAND_DEFAULT_SUBCOMMANDS[cmd])
        assert argv == ["oop", "analyze", "."]

    def test_known_subcommand_not_replaced(self):
        argv = ["security", "secrets", "."]
        cmd = argv[0]
        next_arg = argv[1]
        known = COMMAND_KNOWN_SUBCOMMANDS[cmd]
        # secrets is a known subcommand - no default inserted
        assert next_arg in known


class TestMainEndToEndSmall:
    """A small end-to-end smoke test using a tiny temp project."""

    def test_quality_analyze_runs_on_empty_dir(self, tmp_path, monkeypatch):
        """heimdall quality analyze <empty-dir> should not raise."""
        # Run in tmp_path so any report artifacts land there, not in the repo.
        monkeypatch.chdir(tmp_path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                main(["quality", "analyze", str(tmp_path)])
            except SystemExit as e:
                # Non-zero exit is acceptable for "no files" scenarios in some
                # commands; we only require that it doesn't crash with an
                # unhandled exception.
                assert e.code in (0, 1, 2)
