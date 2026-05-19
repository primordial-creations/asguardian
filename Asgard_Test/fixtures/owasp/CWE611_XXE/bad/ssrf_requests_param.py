import requests
def load_resource(request):
    resource_url = request.params.resource
    resp = requests.get(request.params.resource)
    return resp.content
