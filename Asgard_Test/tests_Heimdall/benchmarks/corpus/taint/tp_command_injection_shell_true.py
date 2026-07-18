"""TP: command injection through subprocess with shell=True."""

import subprocess


def run():
    cmd = request.args.get("cmd")
    subprocess.run(cmd, shell=True)
