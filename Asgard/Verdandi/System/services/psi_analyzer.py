"""
Pressure Stall Information (PSI) Analyzer

PSI (`/proc/pressure/{cpu,memory,io}`) is the unified replacement for the
utilization-average edge cases that plague CPU%/iowait%/%util heuristics
(RESEARCH_12 sec5). `some` = at least one task stalled; `full` = every
runnable task stalled (whole-container stall). avg10/60/300 give trajectory
for free.
"""

from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.System.models.system_models import PsiReport, PsiResource, PsiSnapshot


class PsiAnalyzer:
    """
    Analyzer for PSI snapshots.

    Example:
        analyzer = PsiAnalyzer()
        report = analyzer.analyze(snapshot)
        # or, for the cross-resource thrashing diagnosis:
        report = analyzer.analyze_cross_resource({
            "memory": mem_snapshot, "io": io_snapshot,
        })
    """

    SOME_WARNING = 10.0
    SOME_SEVERE = 25.0
    FRESH_SPIKE_RATIO = 2.0

    def analyze(
        self,
        snapshot: PsiSnapshot,
        previous: Optional[PsiSnapshot] = None,
    ) -> PsiReport:
        """
        Analyze a single PSI snapshot (optionally with a prior snapshot for
        trajectory/micro-burst detection).

        Severity:
        - full_avg10 > 0 -> critical (total stall, whole-cgroup blocked)
        - some_avg10 > 25 -> severe
        - some_avg10 > 10 -> warning
        - else healthy

        Args:
            snapshot: Current PSI reading
            previous: Prior PSI reading, for trajectory/micro-burst analysis

        Returns:
            PsiReport
        """
        severity = self._severity(snapshot)
        trajectory = self._trajectory(snapshot)
        notes: List[str] = []
        recommendations: List[str] = []

        if severity == "critical":
            notes.append(
                f"{snapshot.resource.value}: full_avg10={snapshot.full_avg10:.1f} — "
                "every runnable task is stalled on this resource right now."
            )
            recommendations.append(
                f"Investigate {snapshot.resource.value} pressure immediately: "
                "full-stall pressure means the whole cgroup/container is blocked."
            )
        elif severity == "severe":
            notes.append(
                f"{snapshot.resource.value}: some_avg10={snapshot.some_avg10:.1f} "
                "(> 25, severe partial-stall pressure)."
            )
        elif severity == "warning":
            notes.append(
                f"{snapshot.resource.value}: some_avg10={snapshot.some_avg10:.1f} "
                "(> 10, elevated partial-stall pressure)."
            )

        if trajectory == "fresh_spike":
            notes.append(
                "avg10 >> avg300: this is a fresh spike, not yet reflected in the "
                "longer trailing averages."
            )
        elif trajectory == "sustained_bottleneck":
            notes.append("avg10 and avg300 both elevated: sustained bottleneck.")

        micro_burst = False
        if previous is not None:
            micro_burst = self._micro_burst(snapshot, previous)
            if micro_burst:
                notes.append(
                    "Delta total_us since the previous snapshot far exceeds what "
                    "avg10 implies: sub-10s stalls (CFS throttle bursts, page-fault "
                    "storms) are being smoothed out of the rolling averages."
                )

        return PsiReport(
            resource=snapshot.resource,
            severity=severity,
            trajectory=trajectory,
            micro_burst_detected=micro_burst,
            notes=notes,
            recommendations=recommendations,
        )

    def analyze_cross_resource(
        self, snapshots: Dict[str, PsiSnapshot]
    ) -> PsiReport:
        """
        Cross-resource diagnosis table (RESEARCH_12 sec5.2):
        - io.some up + memory.some ~= 0 -> pure disk bottleneck
        - memory.full up + io.some up -> thrashing
        - cpu.some up only -> run-queue contention

        Args:
            snapshots: Mapping of resource name ("cpu"|"memory"|"io") to PsiSnapshot

        Returns:
            PsiReport with `cross_resource_diagnosis` populated and the worst
            severity across the supplied resources.
        """
        io_snap = snapshots.get("io")
        mem_snap = snapshots.get("memory")
        cpu_snap = snapshots.get("cpu")

        diagnosis = None
        if mem_snap is not None and mem_snap.full_avg10 > 0 and io_snap is not None and io_snap.some_avg10 > 0:
            diagnosis = (
                "thrashing: memory.full and io.some rising together — memory "
                "pressure is driving swap/reclaim I/O (RESEARCH_12 sec5.2)."
            )
        elif io_snap is not None and io_snap.some_avg10 > self.SOME_WARNING and (
            mem_snap is None or mem_snap.some_avg10 < 1.0
        ):
            diagnosis = "pure disk bottleneck: io.some elevated with memory.some ~= 0."
        elif cpu_snap is not None and cpu_snap.some_avg10 > self.SOME_WARNING and (
            (io_snap is None or io_snap.some_avg10 < 1.0)
            and (mem_snap is None or mem_snap.some_avg10 < 1.0)
        ):
            diagnosis = "run-queue contention: cpu.some elevated in isolation."

        severities = [self._severity(s) for s in snapshots.values()]
        order = {"healthy": 0, "warning": 1, "severe": 2, "critical": 3}
        worst = max(severities, key=lambda s: order[s]) if severities else "healthy"

        notes = []
        if diagnosis:
            notes.append(diagnosis)

        return PsiReport(
            resource=None,
            severity=worst,
            cross_resource_diagnosis=diagnosis,
            notes=notes,
        )

    def _severity(self, snapshot: PsiSnapshot) -> str:
        if snapshot.full_avg10 > 0:
            return "critical"
        if snapshot.some_avg10 > self.SOME_SEVERE:
            return "severe"
        if snapshot.some_avg10 > self.SOME_WARNING:
            return "warning"
        return "healthy"

    def _trajectory(self, snapshot: PsiSnapshot) -> Optional[str]:
        if snapshot.some_avg300 > 0 and snapshot.some_avg10 / snapshot.some_avg300 > self.FRESH_SPIKE_RATIO:
            return "fresh_spike"
        if snapshot.some_avg10 > self.SOME_WARNING and snapshot.some_avg300 > self.SOME_WARNING:
            return "sustained_bottleneck"
        return None

    @staticmethod
    def _micro_burst(snapshot: PsiSnapshot, previous: PsiSnapshot) -> bool:
        delta_us = snapshot.total_us - previous.total_us
        if delta_us <= 0:
            return False
        # avg10 is a percentage of a 10s window; implied stalled-us over that
        # window is roughly avg10% * 10s. If observed delta far exceeds what
        # the current avg10 implies, short bursts are being smoothed away.
        implied_us = (snapshot.some_avg10 / 100.0) * 10_000_000
        return delta_us > implied_us * 3
