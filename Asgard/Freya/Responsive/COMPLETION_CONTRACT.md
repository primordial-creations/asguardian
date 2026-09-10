# Mobile observation completion

Every requested device requires navigation, Flash, hover, text, fixed-element and resource observations. The report carries each check's status in check_outcomes. A failed browser evaluation is an explicit failed observation; it cannot become an empty successful check. Successful findings remain visible when another check fails.

Unknown devices, missing outcomes or failed checks make is_complete false and mobile_friendly_score null. Consumers must reject incomplete scores rather than substitute zero or 100. The mobile CLI returns failure for incomplete scans and renders unavailable measurements without inventing values. Direct individual check callers receive MobileCheckError when evaluation or output processing fails.

Each device context and the browser close in finally blocks, including page-creation and navigation failures. Serialization happens after those resources close. Browser-launch and cleanup failures propagate; they cannot return a healthy report.

The hover heuristic and its browser coverage remain a separate part of the analysis-integrity remediation; completion fields alone do not validate its findings.
