"""TP: open redirect -- attacker-controlled URL passed straight to redirect().

Open redirect (CWE-601) is the closest sink category this engine models to
SSRF-class "attacker steers an outbound URL" bugs; there is no dedicated
SSRF sink (e.g. requests.get(user_url)) in the current sink catalog, so
this fixture is the honest stand-in -- see corpus/taint/manifest.yml.
"""


def go():
    target = request.args.get("next")
    resp = redirect(target)
    return resp
