"""FP: fixed, non-attacker-controlled URL passed to requests.get()."""

import requests


def go():
    resp = requests.get("https://internal.example.com/health")
    return resp.text
