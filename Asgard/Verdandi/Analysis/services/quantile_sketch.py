"""
Mergeable Quantile Sketches (pure Python, stdlib only)

Provides t-digest (merging variant) and DDSketch implementations so that
percentiles can be aggregated across hosts/pages/windows correctly.

Why this exists: per-host (or per-page) percentiles CANNOT be averaged --
the mean of p99s is not the p99 of the union (RESEARCH_15). The sanctioned
cross-source aggregation path is: build one sketch per source, merge the
sketches, then query quantiles on the merged sketch.
"""

import math
from typing import Any, Dict, Iterable, List, Sequence, Tuple


class TDigest:
    """
    t-digest quantile sketch (merging variant, Dunning & Ertl).

    Centroids are (mean, weight) pairs whose maximum weight is bounded by
    the scale function k(q) = (delta / 2*pi) * asin(2q - 1), giving high
    resolution at the distribution tails and coarse resolution in the middle.

    Supports add(), merge(), quantile(), and dict serialization; sketches
    built on different hosts merge without loss of the accuracy guarantee.

    Example:
        d = TDigest()
        for v in samples:
            d.add(v)
        d.merge(other_host_digest)
        p99 = d.quantile(0.99)
    """

    def __init__(self, compression: float = 100.0):
        """
        Args:
            compression: delta parameter; higher = more centroids = more
                accuracy and memory. Accuracy is in RANK space: with
                compression 100 the estimated quantile sits within roughly
                1 rank-percentile of the true one (tighter at the tails).
                The corresponding VALUE-space error depends on the local
                density of the distribution and can exceed 1% relative on
                heavy tails; use DDSketch when a guaranteed relative
                value-space error is required.
        """
        if compression < 20:
            raise ValueError("compression must be >= 20")
        self.compression = float(compression)
        self._centroids: List[Tuple[float, float]] = []  # (mean, weight), sorted
        self._buffer: List[Tuple[float, float]] = []
        self._buffer_limit = int(10 * compression)
        self.count = 0.0
        self.min_value = math.inf
        self.max_value = -math.inf

    def add(self, value: float, weight: float = 1.0) -> None:
        """Add a single value (optionally weighted) to the sketch."""
        if weight <= 0:
            raise ValueError("weight must be positive")
        value = float(value)
        self._buffer.append((value, float(weight)))
        self.count += weight
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        if len(self._buffer) >= self._buffer_limit:
            self._compress()

    def add_batch(self, values: Iterable[float]) -> None:
        """Add many values."""
        for v in values:
            self.add(v)

    def merge(self, other: "TDigest") -> None:
        """
        Merge another t-digest into this one.

        The merged sketch approximates the sketch of the concatenated
        underlying samples -- this is the only correct way to combine
        per-host percentile state (never average per-host percentiles).
        """
        other._compress()
        self._buffer.extend(other._centroids)
        self.count += other.count
        if other.count > 0:
            self.min_value = min(self.min_value, other.min_value)
            self.max_value = max(self.max_value, other.max_value)
        self._compress()

    def _k(self, q: float) -> float:
        q = min(1.0, max(0.0, q))
        return (self.compression / (2.0 * math.pi)) * math.asin(2.0 * q - 1.0)

    def _compress(self) -> None:
        if not self._buffer and len(self._centroids) <= self.compression:
            return
        points = sorted(self._centroids + self._buffer, key=lambda c: c[0])
        self._buffer = []
        if not points:
            return

        total = sum(w for _, w in points)
        merged: List[Tuple[float, float]] = []
        cur_mean, cur_weight = points[0]
        weight_so_far = 0.0
        k_lower = self._k(0.0)

        for mean, weight in points[1:]:
            q_candidate = (weight_so_far + cur_weight + weight) / total
            if self._k(q_candidate) - k_lower <= 1.0:
                new_weight = cur_weight + weight
                cur_mean = (cur_mean * cur_weight + mean * weight) / new_weight
                cur_weight = new_weight
            else:
                merged.append((cur_mean, cur_weight))
                weight_so_far += cur_weight
                k_lower = self._k(weight_so_far / total)
                cur_mean, cur_weight = mean, weight

        merged.append((cur_mean, cur_weight))
        self._centroids = merged

    def quantile(self, q: float) -> float:
        """
        Estimate the q-quantile (q in [0, 1]) via centroid interpolation.

        Raises:
            ValueError: if the sketch is empty or q out of range.
        """
        if not 0.0 <= q <= 1.0:
            raise ValueError(f"q must be in [0, 1], got {q}")
        self._compress()
        if not self._centroids or self.count <= 0:
            raise ValueError("Cannot query quantile of an empty sketch")

        if len(self._centroids) == 1:
            return self._centroids[0][0]

        target = q * self.count
        cumulative = 0.0
        prev_mean, prev_weight = self._centroids[0]
        prev_center = prev_weight / 2.0
        if target <= prev_center:
            # Interpolate between the min and the first centroid.
            frac = target / prev_center if prev_center > 0 else 0.0
            return self.min_value + frac * (prev_mean - self.min_value)

        cumulative = prev_center
        for mean, weight in self._centroids[1:]:
            center = cumulative + prev_weight / 2.0 + weight / 2.0
            if target <= center:
                frac = (target - cumulative) / (center - cumulative)
                return prev_mean + frac * (mean - prev_mean)
            cumulative = center
            prev_mean, prev_weight = mean, weight

        # Interpolate between the last centroid and the max.
        remaining = self.count - cumulative
        frac = (target - cumulative) / remaining if remaining > 0 else 1.0
        return prev_mean + min(1.0, frac) * (self.max_value - prev_mean)

    def percentile(self, pct: float) -> float:
        """Estimate a percentile (0-100)."""
        return self.quantile(pct / 100.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        self._compress()
        return {
            "type": "tdigest",
            "compression": self.compression,
            "count": self.count,
            "min": self.min_value if self.count else None,
            "max": self.max_value if self.count else None,
            "centroids": [[m, w] for m, w in self._centroids],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TDigest":
        """Deserialize a sketch produced by to_dict()."""
        if data.get("type") != "tdigest":
            raise ValueError("Not a serialized t-digest")
        digest = cls(compression=data["compression"])
        digest._centroids = [(float(m), float(w)) for m, w in data["centroids"]]
        digest.count = float(data["count"])
        if data.get("min") is not None:
            digest.min_value = float(data["min"])
        if data.get("max") is not None:
            digest.max_value = float(data["max"])
        return digest


class DDSketch:
    """
    DDSketch: quantile sketch with a RELATIVE-error guarantee.

    Values are placed in geometric buckets index = ceil(log_gamma(x)) with
    gamma = (1 + alpha) / (1 - alpha); any quantile estimate is within
    alpha relative error of the true value. Fully mergeable.

    Only positive values are bucketed; zeros/negatives are counted in a
    dedicated zero bucket (latencies are non-negative by nature).
    """

    def __init__(self, relative_accuracy: float = 0.01):
        if not 0.0 < relative_accuracy < 1.0:
            raise ValueError("relative_accuracy must be in (0, 1)")
        self.relative_accuracy = relative_accuracy
        self._gamma = (1.0 + relative_accuracy) / (1.0 - relative_accuracy)
        self._log_gamma = math.log(self._gamma)
        self._buckets: Dict[int, float] = {}
        self._zero_count = 0.0
        self.count = 0.0

    def add(self, value: float, weight: float = 1.0) -> None:
        """Add a value to the sketch."""
        if weight <= 0:
            raise ValueError("weight must be positive")
        if value <= 0:
            self._zero_count += weight
        else:
            index = math.ceil(math.log(value) / self._log_gamma)
            self._buckets[index] = self._buckets.get(index, 0.0) + weight
        self.count += weight

    def add_batch(self, values: Iterable[float]) -> None:
        """Add many values."""
        for v in values:
            self.add(v)

    def merge(self, other: "DDSketch") -> None:
        """Merge another DDSketch (must share relative_accuracy)."""
        if abs(other.relative_accuracy - self.relative_accuracy) > 1e-12:
            raise ValueError("Cannot merge DDSketches with different accuracies")
        for index, weight in other._buckets.items():
            self._buckets[index] = self._buckets.get(index, 0.0) + weight
        self._zero_count += other._zero_count
        self.count += other.count

    def quantile(self, q: float) -> float:
        """Estimate the q-quantile (q in [0, 1])."""
        if not 0.0 <= q <= 1.0:
            raise ValueError(f"q must be in [0, 1], got {q}")
        if self.count <= 0:
            raise ValueError("Cannot query quantile of an empty sketch")

        rank = q * (self.count - 1)
        if rank < self._zero_count:
            return 0.0

        cumulative = self._zero_count
        for index in sorted(self._buckets):
            cumulative += self._buckets[index]
            if cumulative > rank:
                # Bucket midpoint in value space: 2*gamma^i / (gamma + 1)
                return 2.0 * self._gamma ** index / (self._gamma + 1.0)
        last_index = max(self._buckets)
        return 2.0 * self._gamma ** last_index / (self._gamma + 1.0)

    def percentile(self, pct: float) -> float:
        """Estimate a percentile (0-100)."""
        return self.quantile(pct / 100.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "type": "ddsketch",
            "relative_accuracy": self.relative_accuracy,
            "zero_count": self._zero_count,
            "count": self.count,
            "buckets": {str(k): v for k, v in self._buckets.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DDSketch":
        """Deserialize a sketch produced by to_dict()."""
        if data.get("type") != "ddsketch":
            raise ValueError("Not a serialized DDSketch")
        sketch = cls(relative_accuracy=data["relative_accuracy"])
        sketch._buckets = {int(k): float(v) for k, v in data["buckets"].items()}
        sketch._zero_count = float(data["zero_count"])
        sketch.count = float(data["count"])
        return sketch


def sketch_from_values(
    values: Sequence[float],
    compression: float = 100.0,
) -> TDigest:
    """Build a t-digest from raw samples."""
    digest = TDigest(compression=compression)
    digest.add_batch(values)
    return digest
