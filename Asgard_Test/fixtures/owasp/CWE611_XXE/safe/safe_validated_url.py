from urllib.parse import urlparse
import requests
def safe_request(url):
    parsed = urlparse(url)
    if parsed.netloc not in ["api.example.com"]:
        raise ValueError("Blocked")
    return requests.get(url)
