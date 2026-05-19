import requests
def webhook(request):
    endpoint = request.body.callback_url
    return requests.get(request.body.callback_url)
