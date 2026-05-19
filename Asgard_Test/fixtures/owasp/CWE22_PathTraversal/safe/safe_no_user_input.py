from pathlib import Path
def read_template():
    return Path("/templates/default.html").read_text()
