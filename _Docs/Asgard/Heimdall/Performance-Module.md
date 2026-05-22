# Heimdall Performance Module

## Overview

The Performance module provides comprehensive static performance analysis for codebases, identifying memory inefficiencies, CPU bottlenecks, database anti-patterns, and caching issues. It combines multiple specialized profilers into a unified performance scanning system.

## Analyzers

### 1. Memory Profiler Service

**Purpose**: Detects memory-related performance issues including leaks, high allocations, and inefficient data structures.

**Key Features**:
- Static analysis of memory allocation patterns
- Detection of common memory anti-patterns
- Recommendations for memory-efficient alternatives
- Support for Python, JavaScript, and TypeScript

**Detected Issue Types**:

| Type | Description | Severity |
|------|-------------|----------|
| `memory_leak` | Patterns that may cause memory leaks | HIGH |
| `high_allocation` | Large memory allocations | MEDIUM |
| `circular_reference` | Potential circular references | MEDIUM |
| `large_object` | Very large data structure creation | MEDIUM |
| `unbounded_growth` | Collections that may grow unbounded | HIGH |
| `inefficient_structure` | Suboptimal data structure choices | LOW |

**Detection Patterns**:

```python
# High allocation - readlines() (MEDIUM)
with open(file_path) as f:
    lines = f.readlines()  # Loads entire file into memory
# Recommendation: Iterate over file object directly

# High allocation - JSON load (MEDIUM)
with open(large_file) as f:
    data = json.load(f)  # Can use 2-10x file size in memory
# Recommendation: Use ijson for streaming large JSON files

# Potential memory leak - global list append (HIGH)
global_cache = []
def process(item):
    global_cache.append(item)  # Never cleared
# Recommendation: Use bounded collections or implement cleanup

# Unnecessary copy (LOW)
data_copy = data.copy()  # May not be necessary
# Recommendation: Check if copy is truly needed

# String concatenation in loop (MEDIUM)
result = ""
for item in items:
    result += str(item)  # Creates new string each iteration
# Recommendation: Use ''.join() or list comprehension
```

---

### 2. CPU Profiler Service

**Purpose**: Identifies CPU-intensive patterns including high complexity functions, inefficient loops, and blocking operations.

**Key Features**:
- Cyclomatic complexity calculation
- Detection of blocking operations
- Loop efficiency analysis
- Async/sync pattern detection

**Detected Issue Types**:

| Type | Description | Severity |
|------|-------------|----------|
| `high_complexity` | Functions with high cyclomatic complexity | MEDIUM-CRITICAL |
| `inefficient_loop` | Suboptimal loop patterns | LOW-MEDIUM |
| `blocking_operation` | Operations that block execution | MEDIUM |
| `excessive_recursion` | Deep or unbounded recursion | HIGH |
| `redundant_computation` | Repeated identical calculations | MEDIUM |
| `synchronous_io` | Synchronous I/O in async context | MEDIUM |

**Complexity Thresholds**:

| Complexity | Severity | Description |
|------------|----------|-------------|
| 11-15 | LOW | Moderately complex, consider refactoring |
| 16-20 | MEDIUM | Complex, should refactor |
| 21-30 | HIGH | Very complex, needs immediate attention |
| >30 | CRITICAL | Extremely complex, maintainability risk |

**Detection Examples**:

```python
# Synchronous sleep (MEDIUM)
import time
time.sleep(5)  # Blocks the thread
# Recommendation: Use asyncio.sleep() in async code

# Synchronous HTTP (MEDIUM)
response = requests.get(url)  # Blocks during network I/O
# Recommendation: Use aiohttp or httpx with async

# Regex backtracking risk (HIGH)
re.match(r".*?foo.*?bar.*?", text)  # Multiple greedy wildcards
# Recommendation: Use non-greedy quantifiers or rewrite pattern

# List membership check (LOW)
if item in [1, 2, 3, 4, 5]:  # O(n) lookup
# Recommendation: Use set literal for O(1) lookup

# range(len()) anti-pattern (LOW)
for i in range(len(items)):
    print(items[i])
# Recommendation: Use enumerate() or iterate directly

# Nested loops - JavaScript (MEDIUM)
for (let i = 0; i < arr1.length; i++) {
    for (let j = 0; j < arr2.length; j++) {  // O(n^2)
        // ...
    }
}
# Recommendation: Consider Map/Set for lookups

# DOM query in loop (MEDIUM - JS/TS)
items.forEach(item => {
    document.querySelector('.container')  // Re-queries DOM each iteration
})
# Recommendation: Cache DOM references before the loop
```

---

### 3. Database Analyzer Service

**Purpose**: Detects database performance anti-patterns including N+1 queries, missing indexes, and ORM inefficiencies.

**Key Features**:
- ORM framework detection (Django, SQLAlchemy, Peewee, etc.)
- N+1 query pattern detection
- Index usage analysis
- Query optimization recommendations

**Detected Issue Types**:

