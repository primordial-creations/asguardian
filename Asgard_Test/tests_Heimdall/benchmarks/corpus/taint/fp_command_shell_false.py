"""FP sibling: subprocess with shell=False cannot be shell-injected."""

import subprocess


def run():
    cmd = request.args.get("cmd")
    subprocess.run(cmd, shell=False)
