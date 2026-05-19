from jinja2 import Template
def render(request):
    tmpl = Template(request.params.template)
    return tmpl.render()