| Type | Description | Severity |
|------|-------------|----------|
| `n_plus_one` | N+1 query patterns | MEDIUM |
| `missing_index` | Queries that may need indexes | LOW-MEDIUM |
| `full_table_scan` | Operations that scan entire tables | MEDIUM |
| `excessive_queries` | Too many individual queries | LOW |
| `unoptimized_join` | Inefficient join patterns | MEDIUM |
| `no_pagination` | Large result sets without limits | MEDIUM |
| `eager_loading` | Missing eager loading for relationships | MEDIUM |

**Detected ORMs**:
- Django ORM
- SQLAlchemy
- Peewee
- Tortoise ORM
- Prisma

**Detection Examples**:

```python
# Full table scan - objects.all() (MEDIUM)
users = User.objects.all()  # Fetches entire table
# Recommendation: Add filters, limits, or use pagination

# Raw cursor execute (MEDIUM)
cursor.execute(query)  # Check if inside loop (N+1 risk)
# Recommendation: Use batch queries or bulk operations

# Leading wildcard LIKE (MEDIUM)
SELECT * FROM users WHERE name LIKE '%john%'
# Recommendation: Use full-text search or trigram indexes

# SELECT * (LOW)
SELECT * FROM users WHERE id = 1
# Recommendation: Select only required columns

# DISTINCT without index (LOW)
SELECT DISTINCT category FROM products
# Recommendation: Ensure columns have appropriate indexes

# Individual saves in loop (LOW)
for item in items:
    item.save()  # One query per object
# Recommendation: Use bulk_create() for multiple objects
```

---

### 4. Cache Analyzer Service

**Purpose**: Identifies caching issues and opportunities including missing caches, configuration problems, and anti-patterns.

**Key Features**:
- Cache system detection (Redis, Memcached, functools, etc.)
- Missing cache opportunity identification
- Cache configuration analysis
- TTL and key pattern validation

**Detected Issue Types**:

| Type | Description | Severity |
|------|-------------|----------|
| `missing_cache` | Functions that could benefit from caching | LOW-HIGH |
| `cache_miss` | Inefficient cache access patterns | MEDIUM |
| `stale_cache` | Cache without TTL (may serve stale data) | MEDIUM |
| `inefficient_key` | Poor cache key design | LOW |
| `cache_stampede` | Patterns susceptible to stampede | HIGH |
| `over_caching` | Unbounded cache growth | MEDIUM |

**Detected Cache Systems**:
- Redis
- Memcached
- Python functools (lru_cache, cache)
- Django Cache
- Flask-Caching
- Browser Storage (localStorage, sessionStorage)
- IndexedDB

**Detection Examples**:

```python
# Missing cache opportunity (LOW)
def get_user_data(user_id):  # get/fetch/load/compute pattern
    # Expensive operation without caching
    return database.query(user_id)
# Recommendation: Consider adding @lru_cache or external cache

# Cache without TTL (MEDIUM)
redis.set("user:123", data)  # No expiration set
# Recommendation: Always set a TTL appropriate for data freshness

# Simple cache key (LOW)
cache.get("user")  # No version identifier
# Recommendation: Include version prefix (e.g., 'v1:user:123')

# Query in template (HIGH)
{{ user.orders.all }}  # Database query in template
# Recommendation: Move queries to view/controller

# Unbounded lru_cache (MEDIUM)
@lru_cache()  # No maxsize - can grow unbounded
def compute_expensive(x):
    ...
# Recommendation: Use @lru_cache(maxsize=N) to limit size

# Synchronous localStorage (LOW - JS/TS)
localStorage.setItem("data", value)  # Blocks main thread
# Recommendation: Consider IndexedDB for larger data
```

---

### 5. Static Performance Service

**Purpose**: Orchestrates all performance analyzers into a unified scan with consolidated reporting.

**Key Features**:
- Runs all analyzers in a single scan
- Aggregates findings with severity counts
- Calculates overall performance score (0-100)
- Generates comprehensive reports

**Performance Score Calculation**:
```
Score = 100 - (critical * 20) - (high * 10) - (medium * 5) - (low * 1)
Score = max(0, Score)  # Floor at 0
```

| Score Range | Status |
|-------------|--------|
| 80-100 | Healthy |
| 60-79 | Needs Attention |
| 40-59 | At Risk |
| 0-39 | Critical |

---

## Usage Examples

### CLI Usage

```bash
# Full performance scan
python -m Heimdall performance scan ./src

# Specific analyzers
python -m Heimdall performance memory ./src
python -m Heimdall performance cpu ./src
python -m Heimdall performance database ./src
python -m Heimdall performance cache ./src

# With options
python -m Heimdall performance scan ./src --severity medium --format json
python -m Heimdall performance scan ./src --exclude "test_*" --format markdown
```

### Programmatic Usage

