"""TP: SA4 mute-bug baseline -- no guard at all. Must flag (sanity check
that path-sensitivity additions never suppress an unguarded flow)."""

import subprocess


def run():
    host = request.args.get("host")
    subprocess.run("ping -c 1 " + host, shell=True)
