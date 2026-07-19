"""TP regression, context-coverage fix (adversarial review, reviewer's
exact repro shape): `if eval(request.args['x']):` -- a dynamic construct
used directly as an `if` TEST expression. `visit_If` previously only ran
`_eval` on the test (to compute a taint state) and never dispatched to
`visit_Call`, so a dynamic construct that only ever appeared in an `if`/
`while` test was silently never checked. `eval` is also a registered
concrete `eval_exec` sink (CWE-95, catalog/sinks.py) and the argument
here is attacker-influenced (`request.args['x']`), so per MAJOR-2's
suppression rule this resolves through the concrete sink path."""


def gate():
    if eval(request.args["x"]):
        return True
    return False
