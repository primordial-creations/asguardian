"""
Bragi Architecture Graph Package (Plan 03 — Architecture Enforcement)

Import-graph based layer inference, drift detection, and module-level
cycle detection. Reuses `Bragi.Dependencies.services.graph_service` for the
cached import graph + SCC condensation rather than rebuilding it.
"""
