# Path traversal via open with request params
def read_file(request):
    filename = request.args.get("file")
    with open(request.args.filename) as f:
        return f.read()
