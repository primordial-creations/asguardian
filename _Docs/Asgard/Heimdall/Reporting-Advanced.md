# Heimdall Reporting - Advanced Modules

## Overview

Three advanced reporting modules extend Heimdall's output capabilities: metrics history and trend tracking, PR/MR decoration for GitHub and GitLab, and an MCP server for AI agent integration.

---

## 1. Metrics History and Trend Tracking

**Location:** `Asgard/Asgard/Reporting/History/`

Persists analysis snapshots to a SQLite database at `~/.asgard/history.db` and calculates metric trends over time.

### Snapshot Contents

Each snapshot records:
- Project path, timestamp, git commit, and git branch
- Quality gate status at time of scan
- All dimension ratings (A-E)
- Key metric values (duplication %, debt hours, vulnerability counts, etc.)

### Trend Directions

| Direction | Meaning |
|-----------|---------|
| `IMPROVING` | Metric moving in a positive direction |
| `DEGRADING` | Metric moving in a negative direction |
| `STABLE` | No significant change |
| `INSUFFICIENT_DATA` | Fewer than 2 snapshots available |

Lower values are considered better for: duplication, complexity, debt, vulnerability counts, naming violations. Higher values are better for everything else (coverage, documentation density, etc.).

### Programmatic Usage

```python
from Asgard.Reporting.History import (
    AnalysisSnapshot,
    HistoryStore,
    MetricSnapshot,
    ReportingAnalyzerService,
)

store = HistoryStore()
analyzer = ReportingAnalyzerService(repository=store)

# Save a snapshot after running analysis
snapshot = AnalysisSnapshot(
    snapshot_id="",  # The SQLite adapter assigns an ID when this is empty.
    project_path="./src",
    git_commit="abc123",
    git_branch="main",
    quality_gate_status="passed",
    ratings={"overall": "B", "security": "A", "reliability": "B", "maintainability": "C"},
    metrics=[
        MetricSnapshot(metric_name="duplication_percentage", value=2.3, unit="%"),
        MetricSnapshot(metric_name="technical_debt_hours", value=14.5, unit="hours"),
        MetricSnapshot(metric_name="critical_vulnerabilities", value=0),
        MetricSnapshot(metric_name="high_vulnerabilities", value=2),
        MetricSnapshot(metric_name="comment_density", value=15.2, unit="%"),
    ],
)
store.save_snapshot(snapshot)

# Get trend report for a project
trend_report = analyzer.get_trend_report("./src")

for metric_trend in trend_report.metric_trends:
    print(f"{metric_trend.metric_name}: {metric_trend.direction} "
          f"(current={metric_trend.current_value}, previous={metric_trend.previous_value})")

# Get full snapshot history
snapshots = store.get_snapshots("./src")
for snap in snapshots:
    print(f"{snap.scan_timestamp}: gate={snap.quality_gate_status}, overall={snap.ratings.get('overall')}")
```

### Persistence Boundary

Application analysis depends on `IHistoryRepository`; the SQLite implementation
is an infrastructure adapter. `HistoryStore()` remains the compatibility
composition facade for callers that rely on the historical no-argument SQLite
default, while tests and alternate hosts can inject any repository satisfying
the same save, ordering, limit, latest-record and project-isolation contract.
Importing the port alone does not initialise SQLite or create filesystem state.

The on-disk SQLite schema and JSON fields are unchanged. If a rollout exposes a
consumer incompatibility, revert the History boundary files together and retain
the existing database; no data migration or rollback is required.

### CLI Usage

```bash
python -m Heimdall history show <path>           # Show trend report
python -m Heimdall history list <path>           # List all snapshots
python -m Heimdall history snapshot <path>       # Save a new snapshot (run analysis first)
python -m Heimdall history clear <path>          # Clear history for a project
```

---

## 2. PR Decoration

**Location:** `Asgard/Asgard/Reporting/PRDecoration/`

