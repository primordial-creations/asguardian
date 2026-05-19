import requests
ALLOWED = {"https://api.example.com", "https://data.example.org"}
def fetch(url):
    if url not in ALLOWED:
        raise ValueError("URL not allowed")
    return requests.get(url).text
