"""FP sibling: exact sanitizer (shlex.quote) neutralizes the flow."""

import os
import shlex


def run():
    cmd = request.args.get("cmd")
    os.system("ls " + shlex.quote(cmd))