Posts Heimdall analysis results as comments on GitHub pull requests and GitLab merge requests. Posts a summary comment with quality gate status and ratings, plus inline review comments for detected issues.

### GitHub PR Decoration

```python
from Asgard.Reporting.PRDecoration import GitHubDecorator
from Asgard.Reporting.PRDecoration.models import PRDecorationConfig

config = PRDecorationConfig(
    platform="github",
    api_token=os.environ["GITHUB_TOKEN"],   # PAT or GITHUB_TOKEN
    repository="my-org/my-repo",             # owner/repo format
    pr_number=42,
    max_inline_comments=25,                  # Limit to avoid noise
)

decorator = GitHubDecorator()
result = decorator.decorate(
    config,
    issues=issue_list,          # List of TrackedIssue or similar
    gate_result=gate_result,    # Optional QualityGateResult
    ratings=ratings,            # Optional ProjectRatings
)

print(f"Summary posted: {result.summary_posted}")
print(f"Inline comments posted: {result.inline_comments_posted}")
```

### GitLab MR Decoration

```python
from Asgard.Reporting.PRDecoration import GitLabDecorator
from Asgard.Reporting.PRDecoration.models import PRDecorationConfig

config = PRDecorationConfig(
    platform="gitlab",
    api_token=os.environ["GITLAB_TOKEN"],
    gitlab_api_url=os.environ["GITLAB_API_URL"],  # e.g. https://gitlab.example.com/api/v4
    repository="my-group/my-project",
    pr_number=17,
)

decorator = GitLabDecorator()
result = decorator.decorate(config, issues=issue_list, gate_result=gate_result)
```

### Summary Comment Format

The summary comment includes:
- Quality gate status badge (PASSED / FAILED / WARNING)
- Dimension ratings table (Maintainability, Reliability, Security)
- Issue counts by severity
- Link to full report if available

### CLI Usage

```bash
# Decorate a GitHub PR (reads GITHUB_TOKEN from environment)
python -m Heimdall report decorate-pr \
    --platform=github \
    --repo=my-org/my-repo \
    --pr=42 \
    --scan-path=./src

# Decorate a GitLab MR
python -m Heimdall report decorate-pr \
    --platform=gitlab \
    --repo=my-group/my-project \
    --pr=17 \
    --scan-path=./src
```

### CI/CD Integration Example (GitHub Actions)

```yaml
- name: Run Heimdall and decorate PR
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    python -m Heimdall report decorate-pr \
      --platform=github \
      --repo=${{ github.repository }} \
      --pr=${{ github.event.pull_request.number }} \
      --scan-path=./src
```

---

## 3. MCP Server

**Location:** `Asgard/Asgard/MCP/`

An MCP (Model Context Protocol) server that exposes Asgard analysis data to AI agents and tools such as Claude Code, Cursor, and Windsurf.

### Capabilities

The MCP server exposes the following tools to AI agents:

| Tool | Description |
|------|-------------|
| `run_quality_analysis` | Run Heimdall quality analysis on a path |
| `run_security_scan` | Run Heimdall security scan on a path |
| `get_quality_gate_status` | Evaluate quality gate for a project |
| `get_ratings` | Get A-E ratings for a project |
| `get_issues` | List tracked issues with optional filters |
| `get_trend_report` | Retrieve metrics history and trends |
| `get_compliance_report` | Get OWASP/CWE compliance grades |
| `run_taint_analysis` | Run taint analysis for a path |

### Starting the Server

```bash
python -m Asgard.MCP.server
```

### Registering with Claude Code

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "asgard": {
      "command": "python",
      "args": ["-m", "Asgard.MCP.server"],
      "cwd": "/path/to/Asgard"
    }
  }
}
```

### Programmatic Usage

```python
from Asgard.MCP.server.asgard_mcp_server import AsgardMCPServer

server = AsgardMCPServer()
server.run()  # Starts stdio MCP server
```
