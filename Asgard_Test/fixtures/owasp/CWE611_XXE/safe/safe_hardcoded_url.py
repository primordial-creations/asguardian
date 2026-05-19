import requests
def get_data():
    return requests.get("https://api.internal.example.com/data").json()
