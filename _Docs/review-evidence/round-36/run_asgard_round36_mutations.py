from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[1] / "asgard"
source = repo / "Asgard/Bragi/Quality/models/debt_models.py"
test = "Asgard_Test/tests_Bragi/L3_Contract/test_debt_value_model_contracts.py"
mutations = [
    ("default remediation kind", '        "constant", description="Remediation function shape"', '        "linear", description="Remediation function shape"'),
    ("negative base accepted", 'base_minutes: float = Field(0.0, ge=0.0, description="Constant part / offset in minutes")', 'base_minutes: float = Field(0.0, ge=-1.0, description="Constant part / offset in minutes")'),
    ("batchability above one accepted", '        0.5, ge=0.0, le=1.0,\n        description="Geometric discount', '        0.5, ge=0.0, le=2.0,\n        description="Geometric discount'),
    ("discount floor above one accepted", '        0.0, ge=0.0, le=1.0,\n        description=(\n            "Minimum per-item', '        0.0, ge=0.0, le=2.0,\n        description=(\n            "Minimum per-item'),
    ("effort midpoint divisor", 'return (self.low_minutes + self.high_minutes) / 2.0', 'return (self.low_minutes + self.high_minutes) / 3.0'),
    ("unknown confidence accepted", 'Literal["high", "medium", "low"]', 'Literal["high", "medium", "low", "unknown"]'),
    ("negative churn accepted", 'churn_commits_90d: int = Field(0, ge=0, description="Commits touching the file in 90 days")', 'churn_commits_90d: int = Field(0, ge=-1, description="Commits touching the file in 90 days")'),
    ("ROI default changed", 'overall_roi: float = Field(0.0, description="Overall ROI for addressing all debt")', 'overall_roi: float = Field(1.0, description="Overall ROI for addressing all debt")'),
    ("time horizon wire value changed", 'YEAR = "year"          # ~12 months', 'YEAR = "annual"        # ~12 months'),
    ("projection default changed", 'TimeHorizon.QUARTER, description="Time horizon for projection"', 'TimeHorizon.YEAR, description="Time horizon for projection"'),
    ("effort factor default changed", 'complexity_reduction_factor: float = Field(0.5, description="Hours per complexity point")', 'complexity_reduction_factor: float = Field(0.6, description="Hours per complexity point")'),
    ("interest default changed", 'no_tests: float = Field(0.15, description="15% worse per quarter for no tests")', 'no_tests: float = Field(0.16, description="15% worse per quarter for no tests")'),
]
original = source.read_text()
env = os.environ.copy()
env["TMPDIR"] = str(repo / ".task-tmp")
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
failures: list[str] = []
try:
    for name, old, new in mutations:
        if original.count(old) != 1:
            raise RuntimeError(f"{name}: expected one source target, found {original.count(old)}")
        source.write_text(original.replace(old, new, 1))
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test],
            cwd=repo,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            check=False,
        )
        rejected = result.returncode != 0
        print(f"{name}: exit={result.returncode} rejected={str(rejected).lower()}")
        if not rejected:
            failures.append(name)
        source.write_text(original)
finally:
    source.write_text(original)

if failures:
    print("SURVIVED: " + ", ".join(failures))
    raise SystemExit(1)
print(f"all {len(mutations)} mutations rejected")
