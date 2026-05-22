# Verdandi System Module

## Overview

The System module provides analysis for system resource metrics including memory usage, CPU utilization, and I/O performance.

## Services

### 1. Memory Calculator

**Purpose**: Analyzes memory usage patterns and identifies potential issues.

**Memory Metrics**:
| Metric | Description |
|--------|-------------|
| Used | Currently allocated memory |
| Free | Unallocated memory |
| Cached | Memory used for caching |
| Buffers | Memory used for buffers |
| Available | Memory available for allocation |
| Swap Used | Swap space in use |

**Health Status**:
| Status | Usage |
|--------|-------|
| HEALTHY | < 70% |
| WARNING | 70-85% |
| CRITICAL | > 85% |

**Usage**:
```python
from Verdandi.System import MemoryCalculator

calculator = MemoryCalculator()

memory_data = {
    "total_bytes": 16_000_000_000,
    "used_bytes": 10_000_000_000,
    "free_bytes": 2_000_000_000,
    "cached_bytes": 3_000_000_000,
    "buffers_bytes": 1_000_000_000,
    "swap_total_bytes": 8_000_000_000,
    "swap_used_bytes": 500_000_000
}

result = calculator.analyze(memory_data)

print(f"Usage: {result.usage_percent:.1f}%")
print(f"Available: {result.available_bytes / 1_000_000_000:.1f}GB")
print(f"Status: {result.health_status}")
print(f"Swap Usage: {result.swap_usage_percent:.1f}%")

# Time-series analysis for trends
history = [
    {"timestamp": 1, "used_bytes": 10_000_000_000},
    {"timestamp": 2, "used_bytes": 10_500_000_000},
    {"timestamp": 3, "used_bytes": 11_000_000_000},
]
trend_result = calculator.analyze_trend(history)
print(f"Trend: {trend_result.trend}")
```

---

### 2. CPU Calculator

**Purpose**: Analyzes CPU utilization and identifies performance bottlenecks.

**CPU Metrics**:
| Metric | Description |
|--------|-------------|
| User | Time in user mode |
| System | Time in kernel mode |
| Idle | Idle time |
| IOWait | Waiting for I/O |
| Steal | Time stolen by hypervisor |
| Context Switches | Number of context switches |
| Load Average | 1/5/15 minute load |

**Health Status**:
| Status | Utilization |
|--------|-------------|
| HEALTHY | < 70% |
| WARNING | 70-85% |
| CRITICAL | > 85% |
| IOWAIT_HIGH | IOWait > 20% |

**Usage**:
```python
from Verdandi.System import CpuCalculator

calculator = CpuCalculator()

cpu_data = {
    "user_percent": 45.0,
    "system_percent": 15.0,
    "idle_percent": 35.0,
    "iowait_percent": 5.0,
    "steal_percent": 0.0,
    "cpu_count": 8,
    "load_1m": 4.5,
    "load_5m": 4.2,
    "load_15m": 4.0,
    "context_switches": 50000
}

result = calculator.analyze(cpu_data)

print(f"Total Utilization: {result.total_utilization_percent:.1f}%")
print(f"User: {result.user_percent:.1f}%")
print(f"System: {result.system_percent:.1f}%")
print(f"IOWait: {result.iowait_percent:.1f}%")
print(f"Status: {result.health_status}")
print(f"Load per CPU: {result.load_per_cpu:.2f}")

# Per-core analysis
per_core_data = [
    {"core": 0, "utilization": 80},
    {"core": 1, "utilization": 45},
    {"core": 2, "utilization": 90},
    {"core": 3, "utilization": 30},
]
core_result = calculator.analyze_per_core(per_core_data)
print(f"Hottest Core: {core_result.hottest_core}")
print(f"Imbalance: {core_result.imbalance_ratio:.2f}")
```

---

### 3. I/O Calculator

**Purpose**: Analyzes disk I/O performance and throughput.

**I/O Metrics**:
| Metric | Description |
|--------|-------------|
| Read IOPS | Read operations per second |
| Write IOPS | Write operations per second |
| Read Throughput | Read MB/s |
| Write Throughput | Write MB/s |
| Avg Latency | Average I/O latency |
| Queue Depth | I/O queue depth |
| Utilization | Disk busy percentage |

