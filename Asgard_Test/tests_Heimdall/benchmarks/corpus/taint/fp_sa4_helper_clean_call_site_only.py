"""FP: SA4 context-sensitivity sibling -- this file only exercises the
CLEAN call site (literal argument). A sinking call site elsewhere must not
leak taint into this one via a flow-insensitive/summary-conflated
resolution."""

import subprocess


def run_cmd(host):
    subprocess.run("ping -c 1 " + host, shell=True)


def clean_call():
    run_cmd("localhost")
