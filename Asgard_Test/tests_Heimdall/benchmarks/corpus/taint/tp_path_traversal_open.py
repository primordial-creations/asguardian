"""TP: path traversal -- user-controlled filename passed straight to open()."""


def download():
    filename = request.args.get("file")
    handle = open(filename)
    return handle.read()