```python
from Heimdall.Performance import (
    StaticPerformanceService,
    MemoryProfilerService,
    CpuProfilerService,
    DatabaseAnalyzerService,
    CacheAnalyzerService,
    PerformanceScanConfig
)
from pathlib import Path

# Full performance scan
service = StaticPerformanceService()
report = service.scan(Path("./src"))

print(f"Performance Score: {report.performance_score}/100")
print(f"Total Issues: {report.total_issues}")
print(f"Critical: {report.critical_issues}")
print(f"High: {report.high_issues}")

# Memory profiling only
memory_service = MemoryProfilerService()
memory_report = memory_service.scan(Path("./src"))

for finding in memory_report.findings:
    print(f"[{finding.severity}] {finding.file_path}:{finding.line_number}")
    print(f"  Type: {finding.issue_type}")
    print(f"  {finding.description}")

# CPU profiling
cpu_service = CpuProfilerService()
cpu_report = cpu_service.scan(Path("./src"))

print(f"Average Complexity: {cpu_report.average_complexity:.1f}")
print(f"Max Complexity: {cpu_report.max_complexity}")

# Database analysis
db_service = DatabaseAnalyzerService()
db_report = db_service.scan(Path("./src"))

print(f"ORM Detected: {db_report.orm_detected}")
for finding in db_report.findings:
    print(f"[{finding.severity}] {finding.description}")

# Cache analysis
cache_service = CacheAnalyzerService()
cache_report = cache_service.scan(Path("./src"))

print(f"Cache Systems: {', '.join(cache_report.cache_systems_detected)}")
```

---

## Configuration

### PerformanceScanConfig

```python
PerformanceScanConfig(
    scan_path=Path("."),           # Root path to scan
    scan_memory=True,              # Enable memory analysis
    scan_cpu=True,                 # Enable CPU analysis
    scan_database=True,            # Enable database analysis
    scan_cache=True,               # Enable cache analysis
    min_severity="low",            # Minimum severity: info, low, medium, high, critical
    exclude_patterns=[             # Patterns to exclude
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "test",
        "tests"
    ],
    include_extensions=None,       # File extensions (None = all supported)
    complexity_threshold=10,       # Complexity threshold for findings
    memory_threshold_mb=100        # Memory threshold in MB
)
```

---

## Output Formats

### Text (Default)

```
============================================================
HEIMDALL PERFORMANCE ANALYSIS REPORT
============================================================
Scan Path: ./src
Scanned At: 2024-01-15 10:30:00
Duration: 0.85 seconds

----------------------------------------
SUMMARY
----------------------------------------
Performance Score: 72.0/100
Total Issues: 18
  Critical: 0
  High: 2
  Medium: 8
  Low: 8

----------------------------------------
MEMORY ANALYSIS
----------------------------------------
Files Scanned: 156
Issues Found: 5

  [MEDIUM] src/data_loader.py:45
    readlines() loads entire file into memory as list.
  [LOW] src/cache.py:23
    DataFrame/object copy may not be necessary.

----------------------------------------
CPU/COMPLEXITY ANALYSIS
----------------------------------------
Files Scanned: 156
Functions Analyzed: 892
Issues Found: 8
Average Complexity: 4.2
Max Complexity: 24.0

  [HIGH] src/processor.py:78
    Function has cyclomatic complexity of 24.

----------------------------------------
DATABASE ANALYSIS
----------------------------------------
Files Scanned: 156
Issues Found: 3
ORM Detected: SQLAlchemy

  [MEDIUM] src/models.py:156
    Raw SQL cursor execute - check if inside loop.

----------------------------------------
CACHE ANALYSIS
----------------------------------------
Files Scanned: 156
Issues Found: 2
Cache Systems: Redis, Python functools cache

  [LOW] src/services/user_service.py:34
    Function with get/fetch/load pattern may benefit from caching.

============================================================
RESULT: HEALTHY
============================================================
```

### JSON

```json
{
  "scan_path": "./src",
  "performance_score": 72.0,
  "total_issues": 18,
  "critical_issues": 0,
  "high_issues": 2,
  "memory_report": {
    "total_files_scanned": 156,
    "issues_found": 5,
    "findings": [...]
  },
  "cpu_report": {
    "total_files_scanned": 156,
    "total_functions_analyzed": 892,
    "average_complexity": 4.2,
    "max_complexity": 24.0,
    "findings": [...]
  },
  "database_report": {
    "orm_detected": "SQLAlchemy",
    "findings": [...]
  },
  "cache_report": {
    "cache_systems_detected": ["Redis", "Python functools cache"],
    "findings": [...]
  }
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Scan healthy (no critical/high issues) |
| 1 | Scan needs attention (critical or high issues found) |
| 2 | Fatal error during analysis |

---

## Best Practices

1. **Profile regularly**: Include performance scans in CI/CD pipelines
2. **Focus on high complexity**: Functions with complexity >15 should be refactored
3. **Review database patterns**: N+1 queries are common performance killers
4. **Cache strategically**: Not everything needs caching, but repeated expensive operations do
5. **Monitor memory patterns**: Especially in long-running services
6. **Consider async**: Blocking I/O is a common bottleneck in web applications
7. **Use appropriate severity**: Start with `--severity medium` for actionable findings
