# Path traversal via pathlib
from pathlib import Path
def read_doc(request):
    p = pathlib.Path(request.args.doc)
    return p.read_text()
