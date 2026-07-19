"""FP: SA4 path-sensitivity -- `if <validator>(x): sink(x)` (validated
"then" arm, no early return). Only the THEN branch, where `host` is proven
digits-only, reaches the sink -- clean."""

import subprocess


def run():
    host = request.args.get("host")
    if host.isdigit():
        subprocess.run("ping -c 1 " + host, shell=True)
