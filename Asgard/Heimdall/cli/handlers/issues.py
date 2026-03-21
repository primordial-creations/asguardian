import argparse
import json
import traceback as _traceback
from pathlib import Path

from Asgard.Heimdall.Issues.models.issue_models import (
    IssueFilter,
    IssueStatus,
    IssueSeverity,
    IssueType,
    IssuesSummary,
    TrackedIssue,
)
from Asgard.Heimdall.Issues.services.issue_tracker import IssueTracker


def run_issues_command(args: argparse.Namespace, verbose: bool = False) -> int:
    subcommand = getattr(args, "issues_command", None)

    if subcommand == "list":
        return _run_issues_list(args, verbose)
    if subcommand == "show":
        return _run_issues_show(args, verbose)
    if subcommand == "update":
        return _run_issues_update(args, verbose)
    if subcommand == "assign":
        return _run_issues_assign(args, verbose)
    if subcommand == "summary":
        return _run_issues_summary(args, verbose)

    print("Error: Please specify an issues subcommand (list, show, update, assign, summary).")
    return 1


def _run_issues_list(args: argparse.Namespace, verbose: bool) -> int:
    try:
        project_path = str(Path(args.path).resolve())
        tracker = IssueTracker()

        status_vals = getattr(args, "status", None)
        severity_vals = getattr(args, "severity", None)
        rule_val = getattr(args, "rule", None)

        issue_filter = None
        if status_vals or severity_vals or rule_val:
            issue_filter = IssueFilter(
                status=[IssueStatus(s) for s in status_vals] if status_vals else None,
                severity=[IssueSeverity(s) for s in severity_vals] if severity_vals else None,
                rule_id=rule_val,
            )

        issues = tracker.get_issues(project_path, issue_filter)
        output_format = getattr(args, "format", "text")

        if output_format == "json":
            print(json.dumps([i.dict() for i in issues], default=str, indent=2))
            return 0

        if not issues:
            print(f"No issues found for project: {project_path}")
            return 0

        print(f"\nIssues for: {project_path}")
        print("=" * 70)
        for issue in issues:
            print(
                f"  [{str(issue.severity).upper()}] {issue.issue_id[:8]}  {issue.title}"
            )
            print(f"    Rule: {issue.rule_id}  Status: {issue.status}  File: {issue.file_path}:{issue.line_number}")
            if verbose:
                print(f"    First seen: {issue.first_detected}  Last seen: {issue.last_seen}")
                if issue.assigned_to:
                    print(f"    Assigned to: {issue.assigned_to}")
            print()
        print(f"Total: {len(issues)} issue(s)")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def _run_issues_show(args: argparse.Namespace, verbose: bool) -> int:
    try:
        issue_id = args.issue_id
        tracker = IssueTracker()
        issue = tracker.get_issue(issue_id)

        if not issue:
            print(f"Issue not found: {issue_id}")
            return 1

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(issue.dict(), default=str, indent=2))
            return 0

        print(f"\nIssue: {issue.issue_id}")
        print("=" * 70)
        print(f"  Title:       {issue.title}")
        print(f"  Rule:        {issue.rule_id}")
        print(f"  Type:        {issue.issue_type}")
        print(f"  Severity:    {issue.severity}")
        print(f"  Status:      {issue.status}")
        print(f"  File:        {issue.file_path}:{issue.line_number}")
        print(f"  First seen:  {issue.first_detected}")
        print(f"  Last seen:   {issue.last_seen}")
        print(f"  Scan count:  {issue.scan_count}")
        if issue.assigned_to:
            print(f"  Assigned to: {issue.assigned_to}")
        if issue.git_blame_author:
            print(f"  Author:      {issue.git_blame_author}  ({issue.git_blame_commit})")
        if issue.false_positive_reason:
            print(f"  FP Reason:   {issue.false_positive_reason}")
        print(f"\n  Description: {issue.description}")
        if issue.comments:
            print("\n  Comments:")
            for comment in issue.comments:
                print(f"    - {comment}")
        if issue.tags:
            print(f"\n  Tags: {', '.join(issue.tags)}")
        print()
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def _run_issues_update(args: argparse.Namespace, verbose: bool) -> int:
    try:
        issue_id = args.issue_id
        new_status = IssueStatus(args.status)
        reason = getattr(args, "reason", None)

        tracker = IssueTracker()
        updated = tracker.update_status(issue_id, new_status, reason)

        if not updated:
            print(f"Issue not found: {issue_id}")
            return 1

        print(f"Issue {issue_id[:8]} status updated to: {updated.status}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def _run_issues_assign(args: argparse.Namespace, verbose: bool) -> int:
    try:
        issue_id = args.issue_id
        assignee = args.assignee

        tracker = IssueTracker()
        updated = tracker.assign_issue(issue_id, assignee)

        if not updated:
            print(f"Issue not found: {issue_id}")
            return 1

        print(f"Issue {issue_id[:8]} assigned to: {updated.assigned_to}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1


def _run_issues_summary(args: argparse.Namespace, verbose: bool) -> int:
    try:
        project_path = str(Path(args.path).resolve())
        tracker = IssueTracker()
        summary = tracker.get_summary(project_path)

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(summary.dict(), default=str, indent=2))
            return 0

        print(f"\nIssue Summary for: {project_path}")
        print("=" * 70)
        print(f"  Open:            {summary.total_open}")
        print(f"  Confirmed:       {summary.total_confirmed}")
        print(f"  Resolved:        {summary.total_resolved}")
        print(f"  False Positives: {summary.total_false_positives}")
        print(f"  Wont Fix:        {summary.total_wont_fix}")
        if summary.open_by_severity:
            print("\n  Open by Severity:")
            for sev, count in sorted(summary.open_by_severity.items()):
                print(f"    {sev:12s}: {count}")
        if summary.open_by_type:
            print("\n  Open by Type:")
            for itype, count in sorted(summary.open_by_type.items()):
                print(f"    {itype:20s}: {count}")
        if summary.oldest_open_issue:
            print(f"\n  Oldest open issue: {summary.oldest_open_issue}")
        print()
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        if verbose:
            _traceback.print_exc()
        return 1
