# Path traversal via os.path.join
import os
def serve(request):
    fp = os.path.join("/data", request.params.filename)
    with open(fp) as f:
        return f.read()
