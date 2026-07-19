"""FP: SA4 path-sensitivity -- an early-return guard clause built on a REAL
catalog-recognized value-domain predicate (`str.isdigit()`) proves every
path that reaches the sink has a digits-only `host`, which cannot carry a
shell-injection payload. The guarded/validated path is clean."""

import subprocess


def run():
    host = request.args.get("host")
    if not host.isdigit():
        return "invalid"
    subprocess.run("ping -c 1 " + host, shell=True)
