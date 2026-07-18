# Delivered Plans (removed from `_Docs/Planning/`)

These upgrade plans were verified FULLY implemented (6 independent read-only
audit agents, 2026-07-18) and their plan files removed. See `UPLIFT_STATUS.md`
at the repo root for the full per-plan completeness ledger, including the
evidence (key files/functions) for each. Remaining plan files under
`_Docs/Planning/<Module>/` are PARTIAL or NOT_STARTED — they are the live
to-do list.

| Module | Delivered & removed |
|---|---|
| Heimdall | 08 Hotspots/Test-Context, 09 QualityGate/New-Code |
| Forseti | 01 Compatibility Engine, 02 Rule Registry/Governance, 03 OpenAPI Linting/Completeness/Security, 04 Breaking-Change Lifecycle/Versioning, 05 JSON-Schema Core/Conversion, 08 Reporting/Output |
| Freya | 01 Unified Severity/Scoring, 02 Accessibility Dual-Axis/ARIA, 03 Performance Context/Budgets, 06 Crawler/Config/CI |
| Verdandi | 01 WebVitals, 08 Tracing/APM |
| Volundr | 01 Kubernetes, 03 Docker |
| Bragi | 01 Composite Scoring, 03 Dependency/SBOM/License, 06 Quality-Gate Differential |

Plans deliberately KEPT despite substantial delivery, because a real
acceptance item remains (tracked as PARTIAL): Heimdall 03 (hexagonal
anemic-model / infra-leak detectors), Volundr 06 & 07 (module-doc
reconciliation), among others. Each module's `00_Overview.md` still indexes
its remaining plans.