**Health Status**:
| Status | Condition |
|--------|-----------|
| HEALTHY | Utilization < 70%, latency < 20ms |
| WARNING | Utilization 70-85% or latency 20-50ms |
| CRITICAL | Utilization > 85% or latency > 50ms |

**Usage**:
```python
from Verdandi.System import IoCalculator

calculator = IoCalculator()

io_data = {
    "read_iops": 1500,
    "write_iops": 500,
    "read_bytes_per_sec": 100_000_000,
    "write_bytes_per_sec": 50_000_000,
    "avg_latency_ms": 5.0,
    "queue_depth": 32,
    "utilization_percent": 45.0
}

result = calculator.analyze(io_data)

print(f"Total IOPS: {result.total_iops}")
print(f"Read Throughput: {result.read_throughput_mbps:.1f} MB/s")
print(f"Write Throughput: {result.write_throughput_mbps:.1f} MB/s")
print(f"Avg Latency: {result.avg_latency_ms:.1f}ms")
print(f"Status: {result.health_status}")

# Per-device analysis
devices = [
    {"device": "sda", "read_iops": 1000, "write_iops": 300, "utilization": 40},
    {"device": "sdb", "read_iops": 500, "write_iops": 200, "utilization": 80},
]
device_result = calculator.analyze_per_device(devices)
for dev in device_result.devices:
    print(f"{dev.name}: {dev.utilization}% utilized")
```

---

## CLI Usage

```bash
# Memory analysis
python -m Verdandi system memory stats.json
python -m Verdandi system memory data.json --threshold=80

# CPU analysis
python -m Verdandi system cpu metrics.json
python -m Verdandi system cpu data.json --format=json

# I/O analysis
python -m Verdandi system io iostat.json
python -m Verdandi system io data.json --format=markdown
```

---

## Models Reference

### MemoryMetrics
```python
class MemoryMetrics(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    cached_bytes: Optional[int] = None
    buffers_bytes: Optional[int] = None
    available_bytes: Optional[int] = None
    swap_total_bytes: Optional[int] = None
    swap_used_bytes: Optional[int] = None
```

### MemoryResult
```python
class MemoryResult(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    swap_usage_percent: Optional[float]
    health_status: str
    recommendations: List[str]
```

### CpuMetrics
```python
class CpuMetrics(BaseModel):
    user_percent: float
    system_percent: float
    idle_percent: float
    iowait_percent: Optional[float] = None
    steal_percent: Optional[float] = None
    cpu_count: int
    load_1m: Optional[float] = None
    load_5m: Optional[float] = None
    load_15m: Optional[float] = None
    context_switches: Optional[int] = None
```

### CpuResult
```python
class CpuResult(BaseModel):
    total_utilization_percent: float
    user_percent: float
    system_percent: float
    iowait_percent: float
    load_per_cpu: float
    health_status: str
    recommendations: List[str]
```

### IoMetrics
```python
class IoMetrics(BaseModel):
    read_iops: int
    write_iops: int
    read_bytes_per_sec: int
    write_bytes_per_sec: int
    avg_latency_ms: float
    queue_depth: Optional[int] = None
    utilization_percent: Optional[float] = None
```

### IoResult
```python
class IoResult(BaseModel):
    total_iops: int
    read_throughput_mbps: float
    write_throughput_mbps: float
    avg_latency_ms: float
    utilization_percent: float
    health_status: str
    recommendations: List[str]
```

---

## Best Practices

### Memory
- Keep usage below 85% to avoid OOM situations
- Monitor swap usage - consistent swap indicates insufficient RAM
- Watch for memory leak trends over time

### CPU
- High IOWait indicates I/O bottleneck, not CPU issue
- Load average > CPU count indicates saturation
- Monitor context switches for threading issues

### I/O
- SSD latency should be < 5ms, HDD < 20ms
- Queue depth > 1 indicates I/O backpressure
- Utilization > 70% sustained indicates potential bottleneck
