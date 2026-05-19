ALLOWED_FILES = {"report.pdf", "summary.txt", "data.csv"}
def serve_file(filename):
    if filename not in ALLOWED_FILES:
        return "Not allowed", 403
    return open(f"/static/{filename}").read()
