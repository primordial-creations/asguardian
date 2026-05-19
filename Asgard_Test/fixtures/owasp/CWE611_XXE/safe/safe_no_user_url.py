import urllib.request
def fetch_static():
    with urllib.request.urlopen("https://example.com/static.json") as r:
        return r.read()
