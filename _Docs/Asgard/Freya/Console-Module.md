# Freya Console Module

## Overview

The Console module captures browser console output (JS errors, warnings,
logs), uncaught page exceptions, and failed resource loads while a page
runs, surfacing runtime JavaScript errors that static analysis cannot see.

---

## Package Structure

```
Freya/Console/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── console_models.py
└── services/
    ├── __init__.py
    ├── console_capture.py
    └── _console_capture_helpers.py
```

---

## Services

### ConsoleCapture

Attaches Playwright event listeners (`console`, `pageerror`,
`requestfailed`) for a configurable wait window after navigation, then
aggregates the captured messages into a `ConsoleReport`. Wraps
Playwright's own `ConsoleMessage` type into Freya's Pydantic model rather
than depending on a separate logging/JS-analysis library.

### _console_capture_helpers

Regex-based message classification and deduplication: buckets raw
console output by severity/type (error/warning/log) and collapses
repeated identical messages before scoring.

---

## Models

- `ConsoleMessage`, `ConsoleMessageType`, `ConsoleSeverity` — individual console entries
- `PageError` — uncaught JS exceptions
- `ResourceError` — failed resource loads (404s, blocked requests, etc.)
- `ConsoleReport`, `ConsoleConfig` — aggregate report and capture configuration

---

## CLI Commands

```bash
freya console errors <url>

# Options
--format [text|json|github]
--wait <ms>              # capture window, default 3000
--include-warnings
```

---

## Technology

Zero heavy dependencies: **Playwright only** — this module is inherently
runtime-event based (console/page-error/network-failure listeners), so
there is no meaningful `httpx` use case here. Classification uses stdlib
`re`.

Epistemic note: capture happens over a fixed post-navigation window;
errors that fire later (lazy interactions, delayed timers) will not be
seen unless the wait window covers them. Severity calibration is
**provisional pending RESEARCH_10**; no finding in this category can
reach Blocker.
