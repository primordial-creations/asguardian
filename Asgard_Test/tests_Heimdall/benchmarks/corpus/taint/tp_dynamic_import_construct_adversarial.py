"""TP regression, BLOCKER-2 (adversarial review, reviewer's exact repro):
`__import__(userVar)` -- same ROOT CAUSE as BLOCKER-1 (see
tp_dynamic_getattr_dispatch_construct_adversarial.py): `__import__` is not
a registered sink, so before the Layer-2/Layer-3 triggering fix this
function's only interesting call never triggered Layer 3 and
`_check_dynamic_construct` never ran -- 0 flows. Must surface a
needs-review dynamic_construct finding (CWE-470)."""


def run():
    userVar = request.args.get("mod")
    __import__(userVar)
