// TP regression, BLOCKER-4 (adversarial review, reviewer's exact repro):
// `import(userVar)` -- a dynamic `import()` CALL (distinct from static
// `import ... from` syntax) whose module target is attacker-influenced.
// tree-sitter-js parses the bare `import` keyword used as a call target as
// its own leaf node of type "import"; `_node_chain` had no branch for it,
// so the callee chain resolved to "" and never matched
// `_JS_DYNAMIC_IMPORT_NAMES` -- 0 flows. Must surface a needs-review
// dynamic_construct finding (CWE-470).
app.get('/run', (req, res) => {
    const userVar = req.query.mod;
    import(userVar);
});
