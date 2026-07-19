"""TP: open redirect -- attacker-controlled URL passed straight to redirect().

Historical note: this fixture originally stood in for SSRF (CWE-918) before
a dedicated SSRF sink existed. A real SSRF sink category is now modeled
(see tp_ssrf_requests_get.py / TaintSinkType.SSRF) -- this fixture is kept
as its own genuine open-redirect (CWE-601) case.
"""


def go():
    target = request.args.get("next")
    resp = redirect(target)
    return resp
