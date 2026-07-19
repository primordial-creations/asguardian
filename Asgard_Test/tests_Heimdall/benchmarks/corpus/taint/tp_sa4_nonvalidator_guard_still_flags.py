"""TP: SA4 mute-bug guard case -- `host is not None` is NOT a catalog-
verified value-domain predicate; it proves nothing about the character
content of `host`. The engine must NOT invent a semantic validator here --
the guarded path must still flag."""

import subprocess


def run():
    host = request.args.get("host")
    if host is not None:
        subprocess.run("ping -c 1 " + host, shell=True)
