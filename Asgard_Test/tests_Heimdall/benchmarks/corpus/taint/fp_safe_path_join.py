"""FP sibling: os.path.join of constants only (no user data)."""

import os

BASE = "/srv/app"


def template_dir():
    path = os.path.join(BASE, "templates")
    return open(path)
