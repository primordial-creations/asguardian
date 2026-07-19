"""TP: SA4 branch-join generalization -- one arm assigns the tainted value,
the other assigns a constant. The join must UNION (taint on ANY reaching
path survives), never intersect. Must still flag."""

import subprocess


def run():
    host = request.args.get("host")
    flag = request.args.get("flag")
    if flag:
        cmd = host
    else:
        cmd = "localhost"
    subprocess.run("ping -c 1 " + cmd, shell=True)
