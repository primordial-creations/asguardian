from string import Template
def render(request):
    t = Template(request.params.html)
    return t.safe_substitute()
