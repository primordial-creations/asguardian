"""Benchmark fixture — python.subprocess-shell-true (not imported; scanned as text)."""
import subprocess


def risky(cmd):
    subprocess.run(cmd, shell=True)  # ruleid: python.subprocess-shell-true
    subprocess.Popen(cmd, shell=True)  # ruleid: python.subprocess-shell-true
    subprocess.check_output(  # ruleid: python.subprocess-shell-true
        cmd,
        shell=True,
    )


def safe(cmd):
    subprocess.run(cmd, shell=False)
    subprocess.run([cmd])
    banner = "subprocess.run(x, shell=True) is risky"  # ok: python.subprocess-shell-true
    return banner
