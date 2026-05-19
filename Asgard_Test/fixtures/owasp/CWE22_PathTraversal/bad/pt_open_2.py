# Path traversal via send_file
from flask import send_file, request
def download(request):
    return send_file(request.args.path)
