"""TP regression, BLOCKER-1 (adversarial review, reviewer's exact repro):
`getattr(o, request.args['m'])()` -- a pure dynamic construct with NO
registered concrete sink in the function. Before the ROOT CAUSE fix
(`_layer2_triggers`/`_layer3` in dispatch.py only triggered Layer 3 for
functions containing a registered sink), this function was never
triggered into Layer 3 at all, so `_check_dynamic_construct` never ran
and this reported 0 flows -- a silent, structural false negative on the
whole WS5 feature for any dynamic construct not co-located with a
concrete sink. Must surface a needs-review dynamic_construct finding
(CWE-470)."""


def run(o):
    getattr(o, request.args["m"])()
