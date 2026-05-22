# Heimdall Issues Module

## Overview

The Issues module provides persistent issue tracking with lifecycle management across analysis runs. Issues are stored in a SQLite database at `~/.asgard/issues.db`. This enables tracking which issues are new, how long they have persisted, who introduced them, and their current resolution status.

## Issue Lifecycle

```
open -> confirmed -> resolved -> closed
  |                     |
  +-> false_positive     +-> re-opened (back to open)
  |
  +-> wont_fix
```

| Status | Description |
|--------|-------------|
| `open` | Newly detected or active issue |
| `confirmed` | Reviewed and confirmed as a genuine issue |
| `resolved` | Fixed; will be closed when no longer detected |
| `closed` | No longer detected in the codebase |
| `false_positive` | Reviewed and determined to be a false alarm |
| `wont_fix` | Known issue, accepted risk, will not be fixed |

## Key Features

- **Upsert matching**: Issues are matched across scans by `file_path + rule_id + line_number` (with ±5 line proximity to handle minor edits). New occurrences update `last_seen`; disappearing issues move to `closed`.
- **Git blame enrichment**: On upsert, the author and commit of the introducing change are recorded automatically via `git blame`.
- **Issue persistence**: Issues survive across analysis runs; the `first_detected` timestamp is preserved.
- **Commenting**: Arbitrary comment text can be attached to any issue.

## Programmatic Usage

```python
from Asgard.Heimdall.Issues import IssueTracker
from Asgard.Heimdall.Issues.models import IssueFilter, IssueStatus, IssueSeverity

tracker = IssueTracker()

# Upsert issues from a security report (finds or creates, updates last_seen)
upserted = tracker.upsert_from_security_report(
    project_path="./src",
    security_report=security_report,
)

# Upsert issues from quality report
upserted += tracker.upsert_from_quality_report(
    project_path="./src",
    quality_report=quality_report,
)

# List open issues for a project
issues = tracker.list_issues(
    project_path="./src",
    filters=IssueFilter(status=IssueStatus.OPEN, severity=IssueSeverity.HIGH),
)

# Get summary statistics
summary = tracker.get_summary("./src")
print(f"Open: {summary.open_count}, False positives: {summary.false_positive_count}")

# Lifecycle transitions
tracker.mark_false_positive(issue_id="abc123", reason="Test data, not real credential")
tracker.mark_wont_fix(issue_id="def456")
tracker.resolve_issue(issue_id="ghi789")

# Assignment
tracker.assign_issue(issue_id="abc123", assignee="jake")

# Comment
tracker.add_comment(issue_id="abc123", comment="Investigated: comes from test fixture")

# Close issues no longer detected
tracker.close_resolved_issues(project_path="./src", current_issue_ids={"abc123", "def456"})
```

## Issue Fields

| Field | Description |
|-------|-------------|
| `issue_id` | UUID, unique per issue |
| `project_path` | Root path of the analysed project |
| `rule_id` | Rule identifier (e.g. `sql_injection`, `missing_docstring`) |
| `issue_type` | `bug`, `vulnerability`, `code_smell`, `security_hotspot` |
| `file_path` | File containing the issue |
| `line_number` | Line where the issue was detected |
| `severity` | `critical`, `high`, `medium`, `low`, `info` |
| `status` | See lifecycle above |
| `first_detected` | Timestamp of first occurrence |
| `last_seen` | Timestamp of most recent detection |
| `git_blame_author` | Developer who introduced the code (from git blame) |
| `assigned_to` | Developer assigned to fix the issue |
| `tags` | List of string tags for filtering |
| `comments` | List of comment objects with author/timestamp |
| `scan_count` | Number of times this issue has been detected |

## CLI Usage

```bash
python -m Heimdall issues list <path>                          # List all open issues
python -m Heimdall issues list <path> --status=open            # Filter by status
python -m Heimdall issues list <path> --severity=high          # Filter by severity
python -m Heimdall issues summary <path>                       # Summary statistics
python -m Heimdall issues show <issue_id>                      # Show issue detail
python -m Heimdall issues resolve <issue_id>                   # Mark resolved
python -m Heimdall issues false-positive <issue_id> --reason="..."
python -m Heimdall issues wont-fix <issue_id>
python -m Heimdall issues assign <issue_id> --to=<name>
python -m Heimdall issues comment <issue_id> --text="..."
```
