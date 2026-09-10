# Mobile observation completion

Every requested device requires navigation, Flash, hover, text, fixed-element and resource observations. The report carries each check's status in check_outcomes. A failed browser evaluation is an explicit failed observation; it cannot become an empty successful check. Successful findings remain visible when another check fails.

Unknown devices, missing outcomes or failed checks make is_complete false and mobile_friendly_score null. Consumers must reject incomplete scores rather than substitute zero or 100. The mobile CLI returns failure for incomplete scans and renders unavailable measurements without inventing values. Direct individual check callers receive MobileCheckError when evaluation or output processing fails.

Each device context and the browser close in finally blocks, including page-creation and navigation failures. Serialization happens after those resources close. Browser-launch and cleanup failures propagate; they cannot return a healthy report.

Hover observations inspect at most 200 stylesheets, 2,000 rules, 2,000 DOM elements and 20 candidates. Active accessible hover rules identify hidden targets and reachable triggers; a real pointer hover must reveal the target. An observed focus reveal avoids a hover finding. Declarative click/touch alternatives are not activated and remain unverified. CSS alone does not prove universal interaction accessibility.

Unreadable stylesheets, unsupported selectors/rules, caps, interaction timeouts and script interaction coverage are explicit limitations. Findings may remain visible while these limits make the hover outcome incomplete and invalidate the aggregate score. The direct list-returning hover check raises MobileCheckError on incomplete coverage; the orchestrator consumes the richer assessment. No arbitrary click or touch handler is invoked. Targets in other documents or shadow roots are outside the document CSS heuristic.
