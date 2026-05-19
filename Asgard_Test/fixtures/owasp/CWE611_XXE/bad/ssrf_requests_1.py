import requests
def fetch(request):
    url = request.params.url
    return requests.get(request.params.url).text
