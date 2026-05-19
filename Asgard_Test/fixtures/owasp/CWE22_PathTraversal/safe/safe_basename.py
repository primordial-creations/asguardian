import os
def read_file(filename):
    safe_name = os.path.basename(filename)
    allowed = ["/safe/dir/a.txt", "/safe/dir/b.txt"]
    safe_path = os.path.join("/safe/dir", safe_name)
    if safe_path not in allowed:
        raise ValueError("Not allowed")
    with open(safe_path) as f:
        return f.read()
