// TP regression, BLOCKER-3 (adversarial review, reviewer's exact repro):
// `new Function(req.body.c)` was previously invisible to the taint
// visitor -- tree-sitter-js parses `new Function(...)` as a `new_expression`
// node, which was missing from `_walk`'s call-dispatch tuple (also from
// `_node_chain`'s chain-resolution branches), so this call was never
// checked at all -- 0 flows. `Function` is also a registered concrete
// "eval_exec" sink (CWE-95, catalog/sinks.py), so with the fix this
// resolves through the CONCRETE sink path (not a needs-review
// dynamic_construct finding) -- see MAJOR-2's suppression rule: a call
// site that already produced a concrete sink finding must not ALSO emit a
// redundant dynamic_construct finding for the same node.
app.post('/run', (req, res) => {
    const f = new Function(req.body.c);
    f();
});
