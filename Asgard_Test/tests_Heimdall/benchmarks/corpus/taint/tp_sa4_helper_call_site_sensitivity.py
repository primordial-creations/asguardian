"""TP: SA4 context-sensitivity -- the SAME helper is called from a clean
call site (a literal) and a sinking call site (tainted param). These must
NOT be conflated: exactly one flow, from the tainted call site."""

import subprocess


def run_cmd(host):
    subprocess.run("ping -c 1 " + host, shell=True)


def clean_call():
    run_cmd("localhost")


def tainted_call():
    host = request.args.get("host")
    run_cmd(host)
