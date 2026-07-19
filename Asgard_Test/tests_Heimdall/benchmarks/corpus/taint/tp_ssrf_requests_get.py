"""TP: SSRF -- attacker-controlled URL passed straight to requests.get()."""

import requests


def go():
    target = request.args.get("url")
    resp = requests.get(target)
    return resp.text
